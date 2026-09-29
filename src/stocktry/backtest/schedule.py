"""Monthly signal anchors, shared by the engine (scheduling) and strategies (sampling).

``offset = -1`` (the default) anchors each month on its **last trading day**.
``offset = k >= 0`` anchors each month on its k-th trading day counted from
the month's first trading day (0-based), clamped to the month's last trading
day when the month is shorter. Offsets 0..20 are the "tranches" used to
measure rebalance-day luck.

Both rules are *causal*: on data truncated at an anchor date ``asof`` the
rule applied to the truncated index returns exactly the anchors of the full
index that are <= ``asof`` (past months are complete; in the current month
``asof`` is the last row, so it is its own anchor). Strategies therefore
compute their monthly samples from the truncated frame they are given and
cannot see later data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def month_keys(index: pd.DatetimeIndex) -> np.ndarray:
    """Integer month number of each date (fast numpy path)."""
    return np.asarray(index.values, dtype="datetime64[ns]").astype("datetime64[M]").astype(np.int64)


def month_anchor_positions(index: pd.DatetimeIndex, offset: int = -1) -> np.ndarray:
    """Integer positions in ``index`` of each month's anchor (see module docstring)."""
    n = len(index)
    if n == 0:
        return np.array([], dtype=int)
    key = month_keys(index)
    change = np.flatnonzero(np.diff(key) != 0) + 1
    starts = np.r_[0, change]
    ends = np.r_[change - 1, n - 1]
    if offset < 0:
        return ends
    return np.minimum(starts + offset, ends)


def monthly_sample(frame: pd.DataFrame | pd.Series, offset: int = -1) -> pd.DataFrame | pd.Series:
    """Rows of ``frame`` at the monthly anchors of its own index."""
    pos = month_anchor_positions(frame.index, offset)
    return frame.iloc[pos]


def is_complete_month_end(index: pd.DatetimeIndex) -> np.ndarray:
    """Boolean mask: True where the next row is in a different month (last row: False)."""
    n = len(index)
    if n == 0:
        return np.array([], dtype=bool)
    key = month_keys(index)
    return np.r_[np.diff(key) != 0, False]


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of every *complete* month in ``index``."""
    return index[is_complete_month_end(index)]


def resolve_month_end(index: pd.DatetimeIndex, when: str | pd.Timestamp) -> pd.Timestamp:
    """Last trading day in ``index`` of the month containing ``when`` (e.g. '1996-05')."""
    p = pd.Timestamp(when).to_period("M")
    sel = index[(index.year == p.year) & (index.month == p.month)]
    if len(sel) == 0:
        raise ValueError(f"no trading days in {p} within the calendar")
    return sel[-1]
