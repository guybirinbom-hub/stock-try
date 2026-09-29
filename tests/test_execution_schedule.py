"""Market-hours gate, holidays, early closes, late triggers, missed months, stale clock."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

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
    sc = scenario(tmp_path, now=et(2026, 11, 27, 12, 0))
    assert sc.run().status == "completed"


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
    sc = scenario(tmp_path, now=et(2026, 10, 6, 11))  # scheduled 2026-10-01, trigger 3 sessions late
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
    sc = scenario(tmp_path, now=et(2026, 8, 3, 11))
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
