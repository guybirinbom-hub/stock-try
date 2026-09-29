"""Data-quality checks that gate every backtest.

Each ``check_*`` function returns ``(passed: bool, detail: str)`` and is pure.
:func:`run_quality_checks` runs them all and raises :class:`DataQualityError`
listing every failure (unless ``raise_on_fail=False``).

Checks (bars have the schema in :data:`stocktry.data.universe.BAR_COLUMNS`):

1. at least 20 rows;
2. strictly increasing dates;
3. positive prices (open, high, low, close and, where present, close_raw);
4. no |daily return of ``close_raw``| > 50 % unless that date carries a split
   flag; and the same 50 % limit on the *adjusted* series the engine trades
   (close-to-close, previous close to open, open to close);
5. no run of >= 5 identical consecutive closes on an equity-like fund
   (equity, international equity, REIT), checked on ``close_raw`` and on the
   adjusted close -- stale-price detector;
6. median bar spacing <= 1 business day (daily data, not weekly/monthly) and
   no gap longer than :data:`MAX_GAP_BDAYS` business days, except across the
   known exchange closures in :data:`KNOWN_CLOSURES` (a missing week or month
   of bars would otherwise be booked as one return or forward-filled flat);
7. a known dividend payer has >= 1 dividend event in every *full* calendar
   year of its history (first and last partial years are skipped);
8. per full calendar year, total return minus price return lies within a
   plausible band for the asset class (percentage points, see
   :data:`TR_PR_GAP_BANDS`); payers must also show a gap of at least
   :data:`MIN_PAYER_GAP` in every full year;
9. adjusted and as-traded daily returns agree except for the day's
   distribution: with ``f = close / close_raw``, on every date
   ``f_t / f_{t-1}`` equals ``1 / (1 - dividend_t / close_raw_{t-1})`` within
   :data:`ADJ_CONSISTENCY_TOL` (Yahoo-style backward adjustment; exactly 1 on
   days without a distribution). Split-flagged dates and rows without an
   as-traded close (spliced proxy segments) are skipped. This is what catches
   a corrupted adjusted close or open whose as-traded close is clean.

``close_raw`` from Yahoo is the *split-adjusted* close (``auto_adjust=False``
still back-adjusts splits), not the literal as-traded print; see
docs/methodology.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from .universe import SymbolMeta, get_meta

MIN_ROWS = 20
MAX_ABS_RAW_RETURN = 0.50
STALE_RUN_LENGTH = 5
MAX_MEDIAN_SPACING_BDAYS = 1.0
MAX_GAP_BDAYS = 3  # longest normal gap: a holiday next to a weekend plus a one-off closure (Sandy 2012)
#: Unscheduled full-day exchange closures longer than a normal holiday; business days inside
#: them do not count towards a gap. (Other one-day closures fit inside MAX_GAP_BDAYS.)
KNOWN_CLOSURES: tuple[tuple[str, str], ...] = (
    ("2001-09-11", "2001-09-14"),  # September 11 attacks
    ("2012-10-29", "2012-10-30"),  # Hurricane Sandy
)
ADJ_CONSISTENCY_TOL = 0.001  # 0.1 % per day; the cached Yahoo series agree to better than 1e-5
# (lower, upper) bounds for yearly TR - PR in decimal (0.10 = 10 percentage points).
TR_PR_GAP_BANDS: dict[str, tuple[float, float]] = {
    "us_equity": (-0.0025, 0.10),
    "intl_equity": (-0.0025, 0.10),
    "reit": (-0.0025, 0.12),
    "us_treasury": (-0.0025, 0.16),
    "us_bond": (-0.0025, 0.16),
    "commodity": (-0.0025, 0.10),
    "gold": (-0.0025, 0.02),
    "cash": (-0.0025, 0.10),
}
MIN_PAYER_GAP = 0.001  # a dividend payer's TR must beat its PR by >= 10 bp in every full year


class DataQualityError(ValueError):
    """A bar series failed one or more quality checks."""


@dataclass
class QualityReport:
    symbol: str
    results: dict[str, tuple[bool, str]] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(ok for ok, _ in self.results.values())

    @property
    def failures(self) -> dict[str, str]:
        return {k: d for k, (ok, d) in self.results.items() if not ok}

    def to_dict(self) -> dict:
        return {k: {"passed": ok, "detail": d} for k, (ok, d) in self.results.items()}


def check_min_rows(df: pd.DataFrame, n: int = MIN_ROWS) -> tuple[bool, str]:
    return (len(df) >= n, f"{len(df)} rows (min {n})")


def check_increasing_dates(df: pd.DataFrame) -> tuple[bool, str]:
    idx = df.index
    if len(idx) < 2:
        return True, "fewer than 2 rows"
    d = np.diff(idx.values.astype("datetime64[ns]").astype("int64"))
    bad = int((d <= 0).sum())
    return bad == 0, f"{bad} non-increasing steps"


def check_positive_prices(df: pd.DataFrame) -> tuple[bool, str]:
    cols = [c for c in ("open", "high", "low", "close", "close_raw") if c in df.columns]
    vals = df[cols]
    bad = int(((vals <= 0) | ~np.isfinite(vals)).where(vals.notna(), False).sum().sum())
    missing_close = int(df["close"].isna().sum())
    ok = bad == 0 and missing_close == 0
    return ok, f"{bad} non-positive/non-finite prices, {missing_close} missing closes"


def check_raw_jumps(
    df: pd.DataFrame, split_dates: Iterable[pd.Timestamp] = (), max_abs: float = MAX_ABS_RAW_RETURN
) -> tuple[bool, str]:
    raw = df["close_raw"] if "close_raw" in df.columns else df["close"]
    raw = raw.where(raw.notna(), df["close"])
    r = raw.pct_change().abs()
    splits = {pd.Timestamp(d).normalize() for d in split_dates}
    big = r[r > max_abs]
    unflagged = [d for d in big.index if d.normalize() not in splits]
    if unflagged:
        return False, f"{len(unflagged)} unflagged |raw return| > {max_abs:.0%}, first {unflagged[0].date()}"
    return True, f"max |raw return| {float(r.max() if len(r) else 0):.3f}"


def check_adjusted_jumps(
    df: pd.DataFrame, split_dates: Iterable[pd.Timestamp] = (), max_abs: float = MAX_ABS_RAW_RETURN
) -> tuple[bool, str]:
    """No |move| > ``max_abs`` in the adjusted series the engine trades: close to close,
    previous close to open, and open to close (split-flagged dates excepted)."""
    c, o = df["close"], df["open"]
    prev = c.shift(1)
    moves = pd.concat([(c / prev - 1).abs(), (o / prev - 1).abs(), (c / o - 1).abs()], axis=1).max(axis=1)
    splits = {pd.Timestamp(d).normalize() for d in split_dates}
    big = moves[moves > max_abs]
    unflagged = [d for d in big.index if d.normalize() not in splits]
    if unflagged:
        return False, (f"{len(unflagged)} unflagged adjusted open/close moves > {max_abs:.0%}, "
                       f"first {unflagged[0].date()}")
    return True, f"max adjusted move {float(moves.max() if len(moves) else 0):.3f}"


def check_adjustment_consistency(
    df: pd.DataFrame, split_dates: Iterable[pd.Timestamp] = (), tol: float = ADJ_CONSISTENCY_TOL
) -> tuple[bool, str]:
    """Adjusted and as-traded daily returns differ only by the day's distribution (check 9)."""
    if "close_raw" not in df.columns or "dividend" not in df.columns:
        return True, "no as-traded close; not applied"
    raw = df["close_raw"]
    f = df["close"] / raw
    ratio = f / f.shift(1)
    d = df["dividend"].fillna(0.0) / raw.shift(1)
    expected = 1.0 / (1.0 - d)
    resid = (ratio - expected).abs()
    splits = {pd.Timestamp(x).normalize() for x in split_dates}
    resid = resid[np.isfinite(resid) & ~resid.index.normalize().isin(list(splits))]
    if resid.empty:
        return True, "no consecutive as-traded closes; not applied"
    bad = resid[resid > tol]
    if not bad.empty:
        return False, (f"{len(bad)} dates where adjusted and as-traded returns disagree beyond the distribution "
                       f"(> {tol:.2%}), first {bad.index[0].date()} ({float(bad.iloc[0]):.4f})")
    return True, f"max |adjusted/as-traded residual| {float(resid.max()):.2e}"


