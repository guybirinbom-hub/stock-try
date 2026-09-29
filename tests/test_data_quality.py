"""Every data-quality failure mode, plus a clean series that passes."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocktry.data import quality as Q
from stocktry.data.universe import get_meta

EQ = get_meta("SPY")
BOND = get_meta("IEF")
GOLD = get_meta("GLD")


def test_clean_payer_passes(dividend_payer_bars):
    rep = Q.run_quality_checks(dividend_payer_bars, "SPY", EQ)
    assert rep.passed, rep.failures


def test_min_rows(bars_factory):
    ok, _ = Q.check_min_rows(bars_factory(np.ones(19)))
    assert not ok


def test_increasing_dates(bars_factory):
    df = bars_factory(np.linspace(1, 2, 30))
    df = df.iloc[[0, 2, 1] + list(range(3, 30))]
    assert not Q.check_increasing_dates(df)[0]


def test_positive_prices(bars_factory):
    df = bars_factory(np.linspace(1, 2, 30))
    df.iloc[5, df.columns.get_loc("low")] = 0.0
    assert not Q.check_positive_prices(df)[0]


def test_raw_jump_without_and_with_split_flag(bars_factory):
    c = np.r_[np.full(20, 100.0), np.full(20, 40.0)]  # -60 % overnight
    df = bars_factory(c)
    assert not Q.check_raw_jumps(df)[0]
    assert Q.check_raw_jumps(df, split_dates=[df.index[20]])[0]


def test_stale_run_equity_fails_bond_not_applied(bars_factory):
    c = np.r_[np.linspace(100, 101, 20), np.full(5, 101.5), np.linspace(102, 103, 20)]
    df = bars_factory(c)
    assert not Q.check_stale_runs(df, EQ)[0]
    assert Q.check_stale_runs(df, BOND)[0]
    c4 = np.r_[np.linspace(100, 101, 20), np.full(4, 101.5), np.linspace(102, 103, 20)]
    assert Q.check_stale_runs(bars_factory(c4), EQ)[0]


def test_bar_spacing_weekly_fails(bars_factory):
    idx = pd.date_range("2020-01-03", periods=40, freq="W-FRI")
    assert not Q.check_bar_spacing(bars_factory(np.linspace(1, 2, 40), dates=idx))[0]
    assert Q.check_bar_spacing(bars_factory(np.linspace(1, 2, 40)))[0]


def test_dividend_count_payer_with_missing_year(dividend_payer_bars):
    df = dividend_payer_bars.copy()
    yr = df.index.year == 2008
    df.loc[yr, "dividend"] = 0.0
    ok, detail = Q.check_dividend_counts(df, EQ)
    assert not ok and "2008" in detail
    assert Q.check_dividend_counts(df, GOLD)[0]  # non-payer: not applied


def test_tr_pr_gap_out_of_band(dividend_payer_bars):
    df = dividend_payer_bars.copy()
    # A payer whose adjusted close equals its as-traded close: gap 0 < 10 bp floor.
    df["close"] = df["close_raw"]
    assert not Q.check_tr_pr_gap(df, EQ)[0]
    # Absurd adjustment: adjusted series grows 30 %/yr faster than as-traded.
    df2 = dividend_payer_bars.copy()
    t = np.arange(len(df2)) / 252
    df2["close"] = df2["close_raw"] * 1.3**t
    assert not Q.check_tr_pr_gap(df2, EQ)[0]


def test_run_quality_raises_with_all_failures(bars_factory):
    c = np.r_[np.full(20, 100.0), np.full(20, 40.0)]
    with pytest.raises(Q.DataQualityError) as e:
        Q.run_quality_checks(bars_factory(c), "SPY", EQ)
    assert "raw_jumps" in str(e.value) and "stale_runs" in str(e.value)


def test_longest_identical_run():
    assert Q.longest_identical_run(pd.Series([1, 1, 2, 2, 2, 3])) == 3
    assert Q.longest_identical_run(pd.Series([1, 2, 3])) == 1


def test_adjustment_consistency_accepts_a_clean_payer_and_rejects_a_bad_open(dividend_payer_bars):
    ok, _ = Q.check_adjustment_consistency(dividend_payer_bars)
    assert ok
    bad = dividend_payer_bars.copy()
    d = bad.index[700]
    bad.loc[d, "open"] *= 1.8  # only the adjusted open is corrupted
    ok, detail = Q.check_adjusted_jumps(bad)
    assert not ok and str(d.date()) in detail


def test_known_closure_is_not_a_gap(bars_factory):
    idx = pd.bdate_range("2001-08-01", "2001-10-31")
    idx = idx[(idx < pd.Timestamp("2001-09-11")) | (idx > pd.Timestamp("2001-09-14"))]  # 9/11 closure
    ok, _ = Q.check_max_gap(bars_factory(np.linspace(100, 101, len(idx)), dates=idx))
    assert ok
    idx2 = pd.bdate_range("2002-08-01", "2002-10-31")
    idx2 = idx2[(idx2 < pd.Timestamp("2002-09-10")) | (idx2 > pd.Timestamp("2002-09-13"))]  # same hole, no closure
    ok, _ = Q.check_max_gap(bars_factory(np.linspace(100, 101, len(idx2)), dates=idx2))
    assert not ok
