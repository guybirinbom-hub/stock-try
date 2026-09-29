"""Fetch and cache daily total-return-adjusted bars, T-bill yields and Fama-French factors.

Source chain for ETF / mutual-fund bars (first sane result wins):

1. ``yfinance`` -- ``Ticker.history(period="max", auto_adjust=False, actions=True)``;
2. raw Yahoo v8 chart API with a browser User-Agent and ``period1=0&period2=now``
   (never ``range=max``, which silently returns coarse bars);
3. the last good CSV in the cache (stale), with a warning.

Output schema (tz-naive ``DatetimeIndex`` named ``date``):
``open, high, low, close`` total-return adjusted (split + dividend; factor =
Adj Close / Close applied to O/H/L), ``volume`` shares, ``close_raw`` the
as-traded (split-adjusted) close in dollars and ``dividend`` the cash
distribution per share on its ex-date in dollars.

Cache: one CSV per symbol under ``<data dir>/cache`` with a sidecar
``<SYMBOL>.manifest.json`` (source, retrieved_utc, sha256 of the CSV bytes,
first/last date, row count, split dates). The data directory is
``$STOCKTRY_DATA_DIR`` if set, else ``<repo>/data``. Vendor data is for
personal research use and is never committed (``data/`` is gitignored).

FRED ``DTB3`` (3-month T-bill secondary-market discount rate, percent) is
fetched from the keyless ``fredgraph.csv`` endpoint with the *default*
python-requests User-Agent (a browser UA is reset by FRED). Ken French
monthly factors come from the keyless zip on the Dartmouth site.

No function here reads or logs any credential; none are needed.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from .quality import run_quality_checks
from .universe import BAR_COLUMNS, get_meta

log = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
FF_FACTORS_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
)
HTTP_TIMEOUT = 60.0


class FetchError(RuntimeError):
    """No source produced usable data."""


class CacheIntegrityError(RuntimeError):
    """A cached file does not match the sha256 recorded in its manifest."""


# --------------------------------------------------------------------------- paths
def data_dir() -> Path:
    env = os.environ.get("STOCKTRY_DATA_DIR")
    if env:
        return Path(env)
    repo = Path(__file__).resolve().parents[3]
    if (repo / "pyproject.toml").exists():
        return repo / "data"
    return Path.cwd() / "data"


def cache_dir() -> Path:
    return data_dir() / "cache"


def _csv_path(name: str, cdir: Path | None = None) -> Path:
    return (cdir or cache_dir()) / f"{name.upper()}.csv"


def _manifest_path(name: str, cdir: Path | None = None) -> Path:
    return (cdir or cache_dir()) / f"{name.upper()}.manifest.json"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------- normalisation
def normalize_bars(raw: pd.DataFrame) -> pd.DataFrame:
    """Turn vendor columns into the package schema.

    ``raw`` must have columns ``open, high, low, close_raw, adj_close, volume,
    dividend`` (as-traded O/H/L/C, vendor adjusted close). The adjustment
    factor ``adj_close / close_raw`` is applied to open/high/low so that all
    four OHLC fields are on the same total-return scale.
    """
    df = raw.dropna(subset=["close_raw", "adj_close"]).copy()
    df = df[(df["close_raw"] > 0) & (df["adj_close"] > 0)]
    factor = df["adj_close"] / df["close_raw"]
    out = pd.DataFrame(
        {
            "open": df["open"] * factor,
            "high": df["high"] * factor,
            "low": df["low"] * factor,
            "close": df["adj_close"],
            "volume": df["volume"].fillna(0).astype("int64"),
            "close_raw": df["close_raw"],
            "dividend": df["dividend"].fillna(0.0).astype(float),
        },
        index=df.index,
    )
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    # Missing/zero opens (rare vendor gaps): fall back to the adjusted close of that day.
    for c in ("open", "high", "low"):
        bad = ~(out[c] > 0)
        out.loc[bad, c] = out.loc[bad, "close"]
    return out[BAR_COLUMNS]


# --------------------------------------------------------------------------- sources
def fetch_yfinance(symbol: str) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    import yfinance as yf  # imported lazily: heavy and network-bound

    logging.getLogger("yfinance").setLevel(logging.WARNING)
    h = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise FetchError("yfinance returned no rows")
    raw = pd.DataFrame(
        {
            "open": h["Open"],
            "high": h["High"],
            "low": h["Low"],
            "close_raw": h["Close"],
            "adj_close": h["Adj Close"],
            "volume": h["Volume"],
            "dividend": h["Dividends"] if "Dividends" in h else 0.0,
        }
    )
    splits: list[pd.Timestamp] = []
    if "Stock Splits" in h:
        s = h["Stock Splits"]
        idx = pd.DatetimeIndex(s[s > 0].index)
        splits = list((idx.tz_localize(None) if idx.tz is not None else idx).normalize())
    return normalize_bars(raw), splits


def fetch_yahoo_raw(symbol: str, retries: int = 3) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    params = {
        "period1": 0,  # NOT range=max (coarse bars)
        "period2": int(time.time()) + 86400,
        "interval": "1d",
        "events": "div,split",
        "includeAdjustedClose": "true",
    }
    last_err: Exception | None = None
    r = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(YAHOO_CHART_URL.format(symbol=symbol), params=params,
                             headers={"User-Agent": BROWSER_UA}, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                break
            last_err = FetchError(f"HTTP {r.status_code}")
        except requests.RequestException as e:
            last_err = e
        time.sleep(2**attempt)
    else:
        raise FetchError(f"yahoo_raw failed after {retries} tries: {last_err}")
    res = r.json()["chart"]["result"][0]
    if res["meta"].get("dataGranularity") != "1d":
        raise FetchError(f"unexpected granularity {res['meta'].get('dataGranularity')}")
    tz = res["meta"].get("exchangeTimezoneName", "America/New_York")
    idx = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(tz).tz_localize(None).normalize()
    q = res["indicators"]["quote"][0]
    raw = pd.DataFrame(
        {
            "open": q["open"],
            "high": q["high"],
            "low": q["low"],
            "close_raw": q["close"],
            "adj_close": res["indicators"]["adjclose"][0]["adjclose"],
            "volume": q["volume"],
            "dividend": 0.0,
        },
        index=idx,
        dtype="float64",
    )
    raw = raw[~raw.index.duplicated(keep="last")]
    events = res.get("events", {})
    for ev in events.get("dividends", {}).values():
        d = pd.Timestamp(ev["date"], unit="s", tz="UTC").tz_convert(tz).tz_localize(None).normalize()
        if d in raw.index:
            raw.loc[d, "dividend"] = ev["amount"]
    splits = [
        pd.Timestamp(ev["date"], unit="s", tz="UTC").tz_convert(tz).tz_localize(None).normalize()
        for ev in events.get("splits", {}).values()
    ]
    return normalize_bars(raw), splits


SOURCES = {"yfinance": fetch_yfinance, "yahoo_raw": fetch_yahoo_raw}


# --------------------------------------------------------------------------- cache
def write_bars_cache(symbol: str, df: pd.DataFrame, source: str, splits: list[pd.Timestamp] | None = None,
                     cdir: Path | None = None, quality: dict | None = None) -> dict:
    """Write ``<SYMBOL>.csv`` and its manifest; return the manifest dict."""
    cdir = cdir or cache_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    df[BAR_COLUMNS].to_csv(buf, float_format="%.10g", date_format="%Y-%m-%d")
    data = buf.getvalue().encode()
    _csv_path(symbol, cdir).write_bytes(data)
    manifest = {
        "symbol": symbol.upper(),
        "source": source,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(data),
        "first_date": str(df.index[0].date()),
        "last_date": str(df.index[-1].date()),
        "rows": int(len(df)),
        "dividend_events": int((df["dividend"] > 0).sum()),
        "splits": [str(pd.Timestamp(d).date()) for d in (splits or [])],
        "schema": BAR_COLUMNS,
        "adjustment": "OHLC total-return adjusted: factor = vendor Adj Close / Close",
    }
    if quality is not None:
        manifest["quality"] = quality
    _manifest_path(symbol, cdir).write_text(json.dumps(manifest, indent=2))
    return manifest


def read_manifest(name: str, cdir: Path | None = None) -> dict:
    p = _manifest_path(name, cdir)
    if not p.exists():
        raise FetchError(f"no manifest at {p}")
    return json.loads(p.read_text())


def read_verified_bytes(name: str, cdir: Path | None = None) -> bytes:
    """Bytes of the cached ``<NAME>.csv`` after checking them against the manifest sha256.

    Used on *every* cache-read path (normal reads and the stale fallbacks after a
    network failure). A missing manifest or a hash mismatch raises
    :class:`CacheIntegrityError`: a tampered or truncated file is never parsed.
    """
    p = _csv_path(name, cdir)
    if not p.exists():
        raise FetchError(f"no cache at {p}")
    data = p.read_bytes()
    try:
        manifest = read_manifest(name, cdir)
    except FetchError:
        raise CacheIntegrityError(f"{name.upper()}: cache file has no manifest; refusing to use it") from None
    if manifest.get("sha256") != sha256_bytes(data):
        raise CacheIntegrityError(f"{name.upper()}: cache file does not match manifest sha256")
    return data


def read_bars_cache(symbol: str, cdir: Path | None = None, verify: bool = True) -> tuple[pd.DataFrame, dict]:
    """Read a cached bar CSV and its manifest, verifying the sha256."""
    p = _csv_path(symbol, cdir)
    if not p.exists():
        raise FetchError(f"no cache at {p}")
    data = p.read_bytes()
    manifest = read_manifest(symbol, cdir)
    if verify and manifest.get("sha256") != sha256_bytes(data):
        raise CacheIntegrityError(f"{symbol}: cache file does not match manifest sha256")
    df = pd.read_csv(io.BytesIO(data), index_col="date", parse_dates=["date"])
    df.index = pd.DatetimeIndex(df.index)
    df["volume"] = df["volume"].fillna(0).astype("int64")
    return df[BAR_COLUMNS], manifest


def fetch_bars(symbol: str, sources: tuple[str, ...] = ("yfinance", "yahoo_raw"),
               cdir: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Try each network source; quality-check; write the cache. Raises FetchError."""
    errors = []
    meta = get_meta(symbol)
    for name in sources:
        try:
            df, splits = SOURCES[name](symbol)
            rep = run_quality_checks(df, symbol, meta, split_dates=splits, raise_on_fail=True)
            manifest = write_bars_cache(symbol, df, name, splits, cdir, quality=rep.to_dict())
            return df, manifest
        except Exception as e:  # noqa: BLE001 - any failure moves to the next source
            errors.append(f"{name}: {type(e).__name__}: {e}")
            log.warning("%s via %s failed: %s", symbol, name, e)
    raise FetchError(f"{symbol}: all network sources failed -> " + " | ".join(errors))