def longest_identical_run(close: pd.Series) -> int:
    """Length of the longest run of identical consecutive values (1 = no repeats)."""
    v = close.dropna().to_numpy()
    if len(v) == 0:
        return 0
    best = cur = 1
    for i in range(1, len(v)):
        if v[i] == v[i - 1]:
            cur += 1
            best = max(best, cur)
        else:
            cur = 1
    return best


def check_stale_runs(df: pd.DataFrame, meta: SymbolMeta, run_len: int = STALE_RUN_LENGTH) -> tuple[bool, str]:
    if not meta.is_equity_like:
        return True, f"not applied to asset class {meta.asset_class}"
    runs = {"adjusted": longest_identical_run(df["close"])}
    if "close_raw" in df.columns and df["close_raw"].notna().any():
        runs["as-traded"] = longest_identical_run(df["close_raw"])
    run = max(runs.values())
    detail = ", ".join(f"{k} {v}" for k, v in runs.items())
    return run < run_len, f"longest identical-close run: {detail} (fail at >= {run_len})"


def check_bar_spacing(df: pd.DataFrame, max_median: float = MAX_MEDIAN_SPACING_BDAYS) -> tuple[bool, str]:
    if len(df) < 2:
        return False, "fewer than 2 rows"
    d = df.index.values.astype("datetime64[D]")
    b = np.busday_count(d[:-1], d[1:])
    med = float(np.median(b))
    return med <= max_median, f"median spacing {med:g} business days (max {max_median:g})"


