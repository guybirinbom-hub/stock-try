"""Adversarial tests for the execution layer (review of 2026-09-29).

Each test named ``test_exec_NN_*`` targets one finding id (EXEC-NN) and FAILS while
the bug is present; it is left in place on purpose and should pass once the
production code is fixed. Tests named ``test_ok_*`` probe an attack that the
code already resists (evidence that the defence works); they pass.

Offline: LocalSimBroker, an in-process fake HTTP adapter or a 127.0.0.1 server.
No production code is modified here.
"""

from __future__ import annotations

import http.server
import importlib.util
import io
import json
import logging
import sys
import threading
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from stocktry.execution.alerts import Alerter
from stocktry.execution.broker import TERMINAL_STATUSES
from stocktry.execution.guards import CLOSE_BUFFER, GuardViolation
from stocktry.execution.logsafe import configure_logging
from stocktry.execution.sessions import ET, session_on, sim_nyse_calendar
from stocktry.execution.simbroker import HARDENED_CONFIG
from stocktry.execution.testing import et, make_sim, scenario

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "sample_targets.json"
CAL = sim_nyse_calendar(date(2026, 1, 1), date(2027, 12, 31))


# --------------------------------------------------------------------------- helpers
@pytest.fixture
def script(monkeypatch):
    """Load scripts/paper_rebalance.py as a module (same isolation as test_execution_script.py)."""
    spec = importlib.util.spec_from_file_location("paper_rebalance_adv", REPO / "scripts" / "paper_rebalance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for k in ("KILL_SWITCH", "LIVE_TRADING", "NTFY_TOPIC", "HEALTHCHECK_URL", "KILL_SWITCH_FILE",
              "APCA_API_KEY_ID", "APCA_API_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KILL_SWITCH_FILE", "/nonexistent/stocktry-adv-kill-switch")
    orig_out, orig_err = sys.stdout, sys.stderr
    yield mod
    sys.stdout, sys.stderr = orig_out, orig_err
    root = logging.getLogger()
    for h in list(root.handlers):
        if h.get_name() == "stocktry-scrubbed":
            root.removeHandler(h)


@pytest.fixture
def restore_logging():
    root = logging.getLogger()
    old_handlers, old_level = list(root.handlers), root.level
    yield
    for h in list(root.handlers):
        if h not in old_handlers:
            root.removeHandler(h)
    root.setLevel(old_level)


# =========================================================================== EXEC-01
def test_exec_01_no_new_legs_traded_later_in_month_after_rebalance_day(tmp_path):
    """EXEC-01: a heartbeat trigger later in the month must not start new trades.

    The runbook recommends firing every weekday and says a later trigger "finds
    the orders already placed and does nothing". But ``_Run.eligible`` treats any
    leg with no order yet as attempt 1, so a leg that was within $1 of target on
    the rebalance day (skipped as drift) is traded mid-month as soon as prices
    drift it past $1. The backtest trades only at the monthly anchor, so this is
    extra turnover, extra fee-floor cost, and a Gate B signal/tracking mismatch.
    """
    # $130 account; GLD already exactly at its 20% target on 2026-10-01 -> no GLD leg that day.
    sc = scenario(tmp_path, cash=5.0, positions={"SPY": 0.16, "IEF": 0.2, "GLD": 0.104})
    first = sc.run()
    assert first.status == "completed"
    day1 = {o.client_order_id for o in sc.broker.orders}
    assert not any("-GLD-" in c for c in day1)  # GLD was left as drift on the rebalance day

    # Two weeks later, same (still due) rebalance id; GLD has rallied 20%.
    sc.broker.set_now(et(2026, 10, 15, 11))
    sc.broker.set_prices({"GLD": 300.0})
    sc.refresh()
    assert sc.rebalance_id == "demo-2026-10-01"
    sc.run()
    new = sorted({o.client_order_id for o in sc.broker.orders} - day1)
    assert new == [], f"EXEC-01: mid-month heartbeat traded new legs of an already executed rebalance: {new}"


