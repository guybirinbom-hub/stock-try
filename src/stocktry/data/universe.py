"""Symbol metadata, splice table and return-based splicing of ETF histories.

Units used in this module:
* ``expense_ratio`` is a decimal fraction per year (0.000945 = 0.0945 %/yr).
* ``half_spread_bp`` is basis points of traded notional charged per side
  (1 bp = 0.01 %).

Splicing rules (see docs/methodology.md):
* A splice joins a mutual-fund proxy's history onto an ETF *on returns* at a
  month boundary. Daily proxy returns up to and including the ETF's first
  month-end are used; ETF returns afterwards. Each proxy daily return is
  adjusted by ``(ER_proxy - ER_target) / 252`` so that a month of ~21 trading
  days carries ``(ER_proxy - ER_target) / 12`` -- the monthly adjustment in the
  specification, spread evenly across trading days.
* A splice is accepted only if the two series overlap for at least 36 full
  months with a monthly-return correlation of at least 0.995 (equity / REIT)
  or 0.95 (bonds). The correlation is measured over the whole overlap.
* International (VGTSX vs EFA) and commodities (DBC) are never spliced.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BAR_COLUMNS: list[str] = ["open", "high", "low", "close", "volume", "close_raw", "dividend"]


@dataclass(frozen=True)
class SymbolMeta:
    """Static facts about one tradable (or proxy) instrument.

    Expense ratios are the most recent published figures known when this file
    was written (approximate; historical expense ratios were usually higher).
    They are used only for splice adjustments and for index-level series; real
    fund price series are already net of fees and are never charged again.
    """

    symbol: str
    name: str
    asset_class: str  # us_equity, intl_equity, us_treasury, us_bond, reit, commodity, gold, cash
    inception: str  # first daily bar in the Yahoo history (ISO date)
    expense_ratio: float  # decimal per year
    half_spread_bp: float  # bp of notional per side
    fractionable: bool  # fractional quantities allowed (ETFs: at Alpaca; proxies: fund dealing)
    is_proxy: bool = False  # Vanguard mutual fund used only as a pre-inception proxy
    pays_dividends: bool = True  # expected to pay >= 1 distribution every full calendar year
    is_index_level: bool = False  # an index (not a fund): expense ratio must be subtracted
    notes: str = ""
    valid_from: str | None = None  # vendor data before this date failed an external cross-check; dropped

    @property
    def is_equity_like(self) -> bool:
        return self.asset_class in {"us_equity", "intl_equity", "reit"}


_M = SymbolMeta
UNIVERSE: dict[str, SymbolMeta] = {
    m.symbol: m
    for m in [
        _M("SPY", "SPDR S&P 500 ETF", "us_equity", "1993-01-29", 0.000945, 0.5, True),
        _M("VTI", "Vanguard Total Stock Market ETF", "us_equity", "2001-06-15", 0.0003, 1.0, True),
        _M("IEF", "iShares 7-10 Year Treasury Bond ETF", "us_treasury", "2002-07-30", 0.0015, 1.0, True),
        _M("AGG", "iShares Core US Aggregate Bond ETF", "us_bond", "2003-09-29", 0.0003, 1.5, True),
        _M("BND", "Vanguard Total Bond Market ETF", "us_bond", "2007-04-10", 0.0003, 1.5, True),
        _M("VNQ", "Vanguard Real Estate ETF", "reit", "2004-09-29", 0.0013, 1.5, True),
        _M("GLD", "SPDR Gold Shares", "gold", "2004-11-18", 0.0040, 1.5, True, pays_dividends=False),
        _M("EFA", "iShares MSCI EAFE ETF", "intl_equity", "2001-08-27", 0.0035, 1.5, True,
           notes="expense ratio approximate"),
        _M("DBC", "Invesco DB Commodity Index Tracking Fund", "commodity", "2006-02-06", 0.0085, 3.0, True,
           pays_dividends=False, notes="distributions irregular; fractionability at Alpaca unverified"),
        _M("BIL", "SPDR Bloomberg 1-3 Month T-Bill ETF", "cash", "2007-05-30", 0.001354, 0.5, True,
           pays_dividends=False, notes="paid no distributions in several zero-rate years"),
        _M("SHV", "iShares Short Treasury Bond ETF", "cash", "2007-01-11", 0.0015, 0.5, True,
           pays_dividends=False, notes="paid no distributions in some zero-rate years"),
        # Vanguard mutual-fund proxies: 0 bp spread (NAV dealing), bought in fractional dollar amounts;
        # is_proxy=True marks them as history-only (not tradable at Alpaca).
        _M("VFINX", "Vanguard 500 Index Fund Investor", "us_equity", "1980-01-02", 0.0014, 0.0, True, is_proxy=True,
           valid_from="1987-01-01",
           notes="Yahoo total return understates the published S&P 500 TR by 2.3-9.4 pp/yr in 1981-1986 "
                 "(Ken French cross-check); data before 1987 is not used"),
        _M("VTSMX", "Vanguard Total Stock Market Index Investor", "us_equity", "1992-04-27", 0.0014, 0.0, True,
           is_proxy=True),
        _M("VFITX", "Vanguard Intermediate-Term Treasury Investor", "us_treasury", "1991-10-28", 0.0020, 0.0, True,
           is_proxy=True),
        _M("VBMFX", "Vanguard Total Bond Market Index Investor", "us_bond", "1986-12-11", 0.0015, 0.0, True,
           is_proxy=True),
        _M("VGSIX", "Vanguard Real Estate Index Investor", "reit", "1996-05-13", 0.0026, 0.0, True, is_proxy=True),
        _M("VGTSX", "Vanguard Total International Stock Index Investor", "intl_equity", "1996-04-29", 0.0017, 0.0,
           True, is_proxy=True, notes="includes emerging markets and Canada; EAFE does not"),
    ]
}


def get_meta(symbol: str) -> SymbolMeta:
    """Metadata for ``symbol``; unknown symbols get a conservative default (5 bp, equity)."""
    s = symbol.upper()
    if s in UNIVERSE:
        return UNIVERSE[s]
    return SymbolMeta(s, s, "us_equity", "1900-01-01", 0.0, 5.0, True, notes="not in universe table")


@dataclass(frozen=True)
class SpliceRule:
    """How (and whether) an ETF's pre-inception history may be extended with a proxy."""

    target: str
    proxy: str | None
    enabled: bool
    min_corr: float
    min_overlap_months: int = 36
    reason: str = ""


