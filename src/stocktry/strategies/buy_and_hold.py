"""Benchmarks: 100 % SPY (the null hypothesis) and an annually rebalanced 60/40."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import StrategySpec, upto


def _available(closes: pd.DataFrame, sym: str) -> bool:
    return sym in closes.columns and np.isfinite(closes[sym].iloc[-1])


def make_buy_and_hold(symbol: str = "SPY", name: str | None = None) -> StrategySpec:
    """100 % in ``symbol`` whenever it has a price; the engine only trades drift of cents (skipped)."""

    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        return {symbol: 1.0} if _available(closes, symbol) else {}

    return StrategySpec(
        name=name or f"{symbol.lower()}_buy_hold",
        universe=[symbol],
        cash_symbol=None,
        compute_targets=compute_targets,
        params={"symbol": symbol},
        family="buy_hold",
        description=f"Buy and hold 100% {symbol} (benchmark / null hypothesis)",
        allows_exit_to_cash=False,  # a target of cash is always a bug for the benchmark
    )


def make_sixty_forty(equity: str = "SPY", bond: str = "AGG", equity_weight: float = 0.6,
                     name: str = "sixty_forty") -> StrategySpec:
    """60/40 reference, rebalanced once a year (signal at the December month-end, trades early January).

    Between rebalances the weights drift with the market. In the proxy sample
    AGG is spliced with VBMFX before 2003-09.
    """

    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        out: dict[str, float] = {}
        if _available(closes, equity):
            out[equity] = equity_weight
        if _available(closes, bond):
            out[bond] = 1.0 - equity_weight
        return out

    return StrategySpec(
        name=name,
        universe=[equity, bond],
        cash_symbol=None,
        compute_targets=compute_targets,
        params={"equity": equity, "bond": bond, "equity_weight": equity_weight},
        family="sixty_forty",
        rebalance_months=(12,),
        description=f"{equity_weight:.0%} {equity} / {1-equity_weight:.0%} {bond}, rebalanced annually",
        allows_exit_to_cash=False,
    )