# =========================================================================== EXEC-02
@pytest.mark.parametrize("lookup_latency_s", [0, 15])
def test_exec_02_market_window_is_rechecked_before_every_order(tmp_path, lookup_latency_s):
    """EXEC-02: the market-hours gate is evaluated once, at run start.

    With the production poll settings (poll_interval_s=2, poll_max=30), sells
    that partially fill and have to be cancelled keep the run busy for minutes,
    and the buys are then submitted after close-30min without re-checking the
    gate. With a slow API (each lookup taking the 15 s read timeout) the buys
    are submitted after the 16:00 close, where Alpaca accepts a market DAY order
    and queues it for the next open (the sim marks it ``accepted``). The runbook
    promises orders are only ever sent between open+30 and close-30 and that
    market orders are never queued for the next open.
    """
    # $130: SPY $80, IEF ~$40, GLD $0, cash $10 -> two sells then one buy, all inside default caps.
    sc = scenario(
        tmp_path, now=et(2026, 10, 1, 15, 29), cash=10.0,
        positions={"SPY": 0.16, "IEF": 0.421052631, "GLD": 0.0},
        targets={"SPY": 0.45, "IEF": 0.2, "GLD": 0.24},
        scripted_fill_fractions={"SPY": [0.5, 0.5], "IEF": [0.5, 0.5]}, partial_final_status=None,
    )
    broker = sc.broker
    if lookup_latency_s:
        broker.before_lookup_hook = lambda cid: broker.advance(timedelta(seconds=lookup_latency_s))
    cfg = replace(sc.cfg, poll_interval_s=2.0, poll_max=30,
                  sleep=lambda s: broker.advance(timedelta(seconds=s)))
    try:
        sc.run(cfg=cfg)
    except GuardViolation:
        pass
    session = session_on(CAL, date(2026, 10, 1))
    last_ok = session.close - CLOSE_BUFFER
    late = [(o.client_order_id, o.submitted_at.astimezone(ET).strftime("%H:%M:%S"), o.status)
            for o in broker.orders if o.submitted_at > last_ok]
    assert late == [], f"EXEC-02: orders sent after {last_ok.strftime('%H:%M')} ET: {late}"


# =========================================================================== EXEC-03
def test_exec_03_stopped_order_is_not_treated_as_final(tmp_path):
    """EXEC-03: ``stopped`` is in TERMINAL_STATUSES, but per Alpaca a stopped order
    has a *guaranteed* trade that has not happened yet. The runner then sizes and
    sends ``-a2`` for the full residual while ``-a1`` is still going to fill:
    a duplicate order for the same leg.
    """
    sc = scenario(tmp_path, scripted_fill_fractions={"IEF": [0.0]}, partial_final_status="stopped")
    sc.run()
    ief = sorted((o for o in sc.broker.orders if o.symbol == "IEF"), key=lambda o: o.client_order_id)
    statuses = [(o.client_order_id[-2:], o.status, str(o.filled_qty)) for o in ief]
    assert statuses[0][:2] == ("a1", "stopped")
    assert len(ief) == 1, f"EXEC-03: a2 sent while a1 is 'stopped' (fill guaranteed): {statuses}"
    assert "stopped" not in TERMINAL_STATUSES


# =========================================================================== EXEC-04
def test_exec_04_string_false_does_not_declare_exit_to_cash(tmp_path):
    """EXEC-04: ``load_targets_file`` uses ``bool(raw.get('allows_exit_to_cash'))``, so
    the JSON string ``"false"`` (or ``"no"``, ``"0"``) turns the declaration ON. That
    disables the ``sell_everything_not_declared`` guard and exempts every full-exit
    sell from the per-order and daily caps.
    """
    from stocktry.execution.strategy_io import load_targets_file

    raw = json.loads(FIXTURE.read_text())
    raw["allows_exit_to_cash"] = "false"
    raw["targets"] = {}  # a bug that says "sell everything"
    p = tmp_path / "t.json"
    p.write_text(json.dumps(raw))
    # Corrected by the fixer (round 1): the reviewer's own suggested fix is to *refuse* a non-boolean
    # declaration ("if not isinstance(v, bool): raise ValueError"), which the script reports as a
    # configuration error (exit 4). The original assertion assumed the loader returns an object, so it
    # failed on that stricter fix. Refusal is accepted, as test_ff_parser_... accepts FetchError; if the
    # loader does return, the declaration must be False.
    try:
        inputs = load_targets_file(p)
    except ValueError as exc:
        assert "allows_exit_to_cash" in str(exc)
        return
    assert inputs.allows_exit_to_cash is False, (
        "EXEC-04: the string 'false' was parsed as a declaration that exits to cash are allowed")


