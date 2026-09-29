"""Stationary block bootstrap: determinism, block structure, percentile ordering."""
from __future__ import annotations

import numpy as np
import pandas as pd

from stocktry.validation.bootstrap import bootstrap, path_metrics, percentile_table, stationary_bootstrap_indices


def test_indices_block_structure():
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(50, 200, mean_block=1e12, rng=rng)  # never jumps: one circular block
    d = (idx[:, 1:] - idx[:, :-1]) % 50
    assert (d == 1).all()
    idx6 = stationary_bootstrap_indices(1000, 50, mean_block=6, rng=np.random.default_rng(1))
    cont = ((idx6[:, 1:] - idx6[:, :-1]) % 1000 == 1).mean()
    assert 0.78 < cont < 0.88  # P(continue) = 1 - 1/6 = 0.833 (plus rare coincidences)


def test_deterministic_and_ordered():
    rng = np.random.default_rng(3)
    idx = pd.date_range("2000-01-31", periods=240, freq="ME")
    df = pd.DataFrame({"a": rng.normal(0.008, 0.04, 240), "b": rng.normal(0.006, 0.02, 240), "rf": 0.002},
                      index=idx)
    b1 = bootstrap(df, n_paths=500, seed=11)
    b2 = bootstrap(df, n_paths=500, seed=11)
    np.testing.assert_array_equal(b1["a"]["cagr"], b2["a"]["cagr"])
    t = percentile_table(b1)
    for s in ("a", "b"):
        assert t.loc[s, "cagr_p5"] <= t.loc[s, "cagr_p50"] <= t.loc[s, "cagr_p95"]
        assert t.loc[s, "sharpe_p5"] <= t.loc[s, "sharpe_p50"] <= t.loc[s, "sharpe_p95"]
        assert 0 <= t.loc[s, "dd_mag_p5"] <= t.loc[s, "dd_mag_p50"] <= t.loc[s, "dd_mag_p95"] <= 1
    assert t.loc["b", "dd_mag_p50"] < t.loc["a", "dd_mag_p50"]  # lower-vol series draws down less


def test_path_metrics_match_direct_computation():
    r = np.array([[0.1, -0.05, 0.02, 0.03]])
    m = path_metrics(r, np.full((1, 4), 0.001))
    assert abs(m["cagr"][0] - (1.097877**3 - 1)) < 1e-12
    assert abs(m["max_dd"][0] - (1.045 / 1.1 - 1)) < 1e-12
    assert abs(m["sharpe"][0] - 0.024 / np.sqrt(0.0113 / 3) * np.sqrt(12)) < 1e-12
