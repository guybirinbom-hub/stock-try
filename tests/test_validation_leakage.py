"""The two structural leakage tests (identity and perfect foresight) plus the gap and shift variants."""
from __future__ import annotations

import pandas as pd
import pytest

from stocktry.backtest.costs import CostModel
from stocktry.backtest.engine import EngineConfig
from stocktry.data.panel import panel_from_bars
from stocktry.strategies.trend import make_trend_sma
from stocktry.validation import leakage as L

from conftest import gbm_close, make_bars


def test_identity_buy_and_hold_equals_total_return_series(dividend_payer_bars):
    panel = panel_from_bars({"SPY": dividend_payer_bars}, pd.Series(3.0, index=dividend_payer_bars.index))
    r = L.identity_test(panel, "SPY", start="2005-01")
    assert r["passed"]
    assert abs(r["tracking_diff_bp_per_year"]) < 1.0 and r["max_abs_monthly_diff_bp"] < 1e-3


def test_foresight_useless_with_lag_huge_with_same_bar():
    r = L.foresight_test(L.synthetic_monthly_panel(n_months=600, seed=7))
    assert r["lagged_sharpe_within_noise"] and r["lagged_alpha_within_noise"]
    assert r["same_bar_huge"]
    assert r["sharpe_same_bar"] > 10 * r["sharpe_se"] and r["alpha_t_same_bar"] > 10


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_foresight_holds_across_seeds(seed):
    r = L.foresight_test(L.synthetic_monthly_panel(n_months=480, seed=seed))
    assert r["lagged_alpha_within_noise"] and r["same_bar_huge"]


def test_gap_foresight_default_next_open_path():
    r = L.gap_foresight_test(L.synthetic_daily_panel(n_days=252 * 100, seed=11))
    assert r["lagged_no_gap_capture"] and r["same_bar_captures_gap"]


def test_one_bar_shift_small_for_slow_rule():
    idx = pd.bdate_range("2000-01-03", periods=252 * 12)
    panel = panel_from_bars({"SPY": make_bars(gbm_close(len(idx), seed=9), dates=idx)}, pd.Series(2.0, index=idx))
    out = L.one_bar_shift(make_trend_sma("SPY", 10), panel, EngineConfig(costs=CostModel.gate(), start="2001-06"))
    assert abs(out["delta_sharpe"]) < 0.3


def test_alpha_tstat_recovers_known_alpha():
    import numpy as np

    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0.005, 0.04, 2000))
    y = 0.002 + 0.5 * x + pd.Series(rng.normal(0, 0.001, 2000))
    a, t, b = L.alpha_tstat(y, x)
    assert a == pytest.approx(0.002, abs=1e-4) and b == pytest.approx(0.5, abs=0.01) and t > 50
