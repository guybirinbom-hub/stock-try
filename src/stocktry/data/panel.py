"""Aligned wide price panels for the backtest engine.

A :class:`PricePanel` holds, on one trading calendar (union of the member
series' dates), the adjusted closes and opens, the factor that converts
adjusted dollars to as-traded dollars (``close_raw / close``; 1.0 where
unknown, e.g. in spliced proxy segments), per-column cost metadata and the
T-bill cash index.

Data modes:

* ``"etf"``   -- each column is the ETF's own vendor series, nothing else.
  (Rows before ``SymbolMeta.valid_from`` are dropped in every mode.)
* ``"proxy"`` -- columns with an accepted splice rule are extended backwards
  with their mutual-fund proxy (see :mod:`stocktry.data.universe`); columns in
  :data:`~stocktry.data.universe.PROXY_SUBSTITUTES` (EFA) are *replaced* by the
  proxy fund's own series for the whole period (VGTSX), never spliced.

Closes are forward-filled between each column's first and last real bar
(never before the first, never after the last); a missing open is replaced by
that day's forward-filled close. A column that ends early therefore ends the
panel early: :meth:`PricePanel.last_complete_month_end` uses each column's
last *real* bar, so a series is never carried flat past its data.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from .quality import (
    check_adjusted_jumps,
    check_bar_spacing,
    check_increasing_dates,
    check_max_gap,
    check_positive_prices,
    check_raw_jumps,
    run_quality_checks,
    DataQualityError,
)
from .rates import TBILL_COLUMN, tbill_daily_rate, tbill_index
from .universe import PROXY_SUBSTITUTES, SPLICES, SymbolMeta, get_meta, splice_bars

BarsLoader = Callable[[str], tuple[pd.DataFrame, dict]]

log = logging.getLogger(__name__)

#: Columns whose last real bars differ by more than this many business days are logged loudly
#: (the panel still ends at the earliest last bar, so nothing is carried flat).
LAST_BAR_SPREAD_WARN_BDAYS = 5


def ffill_within(s: pd.Series) -> pd.Series:
    """Forward-fill ``s`` only between its first and last valid values (NaN outside)."""
    first, last = s.first_valid_index(), s.last_valid_index()
    if first is None:
        return s.copy()
    out = s.ffill()
    out[(out.index < first) | (out.index > last)] = np.nan
    return out


def align_closes(frame: pd.DataFrame) -> pd.DataFrame:
    """Wide close frame with each column forward-filled between its first and last real bar.

    The single alignment rule shared by the backtest panel and the paper runner
    (a missing vendor row inside a series is carried forward; nothing is filled
    before a series starts or after it ends).
    """
    return frame.sort_index().apply(ffill_within)


@dataclass
class PricePanel:
    closes: pd.DataFrame
    opens: pd.DataFrame
    raw_factor: pd.DataFrame
    meta: dict[str, SymbolMeta]
    tbill_rate: pd.Series
    tbill_index: pd.Series
    sources: dict[str, str] = field(default_factory=dict)
    splices: dict[str, dict] = field(default_factory=dict)
    mode: str = "etf"

    @property
    def calendar(self) -> pd.DatetimeIndex:
        return self.closes.index

    @property
    def symbols(self) -> list[str]:
        return list(self.closes.columns)

    def first_valid(self, symbol: str) -> pd.Timestamp | None:
        return self.closes[symbol].first_valid_index()

    def last_bar(self, symbol: str) -> pd.Timestamp | None:
        """Date of ``symbol``'s last real bar (closes are never filled past it)."""
        return self.closes[symbol].last_valid_index()

    def last_complete_month_end(self) -> pd.Timestamp:
        """Last trading day of the last month that is complete in *every* column.

        Uses each column's last real bar, so a series that stops early ends the panel
        there instead of being carried flat to the end of the calendar.
        """
        last_common = min(self.closes[c].last_valid_index() for c in self.closes.columns)
        cal = self.calendar[self.calendar <= last_common]
        per = cal.to_period("M")
        is_me = np.r_[per[1:] != per[:-1], False]
        me = cal[is_me]
        return me[-1]

    def strategy_frame(self, symbols: list[str]) -> pd.DataFrame:
        """Closes for ``symbols`` plus the T-bill index column, as passed to strategies."""
        df = self.closes[symbols].copy()
        df[TBILL_COLUMN] = self.tbill_index
        return df


def _align(frames: dict[str, pd.DataFrame], calendar: pd.DatetimeIndex) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    closes, opens, factors = {}, {}, {}
    for sym, df in frames.items():
        c = df["close"].reindex(calendar)
        first, last = df.index[0], df.index[-1]
        outside = (calendar < first) | (calendar > last)
        c_ff = c.ffill()
        c_ff[outside] = np.nan  # never before the first bar, never past the last one
        o = df["open"].reindex(calendar)
        o = o.where(o.notna(), c_ff)
        o[outside] = np.nan
        raw = df["close_raw"] if "close_raw" in df.columns else pd.Series(np.nan, index=df.index)
        f = (raw / df["close"]).reindex(calendar).ffill()
        f = f.where(np.isfinite(f) & (f > 0), 1.0)
        closes[sym], opens[sym], factors[sym] = c_ff, o, f
    return pd.DataFrame(closes), pd.DataFrame(opens), pd.DataFrame(factors)