# =========================================================================== EXEC-05
def test_exec_05_registry_targets_match_engine_when_one_sleeve_misses_a_row(monkeypatch):
    """EXEC-05: the runner builds its close frame with ``pd.DataFrame(closes)`` (outer
    join, no forward fill) while the backtest panel forward-fills each symbol
    (``stocktry.data.panel._align``). One missing vendor row for one sleeve at a
    past month-end puts a NaN into that sleeve's monthly sample, ``sma_signal``
    returns None and the runner counts the sleeve as OUT for the next 10 months:
    a spurious exit (cap-exempt for a declared strategy) that the engine never
    makes. Freshness guards only look at the last session, so they do not catch it.
    """
    pytest.importorskip("stocktry.strategies.registry")
    from stocktry.execution import strategy_io

    idx = pd.bdate_range("2025-01-02", "2026-09-30")
    trend = np.exp(np.linspace(0.0, 0.4, len(idx)))  # every sleeve in a clean uptrend
    frame = pd.DataFrame({s: 100 * trend for s in ("SPY", "EFA", "IEF", "VNQ")}, index=idx)
    gap = pd.Timestamp("2026-06-30")  # a past month-end anchor inside the 10-month lookback
    vnq = frame["VNQ"].drop(gap)  # the vendor simply has no VNQ row that day

    def fake_fetch(symbols, *, refresh):
        closes = {s: (vnq if s == "VNQ" else frame[s]) for s in symbols}
        return pd.DataFrame(closes).sort_index(), {s: [] for s in symbols}

    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", fake_fetch)
    runner_inputs = strategy_io.inputs_from_registry(
        "gtaa4", decision_date=date(2026, 9, 30), last_session=date(2026, 9, 30), refresh=False)

    spec = strategy_io.load_registry_spec("gtaa4")
    engine_like = pd.DataFrame({s: (vnq if s == "VNQ" else frame[s]) for s in spec.universe}).sort_index().ffill()
    ts = pd.Timestamp("2026-09-30")
    engine_targets = spec.compute_targets(engine_like.loc[:ts], ts)
    assert engine_targets == {"SPY": 0.25, "EFA": 0.25, "IEF": 0.25, "VNQ": 0.25}
    assert runner_inputs.targets == engine_targets, (
        f"EXEC-05: runner targets {runner_inputs.targets} differ from engine targets {engine_targets}")


# =========================================================================== EXEC-06
def test_exec_06_healthcheck_url_not_leaked_by_debug_http_logs(monkeypatch, restore_logging):
    """EXEC-06: with ``-v`` (DEBUG) urllib3 logs ``"GET /<ping-uuid> HTTP/1.1"``. The
    Scrubber only redacts the *full* HEALTHCHECK_URL string, so the ping UUID (which
    lets anyone send fake heartbeats and silence the dead-man alert) is printed.
    Uses a real request to a 127.0.0.1 server.
    """
    uuid = "0f3a1b2c-3d4e-5f60-7182-93a4b5c6d7e8"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *a):  # keep the server quiet
            pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        for k in ("NO_PROXY", "no_proxy"):
            monkeypatch.setenv(k, "127.0.0.1,localhost")
        url = f"http://127.0.0.1:{srv.server_address[1]}/{uuid}"
        buf = io.StringIO()
        configure_logging(logging.DEBUG, stream=buf, env={"HEALTHCHECK_URL": url})
        Alerter(healthcheck_url=url).ping_success()
    finally:
        srv.shutdown()
        srv.server_close()
    out = buf.getvalue()
    assert "GET /" in out  # the debug line was produced
    assert uuid not in out, "EXEC-06: healthcheck ping UUID printed in DEBUG logs"


