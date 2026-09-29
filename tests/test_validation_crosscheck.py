"""Independent engine cross-check against bt 1.2.3 and the Fama-French helpers, on synthetic data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from stocktry.data.panel import panel_from_bars
from stocktry.data.rates import tbill_index
from stocktry.validation import crosscheck as X

from conftest import gbm_close, make_bars


def test_engine_matches_bt_on_synthetic_series():
    idx = pd.bdate_range("2000-01-03", periods=252 * 8)
    panel = panel_from_bars({"SPY": make_bars(gbm_close(len(idx), 0.06, 0.2, seed=21), dates=idx)}, None)
    df = X.bt_crosscheck(panel, "SPY", start="2001-01")
    gated = df[df["gated"]]
    assert len(gated) == 2 and gated["passed"].all()
    # Pre-registered gate is 1 bp; the only residual is cent-rounding of notional orders (~1e-6 bp).
    assert (gated["max_abs_diff_bp"] < 1e-3).all()


def test_ff_rf_and_market_helpers():
    cal = pd.bdate_range("1990-01-01", "1995-12-31")
    y = pd.Series(6.0, index=cal)
    idx = tbill_index(cal, y)
    me = pd.date_range("1990-01-31", "1995-12-31", freq="ME")
    ours_m = idx.groupby(idx.index.to_period("M")).last().pct_change()
    ff = pd.DataFrame({"Mkt-RF": 0.01, "SMB": 0.0, "HML": 0.0, "RF": ours_m.reindex(me.to_period("M")).to_numpy()},
                      index=me).iloc[1:]
    r = X.ff_rf_crosscheck(idx, ff, since="1990-02")
    assert r["passed"] and r["max_abs_diff_bp"] < 1e-9
    spy = pd.Series(np.cumprod(np.full(len(cal), 1.0004)), index=cal)
    m = X.ff_market_crosscheck(spy, ff)
    assert m["months"] > 60 and np.isfinite(m["cagr_diff_bp"])
