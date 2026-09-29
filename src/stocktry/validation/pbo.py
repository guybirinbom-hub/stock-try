"""Probability of backtest overfitting via CSCV (Bailey, Borwein, Lopez de Prado & Zhu 2016).

Input: a T x N matrix of monthly (excess) returns, one column per
configuration of a parameter grid. Procedure:

1. Drop the earliest ``T mod S`` rows and split the rest into S contiguous
   blocks of equal length (default S = 16).
2. For every combination of S/2 blocks (C(16, 8) = 12,870 -- all of them;
   the computation is vectorized, so no sampling is needed): the chosen
   blocks form the in-sample (IS) set and the rest the out-of-sample (OOS) set.
3. Performance = per-period Sharpe ratio. Pick n* = argmax IS Sharpe. Let
   w = rank of n*'s OOS Sharpe among all N OOS Sharpes / (N + 1)
   (ranks 1..N ascending, ties averaged). Logit = ln(w / (1 - w)).
4. PBO = fraction of splits with logit <= 0 (IS winner at or below the OOS median).

Also reported: the probability that the IS winner loses money OOS (Sharpe < 0)
and the slope of OOS on IS Sharpe of the selected configuration.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy.stats import rankdata


@dataclass(frozen=True)
class PBOResult:
    pbo: float
    logits: np.ndarray
    n_splits: int
    s_blocks: int
    n_configs: int
    t_used: int
    prob_oos_loss: float
    is_oos_slope: float
    median_logit: float

    def to_dict(self) -> dict:
        return {"pbo": self.pbo, "n_splits": self.n_splits, "s_blocks": self.s_blocks, "n_configs": self.n_configs,
                "t_used": self.t_used, "prob_oos_loss": self.prob_oos_loss, "is_oos_slope": self.is_oos_slope,
                "median_logit": self.median_logit}


def _block_stats(x: np.ndarray, s: int) -> tuple[np.ndarray, np.ndarray, int]:
    t, n = x.shape
    m = t // s
    xb = x[t - m * s:].reshape(s, m, n)
    return xb.sum(axis=1), (xb**2).sum(axis=1), m


def _sharpe_from_sums(sm: np.ndarray, sq: np.ndarray, cnt: int) -> np.ndarray:
    mean = sm / cnt
    var = (sq - cnt * mean**2) / (cnt - 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(var > 0, mean / np.sqrt(np.maximum(var, 1e-300)), 0.0)


def cscv_pbo(returns: np.ndarray, s_blocks: int = 16, max_splits: int | None = None, seed: int = 0) -> PBOResult:
    """PBO for a (T x N) return matrix. ``max_splits`` samples combinations (seeded) if set."""
    x = np.asarray(returns, dtype=float)
    if x.ndim != 2 or x.shape[1] < 2:
        raise ValueError("need a T x N matrix with N >= 2 configurations")
    if s_blocks % 2 or s_blocks < 4:
        raise ValueError("s_blocks must be even and >= 4")
    if np.isnan(x).any():
        raise ValueError("returns contain NaN")
    t, n = x.shape
    sums, sqs, m = _block_stats(x, s_blocks)
    combos = np.array(list(combinations(range(s_blocks), s_blocks // 2)))
    if max_splits is not None and len(combos) > max_splits:
        rng = np.random.default_rng(seed)
        combos = combos[np.sort(rng.choice(len(combos), max_splits, replace=False))]
    inc = np.zeros((len(combos), s_blocks))
    inc[np.arange(len(combos))[:, None], combos] = 1.0
    cnt = (s_blocks // 2) * m
    sr_is = _sharpe_from_sums(inc @ sums, inc @ sqs, cnt)
    sr_oos = _sharpe_from_sums((1 - inc) @ sums, (1 - inc) @ sqs, cnt)
    best = np.argmax(sr_is, axis=1)
    ranks = rankdata(sr_oos, axis=1)  # 1..N ascending, ties averaged
    w = ranks[np.arange(len(combos)), best] / (n + 1.0)
    logits = np.log(w / (1.0 - w))
    sel_is = sr_is[np.arange(len(combos)), best]
    sel_oos = sr_oos[np.arange(len(combos)), best]
    slope = float(np.polyfit(sel_is, sel_oos, 1)[0]) if np.std(sel_is) > 0 else float("nan")
    return PBOResult(
        pbo=float(np.mean(logits <= 0)), logits=logits, n_splits=len(combos), s_blocks=s_blocks, n_configs=n,
        t_used=m * s_blocks, prob_oos_loss=float(np.mean(sel_oos < 0)), is_oos_slope=slope,
        median_logit=float(np.median(logits)),
    )