# =========================================================================== EXEC-07
@pytest.mark.parametrize("action", [["--harden-account"], ["--engage-kill-switch"]])
def test_exec_07_admin_action_with_live_flag_but_no_env_refuses(script, monkeypatch, capsys, action):
    """EXEC-07: ``--live`` without ``LIVE_TRADING=yes-live`` is silently downgraded to a
    PAPER client for admin actions (only a log warning). ``--live --harden-account``
    then hardens and 'confirms' the paper account, giving false assurance about
    the live account the runbook (s.14) is verifying; ``--live --engage-kill-switch``
    suspends the wrong account. The trading path refuses the same flag mismatch.
    """
    pytest.importorskip("alpaca")
    from stocktry.execution import killswitch, preflight

    monkeypatch.setenv("APCA_API_KEY_ID", "PKDUMMYDUMMYDUMMY123")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "d" * 40)
    seen = []
    monkeypatch.setattr(preflight, "harden_account", lambda b: seen.append(b.name) or {"x": "confirmed"})
    monkeypatch.setattr(killswitch, "engage_broker_kill_switch", lambda b: seen.append(b.name))
    rc = script.main(["--broker", "alpaca", "--live", *action])
    assert rc != 0 and seen == [], (
        f"EXEC-07: --live without LIVE_TRADING ran {action[0]} against {seen} and exited {rc}")


# =========================================================================== EXEC-08
@pytest.mark.parametrize("extra", [
    ["--targets-json", "/nonexistent/targets.json"],
    ["--targets-json", str(FIXTURE), "--capital", "nan"],
    ["--targets-json", str(FIXTURE), "--capital", "inf"],
])
def test_exec_08_cli_bad_inputs_exit_with_config_code(script, tmp_path, capsys, extra):
    """EXEC-08: a missing targets file or a non-finite ``--capital`` escapes as an
    uncaught traceback (FileNotFoundError / decimal.InvalidOperation), i.e. process
    exit 1, which the documented exit-code contract reserves for "rebalance
    incomplete, an alert was sent". Expected: exit 4 (configuration error).
    """
    try:
        rc = script.main(["--broker", "sim", *extra, "--no-dry-run", "--ledger", str(tmp_path / "l.jsonl")])
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"EXEC-08: uncaught {type(exc).__name__} (process exit 1) instead of EXIT_CONFIG")
    assert rc == script.EXIT_CONFIG


# =========================================================================== EXEC-09
def test_exec_09_paper_workflow_installs_hash_pinned_dependencies():
    """EXEC-09: the workflow that receives the Alpaca paper secrets falls back to
    ``pip install -r requirements.txt`` because neither ``requirements.lock`` nor
    ``requirements-hashed.txt`` exists. requirements.txt pins 11 top-level
    packages without hashes; ~45 transitive packages (pydantic, urllib3,
    websockets, msgpack, ...) float. The research report (s.10) promises
    hash-pinned dependencies.
    """
    wf = (REPO / ".github" / "workflows" / "paper-rebalance.yml").read_text()
    assert "--require-hashes" in wf
    locks = [p for p in (REPO / "requirements.lock", REPO / "requirements-hashed.txt") if p.exists()]
    assert locks and "--hash=sha256:" in locks[0].read_text(), (
        "EXEC-09: no hash-pinned lock file; the paper workflow installs unpinned transitive dependencies")


