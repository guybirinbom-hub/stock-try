"""Recent daily bars from Alpaca Market Data: the licence-clean price source for the paper runner.

Why this exists: the research cache (``stocktry.data.fetch``) is personal-use
research data downloaded from Yahoo, whose terms forbid automated collection.
An *unattended* runner must not scrape it, so ``scripts/paper_rebalance.py``
takes its prices from the broker's own market-data API, which the account is
licensed to use (docs/research-report.md s.10 and s.14).

* Bars: ``StockHistoricalDataClient.get_stock_bars`` with
  ``timeframe=Day`` and ``adjustment="all"`` (split- and dividend-adjusted, the
  same total-return basis as the research cache's ``close``).
* Feed: ``"iex"`` by default, because paper-only accounts are entitled to the
  IEX feed only (one exchange; its last trade can differ from the consolidated
  close by a few cents). ``"sip"`` (consolidated) is allowed when explicitly
  configured for a funded account with that subscription.
* Dividends (best effort): cash dividends from the corporate-actions endpoint,
  on their ex-dates, for the runner's *modelled*-dividend ledger. If that call
  fails the dividend column is 0 and a warning is logged.
* Keys: ``APCA_API_KEY_ID`` / ``APCA_API_SECRET_KEY`` from the environment
  only; never stored on an object, logged or put in an exception.

Output: ``{symbol: DataFrame}`` in the schema of
:func:`stocktry.data.fetch.get_bars` -- tz-naive ``DatetimeIndex`` named
``date`` (the New York session date) and columns ``open, high, low, close,
volume, close_raw, dividend``. ``close_raw`` equals ``close`` here (Alpaca
returns one adjustment basis per request); the runner uses only ``close``.
Bars are fetched fresh on every call; nothing is cached or committed.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Mapping

import pandas as pd

from .universe import BAR_COLUMNS

log = logging.getLogger(__name__)

__all__ = ["AlpacaDataError", "FEEDS", "DEFAULT_FEED", "DEFAULT_HISTORY_DAYS", "get_bars_alpaca",
           "resolve_feed", "make_data_clients"]

FEEDS = ("iex", "sip")
DEFAULT_FEED = "iex"  # paper-only accounts are entitled to IEX only
#: ~26 months of daily bars: a 12-month momentum return needs 13 month-end closes, a 10-month SMA 10;
#: the margin covers holidays and the current partial month (the task minimum is 18 months).
DEFAULT_HISTORY_DAYS = 800
MIN_HISTORY_DAYS = 550  # never fetch less than ~18 months
NY = "America/New_York"
HTTP_TIMEOUT = (5.0, 30.0)


class AlpacaDataError(RuntimeError):
    """Alpaca Market Data returned nothing usable (the message never contains credentials)."""


def resolve_feed(feed: str | None, env: Mapping[str, str] | None = None) -> str:
    """The data feed to use: the argument, else ``APCA_DATA_FEED``, else ``"iex"``. Only iex/sip."""
    env = os.environ if env is None else env
    f = (feed or env.get("APCA_DATA_FEED") or DEFAULT_FEED).strip().lower()
    if f not in FEEDS:
        raise ValueError(f"unsupported Alpaca data feed {f!r}; use one of {FEEDS} (paper-only accounts: iex)")
    return f


def make_data_clients(env: Mapping[str, str] | None = None) -> tuple[Any, Any]:
    """(bars client, corporate-actions client) built from the environment keys, raw-data mode, with timeouts."""
    env = os.environ if env is None else env
    key, secret = env.get("APCA_API_KEY_ID"), env.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise AlpacaDataError("APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set to use Alpaca market data")
    try:
        from alpaca.data.historical.corporate_actions import CorporateActionsClient
        from alpaca.data.historical.stock import StockHistoricalDataClient
    except ImportError as exc:  # pragma: no cover - alpaca-py is pinned in requirements
        raise AlpacaDataError(f"alpaca-py is not installed ({exc})") from None
    bars = StockHistoricalDataClient(key, secret, raw_data=True)
    ca = CorporateActionsClient(key, secret, raw_data=True)
    _add_timeout(bars)
    _add_timeout(ca)
    return bars, ca


def _add_timeout(client: Any) -> None:
    """Explicit (connect, read) timeout on every request (the SDK sets none). Reads only: SDK retries on
    429/504 are harmless for GETs and are left as they are."""
    session = getattr(client, "_session", None)
    if session is None:  # pragma: no cover - depends on SDK internals; a missing timeout is not fatal here
        return
    from requests.adapters import HTTPAdapter

    class _Timeout(HTTPAdapter):
        def send(self, request, **kw):  # type: ignore[override]
            if kw.get("timeout") is None:
                kw["timeout"] = HTTP_TIMEOUT
            return super().send(request, **kw)

    session.mount("https://", _Timeout())
    session.mount("http://", _Timeout())


def _field(bar: Any, short: str, long: str) -> Any:
    if isinstance(bar, Mapping):
        return bar.get(short, bar.get(long))
    return getattr(bar, long, getattr(bar, short, None))


def _bars_by_symbol(resp: Any) -> Mapping[str, Iterable[Any]]:
    """Raw-data dict ``{symbol: [bar, ...]}`` (possibly wrapped in ``{"bars": ...}``) or a BarSet."""
    if hasattr(resp, "data") and not isinstance(resp, Mapping):
        return resp.data
    if isinstance(resp, Mapping) and "bars" in resp and isinstance(resp["bars"], Mapping):
        return resp["bars"]
    if isinstance(resp, Mapping):
        return resp
    raise AlpacaDataError(f"unexpected bars response type {type(resp).__name__}")


def _session_date(ts: Any) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    return t.tz_convert(NY).tz_localize(None).normalize()


def _frame(sym: str, rows: Iterable[Any]) -> pd.DataFrame:
    recs = []
    for b in rows:
        if b is None:
            continue
        recs.append({"date": _session_date(_field(b, "t", "timestamp")), "open": _field(b, "o", "open"),
                     "high": _field(b, "h", "high"), "low": _field(b, "l", "low"), "close": _field(b, "c", "close"),
                     "volume": _field(b, "v", "volume")})
    if not recs:
        raise AlpacaDataError(f"no daily bars returned for {sym}")
    df = pd.DataFrame(recs).set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    df = df[df["close"] > 0]
    for c in ("open", "high", "low"):
        bad = ~(df[c] > 0)
        df.loc[bad, c] = df.loc[bad, "close"]
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype("int64")
    df["close_raw"] = df["close"]  # one adjustment basis per request; the runner uses close only
    df["dividend"] = 0.0
    df.index.name = "date"
    return df[BAR_COLUMNS]


def _dividends(ca_client: Any, symbols: list[str], start: date, end: date) -> dict[str, list[tuple[date, float]]]:
    from alpaca.data.enums import CorporateActionsType
    from alpaca.data.requests import CorporateActionsRequest

    req = CorporateActionsRequest(symbols=symbols, types=[CorporateActionsType.CASH_DIVIDEND], start=start, end=end)
    resp = ca_client.get_corporate_actions(req)
    data = resp.data if hasattr(resp, "data") and not isinstance(resp, Mapping) else resp
    rows = (data or {}).get("cash_dividends", []) if isinstance(data, Mapping) else []
    out: dict[str, list[tuple[date, float]]] = {}
    for r in rows:
        sym = _field(r, "symbol", "symbol")
        ex = _field(r, "ex_date", "ex_date")
        rate = _field(r, "rate", "rate")
        if sym in symbols and ex is not None and rate:
            out.setdefault(sym, []).append((pd.Timestamp(ex).date(), float(rate)))
    return out


def get_bars_alpaca(
    symbols: Iterable[str],
    *,
    end: date | None = None,
    history_days: int = DEFAULT_HISTORY_DAYS,
    feed: str | None = None,
    env: Mapping[str, str] | None = None,
    client: Any = None,
    corporate_actions_client: Any = None,
    dividends: bool = True,
) -> dict[str, pd.DataFrame]:
    """Daily bars for ``symbols`` from Alpaca Market Data, in the :func:`~stocktry.data.fetch.get_bars` schema.

    ``end`` defaults to today (UTC); bars from ``end - history_days`` (at least ~18 months) to ``end``.
    ``client``/``corporate_actions_client`` are injectable for tests; by default they are built from
    ``APCA_API_KEY_ID``/``APCA_API_SECRET_KEY``. Raises :class:`AlpacaDataError` if any symbol has no bars.
    """
    syms = [s.upper() for s in dict.fromkeys(symbols)]
    if not syms:
        raise ValueError("no symbols requested")
    feed_name = resolve_feed(feed, env)
    if client is None:
        client, ca = make_data_clients(env)
        corporate_actions_client = corporate_actions_client or ca
    end_d = end or datetime.now(timezone.utc).date()
    start_d = end_d - timedelta(days=max(int(history_days), MIN_HISTORY_DAYS))
    from alpaca.data.enums import Adjustment, DataFeed
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = StockBarsRequest(
        symbol_or_symbols=syms, timeframe=TimeFrame.Day,
        start=datetime.combine(start_d, time(0, 0), timezone.utc),
        end=datetime.combine(end_d + timedelta(days=1), time(0, 0), timezone.utc),
        adjustment=Adjustment.ALL, feed=DataFeed(feed_name),
    )
    try:
        by_sym = _bars_by_symbol(client.get_stock_bars(req))
    except AlpacaDataError:
        raise
    except Exception as exc:  # noqa: BLE001 - SDK/HTTP errors: type only, never the request (it carries no keys,
        raise AlpacaDataError(f"Alpaca bars request failed: {type(exc).__name__}") from None  # but stay terse)
    out = {s: _frame(s, by_sym.get(s) or []) for s in syms}
    if dividends and corporate_actions_client is not None:
        try:
            divs = _dividends(corporate_actions_client, syms, start_d, end_d)
        except Exception as exc:  # noqa: BLE001 - best effort: modelled dividends only
            log.warning("Alpaca corporate actions unavailable (%s); dividends set to 0", type(exc).__name__)
            divs = {}
        for s, rows in divs.items():
            df = out[s]
            for ex, amt in rows:
                ts = pd.Timestamp(ex)
                if ts in df.index:
                    df.loc[ts, "dividend"] = df.loc[ts, "dividend"] + amt
    return out
