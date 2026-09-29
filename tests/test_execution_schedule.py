"""Market-hours gate, holidays, early closes, late triggers, missed months, stale clock."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal

import pytest

from stocktry.execution.alerts import Alerter
from stocktry.execution.guards import GuardViolation
from stocktry.execution.ledger import Ledger
from stocktry.execution.runner import compute_due_rebalance
from stocktry.execution.sessions import (
    due_rebalance_date,
    last_completed_session,
    make_client_order_id,
    previous_session,
    sim_nyse_calendar,
)
from stocktry.execution.testing import et, quotes_for, rid, scenario

CAL = sim_nyse_calendar(date(2026, 1, 1), date(2027, 12, 31))


@pytest.mark.parametrize(
    "now, reason",
    [
        (et(2026, 10, 1, 9, 45), "within_30_min_of_open"),
        (et(2026, 10, 1, 15, 45), "within_30_min_of_close"),
        (et(2026, 10, 1, 8, 0), "market_closed"),
        (et(2026, 10, 1, 17, 0), "market_closed"),
        (et(2026, 10, 3, 11, 0), "no_session_today"),  # Saturday
        (et(2026, 11, 26, 11, 0), "no_session_today"),  # Thanksgiving
        (et(2026, 11, 27, 12, 45), "within_30_min_of_close"),  # early close 13:00 ET
    ],
)
def test_outside_market_window_does_nothing(tmp_path, now, reason):
    sc = scenario(tmp_path, now=now)
    res = sc.run()
    assert res.status == "skipped"
    assert res.reason == reason
    assert res.exit_code == 0
    assert sc.broker.orders == [] and sc.broker.submit_calls == 0
    assert sc.transport.calls == []  # no alert, no healthcheck ping
    assert Ledger(sc.cfg.ledger_path).read()[-1]["event"] == "skipped"


def test_inside_window_on_early_close_day_trades(tmp_path):
    # 2025-07-03 closes at 13:00 ET and is the 3rd session of July, so it is inside both the 10:00-12:30
    # market window and the rebalance's execution window. (The earlier 2026-11-27 example is the 19th session
    # of November: since EXEC-14 a rebalance is never started that late in its month.)
    # Since EXEC-01b new legs are opened only on the scheduled session (2025-07-01) unless the operator
    # confirms a late start, so this test sets late_start; what it checks (the early-close market window)
    # is unchanged.
    sc = scenario(tmp_path, now=et(2025, 7, 3, 12, 0), cfg_overrides={"late_start": True})
    assert sc.rebalance_id == "demo-2025-07-01"
    assert sc.run().status == "completed"


def test_rebalance_is_not_started_after_its_execution_window(tmp_path):
    """EXEC-14: a due rebalance is traded only in the first 5 sessions of its month; later runs do nothing
    (and ping the dead-man check: a normal mid-month heartbeat)."""
    sc = scenario(tmp_path, now=et(2026, 10, 8, 11))  # session 6 of October
    sc.cfg = replace(sc.cfg, alerter=Alerter(healthcheck_url="https://hc.example/x", transport=sc.transport))
    res = sc.run()
    assert res.status == "skipped" and "execution_window_closed" in res.reason and res.exit_code == 0
    assert sc.broker.orders == []
    assert ("GET", "https://hc.example/x", {}) in sc.transport.calls
    late6 = scenario(tmp_path / "l6", now=et(2026, 10, 8, 11), cfg_overrides={"late_start": True})
    assert "execution_window_closed" in late6.run().reason and late6.broker.orders == []  # no override past it
    # Session 5 is still inside the window, but since EXEC-01b only an operator-confirmed late start may open
    # legs after the scheduled session; an unattended trigger does nothing there (see the tests below).
    sc5 = scenario(tmp_path / "s5", now=et(2026, 10, 7, 11), cfg_overrides={"late_start": True})
    assert sc5.run().status == "completed"


@pytest.mark.parametrize("now, pinged", [(et(2026, 10, 3, 11), True), (et(2026, 10, 1, 17, 0), False)])
def test_skip_pings_only_when_the_scheduler_fired_at_a_valid_time(tmp_path, now, pinged):
    """EXEC-12: a weekend/holiday run pings (runner alive); a run on a session day outside the market window
    does not, so a mistimed scheduler still trips the dead-man alert."""
    sc = scenario(tmp_path, now=now)
    sc.cfg = replace(sc.cfg, alerter=Alerter(healthcheck_url="https://hc.example/x", transport=sc.transport))
    assert sc.run().status == "skipped"
    assert (("GET", "https://hc.example/x", {}) in sc.transport.calls) is pinged


def test_stale_broker_clock_is_refused(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.inject_stale_clock(timedelta(hours=3))
    with pytest.raises(GuardViolation) as ei:
        sc.run()
    assert ei.value.code == "stale_clock"
    assert sc.broker.orders == []
    assert sc.transport.calls, "a hard block must alert"


def test_due_rebalance_is_first_session_of_month_and_skips_holidays():
    assert due_rebalance_date(CAL, et(2026, 10, 1, 11)) == date(2026, 10, 1)
    assert due_rebalance_date(CAL, et(2026, 10, 20, 11)) == date(2026, 10, 1)
    assert due_rebalance_date(CAL, et(2027, 1, 4, 11)) == date(2027, 1, 4)  # Jan 1 2027 is a holiday
    assert due_rebalance_date(CAL, et(2027, 1, 1, 11)) == date(2026, 12, 1)  # before this month's first session
    assert previous_session(CAL, date(2026, 10, 1)) == date(2026, 9, 30)
    assert last_completed_session(CAL, et(2026, 10, 1, 11)) == date(2026, 9, 30)
    assert last_completed_session(CAL, et(2026, 10, 1, 16, 1)) == date(2026, 10, 1)


def test_late_trigger_trades_once_with_fresh_data(tmp_path):
    # Scheduled 2026-10-01, trigger 3 sessions late. Since EXEC-01b an unattended late trigger opens no leg
    # (test_later_sessions_never_open_new_legs_without_the_operator); the operator's --late-start does,
    # once, with fresh data.
    sc = scenario(tmp_path, now=et(2026, 10, 6, 11), cfg_overrides={"late_start": True})
    assert sc.rebalance_id == "demo-2026-10-01"
    stale = quotes_for(sc.broker, session=date(2026, 10, 2))
    with pytest.raises(GuardViolation) as ei:
        sc.run(prices=stale)
    assert ei.value.code == "price_stale"
    res = sc.run()  # quotes dated 2026-10-05, the last completed session
    assert res.status == "completed"
    n = len(sc.broker.orders)
    sc.broker.set_now(et(2026, 10, 7, 11))
    sc.refresh()
    assert sc.run().status == "already_done"
    assert len(sc.broker.orders) == n


def test_two_missed_months_trade_only_the_latest(tmp_path):
    # 2026-10-05 is session 3 of October: opening its legs needs the operator's late start (EXEC-01b).
    sc = scenario(tmp_path, now=et(2026, 8, 3, 11), cfg_overrides={"late_start": True})
    sc.broker.submit_order("SPY", "buy", qty=Decimal("0.01"),
                           client_order_id=make_client_order_id(rid("demo", date(2026, 8, 3)), "SPY", "buy", 1))
    sc.broker.set_now(et(2026, 10, 5, 11))  # September and October 1st both missed
    sc.refresh()
    assert sc.rebalance_id == "demo-2026-10-01"
    with pytest.raises(GuardViolation) as ei:
        sc.run(rebalance_id="demo-2026-09-01")
    assert ei.value.code == "rebalance_id_not_due"
    res = sc.run()
    assert res.status == "completed"
    ids = [o.client_order_id for o in sc.broker.orders]
    assert not any("2026-09-01" in i for i in ids)
    assert sum("2026-10-01" in i for i in ids) == 3
    assert compute_due_rebalance(sc.broker, "demo").rebalance_id == "demo-2026-10-01"


def test_newer_rebalance_wins_over_unfinished_older_one(tmp_path):
    # September: IEF only half fills on both attempts -> incomplete.
    sc = scenario(tmp_path, now=et(2026, 9, 1, 11), scripted_fill_fractions={"IEF": [0.5, 0.5]})
    assert sc.run().status == "incomplete"
    sept = {o.client_order_id for o in sc.broker.orders}
    sc.broker.set_now(et(2026, 10, 1, 11))
    sc.refresh()
    res = sc.run()
    new_ids = {o.client_order_id for o in sc.broker.orders} - sept
    assert new_ids and all(i.startswith("demo-2026-10-01-") for i in new_ids)
    assert not any(i.startswith("demo-2026-09-01-") and i.endswith("-a3") for i in new_ids)
    assert res.status in ("completed", "incomplete")


def test_future_rebalance_id_is_refused(tmp_path):
    sc = scenario(tmp_path)
    with pytest.raises(GuardViolation) as ei:
        sc.run(rebalance_id="demo-2026-11-02")
    assert ei.value.code == "rebalance_id_not_due"


# ---------------------------------------------------------------- new legs only on the scheduled session (EXEC-01b)
def _hc(sc):
    sc.cfg = replace(sc.cfg, alerter=Alerter(healthcheck_url="https://hc.example/x", transport=sc.transport))


@pytest.mark.parametrize("day", [2, 5, 7])  # 2026-10-02 is session 2, 10-07 session 5 (10-05 is 3)
def test_later_sessions_never_open_new_legs_without_the_operator(tmp_path, day):
    """No order of the rebalance exists and no ledger (a fresh CI runner): a trigger after the scheduled
    session plans the drift but sends nothing, exits 0 and pings (a normal heartbeat)."""
    sc = scenario(tmp_path, now=et(2026, 10, day, 11))
    _hc(sc)
    assert sc.rebalance_id == "demo-2026-10-01"
    res = sc.run()
    assert res.status == "skipped" and res.exit_code == 0 and "first_session_passed" in res.reason
    assert sc.broker.orders == [] and sc.broker.submit_calls == 0
    assert res.planned == [] and {s.reason for s in res.skipped} >= {"first_session_passed"}
    assert ("GET", "https://hc.example/x", {}) in sc.transport.calls
    assert Ledger(sc.cfg.ledger_path).read()[-1]["status"] == "skipped"


def test_same_day_rerun_after_nothing_to_do_opens_no_leg(tmp_path):
    """With the ledger, a 'nothing_to_do' run closes the rebalance's new legs even on the scheduled session."""
    sc = scenario(tmp_path, cash=0.0, positions={"SPY": 0.13, "IEF": 39 / 95, "GLD": 0.104})
    assert sc.run().status == "nothing_to_do"
    sc.broker.set_now(et(2026, 10, 1, 14))
    sc.broker.set_prices({"GLD": 300.0})
    sc.refresh()
    res = sc.run()
    assert sc.broker.orders == [] and res.status == "nothing_to_do"
    assert {s.reason for s in res.skipped} >= {"rebalance_already_evaluated"}