# =========================================================================== EXEC-10
def test_exec_10_sim_reserves_buying_power_for_open_buy_orders():
    """EXEC-10 (simulator fidelity): Alpaca reduces ``non_marginable_buying_power`` by
    open buy orders; the simulator reports it equal to cash, so tests cannot catch
    sizing that ignores reserved cash (Alpaca would reject the second buy).
    """
    b = make_sim(cash=100.0, now=et(2026, 10, 1, 8, 0))  # before the open: the order stays open
    b.submit_order("SPY", "buy", notional=Decimal("60.00"), client_order_id="x-2026-10-01-SPY-buy-a1")
    acct = b.get_account()
    assert acct.non_marginable_buying_power <= Decimal("40.00"), (
        f"EXEC-10: sim reports {acct.non_marginable_buying_power} buying power with a $60 buy still open")


# =========================================================================== EXEC-11
def test_exec_11_refresh_data_also_refreshes_tbill_yield(monkeypatch):
    """EXEC-11: ``--refresh-data`` (default for alpaca) refetches bars but the absolute-
    momentum hurdle calls ``get_tbill_yield()`` with ``refresh=False``, so a local
    DTB3 cache is never updated by the runner; trend_absmom12 / trend_ensemble
    signals then use a stale T-bill series that the backtest (run later on a
    refreshed cache) does not.
    """
    pytest.importorskip("stocktry.strategies.registry")
    from stocktry.data import fetch as data_fetch
    from stocktry.execution import strategy_io

    idx = pd.bdate_range("2024-01-02", "2026-09-30")
    calls = []

    def fake_tbill(*, refresh=False):
        calls.append(refresh)
        return pd.Series(4.0, index=idx)

    monkeypatch.setattr(data_fetch, "get_tbill_yield", fake_tbill)
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends",
                        lambda symbols, *, refresh: (pd.DataFrame({s: np.linspace(100, 130, len(idx))
                                                                   for s in symbols}, index=idx), {}))
    strategy_io.inputs_from_registry("trend_absmom12", decision_date=date(2026, 9, 30),
                                     last_session=date(2026, 9, 30), refresh=True)
    assert calls and all(calls), f"EXEC-11: T-bill yield loaded with refresh={calls} on a refresh run"


