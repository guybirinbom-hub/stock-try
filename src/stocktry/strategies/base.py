"""Strategy contract and shared signal helpers.

Contract (shared with the execution builder):

``StrategySpec.compute_targets(closes, asof) -> dict[str, float]``

* ``closes``: wide DataFrame of **adjusted** closes, columns = symbols, rows =
  trading dates up to and including ``asof``. The backtest engine adds a
  ``"^TBILL"`` column (T-bill total-return index); strategies that need it
  load it themselves when it is absent (live use).
* returns target weights for **risky** symbols only (non-negative, summing to
  <= 1.0); the remainder is cash (T-bills, or ``cash_symbol`` if set).
* must use only rows at or before ``asof``.

Extra fields beyond the contract (``params``, ``family``, ``signal_offset``,
``rebalance_months``, ``description``, ``allows_exit_to_cash``,
``uses_tbill``) have defaults so the contract fields stay positional-compatible.

``allows_exit_to_cash`` is the strategy's own declaration that its rule may move
most or all of the portfolio to cash by design (trend filters, GTAA). The paper
runner reads it: an undeclared strategy that suddenly targets cash is treated as
a bug and blocked. It defaults to False (the safe value). ``uses_tbill`` marks
rules that read the ``"^TBILL"`` column (absolute momentum), so the paper
runner loads the T-bill series only for them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np
import pandas as pd

from ..backtest.schedule import month_anchor_positions
from ..data.rates import TBILL_COLUMN

TargetFn = Callable[[pd.DataFrame, pd.Timestamp], dict[str, float]]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    universe: list[str]
    cash_symbol: str | None
    compute_targets: TargetFn
    params: dict[str, Any] = field(default_factory=dict)
    family: str = ""
    signal_offset: int = -1  # -1 = last trading day of month; k = k-th trading day (tranches)
    rebalance_months: tuple[int, ...] | None = None  # None = every month; (12,) = annually after Dec
    description: str = ""
    allows_exit_to_cash: bool = False  # the rule may target (mostly) cash by design; see module docstring
    uses_tbill: bool = False  # the rule reads the "^TBILL" column


def monthly_values(series: pd.Series, offset: int = -1) -> np.ndarray:
    """Values of ``series`` at its monthly anchors (NaN kept), oldest first."""
    pos = month_anchor_positions(series.index, offset)
    return series.to_numpy(dtype=float)[pos]


def sma_signal(monthly: np.ndarray, lookback: int) -> bool | None:
    """Faber rule: True if the last monthly close > mean of the last ``lookback`` monthly closes
    (the mean includes the current close). ``None`` if fewer than ``lookback`` valid values."""
    tail = monthly[-lookback:]
    if len(tail) < lookback or not np.all(np.isfinite(tail)):
        return None
    return bool(tail[-1] > tail.mean())


def absmom_signal(monthly: np.ndarray, tbill_monthly: np.ndarray, lookback: int) -> bool | None:
    """Antonacci absolute momentum: True if the trailing ``lookback``-month total return exceeds the
    T-bill total return over the same anchors. ``None`` if history is insufficient."""
    if len(monthly) < lookback + 1 or len(tbill_monthly) < lookback + 1:
        return None
    a0, a1 = monthly[-1 - lookback], monthly[-1]
    t0, t1 = tbill_monthly[-1 - lookback], tbill_monthly[-1]
    if not (np.isfinite(a0) and np.isfinite(a1) and np.isfinite(t0) and np.isfinite(t1)) or a0 <= 0 or t0 <= 0:
        return None
    return bool(a1 / a0 - 1.0 > t1 / t0 - 1.0)


def tbill_column(closes: pd.DataFrame, asof: pd.Timestamp) -> pd.Series:
    """The T-bill index aligned to ``closes`` (engine-provided, or built from the cache for live use)."""
    if TBILL_COLUMN in closes.columns:
        return closes[TBILL_COLUMN]
    from ..data.fetch import get_tbill_yield  # live path only; the engine always supplies the column
    from ..data.rates import tbill_index

    y = get_tbill_yield()
    y = y[y.index <= asof]
    return tbill_index(closes.index, y)


def upto(closes: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Defensive truncation: drop any rows after ``asof`` (the engine never passes any)."""
    if len(closes) and closes.index[-1] > asof:
        return closes.loc[:asof]
    return closes