def test_late_start_is_refused_after_an_evaluated_rebalance_or_once_orders_exist(tmp_path):
    # evaluated (nothing_to_do) on session 1, operator asks for a late start on session 2: refused
    sc = scenario(tmp_path, cash=0.0, positions={"SPY": 0.13, "IEF": 39 / 95, "GLD": 0.104})
    assert sc.run().status == "nothing_to_do"
    sc.broker.set_now(et(2026, 10, 2, 11))
    sc.broker.set_prices({"GLD": 300.0})
    sc.refresh()
    assert sc.run(cfg=replace(sc.cfg, late_start=True)).status == "nothing_to_do" and sc.broker.orders == []
    # orders placed on session 1 (GLD left as drift), late start on session 3: no new GLD leg
    sc2 = scenario(tmp_path / "b", cash=5.0, positions={"SPY": 0.16, "IEF": 0.2, "GLD": 0.104})
    assert sc2.run().status == "completed"
    day1 = {o.client_order_id for o in sc2.broker.orders}
    sc2.broker.set_now(et(2026, 10, 5, 11))
    sc2.broker.set_prices({"GLD": 300.0})
    sc2.refresh()
    res = sc2.run(cfg=replace(sc2.cfg, late_start=True))
    assert {o.client_order_id for o in sc2.broker.orders} == day1
    assert any(s.reason == "rebalance_already_executed" for s in res.skipped)