def get_bars_with_manifest(symbol: str, *, refresh: bool = False, cdir: Path | None = None
                           ) -> tuple[pd.DataFrame, dict]:
    """Like :func:`get_bars` but also returns the manifest (``manifest['stale']`` is set on fallback)."""
    symbol = symbol.upper()
    if not refresh:
        try:
            return read_bars_cache(symbol, cdir)
        except FetchError:
            pass  # no cache yet -> fetch
    try:
        return fetch_bars(symbol, cdir=cdir)
    except FetchError as e:
        try:
            df, manifest = read_bars_cache(symbol, cdir)
        except FetchError:
            raise e from None
        log.warning("%s: network failed, using STALE cache last dated %s", symbol, manifest.get("last_date"))
        manifest = dict(manifest, stale=True)
        return df, manifest


def get_bars(symbol: str, *, refresh: bool = False) -> pd.DataFrame:
    """Daily bars for ``symbol`` (contract function).

    Returns a DataFrame indexed by tz-naive date with columns ``open, high,
    low, close, volume, close_raw, dividend``; OHLC are total-return adjusted
    (dollars on the vendor's adjusted scale), ``close_raw`` is the as-traded
    close in dollars and ``dividend`` is dollars per share on the ex-date.

    With ``refresh=False`` a cached copy is returned if one exists (it may be
    old -- callers that need fresh data pass ``refresh=True``). With
    ``refresh=True`` the network chain yfinance -> raw Yahoo is tried and, if
    both fail, the stale cache is returned with a logged warning. Raises
    :class:`FetchError` when nothing is available.
    """
    return get_bars_with_manifest(symbol, refresh=refresh)[0]


