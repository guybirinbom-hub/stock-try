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
