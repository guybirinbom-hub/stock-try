"""Deflated Sharpe ratio: the Bailey & Lopez de Prado (2014) worked example, and basic properties."""
from __future__ import annotations

import math

import pytest

from stocktry.validation.dsr import deflated_sharpe, expected_max_sharpe, probabilistic_sharpe

# Paper's example: annualized SR 2.5 over 5 years of daily data (T = 1250, 250 days/yr), 100 trials whose
# annualized Sharpe ratios have variance 0.5, skew -3, kurtosis 10. Per-period units throughout.
SR = 2.5 / math.sqrt(250)
V = 0.5 / 250
T = 1250


def test_worked_example_100_trials():
    r = deflated_sharpe(SR, T, skew=-3.0, kurtosis=10.0, var_sr=V, n_trials=100)
    assert r.sr0 * math.sqrt(250) == pytest.approx(1.7894, abs=1e-3)  # E[max SR], annualized
    assert r.dsr == pytest.approx(0.9004, abs=1e-3)


def test_worked_example_46_trials():
    r = deflated_sharpe(SR, T, skew=-3.0, kurtosis=10.0, var_sr=V, n_trials=46)
    assert r.dsr == pytest.approx(0.9505, abs=1e-3)


def test_properties():
    assert expected_max_sharpe(0.01, 1) == 0.0
    assert expected_max_sharpe(0.01, 10) < expected_max_sharpe(0.01, 100) < expected_max_sharpe(0.01, 1000)
    assert expected_max_sharpe(0.02, 100) > expected_max_sharpe(0.01, 100)
    assert probabilistic_sharpe(0.1, 0.1, 100) == pytest.approx(0.5)
    # Negative skew and fat tails lower confidence in a positive Sharpe.
    assert probabilistic_sharpe(0.1, 0.0, 120, -1.0, 6.0) < probabilistic_sharpe(0.1, 0.0, 120, 0.0, 3.0)
    # Normal case z = SR * sqrt(T - 1) / sqrt(1 + SR^2 / 2)
    z = 0.1 * math.sqrt(119) / math.sqrt(1 + 0.5 * 0.01)
    from scipy.stats import norm
    assert probabilistic_sharpe(0.1, 0.0, 120) == pytest.approx(norm.cdf(z))
