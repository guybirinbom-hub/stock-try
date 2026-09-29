"""Cash-return conventions built from FRED DTB3.

Convention (stated once, used everywhere -- engine cash, Sharpe excess returns
and the absolute-momentum hurdle):

* ``DTB3`` is the 3-month T-bill rate in **percent per year** (discount basis).
* Cash earns a **daily accrual**: on trading day *t* the cash balance grows by
  ``DTB3(t-1) / 100 / 252``, where ``DTB3(t-1)`` is the most recent FRED
  observation on or before the previous trading day (so the rate is known
  before the day starts; FRED holidays are forward-filled). Days before the
  first observation earn 0 (never back-filled from a later observation).
* The T-bill total-return index is the cumulative product of ``1 + rate``.
  Monthly T-bill returns are ratios of this index at month-end trading days.

The discount basis slightly understates the investment yield and daily
compounding over 252 days slightly overstates it; the two partly offset. The
Ken French RF cross-check measures the net difference.
"""
from __future__ import annotations

import pandas as pd

TBILL_COLUMN = "^TBILL"
TRADING_DAYS_PER_YEAR = 252


def tbill_daily_rate(calendar: pd.DatetimeIndex, dtb3_pct: pd.Series) -> pd.Series:
    """Per-trading-day cash return (decimal) applied on each calendar date."""
    y = dtb3_pct.dropna().sort_index()
    if y.empty:
        return pd.Series(0.0, index=calendar)
    both = y.reindex(y.index.union(calendar)).ffill()
    on_cal = both.reindex(calendar)
    prev = on_cal.shift(1)
    if len(calendar):
        before = y[y.index < calendar[0]]
        prev.iloc[0] = before.iloc[-1] if len(before) else float("nan")
    # Never back-fill: a day before the first DTB3 observation has no known rate and earns 0.
    # (Back-filling would apply a yield published later -- look-ahead. Latent: DTB3 starts in 1954.)
    prev = prev.fillna(0.0)
    return prev / 100.0 / TRADING_DAYS_PER_YEAR


def tbill_index(calendar: pd.DatetimeIndex, dtb3_pct: pd.Series) -> pd.Series:
    """Cumulative T-bill growth of $1 on ``calendar`` (1.0 on the first date)."""
    rate = tbill_daily_rate(calendar, dtb3_pct)
    idx = (1.0 + rate).cumprod()
    idx = idx / idx.iloc[0]
    idx.name = TBILL_COLUMN
    return idx


def monthly_from_index(index_series: pd.Series, month_ends: pd.DatetimeIndex) -> pd.Series:
    """Monthly returns of an index sampled at the given month-end dates."""
    s = index_series.reindex(month_ends)
    return s.pct_change().iloc[1:]
