"""The pre-registered evaluation samples.

Each sample starts as cash at the close of the last trading day of
``first_signal`` (that day's month-end is also the first signal date) and
ends at the last month-end that is complete for every series. Monthly
returns therefore begin in the month after ``first_signal``.

* ``long``  -- proxy data (SPY spliced with VFINX before 1993-02; AGG with
  VBMFX before 2003-10). VFINX data before 1987 failed the Ken French
  cross-check and is excluded, so the first signal is 1988-07, when every
  lookback in the 3..18-month sweep grid is formed from 1987+ data.
  Single-asset strategies and the 60/40 only.
* ``proxy`` -- proxy data from 1996-05, the first month-end at which the
  REIT (VGSIX) and international (VGTSX) funds both have prices. Adds GTAA-4;
  its REIT and international sleeves hold cash until their SMA is formed.
* ``etf``   -- ETF prices only, from 2006-02 (DBC's first month-end). Adds
  GTAA-5; its commodity sleeve holds cash until DBC has enough history.
"""
from __future__ import annotations

from dataclasses import dataclass

SINGLE_ASSET = ("spy_buy_hold", "sixty_forty", "trend_sma10", "trend_absmom12", "trend_ensemble")


@dataclass(frozen=True)
class Sample:
    name: str
    label: str
    data_mode: str  # "proxy" | "etf"
    first_signal: str  # YYYY-MM
    strategies: tuple[str, ...]
    symbols: tuple[str, ...]
    history_start: str  # panel start (lookback history before the first signal)
    primary_for: tuple[str, ...] = ()  # candidates whose Gate A evaluation uses this sample


SAMPLES: dict[str, Sample] = {
    "long": Sample("long", "Long proxy sample (single asset)", "proxy", "1988-07", SINGLE_ASSET,
                   ("SPY", "AGG"), "1987-01-01"),
    "proxy": Sample("proxy", "Proxy sample", "proxy", "1996-05", SINGLE_ASSET + ("gtaa4",),
                    ("SPY", "AGG", "EFA", "IEF", "VNQ"), "1993-01-01",
                    primary_for=("trend_sma10", "trend_absmom12", "trend_ensemble", "gtaa4")),
    "etf": Sample("etf", "ETF-only sample", "etf", "2006-02", SINGLE_ASSET + ("gtaa4", "gtaa5"),
                  ("SPY", "AGG", "EFA", "IEF", "VNQ", "DBC"), "2001-01-01", primary_for=("gtaa5",)),
}