# =========================================================================== EXEC-12
def test_exec_12_successful_hold_month_run_pings_the_dead_man_check(script, tmp_path, monkeypatch, capsys):
    """EXEC-12: the runbook says the runner pings HEALTHCHECK_URL after every successful
    run so healthchecks.io alerts when runs stop. For an annually rebalanced strategy
    (sixty_forty) the script returns 0 on "not a rebalance month" *before* the
    runner, so no ping is ever sent for 11 months a year. (Separately, market-closed
    skips never ping by design, so the runbook's 1-day period + 1-day grace fires a
    false "down" alert every weekend: last ping Fri 18:05 UTC, next Mon 15:35 UTC.)
    """
    pytest.importorskip("stocktry.strategies.registry")
    from stocktry.execution import alerts, strategy_io

    def fake_fetch(symbols, *, refresh):
        idx = pd.bdate_range("2024-01-02", "2026-10-30")
        return pd.DataFrame({s: np.linspace(100, 130, len(idx)) for s in symbols}, index=idx), {}

    sent = []
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", fake_fetch)
    monkeypatch.setattr(alerts, "_requests_transport", lambda m, u, kw: sent.append((m, u)))
    monkeypatch.setenv("HEALTHCHECK_URL", "https://hc-ping.example/abc")
    rc = script.main(["--broker", "sim", "--strategy", "sixty_forty", "--rebalance-date", "2026-10-01",
                      "--dry-run", "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert rc == 0 and "not a rebalance month" in out
    assert ("GET", "https://hc-ping.example/abc") in sent, "EXEC-12: successful hold-month run sent no heartbeat"


# =========================================================================== EXEC-13
def test_exec_13_open_foreign_order_blocks_trading_before_orders_are_sent(tmp_path):
    """EXEC-13: open orders not placed by this strategy (e.g. a manual dashboard order)
    are ignored when planning: the whitelist only looks at *positions*, and the
    ``foreign_orders`` alert is raised in ``_reconcile`` after trading. When the
    foreign order fills, the symbol overshoots its target.
    """
    sc = scenario(tmp_path, scripted_fill_fractions={"GLD": [0.0]}, partial_final_status=None)
    manual = sc.broker.submit_order("GLD", "buy", notional=Decimal("20.00"), client_order_id="manual-dashboard-1")
    assert manual.status == "partially_filled" and manual.filled_qty == 0  # open, nothing filled yet
    with pytest.raises(GuardViolation):
        sc.run()
    runner_gld = [o.client_order_id for o in sc.broker.orders if o.symbol == "GLD" and o.client_order_id != manual.client_order_id]
    assert runner_gld == [], f"EXEC-13: traded GLD {runner_gld} while a foreign GLD order was open"


# =========================================================================== defences that hold
def test_ok_dry_run_with_open_order_never_submits_or_cancels(tmp_path):
    sc = scenario(tmp_path, scripted_fill_fractions={"SPY": [0.5]}, partial_final_status=None)
    open_order = sc.broker.submit_order("SPY", "sell", notional=Decimal("15.00"),
                                        client_order_id="demo-2026-10-01-SPY-sell-a1")
    assert open_order.status == "partially_filled"
    calls = sc.broker.submit_calls
    res = sc.run(cfg=replace(sc.cfg, dry_run=True))
    assert res.status == "dry_run"
    assert sc.broker.submit_calls == calls
    assert sc.broker.get_order_by_client_id("demo-2026-10-01-SPY-sell-a1").status != "canceled"


def test_ok_preflight_runs_in_dry_run_too(tmp_path):
    sc = scenario(tmp_path, config=replace(HARDENED_CONFIG, max_margin_multiplier="2"),
                  cfg_overrides={"dry_run": True})
    with pytest.raises(GuardViolation) as ei:
        sc.run()
    assert ei.value.code == "margin_enabled"


def test_ok_buys_sized_from_non_marginable_buying_power_not_cash(tmp_path):
    """Leverage probe: the broker reports less non-marginable buying power than cash."""
    sc = scenario(tmp_path)
    real = sc.broker.get_account

    def tighter():
        a = real()
        return replace(a, non_marginable_buying_power=max(a.cash - Decimal("15"), Decimal(0)),
                       buying_power=a.cash * 4)

    sc.broker.get_account = tighter
    sc.run()
    buys = sum((o.filled_notional for o in sc.broker.orders if o.side == "buy"), Decimal(0))
    sells = sum((o.filled_notional for o in sc.broker.orders if o.side == "sell"), Decimal(0))
    assert buys <= Decimal("21") - Decimal("15") + sells  # never more than min(cash, nmbp) + proceeds


@pytest.mark.parametrize("skew_s, ok", [(299, True), (301, False)])
def test_ok_clock_skew_boundary(tmp_path, skew_s, ok):
    sc = scenario(tmp_path)
    cfg = replace(sc.cfg, local_now=lambda: sc.broker.now + timedelta(seconds=skew_s))
    if ok:
        assert sc.run(cfg=cfg).status == "completed"
    else:
        with pytest.raises(GuardViolation) as ei:
            sc.run(cfg=cfg)
        assert ei.value.code == "stale_clock" and sc.broker.orders == []


def test_ok_dst_first_week_winter_trigger_time_is_inside_window(tmp_path):
    """2026-11-02 (Monday after DST ends): the 15:35 UTC trigger is 10:35 EST, inside the window."""
    from datetime import datetime, timezone

    sc = scenario(tmp_path, now=datetime(2026, 11, 2, 15, 35, tzinfo=timezone.utc))
    assert sc.rebalance_id == "demo-2026-11-02"
    assert sc.run().status == "completed"


def test_ok_sdk_429_on_post_is_not_retried(monkeypatch):
    """alpaca-py retries 429 as well as 504; after neutralization one POST only."""
    pytest.importorskip("alpaca")
    import requests
    from requests.adapters import HTTPAdapter

    from stocktry.execution.alpaca_broker import AlpacaBroker
    from stocktry.execution.broker import BrokerHTTPError

    env = {"APCA_API_KEY_ID": "PKDUMMYDUMMYDUMMY123", "APCA_API_SECRET_KEY": "d" * 40}
    b = AlpacaBroker(env=env, sleep=lambda s: None)
    calls = []

    def serve(self, request, **kw):
        calls.append((request.method, request.url, kw.get("timeout")))
        resp = requests.Response()
        resp.request, resp.url = request, request.url
        if request.method == "POST":
            resp.status_code, resp._content = 429, b'{"code":42910000,"message":"rate limit exceeded"}'
        else:
            resp.status_code, resp._content = 404, b'{"code":40410000,"message":"order not found"}'
        return resp

    monkeypatch.setattr(HTTPAdapter, "send", serve)
    with pytest.raises(BrokerHTTPError):
        b.submit_order("SPY", "buy", notional=Decimal("5.00"), client_order_id="demo-2026-10-01-SPY-buy-a1")
    assert [c[0] for c in calls].count("POST") == 1
    assert all(c[2] == (5.0, 15.0) for c in calls)


# =========================================================================== RECHECK (round 1)
# Added by the recheck of the fixer's round-1 changes. Each test FAILS while the named defect is present.

def test_recheck_exec_01b_no_new_legs_after_a_nothing_to_do_rebalance_day(tmp_path):
    """EXEC-01 (variant, still open): the fix allows new ``a1`` legs whenever no order of the rebalance
    exists yet, and blocks them only after a ``run_end`` with status completed/already_done. A rebalance
    day on which every leg was within $1 of target ends with status ``nothing_to_do`` and places no
    order, so the next trigger (session 2..5 of the window, same ledger) opens brand-new legs on
    drifted prices: exactly the mid-month trading the backtest never does. Common for small accounts.
    (In the GitHub workflow the ledger is not persisted between runs at all, so only the broker's
    order list is available there; the rule must not depend on an order having been placed.)"""
    # $130 exactly at target (SPY 0.5, IEF 0.3, GLD 0.2 at 500/95/250): nothing to trade on 2026-10-01.
    sc = scenario(tmp_path, cash=0.0, positions={"SPY": 0.13, "IEF": 39 / 95, "GLD": 0.104})
    first = sc.run()
    assert first.status == "nothing_to_do" and not sc.broker.orders

    sc.broker.set_now(et(2026, 10, 2, 11))  # session 2 of the execution window, same ledger
    sc.broker.set_prices({"GLD": 300.0})
    sc.refresh()
    assert sc.rebalance_id == "demo-2026-10-01"
    sc.run()
    new = sorted(o.client_order_id for o in sc.broker.orders)
    assert new == [], f"EXEC-01: a later trigger opened new legs of an already evaluated rebalance: {new}"


def test_recheck_new_harden_account_actually_hardens(script, monkeypatch, capsys):
    """NEW (regression from the EXEC-07 fix): in ``admin_action`` the line ``if args.harden_account:``
    was replaced by the new ``--live`` refusal, leaving ``harden_account(broker)`` as dead code after
    ``return EXIT_KILL``. ``--broker alpaca --harden-account`` now falls through to
    ``release_broker_kill_switch(broker, None)`` and exits 2 with ``release_not_confirmed``: the
    runbook's account-hardening step can no longer be performed from the script."""
    from stocktry.execution import preflight
    from stocktry.execution.testing import make_sim

    sim = make_sim()
    seen = []
    monkeypatch.setattr(script, "make_alpaca_broker", lambda args: sim)
    monkeypatch.setattr(preflight, "harden_account", lambda b: seen.append(b.name) or {"suspend_trade": "confirmed"})
    rc = script.main(["--broker", "alpaca", "--harden-account"])
    out = capsys.readouterr().out
    assert rc == 0 and seen == [sim.name], f"--harden-account did not harden (exit {rc}): {out!r}"


def test_recheck_new_alpaca_fallback_never_collects_from_yahoo(monkeypatch):
    """NEW: with ``--price-source alpaca`` (the unattended workflow), any Alpaca data failure falls back
    to ``fetch_closes_and_dividends(symbols, refresh=refresh)``, and ``refresh`` defaults to True for
    ``--broker alpaca``. In GitHub Actions there is no cache, so the fallback performs an automated
    Yahoo download from the unattended job -- which the research report s.10 rules out ("Unattended
    paper or live runs: prices from the broker's own market-data API ..., never from Yahoo"). The
    fallback may read an existing local cache, but must never refresh it from the network."""
    from stocktry.execution import strategy_io

    def alpaca_down(symbols, *, end, feed=None, env=None):
        raise RuntimeError("Alpaca market data unavailable")

    refreshes = []

    def cache(symbols, *, refresh):
        refreshes.append(refresh)
        idx = pd.bdate_range("2025-01-02", "2026-09-30")
        return pd.DataFrame({s: np.linspace(100, 120, len(idx)) for s in symbols}, index=idx), {}

    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends_alpaca", alpaca_down)
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", cache)
    try:
        strategy_io.load_closes(["SPY"], price_source="alpaca", refresh=True, end=date(2026, 9, 30))
    except Exception:  # refusing to fall back at all is also acceptable
        pass
    assert True not in refreshes, "Alpaca failure fell back to a network (Yahoo) refresh from the unattended runner"


# =========================================================================== RECHECK (round 2)
# Added by the recheck of the fixer's round-2 changes.

def test_recheck2_exec_01_ci_like_fresh_ledger_on_session_3_opens_no_leg(tmp_path):
    """EXEC-01 variation (passes): session 1 evaluated as nothing_to_do, then a trigger on session 3 on a
    runner with an EMPTY ledger (as on GitHub Actions) and large drift: the broker/calendar rule alone
    must keep new legs closed."""
    from stocktry.execution.testing import scenario

    sc = scenario(tmp_path, cash=0.0, positions={"SPY": 0.13, "IEF": 39 / 95, "GLD": 0.104})
    assert sc.run().status == "nothing_to_do"
    sc.broker.set_now(et(2026, 10, 5, 15, 30))  # session 3
    sc.broker.set_prices({"GLD": 300.0, "SPY": 450.0})
    sc.refresh()
    res = sc.run(cfg=replace(sc.cfg, ledger_path=tmp_path / "fresh-runner" / "demo.jsonl"))
    assert sc.broker.orders == [] and res.status == "skipped" and "first_session_passed" in res.reason


def test_recheck2_new_late_start_with_unreadable_ledger_ignores_the_evaluated_run(tmp_path):
    """NEW (low): ``--late-start`` is documented to open legs "only while ... the local ledger shows no
    evaluated run". ``_new_leg_gate`` treats an unreadable ledger (a line cut short by a crash) as EMPTY,
    so the evaluated-run check silently passes and a late start opens brand-new legs on drifted prices
    although session 1 was evaluated (``nothing_to_do``). Because ``Ledger.append`` writes after the
    partial line without a newline, the ledger stays unreadable for every later run. The broker rule
    alone is fine for unattended runs, but the operator override must fail closed when its cross-check
    cannot be performed (refuse ``late_start`` when the ledger cannot be read)."""
    from stocktry.execution.testing import scenario

    sc = scenario(tmp_path, cash=0.0, positions={"SPY": 0.13, "IEF": 39 / 95, "GLD": 0.104})
    assert sc.run().status == "nothing_to_do"  # session 1 was evaluated
    with open(sc.cfg.ledger_path, "a", encoding="utf-8") as fh:
        fh.write('{"event": "run_end", "status": "compl')  # a later run crashed mid-write
    sc.broker.set_now(et(2026, 10, 2, 11))  # session 2
    sc.broker.set_prices({"GLD": 300.0})
    sc.refresh()
    sc.run(cfg=replace(sc.cfg, late_start=True))
    new = sorted(o.client_order_id for o in sc.broker.orders)
    assert new == [], f"late start bypassed the evaluated-run check through an unreadable ledger: {new}"