def _closure_days() -> np.ndarray:
    days = [np.arange(np.datetime64(a), np.datetime64(b) + 1, dtype="datetime64[D]") for a, b in KNOWN_CLOSURES]
    return np.concatenate(days) if days else np.array([], dtype="datetime64[D]")


def check_max_gap(df: pd.DataFrame, max_gap: int = MAX_GAP_BDAYS) -> tuple[bool, str]:
    """No gap between consecutive bars longer than ``max_gap`` business days, not counting
    business days inside :data:`KNOWN_CLOSURES`."""
    if len(df) < 2:
        return True, "fewer than 2 rows"
    d = df.index.values.astype("datetime64[D]")
    gaps = np.busday_count(d[:-1], d[1:])
    closed = _closure_days()
    if len(closed):
        closed = closed[np.is_busday(closed)]
        # closure business days in [d_i + 1, d_{i+1}) excuse that many missing days
        lo = np.searchsorted(closed, d[:-1] + 1, side="left")
        hi = np.searchsorted(closed, d[1:], side="left")
        gaps = gaps - (hi - lo)
    i = int(np.argmax(gaps))
    worst = int(gaps[i])
    detail = f"longest gap {worst} business days after {pd.Timestamp(d[i]).date()} (max {max_gap})"
    return worst <= max_gap, detail


def _full_years(idx: pd.DatetimeIndex) -> list[int]:
    if len(idx) == 0:
        return []
    return list(range(idx[0].year + 1, idx[-1].year))


def check_dividend_counts(df: pd.DataFrame, meta: SymbolMeta) -> tuple[bool, str]:
    if not meta.pays_dividends:
        return True, "not a regular payer; not applied"
    years = _full_years(df.index)
    if not years:
        return True, "no full calendar year"
    ev = (df["dividend"].fillna(0) > 0).groupby(df.index.year).sum()
    zero = [y for y in years if int(ev.get(y, 0)) == 0]
    return not zero, (f"zero dividend events in full years {zero}" if zero else f"{len(years)} full years ok")


def yearly_tr_pr_gap(df: pd.DataFrame) -> pd.Series:
    """Total return minus price return per full calendar year (decimal)."""
    if "close_raw" not in df.columns or df["close_raw"].isna().any():
        return pd.Series(dtype=float)
    ye_tr = df["close"].groupby(df.index.year).last()
    ye_pr = df["close_raw"].groupby(df.index.year).last()
    gap = (ye_tr.pct_change() - ye_pr.pct_change()).dropna()
    years = _full_years(df.index)
    return gap[gap.index.isin(years)]


def check_tr_pr_gap(df: pd.DataFrame, meta: SymbolMeta) -> tuple[bool, str]:
    gap = yearly_tr_pr_gap(df)
    if gap.empty:
        return True, "no full years with as-traded closes"
    lo, hi = TR_PR_GAP_BANDS.get(meta.asset_class, (-0.0025, 0.12))
    if meta.pays_dividends:
        lo = max(lo, MIN_PAYER_GAP)
    bad = gap[(gap < lo) | (gap > hi)]
    detail = f"yearly TR-PR gap {gap.min()*1e4:.0f}..{gap.max()*1e4:.0f} bp (band {lo*1e4:.0f}..{hi*1e4:.0f} bp)"
    if not bad.empty:
        detail += f"; out of band in {list(bad.index)}"
    return bad.empty, detail


def run_quality_checks(
    df: pd.DataFrame,
    symbol: str,
    meta: SymbolMeta | None = None,
    split_dates: Iterable[pd.Timestamp] = (),
    raise_on_fail: bool = True,
) -> QualityReport:
    """Run every check; raise :class:`DataQualityError` on any failure if requested."""
    meta = meta or get_meta(symbol)
    rep = QualityReport(symbol)
    rep.results["min_rows"] = check_min_rows(df)
    rep.results["increasing_dates"] = check_increasing_dates(df)
    if len(df) >= 2:
        rep.results["positive_prices"] = check_positive_prices(df)
        rep.results["raw_jumps"] = check_raw_jumps(df, split_dates)
        rep.results["adjusted_jumps"] = check_adjusted_jumps(df, split_dates)
        rep.results["adjustment_consistency"] = check_adjustment_consistency(df, split_dates)
        rep.results["stale_runs"] = check_stale_runs(df, meta)
        rep.results["bar_spacing"] = check_bar_spacing(df)
        rep.results["max_gap"] = check_max_gap(df)
        rep.results["dividend_counts"] = check_dividend_counts(df, meta)
        rep.results["tr_pr_gap"] = check_tr_pr_gap(df, meta)
    if raise_on_fail and not rep.passed:
        msg = "; ".join(f"{k}: {v}" for k, v in rep.failures.items())
        raise DataQualityError(f"{symbol}: {msg}")
    return rep