def panel_from_bars(
    frames: dict[str, pd.DataFrame],
    dtb3_pct: pd.Series | None = None,
    meta: dict[str, SymbolMeta] | None = None,
    sources: dict[str, str] | None = None,
    splices: dict[str, dict] | None = None,
    mode: str = "etf",
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
) -> PricePanel:
    """Build a panel from already-loaded bar frames (used by tests and :func:`build_panel`).

    ``dtb3_pct`` is the DTB3 yield in percent; ``None`` means cash earns 0.
    """
    cal = pd.DatetimeIndex(sorted(set().union(*[set(df.index) for df in frames.values()])))
    if start is not None:
        cal = cal[cal >= pd.Timestamp(start)]
    if end is not None:
        cal = cal[cal <= pd.Timestamp(end)]
    closes, opens, factors = _align(frames, cal)
    y = dtb3_pct if dtb3_pct is not None else pd.Series(0.0, index=cal)
    return PricePanel(
        closes=closes,
        opens=opens,
        raw_factor=factors,
        meta={s: (meta or {}).get(s, get_meta(s)) for s in frames},
        tbill_rate=tbill_daily_rate(cal, y),
        tbill_index=tbill_index(cal, y),
        sources=sources or {s: "provided" for s in frames},
        splices=splices or {},
        mode=mode,
    )


def _structural_checks(df: pd.DataFrame, name: str) -> None:
    for fn in (check_increasing_dates, check_positive_prices, check_bar_spacing, check_max_gap,
               check_adjusted_jumps):
        ok, detail = fn(df)
        if not ok:
            raise DataQualityError(f"{name}: {fn.__name__}: {detail}")
    # Spliced series mix proxy (adjusted only) and ETF (as-traded) segments: check adjusted closes.
    ok, detail = check_raw_jumps(df.drop(columns=["close_raw"], errors="ignore"))
    if not ok:
        raise DataQualityError(f"{name}: raw_jumps: {detail}")


def load_series(symbol: str, mode: str, loader: BarsLoader, run_quality: bool = True
                ) -> tuple[pd.DataFrame, str, dict | None, SymbolMeta]:
    """Load one panel column according to ``mode``; returns (bars, source description, splice info, cost meta)."""

    def _load(sym: str) -> pd.DataFrame:
        df, manifest = loader(sym)
        if manifest.get("stale"):
            # get_bars_with_manifest fell back to an old cache after a failed refresh: refuse,
            # rather than silently backtest (or trade) on data that stopped at an unknown date.
            raise DataQualityError(
                f"{sym}: refresh failed and only a STALE cache (last dated {manifest.get('last_date')}) is "
                "available; rerun when the source is reachable, or without --refresh to use the cache as is")
        vf = get_meta(sym).valid_from
        if vf is not None:
            df = df.loc[df.index >= pd.Timestamp(vf)]
        if run_quality:
            splits = [pd.Timestamp(d) for d in manifest.get("splits", [])]
            run_quality_checks(df, sym, get_meta(sym), split_dates=splits)
        return df

    sym = symbol.upper()
    if mode == "etf":
        df = _load(sym)
        return df, f"{sym} vendor series", None, get_meta(sym)
    if mode != "proxy":
        raise ValueError(f"unknown mode {mode!r}")
    if sym in PROXY_SUBSTITUTES:
        sub = PROXY_SUBSTITUTES[sym]
        df = _load(sub)
        return df, f"{sub} substituted for {sym} (whole period; no splice)", None, get_meta(sub)
    rule = SPLICES.get(sym)
    if rule is None or not rule.enabled or rule.proxy is None:
        df = _load(sym)
        return df, f"{sym} vendor series (no splice)", None, get_meta(sym)
    target = _load(sym)
    proxy = _load(rule.proxy)
    spliced, info = splice_bars(target, proxy, rule)
    if run_quality:
        _structural_checks(spliced, f"{sym}<-{rule.proxy}")
    desc = f"{sym} spliced with {rule.proxy} returns through {info.boundary}"
    return spliced, desc, info.to_dict(), get_meta(sym)


def build_panel(
    symbols: list[str],
    mode: str = "etf",
    *,
    loader: BarsLoader | None = None,
    dtb3_pct: pd.Series | None = None,
    start: pd.Timestamp | str | None = None,
    end: pd.Timestamp | str | None = None,
    run_quality: bool = True,
) -> PricePanel:
    """Load, quality-gate, splice/substitute and align ``symbols`` for ``mode``.

    By default bars come from the cache/network via
    :func:`stocktry.data.fetch.get_bars_with_manifest` and cash yields from
    :func:`stocktry.data.fetch.get_tbill_yield`. Raises
    :class:`~stocktry.data.quality.DataQualityError` on any failed check.
    """
    if loader is None or dtb3_pct is None:
        from . import fetch

        loader = loader or (lambda s: fetch.get_bars_with_manifest(s))
        dtb3_pct = dtb3_pct if dtb3_pct is not None else fetch.get_tbill_yield()
    frames, sources, splices, meta = {}, {}, {}, {}
    for s in dict.fromkeys(x.upper() for x in symbols):
        df, desc, sp, m = load_series(s, mode, loader, run_quality)
        frames[s], sources[s], meta[s] = df, desc, m
        if sp:
            splices[s] = sp
    lasts = {s: df.index[-1] for s, df in frames.items()}
    if len(lasts) > 1:
        lo, hi = min(lasts.values()), max(lasts.values())
        spread = int(np.busday_count(lo.date(), hi.date()))
        if spread > LAST_BAR_SPREAD_WARN_BDAYS:
            log.warning("series end on different dates (%s); the panel ends at the earliest, %s",
                        ", ".join(f"{k} {v.date()}" for k, v in sorted(lasts.items())), lo.date())
    return panel_from_bars(frames, dtb3_pct, meta, sources, splices, mode, start, end)
