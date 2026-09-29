"""Probabilistic and deflated Sharpe ratios (Bailey & Lopez de Prado 2012, 2014).

All Sharpe ratios here are **per period** (not annualized): for monthly data
SR = mean(monthly excess) / std(monthly excess); an annualized SR is divided by
sqrt(periods per year) before use. ``T`` is the number of return observations;
``kurtosis`` is **non-excess** (normal = 3).

* PSR(SR*) = Phi( (SR - SR*) * sqrt(T - 1) / sqrt(1 - skew * SR + (kurt - 1) / 4 * SR^2) )
* Expected maximum Sharpe of N zero-skill trials with cross-trial variance V
  (per-period units):
  E[max SR] = sqrt(V) * ((1 - g) * Phi^-1(1 - 1/N) + g * Phi^-1(1 - 1/(N e))), g = 0.5772...
* DSR = PSR(E[max SR]).

V must be the empirical **variance of the Sharpe ratios across trials** (as the
paper specifies), not 1/T.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.stats import norm

EULER_GAMMA = 0.5772156649015329


def expected_max_sharpe(var_sr: float, n_trials: int) -> float:
    """E[max SR] of ``n_trials`` independent zero-skill trials (per-period units). 0 for N <= 1."""
    if n_trials <= 1 or var_sr <= 0:
        return 0.0
    n = float(n_trials)
    z1 = norm.ppf(1.0 - 1.0 / n)
    z2 = norm.ppf(1.0 - 1.0 / (n * math.e))
    return math.sqrt(var_sr) * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)


def psr_z(sr: float, sr_star: float, t: int, skew: float, kurtosis: float) -> float:
    denom = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr * sr
    if denom <= 0 or t < 2:
        return float("nan")
    return (sr - sr_star) * math.sqrt(t - 1.0) / math.sqrt(denom)


def probabilistic_sharpe(sr: float, sr_star: float, t: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """P(true SR > sr_star) given an observed per-period ``sr`` over ``t`` observations."""
    z = psr_z(sr, sr_star, t, skew, kurtosis)
    return float(norm.cdf(z)) if math.isfinite(z) else float("nan")


@dataclass(frozen=True)
class DSRResult:
    sr: float  # per period
    sr0: float  # E[max SR] threshold, per period
    dsr: float
    n_trials: int
    var_sr: float  # per-period^2
    t: int
    skew: float
    kurtosis: float

    def to_dict(self, periods_per_year: int = 12) -> dict:
        a = math.sqrt(periods_per_year)
        return {
            "sr_per_period": self.sr, "sr_annualized": self.sr * a, "sr0_per_period": self.sr0,
            "sr0_annualized": self.sr0 * a, "dsr": self.dsr, "n_trials": self.n_trials,
            "var_sr_per_period": self.var_sr, "t": self.t, "skew": self.skew, "kurtosis": self.kurtosis,
        }


def deflated_sharpe(sr: float, t: int, skew: float, kurtosis: float, var_sr: float, n_trials: int) -> DSRResult:
    """Deflated Sharpe ratio of a candidate selected from ``n_trials`` with cross-trial variance ``var_sr``."""
    sr0 = expected_max_sharpe(var_sr, n_trials)
    return DSRResult(sr, sr0, probabilistic_sharpe(sr, sr0, t, skew, kurtosis), n_trials, var_sr, t, skew, kurtosis)
