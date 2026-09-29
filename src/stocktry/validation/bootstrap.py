"""Stationary block bootstrap (Politis & Romano 1994) of monthly returns.

Each path has the sample's length T. It starts at a uniformly random month;
at each subsequent step it continues to the next month (wrapping around the
end) with probability 1 - 1/b, or jumps to a new uniformly random month with
probability 1/b, so block lengths are geometric with mean ``b`` months
(default 6). All series in a DataFrame (strategy, benchmark, T-bill) are
resampled with the *same* indices so their joint behaviour is preserved.
Randomness comes only from ``numpy.random.default_rng(seed)``.

Per path: CAGR (12 / T exponent), annualized Sharpe versus the resampled
T-bill column, and maximum drawdown of the monthly equity path. Reported:
5th / 50th / 95th percentiles; for drawdowns the "95th percentile" is the
95th percentile of drawdown *magnitude* (a bad-tail number).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def stationary_bootstrap_indices(t: int, n_paths: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Index matrix of shape (n_paths, t)."""
    if mean_block < 1:
        raise ValueError("mean_block must be >= 1")
    p = 1.0 / mean_block
    idx = np.empty((n_paths, t), dtype=np.int64)
    idx[:, 0] = rng.integers(0, t, n_paths)
    jumps = rng.random((n_paths, t)) < p
    fresh = rng.integers(0, t, (n_paths, t))
    for k in range(1, t):
        idx[:, k] = np.where(jumps[:, k], fresh[:, k], (idx[:, k - 1] + 1) % t)
    return idx


def path_metrics(r: np.ndarray, rf: np.ndarray | None = None, periods_per_year: int = 12) -> dict[str, np.ndarray]:
    """Vectorized metrics for a (paths, T) matrix of returns."""
    t = r.shape[1]
    growth = np.prod(1.0 + r, axis=1)
    cagr = np.where(growth > 0, growth ** (periods_per_year / t) - 1.0, -1.0)
    ex = r - (rf if rf is not None else 0.0)
    sd = ex.std(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        sharpe = np.where(sd > 0, ex.mean(axis=1) / sd * math.sqrt(periods_per_year), np.nan)
    eq = np.cumprod(1.0 + r, axis=1)
    eq = np.concatenate([np.ones((r.shape[0], 1)), eq], axis=1)
    peak = np.maximum.accumulate(eq, axis=1)
    mdd = (eq / peak - 1.0).min(axis=1)
    return {"cagr": cagr, "sharpe": sharpe, "max_dd": mdd}


def bootstrap(returns: pd.DataFrame, rf_col: str | None = "rf", mean_block: float = 6.0, n_paths: int = 2000,
              seed: int = 20260929) -> dict[str, dict[str, np.ndarray]]:
    """Bootstrap every non-rf column of ``returns`` jointly; returns per-column metric arrays."""
    df = returns.dropna()
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(len(df), n_paths, mean_block, rng)
    rf = df[rf_col].to_numpy()[idx] if rf_col and rf_col in df.columns else None
    out = {}
    for c in df.columns:
        if c == rf_col:
            continue
        out[c] = path_metrics(df[c].to_numpy()[idx], rf)
    return out


def percentile_table(boot: dict[str, dict[str, np.ndarray]], pcts: tuple[int, ...] = (5, 50, 95)) -> pd.DataFrame:
    """Rows = series; columns = metric percentiles. Drawdown columns use magnitude percentiles."""
    rows = {}
    for name, m in boot.items():
        row = {}
        for p in pcts:
            row[f"cagr_p{p}"] = float(np.nanpercentile(m["cagr"], p))
            row[f"sharpe_p{p}"] = float(np.nanpercentile(m["sharpe"], p))
            row[f"dd_mag_p{p}"] = float(np.nanpercentile(-m["max_dd"], p))
        row["p_cagr_below_0"] = float(np.mean(m["cagr"] < 0))
        rows[name] = row
    return pd.DataFrame(rows).T