EQUITY_MIN_CORR = 0.995
BOND_MIN_CORR = 0.95

SPLICES: dict[str, SpliceRule] = {
    r.target: r
    for r in [
        SpliceRule("SPY", "VFINX", True, EQUITY_MIN_CORR, reason="S&P 500 index fund"),
        SpliceRule("VTI", "VTSMX", True, EQUITY_MIN_CORR, reason="same index, investor share class"),
        SpliceRule("IEF", "VFITX", True, BOND_MIN_CORR, reason="intermediate Treasuries (5-10y vs 7-10y)"),
        SpliceRule("AGG", "VBMFX", True, BOND_MIN_CORR, reason="US aggregate bond index fund"),
        SpliceRule("BND", "VBMFX", True, BOND_MIN_CORR, reason="same index, investor share class"),
        SpliceRule("VNQ", "VGSIX", True, EQUITY_MIN_CORR, reason="same REIT index, investor share class"),
        SpliceRule("EFA", "VGTSX", False, EQUITY_MIN_CORR,
                   reason="NOT spliced: total-international vs developed-ex-US failed validation "
                          "(research correlation 0.984 < 0.995)"),
        SpliceRule("DBC", None, False, EQUITY_MIN_CORR, reason="NOT spliced: no valid commodity proxy"),
        SpliceRule("GLD", None, False, EQUITY_MIN_CORR, reason="no proxy; series starts at fund inception"),
    ]
}

# In the 'proxy' sample the international sleeve is represented by VGTSX's own
# history (a real, investable fund) for the whole period -- a substitution, not a splice.
PROXY_SUBSTITUTES: dict[str, str] = {"EFA": "VGTSX"}


class SpliceRejected(ValueError):
    """Raised when a proxy fails the overlap/correlation rule."""


@dataclass
class SpliceInfo:
    """What was done to build a spliced series; recorded in the manifest."""

    target: str
    proxy: str
    accepted: bool
    boundary: str | None  # last date whose return comes from the proxy (ISO)
    overlap_months: int
    correlation: float
    min_corr: float
    er_adjust_bp_per_year: float
    first_date: str | None = None
    reason: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "proxy": self.proxy,
            "accepted": self.accepted,
            "splice_boundary": self.boundary,
            "overlap_months": self.overlap_months,
            "correlation": round(float(self.correlation), 6) if np.isfinite(self.correlation) else None,
            "min_corr": self.min_corr,
            "er_adjust_bp_per_year": round(self.er_adjust_bp_per_year, 3),
            "first_date": self.first_date,
            "reason": self.reason,
        }


