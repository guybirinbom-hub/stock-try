"""scripts/paper_rebalance.py end to end on the simulator (offline)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "sample_targets.json"
FIXTURE_INITIAL = REPO / "tests" / "fixtures" / "sample_targets_initial.json"


@pytest.fixture
def script(monkeypatch):
    spec = importlib.util.spec_from_file_location("paper_rebalance", REPO / "scripts" / "paper_rebalance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for k in ("KILL_SWITCH", "LIVE_TRADING", "NTFY_TOPIC", "HEALTHCHECK_URL", "KILL_SWITCH_FILE"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("KILL_SWITCH_FILE", "/nonexistent/stocktry-test-kill-switch")
    orig_out, orig_err = sys.stdout, sys.stderr
    yield mod
    sys.stdout, sys.stderr = orig_out, orig_err  # the script wraps std streams for scrubbing
    import logging

    root = logging.getLogger()
    for h in list(root.handlers):
        if h.get_name() == "stocktry-scrubbed":
            root.removeHandler(h)


def test_dry_run_is_default(script):
    assert script.parse_args(["--targets-json", str(FIXTURE)]).dry_run is True
    assert script.parse_args(["--targets-json", str(FIXTURE), "--no-dry-run"]).dry_run is False


def test_sim_dry_run_prints_plan_and_submits_nothing(script, tmp_path, capsys):
    rc = script.main(["--broker", "sim", "--targets-json", str(FIXTURE), "--capital", "100", "--dry-run",
                      "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "sample_three_asset-2026-10-01-SPY-sell-a1" in out
    assert "status=dry_run" in out
    events = [json.loads(line)["event"] for line in (tmp_path / "l.jsonl").read_text().splitlines()]
    assert "submit_intent" not in events and events[-1] == "run_end"


def test_sim_submit(script, tmp_path, capsys):
    rc = script.main(["--broker", "sim", "--targets-json", str(FIXTURE), "--capital", "100", "--no-dry-run",
                      "--ledger", str(tmp_path / "l.jsonl")])
    out = capsys.readouterr().out
    assert rc == 0 and "status=completed" in out and "submitted 3 order(s)" in out


def test_initial_deployment_needs_carve_out_flag(script, tmp_path, capsys):
    args = ["--broker", "sim", "--targets-json", str(FIXTURE_INITIAL), "--capital", "100", "--no-dry-run",
            "--ledger", str(tmp_path / "l.jsonl")]
    assert script.main(args) == script.EXIT_GUARD
    assert "max_daily_notional" in capsys.readouterr().out
    assert script.main(args + ["--initial-deployment"]) == 0


def test_kill_switch_exit_code(script, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KILL_SWITCH", "on")
    rc = script.main(["--broker", "sim", "--targets-json", str(FIXTURE), "--ledger", str(tmp_path / "l.jsonl")])
    assert rc == script.EXIT_KILL


def test_live_flags_rejected_for_sim_and_without_env(script, tmp_path, capsys):
    assert script.main(["--broker", "sim", "--targets-json", str(FIXTURE), "--live"]) == script.EXIT_CONFIG


def test_missing_alpaca_keys_is_a_config_error(script, monkeypatch, capsys):
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    assert script.main(["--broker", "alpaca", "--targets-json", str(FIXTURE)]) == script.EXIT_CONFIG
    assert script.main(["--broker", "alpaca", "--harden-account"]) == script.EXIT_CONFIG


def test_admin_actions_reach_the_broker(script, monkeypatch, capsys):
    """--harden-account, --engage-kill-switch and --release-kill-switch each perform their own action (NEW-01:
    a lost ``if args.harden_account:`` once made hardening fall through to the release branch)."""
    from dataclasses import replace

    from stocktry.execution.killswitch import RELEASE_CONFIRMATION
    from stocktry.execution.simbroker import HARDENED_CONFIG
    from stocktry.execution.testing import make_sim

    loose = replace(HARDENED_CONFIG, max_margin_multiplier="4", no_shorting=False, max_options_trading_level=2)
    sim = make_sim(config=loose)
    monkeypatch.setattr(script, "make_alpaca_broker", lambda args: sim)

    assert script.main(["--broker", "alpaca", "--harden-account"]) == script.EXIT_OK
    cfg = sim.get_account_configuration()
    assert (cfg.max_margin_multiplier, cfg.no_shorting, cfg.max_options_trading_level) == ("1", True, 0)
    assert cfg.suspend_trade is False and "confirmed" in capsys.readouterr().out

    assert script.main(["--broker", "alpaca", "--engage-kill-switch"]) == script.EXIT_OK
    assert sim.get_account_configuration().suspend_trade is True
    assert script.main(["--broker", "alpaca", "--release-kill-switch", "wrong"]) == script.EXIT_GUARD
    assert sim.get_account_configuration().suspend_trade is True
    assert script.main(["--broker", "alpaca", "--release-kill-switch", RELEASE_CONFIRMATION]) == script.EXIT_OK
    assert sim.get_account_configuration().suspend_trade is False


def test_late_start_flag_reaches_the_runner_and_is_refused_in_ci(script, tmp_path, monkeypatch, capsys):
    """EXEC-01b: on session 2+ an unattended run opens no leg; --late-start (operator only) does; CI refuses it."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("CI", raising=False)
    raw = json.loads(FIXTURE.read_text())
    for q in raw["prices"].values():  # session 2 (2026-10-02) sizes from the 2026-10-01 closes
        q["session"] = "2026-10-01"
    targets = tmp_path / "targets.json"
    targets.write_text(json.dumps(raw))
    base = ["--broker", "sim", "--targets-json", str(targets), "--capital", "100", "--no-dry-run",
            "--sim-now", "2026-10-02T11:00:00-04:00"]
    assert script.main(base + ["--ledger", str(tmp_path / "a.jsonl")]) == 0
    out = capsys.readouterr().out
    assert "status=skipped first_session_passed" in out and "submitted" not in out
    assert script.main(base + ["--ledger", str(tmp_path / "b.jsonl"), "--late-start"]) == 0
    out = capsys.readouterr().out
    assert "status=completed" in out and "submitted 3 order(s)" in out
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert script.main(base + ["--ledger", str(tmp_path / "c.jsonl"), "--late-start"]) == script.EXIT_CONFIG
    assert "refused in CI" in capsys.readouterr().out


