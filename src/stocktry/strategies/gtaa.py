"""Faber-style equal-weight multi-asset trend allocation (GTAA).

Each sleeve gets 1/n of the portfolio when its monthly close is above its
L-month SMA (default L = 10, as published) and that 1/n sits in T-bill cash
otherwise. A sleeve whose series is too short for the SMA is held in cash
until it has L monthly closes ("cash until formed"), which is exactly what an
investor starting on that date could do.

* ``gtaa5``: SPY, EFA, IEF, VNQ, DBC  (ETF-only sample; DBC starts 2006-02).
* ``gtaa4``: SPY, EFA, IEF, VNQ       (no commodities, so the proxy sample can
  start in 1996-05 with VGTSX for EFA, VFITX for IEF, VGSIX for VNQ).

``offset`` selects the signal day within the month (tranching, see
:mod:`stocktry.backtest.schedule`).
"""
from __future__ import annotations

import pandas as pd

from ..backtest.schedule import month_anchor_positions
from .base import StrategySpec, sma_signal, upto

GTAA5_SLEEVES: list[str] = ["SPY", "EFA", "IEF", "VNQ", "DBC"]
GTAA4_SLEEVES: list[str] = ["SPY", "EFA", "IEF", "VNQ"]


def make_gtaa(sleeves: list[str] | None = None, lookback: int = 10, offset: int = -1,
              name: str | None = None) -> StrategySpec:
    sl = list(sleeves or GTAA5_SLEEVES)
    w = 1.0 / len(sl)
    base = "gtaa5" if len(sl) == 5 else f"gtaa{len(sl)}"

    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        closes = upto(closes, asof)
        pos = month_anchor_positions(closes.index, offset)
        out: dict[str, float] = {}
        for s in sl:
            if s in closes.columns and sma_signal(closes[s].to_numpy(dtype=float)[pos], lookback):
                out[s] = w
        return out

    default = lookback == 10 and offset == -1
    return StrategySpec(
        name=name or (base if default else f"{base}_L{lookback}" + (f"_o{offset}" if offset >= 0 else "")),
        universe=sl, cash_symbol=None, compute_targets=compute_targets,
        params={"sleeves": sl, "lookback": lookback, "offset": offset},
        family=base, signal_offset=offset,
        description=f"Equal-weight {len(sl)} sleeves ({', '.join(sl)}), each only above its {lookback}-month SMA",
        allows_exit_to_cash=True,
    )