def month_end_closes(close: pd.Series) -> pd.Series:
    """Close on the last available trading day of each calendar month (index = that date)."""
    s = close.dropna()
    if s.empty:
        return s
    key = s.index.year * 12 + s.index.month
    last = ~pd.Series(key, index=s.index).duplicated(keep="last").to_numpy()
    return s[last]


def monthly_returns_by_period(close: pd.Series) -> pd.Series:
    """Month-over-month returns of month-end closes, indexed by monthly Period.

    The first (possibly partial) month is dropped: a month's return needs the
    previous month-end close.
    """
    me = month_end_closes(close)
    r = me.pct_change().iloc[1:]
    r.index = r.index.to_period("M")
    return r


def validate_splice(target_close: pd.Series, proxy_close: pd.Series, rule: SpliceRule) -> tuple[int, float]:
    """Return (overlap_months, correlation) of monthly returns over the full overlap."""
    a = monthly_returns_by_period(target_close)
    b = monthly_returns_by_period(proxy_close)
    j = pd.concat([a, b], axis=1, join="inner").dropna()
    n = len(j)
    corr = float(j.iloc[:, 0].corr(j.iloc[:, 1])) if n >= 3 else float("nan")
    return n, corr


def splice_bars(
    target: pd.DataFrame,
    proxy: pd.DataFrame,
    rule: SpliceRule,
    target_meta: SymbolMeta | None = None,
    proxy_meta: SymbolMeta | None = None,
) -> tuple[pd.DataFrame, SpliceInfo]:
    """Extend ``target`` bars backwards with ``proxy`` returns (see module docstring).

    Returns the spliced bars (same columns as :data:`BAR_COLUMNS`; in the proxy
    segment ``close_raw`` is NaN, ``dividend`` is 0 and open/high/low keep the
    proxy's intraday ratios to its close) and a :class:`SpliceInfo`.
    Raises :class:`SpliceRejected` if the validation rule fails or the rule is disabled.
    """
    if rule.proxy is None or not rule.enabled:
        raise SpliceRejected(f"{rule.target}: splicing disabled ({rule.reason})")
    tm = target_meta or get_meta(rule.target)
    pm = proxy_meta or get_meta(rule.proxy)
    er_adj_year = pm.expense_ratio - tm.expense_ratio
    n, corr = validate_splice(target["close"], proxy["close"], rule)
    info = SpliceInfo(rule.target, rule.proxy, False, None, n, corr, rule.min_corr, er_adj_year * 1e4)
    if n < rule.min_overlap_months:
        info.reason = f"overlap {n} < {rule.min_overlap_months} months"
        raise SpliceRejected(f"{rule.target}<-{rule.proxy}: {info.reason}")
    if not (np.isfinite(corr) and corr >= rule.min_corr):
        info.reason = f"correlation {corr:.4f} < {rule.min_corr}"
        raise SpliceRejected(f"{rule.target}<-{rule.proxy}: {info.reason}")

    t = target.sort_index()
    p = proxy.sort_index()
    # Boundary: the target's first month-end (last trading day of its first month).
    first = t.index[0]
    in_first_month = t.index[(t.index.year == first.year) & (t.index.month == first.month)]
    boundary = in_first_month[-1]
    if boundary not in p.index:
        raise SpliceRejected(f"{rule.target}: boundary {boundary.date()} missing from proxy calendar")

    pseg = p.loc[:boundary]
    r = pseg["close"].pct_change().fillna(0.0) + er_adj_year / 252.0
    r.iloc[0] = 0.0
    growth = (1.0 + r).cumprod()
    scale = float(t.loc[boundary, "close"]) / float(growth.loc[boundary])
    close_s = growth * scale
    ratio_open = (pseg["open"] / pseg["close"]).where(lambda x: np.isfinite(x) & (x > 0), 1.0)
    ratio_high = (pseg["high"] / pseg["close"]).where(lambda x: np.isfinite(x) & (x > 0), 1.0)
    ratio_low = (pseg["low"] / pseg["close"]).where(lambda x: np.isfinite(x) & (x > 0), 1.0)
    seg = pd.DataFrame(
        {
            "open": close_s * ratio_open,
            "high": close_s * ratio_high,
            "low": close_s * ratio_low,
            "close": close_s,
            "volume": 0,
            "close_raw": np.nan,
            "dividend": 0.0,
        },
        index=pseg.index,
    )
    seg = seg.loc[seg.index < boundary]
    out = pd.concat([seg, t.loc[boundary:, BAR_COLUMNS]])
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out.index.name = "date"
    info.accepted = True
    info.boundary = str(boundary.date())
    info.first_date = str(out.index[0].date())
    info.reason = "accepted"
    return out[BAR_COLUMNS], info