def test_rebalance_date_override_is_sim_only(script):
    assert script.main(["--broker", "alpaca", "--targets-json", str(FIXTURE),
                        "--rebalance-date", "2026-10-01"]) == script.EXIT_CONFIG


def test_missing_core_package_gives_clear_error(script, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "stocktry.strategies.registry", None)
    rc = script.main(["--broker", "sim", "--strategy", "spy_buy_hold", "--rebalance-date", "2026-10-01"])
    assert rc == script.EXIT_CONFIG
    assert "not available" in capsys.readouterr().out


def test_registry_strategy_on_sim_with_synthetic_data(script, tmp_path, monkeypatch, capsys):
    """Uses the core registry if present, with synthetic prices (no network)."""
    pytest.importorskip("stocktry.strategies.registry")
    import numpy as np
    import pandas as pd

    from stocktry.execution import strategy_io

    def fake_fetch(symbols, *, refresh):
        idx = pd.bdate_range("2024-01-02", "2026-10-30")
        frame = pd.DataFrame({s: 100 * np.exp(np.linspace(0, 0.3, len(idx))) for s in symbols}, index=idx)
        return frame, {s: [] for s in symbols}

    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", fake_fetch)
    base = ["--broker", "sim", "--strategy", "spy_buy_hold", "--rebalance-date", "2026-10-01",
            "--capital", "100", "--dry-run", "--ledger", str(tmp_path / "l.jsonl")]
    assert script.main(base) == script.EXIT_GUARD  # $100 into one ETF > per-order cap of $25
    assert "max_order_notional" in capsys.readouterr().out
    rc = script.main(base + ["--initial-deployment", "--max-order-notional", "100", "--max-order-frac", "1",
                             "--limits-ack", script.LIMITS_OVERRIDE_ACK])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "strategy=spy_buy_hold" in out and "targets: SPY=1.0000" in out
    assert "decision_date=2026-09-30" in out and "spy_buy_hold-2026-10-01-SPY-buy-a1" in out


def test_price_source_default_follows_the_keys_and_is_recorded_in_the_ledger(script, tmp_path, monkeypatch, capsys):
    """R4: registry strategies take bars from Alpaca Market Data when keys are set (feed iex unless configured),
    else from the research cache; every run's ledger records the source and feed."""
    pytest.importorskip("stocktry.strategies.registry")
    import numpy as np
    import pandas as pd

    from stocktry.execution import strategy_io

    idx = pd.bdate_range("2024-01-02", "2026-10-30")
    frame = pd.DataFrame({"SPY": 100 * np.exp(np.linspace(0, 0.3, len(idx)))}, index=idx)
    feeds = []
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", lambda symbols, *, refresh: (frame[symbols], {}))
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends_alpaca",
                        lambda symbols, *, end, feed=None, env=None: feeds.append(feed) or (frame[symbols], {},
                                                                                           feed or "iex"))
    for k in ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY", "APCA_DATA_FEED"):
        monkeypatch.delenv(k, raising=False)
    ledger = tmp_path / "l.jsonl"
    base = ["--broker", "sim", "--strategy", "spy_buy_hold", "--rebalance-date", "2026-10-01", "--capital", "100",
            "--dry-run", "--ledger", str(ledger), "--initial-deployment", "--max-order-notional", "100",
            "--max-order-frac", "1", "--limits-ack", script.LIMITS_OVERRIDE_ACK]

    def last_start():
        return [json.loads(l) for l in ledger.read_text().splitlines() if '"run_start"' in l][-1]

    assert script.main(base) == 0
    assert (last_start()["price_source"], last_start()["data_feed"]) == ("cache", None) and feeds == []
    monkeypatch.setenv("APCA_API_KEY_ID", "PKDUMMYDUMMYDUMMY123")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "d" * 40)
    assert script.main(base) == 0
    assert (last_start()["price_source"], last_start()["data_feed"]) == ("alpaca", "iex")
    assert script.main(base + ["--data-feed", "sip"]) == 0
    assert last_start()["data_feed"] == "sip" and feeds[-1] == "sip"
    assert script.main(base + ["--price-source", "cache"]) == 0
    assert last_start()["price_source"] == "cache"
    out = capsys.readouterr().out
    assert "price_source=alpaca feed=iex" in out


def test_corporate_action_symbols_are_validated(script, tmp_path, capsys):
    """EXEC-19: a lowercase or junk --corporate-action value is a configuration error, not silently ignored."""
    rc = script.main(["--broker", "sim", "--targets-json", str(FIXTURE), "--corporate-action", "spy",
                      "--ledger", str(tmp_path / "l.jsonl")])
    assert rc == script.EXIT_CONFIG and "corporate-action" in capsys.readouterr().out