def test_late_start_is_recorded_in_the_ledger(tmp_path):
    sc = scenario(tmp_path, now=et(2026, 10, 2, 11), cfg_overrides={"late_start": True})
    assert sc.run().status == "completed"
    events = [r for r in Ledger(sc.cfg.ledger_path).read() if r["event"] == "late_start"]
    assert events and events[0]["session"] == 2 and events[0]["rebalance_id"] == "demo-2026-10-01"


def test_unreadable_ledger_falls_back_to_the_broker_rule(tmp_path):
    sc = scenario(tmp_path, now=et(2026, 10, 2, 11))
    sc.cfg.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    sc.cfg.ledger_path.write_text('{"event": "run_end", "status": "compl')  # a line cut short by a crash
    with pytest.raises(ValueError):
        Ledger(sc.cfg.ledger_path).read()
    # the ledger line is repaired by nobody: the run still decides from the calendar (session 2: no new legs)
    res = sc.run()
    assert res.status in ("skipped",) and sc.broker.orders == []


def test_late_start_is_refused_when_the_ledger_cannot_be_read(tmp_path):
    """RECHECK2-01: the operator override fails closed when its evaluated-run cross-check cannot run."""
    sc = scenario(tmp_path, now=et(2026, 10, 2, 11), cfg_overrides={"late_start": True})
    sc.cfg.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    sc.cfg.ledger_path.write_text('{"event": "run_end", "status": "compl')  # a line cut short by a crash
    res = sc.run()
    assert res.status == "blocked" and res.exit_code == 2 and sc.broker.orders == []
    assert "late_start_ledger_unreadable" in res.reason and res.alerts == ["late_start_ledger_unreadable"]
    lines = sc.cfg.ledger_path.read_text().splitlines()
    assert lines[0] == '{"event": "run_end", "status": "compl'  # never rewritten
    tail = [json.loads(line) for line in lines[1:]]  # later records stay on their own, readable lines
    assert tail[-1]["event"] == "guard_violation" and tail[-1]["code"] == "late_start_ledger_unreadable"
    assert not any(r["event"] == "late_start" for r in tail)
    # the same run in dry-run mode is refused too (the preview shows what a real run would do)
    assert sc.run(cfg=replace(sc.cfg, dry_run=True)).status == "blocked"
    # an unattended run (no late start) keeps the broker rule: session 2 with no order opens nothing, exit 0
    res2 = sc.run(cfg=replace(sc.cfg, late_start=False))
    assert res2.status == "skipped" and res2.exit_code == 0 and sc.broker.orders == []


def test_ledger_append_starts_a_new_line_after_a_truncated_one(tmp_path):
    path = tmp_path / "l.jsonl"
    led = Ledger(path)
    led.append({"event": "a"})
    with open(path, "a", encoding="utf-8") as fh:
        fh.write('{"event": "run_end", "status": "compl')  # a crash mid-write: no trailing newline
    led.append({"event": "b"})
    led.append({"event": "c"})
    raw = path.read_text(encoding="utf-8")
    assert raw.endswith("\n") and raw.count("\n") == 4
    lines = raw.splitlines()
    assert lines[1] == '{"event": "run_end", "status": "compl'  # the damage stays on its own line
    assert [json.loads(lines[i])["event"] for i in (0, 2, 3)] == ["a", "b", "c"]
    # a file that already ends with a newline gets no blank line; an empty/new file gets no leading newline
    fresh = Ledger(tmp_path / "new.jsonl")
    fresh.append({"event": "x"})
    fresh.append({"event": "y"})
    assert [r["event"] for r in fresh.read()] == ["x", "y"]
    text = (tmp_path / "new.jsonl").read_text()
    assert "\n\n" not in text and not text.startswith("\n")
