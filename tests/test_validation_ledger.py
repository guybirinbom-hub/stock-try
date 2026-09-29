"""Trial ledger: dedupe by trial key, run counting, cross-trial variance, leaky results refused."""
from __future__ import annotations

import json

import numpy as np
import pytest

from stocktry.validation.ledger import HEADLINE_RUN_KEY, TrialLedger, run_key


def _rec(led, lb, sr, sample="s", cost="gate", cap=10_000.0):
    return led.record(strategy=f"sma{lb}", family="trend_sma", params={"lookback": lb}, sample=sample,
                      cost_tier=cost, capital=cap, whole_shares=False, fill="next_open", t=240,
                      sharpe_per_period=sr, skew=-0.5, kurtosis=4.0, cagr=0.08, max_dd=-0.2,
                      first_month="2006-03", last_month="2026-02")


def test_record_dedupe_and_variance(tmp_path):
    led = TrialLedger(tmp_path / "ledger.json")
    k1 = _rec(led, 10, 0.20)
    k1b = _rec(led, 10, 0.20, cost="gate_x2")  # same trial, other configuration
    assert k1 == k1b
    _rec(led, 11, 0.10)
    _rec(led, 12, 0.30)
    _rec(led, 10, 0.25, sample="other")
    assert led.n_trials("s") == 3 and led.n_trials() == 4
    assert led.sharpe_variance("s") == pytest.approx(np.var([0.20, 0.10, 0.30], ddof=1))
    data = json.loads((tmp_path / "ledger.json").read_text())
    tr = data["trials"][k1]
    assert tr["run_count"] == 2 and set(tr["runs"]) == {HEADLINE_RUN_KEY, run_key("gate_x2", 10_000, False,
                                                                                    "next_open")}
    assert led.n_trials("s", ("trend_sma",)) == 3 and led.n_trials("s", ("gtaa4",)) == 0


def test_headline_run_used_for_stats(tmp_path):
    led = TrialLedger(tmp_path / "l.json")
    _rec(led, 10, 0.99, cost="gate_x2")
    _rec(led, 10, 0.20)  # headline configuration
    assert float(led.trials("s")["sharpe_per_period"].iloc[0]) == pytest.approx(0.20)


def test_leaky_refused(tmp_path):
    led = TrialLedger(tmp_path / "l.json")
    with pytest.raises(ValueError):
        led.record(strategy="x", family="x", params={}, sample="s", cost_tier="gate", capital=1.0,
                   whole_shares=False, fill="next_open", t=10, sharpe_per_period=9.0, skew=0.0, kurtosis=3.0,
                   cagr=1.0, max_dd=0.0, first_month="a", last_month="b", leaky=True)
    assert led.n_trials() == 0
