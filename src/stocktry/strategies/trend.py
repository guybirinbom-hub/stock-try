"""Single-asset trend filters on SPY (VFINX before 1993 in the long proxy sample).

Rules (evaluated on monthly anchors; see :mod:`stocktry.backtest.schedule`):

* ``sma``    -- invested if the last close > mean of the last L monthly closes
  (mean includes the current close). Faber's published default L = 10.
* ``absmom`` -- invested if the trailing L-month total return > the trailing
  L-month T-bill total return. Antonacci's published default L = 12.
* ``ensemble`` -- average of the binary signals of both rules over
  lookbacks 6..12 (14 signals) -> fractional exposure in [0, 1].

Defaults are pre-registered exactly as published. Out of the market = cash
earning T-bills (``cash_symbol=None``). If history is insufficient for a
signal, that signal counts as "out".
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .base import StrategySpec, absmom_signal, monthly_values, sma_signal, tbill_column, upto


def make_trend_sma(symbol: str = "SPY", lookback: int = 10, offset: int = -1, name: str | None = None
                   ) -> StrategySpec:
    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        sig = sma_signal(monthly_values(closes[symbol], offset), lookback)
        return {symbol: 1.0} if sig else {}

    return StrategySpec(
        name=name or f"trend_sma{lookback}" + (f"_o{offset}" if offset >= 0 else ""),
        universe=[symbol], cash_symbol=None, compute_targets=compute_targets,
        params={"symbol": symbol, "rule": "sma", "lookback": lookback, "offset": offset},
        family="trend_sma", signal_offset=offset,
        description=f"{symbol} above its {lookback}-month SMA, else T-bills",
        allows_exit_to_cash=True,
    )


def make_trend_absmom(symbol: str = "SPY", lookback: int = 12, offset: int = -1, name: str | None = None
                      ) -> StrategySpec:
    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        tb = monthly_values(tbill_column(closes, asof), offset)
        sig = absmom_signal(monthly_values(closes[symbol], offset), tb, lookback)
        return {symbol: 1.0} if sig else {}

    return StrategySpec(
        name=name or f"trend_absmom{lookback}" + (f"_o{offset}" if offset >= 0 else ""),
        universe=[symbol], cash_symbol=None, compute_targets=compute_targets,
        params={"symbol": symbol, "rule": "absmom", "lookback": lookback, "offset": offset},
        family="trend_absmom", signal_offset=offset,
        description=f"{symbol} {lookback}-month return above T-bills, else T-bills",
        allows_exit_to_cash=True, uses_tbill=True,
    )


def make_trend_ensemble(symbol: str = "SPY", lookbacks: Iterable[int] = range(6, 13),
                        rules: tuple[str, ...] = ("sma", "absmom"), offset: int = -1,
                        name: str = "trend_ensemble") -> StrategySpec:
    lbs = tuple(int(x) for x in lookbacks)

    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        m = monthly_values(closes[symbol], offset)
        tb = monthly_values(tbill_column(closes, asof), offset) if "absmom" in rules else None
        votes = []
        for L in lbs:
            if "sma" in rules:
                votes.append(bool(sma_signal(m, L)))
            if "absmom" in rules:
                votes.append(bool(absmom_signal(m, tb, L)))
        w = sum(votes) / len(votes) if votes else 0.0
        return {symbol: w} if w > 0 else {}

    return StrategySpec(
        name=name, universe=[symbol], cash_symbol=None, compute_targets=compute_targets,
        params={"symbol": symbol, "rules": list(rules), "lookbacks": list(lbs), "offset": offset},
        family="trend_ensemble", signal_offset=offset,
        description=f"{symbol} exposure = share of {len(lbs)*len(rules)} SMA/abs-momentum signals (6-12m) that are on",
        allows_exit_to_cash=True, uses_tbill="absmom" in rules,
    )