# --------------------------------------------------------------------------- FRED DTB3
def parse_fred_csv(text: str, series: str) -> pd.Series:
    """Parse FRED's fredgraph.csv (first column date, '.' = missing) into a float Series."""
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    date_col = df.columns[0]
    s = pd.Series(pd.to_numeric(df[series], errors="coerce").to_numpy(),
                  index=pd.DatetimeIndex(pd.to_datetime(df[date_col])), name=series)
    s.index.name = "date"
    return s.dropna().sort_index()


def _fetch_fred(series: str) -> str:
    # Deliberately the default python-requests User-Agent: FRED resets browser UAs here.
    r = requests.get(FRED_CSV_URL.format(series=series), timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    if not r.text.lstrip().lower().startswith(("observation_date", "date")):
        raise FetchError("FRED response is not a CSV")
    return r.text


def get_tbill_yield(*, refresh: bool = False) -> pd.Series:
    """FRED DTB3: 3-month T-bill secondary-market rate, **percent per year** (discount basis), by date.

    Cached as ``DTB3.csv``; with ``refresh=False`` the cache is used if present.
    On network failure a stale cache is returned with a warning.
    """
    cdir = cache_dir()
    p = _csv_path("DTB3", cdir)
    if p.exists() and not refresh:
        return parse_fred_csv(read_verified_bytes("DTB3", cdir).decode(), "DTB3")
    try:
        text = _fetch_fred("DTB3")
        s = parse_fred_csv(text, "DTB3")
        if len(s) < 1000:
            raise FetchError(f"DTB3 too short ({len(s)})")
    except Exception as e:  # noqa: BLE001
        if p.exists():
            data = read_verified_bytes("DTB3", cdir)  # the stale fallback is hash-checked too
            log.warning("DTB3 fetch failed (%s); using STALE cache", e)
            return parse_fred_csv(data.decode(), "DTB3")
        raise FetchError(f"DTB3 unavailable: {e}") from e
    cdir.mkdir(parents=True, exist_ok=True)
    data = text.encode()
    p.write_bytes(data)
    _manifest_path("DTB3", cdir).write_text(json.dumps({
        "series": "DTB3", "source": "FRED fredgraph.csv (keyless)",
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(data), "first_date": str(s.index[0].date()),
        "last_date": str(s.index[-1].date()), "rows": int(len(s)),
        "units": "percent per year, discount basis", "terms": "FRED content: not committed",
    }, indent=2))
    return s


# --------------------------------------------------------------------------- Ken French
FF_MISSING_CODES = (-99.99, -999.0)  # Ken French data library codes for "missing"


def _ff_value(x: str) -> float:
    v = float(x)
    return float("nan") if any(abs(v - code) < 1e-9 for code in FF_MISSING_CODES) else v


def parse_ff_factors_csv(text: str) -> pd.DataFrame:
    """Parse the monthly block of F-F_Research_Data_Factors.csv.

    Returns decimals (the file is in percent) indexed by month-end Timestamp,
    columns ``Mkt-RF, SMB, HML, RF``. The library's missing-value codes
    (-99.99 and -999) become NaN, never a -99.99% return; consumers drop NaN.
    """
    rows = []
    header_seen = False
    for line in text.splitlines():
        s = line.strip()
        if not header_seen:
            if s.startswith(",Mkt-RF"):
                header_seen = True
            continue
        if not s or "Annual" in s:
            break
        parts = [x.strip() for x in s.split(",")]
        if len(parts[0]) != 6 or not parts[0].isdigit():
            break
        rows.append([parts[0]] + [_ff_value(x) for x in parts[1:5]])
    if not rows:
        raise FetchError("no monthly rows found in Fama-French file")
    df = pd.DataFrame(rows, columns=["yyyymm", "Mkt-RF", "SMB", "HML", "RF"])
    idx = pd.PeriodIndex([f"{r[:4]}-{r[4:]}" for r in df["yyyymm"]], freq="M").to_timestamp(how="end").normalize()
    out = df[["Mkt-RF", "SMB", "HML", "RF"]].set_axis(idx) / 100.0
    out.index.name = "month_end"
    return out


def get_ff_factors(*, refresh: bool = False) -> pd.DataFrame:
    """Ken French monthly factors (decimal), cached as ``FF_FACTORS.csv`` (raw file text)."""
    cdir = cache_dir()
    p = _csv_path("FF_FACTORS", cdir)
    if p.exists() and not refresh:
        return parse_ff_factors_csv(read_verified_bytes("FF_FACTORS", cdir).decode("latin-1"))
    try:
        r = requests.get(FF_FACTORS_URL, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(r.content))
        text = z.read(z.namelist()[0]).decode("latin-1")
        df = parse_ff_factors_csv(text)
    except Exception as e:  # noqa: BLE001
        if p.exists():
            data = read_verified_bytes("FF_FACTORS", cdir)  # the stale fallback is hash-checked too
            log.warning("Fama-French fetch failed (%s); using STALE cache", e)
            return parse_ff_factors_csv(data.decode("latin-1"))
        raise FetchError(f"Fama-French factors unavailable: {e}") from e
    cdir.mkdir(parents=True, exist_ok=True)
    data = text.encode("latin-1")
    p.write_bytes(data)
    _manifest_path("FF_FACTORS", cdir).write_text(json.dumps({
        "series": "F-F_Research_Data_Factors (monthly)", "source": FF_FACTORS_URL,
        "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(data), "first_month": str(df.index[0].date()),
        "last_month": str(df.index[-1].date()), "rows": int(len(df)), "units": "decimal after parsing",
    }, indent=2))
    return df


__all__ = [
    "FetchError", "CacheIntegrityError", "get_bars", "get_bars_with_manifest", "get_tbill_yield",
    "get_ff_factors", "normalize_bars", "parse_fred_csv", "parse_ff_factors_csv", "write_bars_cache",
    "read_bars_cache", "read_verified_bytes", "cache_dir", "data_dir",
]
