"""Every metric against numbers worked out by hand (the arithmetic is in the comments)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from stocktry.backtest import metrics as M

IDX = pd.to_datetime(["2020-01-31", "2020-02-28", "2020-03-31", "2020-04-30"])
R = pd.Series([0.10, -0.05, 0.02, 0.03], index=IDX)
RF = pd.Series(0.001, index=IDX)
B = pd.Series([0.05, -0.02, 0.01, 0.02], index=IDX)


def test_cagr_by_hand():
    # growth = 1.10 * 0.95 * 1.02 * 1.03 = 1.097877; 4 months -> exponent 12/4 = 3
    assert M.cagr(R) == pytest.approx(1.097877**3 - 1, rel=1e-12)
    assert M.total_return(R) == pytest.approx(0.097877, rel=1e-12)


def test_volatility_by_hand():
    # mean 0.025; deviations 0.075, -0.075, -0.005, 0.005; sum sq = 0.0113; /(n-1)=3 -> 0.0037667
    assert M.annualized_vol(R) == pytest.approx(math.sqrt(0.0113 / 3) * math.sqrt(12), rel=1e-12)


def test_sharpe_vs_tbills_by_hand():
    # excess = 0.099, -0.051, 0.019, 0.029; mean 0.024; deviations as above -> sd = sqrt(0.0113/3)
    sr_m = 0.024 / math.sqrt(0.0113 / 3)
    assert M.sharpe_per_period(R, RF) == pytest.approx(sr_m, rel=1e-12)
    assert M.sharpe(R, RF) == pytest.approx(sr_m * math.sqrt(12), rel=1e-12)  # 1.35464
    assert M.sharpe(R, RF) == pytest.approx(1.354638, rel=1e-6)
    # Sharpe vs zero differs: T-bills are subtracted, not ignored
    assert M.sharpe(R, 0.0) != pytest.approx(M.sharpe(R, RF))


def test_sortino_by_hand():
    # downside excess = [0, -0.051, 0, 0]; sqrt(mean of squares) = sqrt(0.002601 / 4) = 0.0255
    assert M.sortino(R, RF) == pytest.approx(0.024 / 0.0255 * math.sqrt(12), rel=1e-12)  # 3.26033


def test_drawdown_duration_calmar_by_hand():
    eq = M.equity_from_returns(R)  # 1, 1.1, 1.045, 1.0659, 1.097877
    np.testing.assert_allclose(eq, [1.0, 1.1, 1.045, 1.0659, 1.097877])
    assert M.max_drawdown(eq) == pytest.approx(1.045 / 1.1 - 1)  # -5 %
    assert M.max_drawdown_duration(eq) == 3  # three periods below the 1.1 peak, never recovered
    assert M.calmar(R) == pytest.approx((1.097877**3 - 1) / 0.05, rel=1e-9)


def test_hit_rate_beta_corr_te_by_hand():
    assert M.hit_rate(R) == 0.75
    # b: mean 0.015, deviations 0.035, -0.035, -0.005, 0.005 -> var = 0.0025/3
    # cov(r, b) = (2*0.075*0.035 + 2*0.005*0.005)/3 = 0.0053/3 -> beta = 0.0053/0.0025 = 2.12
    assert M.beta(R, B) == pytest.approx(2.12, rel=1e-12)
    assert M.correlation(R, B) == pytest.approx((0.0053 / 3) / math.sqrt(0.0113 / 3 * 0.0025 / 3), rel=1e-12)
    # r - b = 0.05, -0.03, 0.01, 0.01; mean 0.01; deviations 0.04, -0.04, 0, 0 -> var 0.0032/3
    assert M.tracking_error(R, B) == pytest.approx(math.sqrt(0.0032 / 3) * math.sqrt(12), rel=1e-12)


def test_annualization_constant_and_alternating():
    idx = pd.date_range("2021-01-31", periods=12, freq="ME")
    const = pd.Series(0.01, index=idx)
    assert M.cagr(const) == pytest.approx(1.01**12 - 1)  # 12.6825 %, not 12 %
    assert M.annualized_vol(const) == pytest.approx(0.0, abs=1e-15)
    alt = pd.Series([0.01, -0.01] * 6, index=idx)
    # mean 0, each squared deviation 1e-4, 12 of them / 11 -> sd = sqrt(12e-4/11); * sqrt(12)
    assert M.annualized_vol(alt) == pytest.approx(math.sqrt(12e-4 / 11) * math.sqrt(12), rel=1e-12)
    two_years = pd.Series([(1.21) ** (1 / 24) - 1] * 24, index=pd.date_range("2021-01-31", periods=24, freq="ME"))
    assert M.cagr(two_years) == pytest.approx(0.10, rel=1e-12)  # 21 % over two years = 10 %/yr


def test_annual_returns_and_regime_slices():
    idx = pd.date_range("2019-11-30", periods=5, freq="ME")  # Nov 2019 .. Mar 2020
    r = pd.Series([0.01, 0.02, 0.03, -0.10, 0.05], index=idx)
    ann = M.annual_returns(r)
    assert ann[2019] == pytest.approx(1.01 * 1.02 - 1)
    assert ann[2020] == pytest.approx(1.03 * 0.90 * 1.05 - 1)
    tr, mdd, n = M.slice_return(r, "2020-02", "2020-03")  # both ends inclusive
    assert n == 2 and tr == pytest.approx(0.90 * 1.05 - 1) and mdd == pytest.approx(-0.10)
    tab = M.regime_table({"x": r}, (("s", "2020-01", "2020-03"), ("missing", "2020-01", "2020-06")))
    assert tab.loc["s", "x"] == pytest.approx(1.03 * 0.90 * 1.05 - 1)
    assert math.isnan(tab.loc["missing", "x"])  # incomplete slice is not reported


def test_skew_kurtosis_normal_is_about_3():
    x = np.random.default_rng(0).normal(size=200_000)
    sk, ku = M.skew_kurtosis(x)
    assert abs(sk) < 0.02 and ku == pytest.approx(3.0, abs=0.05)


def test_count_switches():
    reb = pd.DataFrame({"targets": [{"A": 1.0}, {"A": 1.0}, {}, {}, {"A": 0.5}, {"A": 1.0}]})
    assert M.count_switches(reb) == 3
