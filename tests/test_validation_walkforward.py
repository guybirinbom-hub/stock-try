"""Walk-forward selection, the pre-registered split, and the plateau statistic."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocktry.validation.plateau import plateau_statistic, sweep_frame
from stocktry.validation.walkforward import split_metrics, walk_forward


def test_walk_forward_picks_best_training_sharpe_and_is_causal():
    idx = pd.date_range("2000-01-31", periods=120, freq="ME")
    rng = np.random.default_rng(0)
    a = pd.Series(rng.normal(0.010, 0.02, 120), index=idx)  # good in the first half
    b = pd.Series(rng.normal(0.000, 0.02, 120), index=idx)
    b.iloc[60:] += 0.05  # b becomes great only in the last five years
    rets = pd.DataFrame({"a": a, "b": b})
    rf = pd.Series(0.0, index=idx)
    wf = walk_forward(rets, rf, min_train_months=60, step_months=12)
    assert len(wf.oos_returns) == 60 and wf.oos_returns.index[0] == idx[60]
    assert list(wf.choices["chosen"])[0] == "a"  # chosen on data before 2005 only
    # the first OOS year is exactly a's returns (no peeking at b's later success)
    np.testing.assert_allclose(wf.oos_returns.iloc[:12].to_numpy(), a.iloc[60:72].to_numpy())
    assert list(wf.choices["chosen"])[-1] == "b"  # eventually the evidence switches the choice


def test_split_metrics():
    idx = pd.date_range("2003-01-31", periods=60, freq="ME")
    r = pd.Series(0.01, index=idx)
    r[idx >= "2006-01-01"] = 0.0
    t = split_metrics(r, pd.Series(0.0, index=idx))
    assert t.loc["pre", "months"] == 36 and t.loc["post", "months"] == 24
    assert t.loc["pre", "cagr"] == pytest.approx(1.01**12 - 1) and t.loc["post", "cagr"] == 0.0


def test_plateau_statistic():
    s = pd.Series({lb: 0.6 for lb in range(3, 19)})
    s[8], s[12] = 0.45, 0.66
    st = plateau_statistic(s, 10)
    assert st["neighbors"] == [8, 9, 10, 11, 12]  # |p - 10| <= 2.5
    assert st["min_retained"] == pytest.approx(0.75) and st["worst_neighbor"] == 8
    st12 = plateau_statistic(s, 12)
    assert st12["neighbors"] == [9, 10, 11, 12, 13, 14, 15]  # |p - 12| <= 3
    neg = plateau_statistic(pd.Series({9: 0.1, 10: -0.1, 11: 0.1}), 10)
    assert np.isnan(neg["min_retained"])


def test_sweep_frame():
    rows = [{"rule": r, "lb": lb, "sharpe": lb / 10} for r in ("sma", "absmom") for lb in (3, 4)]
    t = sweep_frame(rows, "rule", "lb")
    assert t.loc["sma", 4] == 0.4 and t.shape == (2, 2)
