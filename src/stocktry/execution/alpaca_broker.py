"""Alpaca adapter (alpaca-py 0.44.0) with the duplicate-order hazard neutralized.

Safety properties
-----------------
* Paper by default. A live client is built only when BOTH ``live=True`` is
  passed AND env ``LIVE_TRADING=yes-live``. ``live=True`` without the env var
  **raises** (it never falls back to a paper client: an admin action such as
  hardening or the broker kill switch would otherwise silently act on the
  wrong account). The runner separately requires the ``--i-understand-live``
  flag before it will submit to a live broker.
* Keys come only from env ``APCA_API_KEY_ID`` / ``APCA_API_SECRET_KEY``; they
  are never stored on this object, logged or included in exceptions.
* alpaca-py's ``RESTClient._request`` retries *any* request (including
  ``POST /v2/orders``) on HTTP 429/504, 3 times, 3 s apart, with no timeout
  (``alpaca/common/rest.py``: ``self._retry``, ``self._retry_codes``,
  ``self._retry_wait``, ``self._session``; defaults in
  ``alpaca/common/constants.py``). A 504 returned *after* the order was
  accepted would therefore create a duplicate order. ``neutralize_retries``
  sets ``_retry_codes`` to a NEW empty list (the default list object is shared
  module state and must not be mutated), ``_retry`` and ``_retry_wait`` to 0,
  and mounts an ``HTTPAdapter`` that applies an explicit (connect, read)
  timeout to every request. If any of these private attributes disappears in
  a future SDK, construction fails loudly instead of silently re-enabling
  retries; a unit test pins this.
* ``submit_order`` sends ``POST /v2/orders`` once. On ANY exception it looks
  the order up by ``client_order_id`` before deciding the submit failed.
* Notional orders are market DAY orders with the notional as an exact
  2-decimal string (the API types it as a string); ``qty`` is never sent with
  a notional. Values that would need rounding are refused, not rounded.

Endpoints are called through the SDK's own ``get``/``post``/``patch``/
``delete`` with ``raw_data=True`` so fields the SDK's models do not know
(e.g. ``disable_overnight_trading``) pass through, and a model validation
change cannot break order handling.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from requests.adapters import HTTPAdapter

from .broker import (
    DUPLICATE_CLIENT_ORDER_ID_MESSAGE,
    Account,
    AccountConfig,
    Activity,
    AssetInfo,
    BrokerError,
    BrokerHTTPError,
    BrokerTimeout,
    CalendarDay,
    Clock,
    DuplicateClientOrderId,
    LatestPrice,
    Order,
    Position,
)
from .killswitch import LIVE_ENV, LIVE_ENV_VALUE
from .preflight import harden_account  # noqa: F401  (re-export: harden_account(AlpacaBroker(...)))
from .sessions import ET

__all__ = ["AlpacaBroker", "TimeoutHTTPAdapter", "neutralize_retries", "RETRY_ATTRIBUTES", "harden_account"]

log = logging.getLogger("stocktry.execution.alpaca")

#: Private alpaca-py RESTClient attributes this module depends on (verified in 0.44.0).
RETRY_ATTRIBUTES = ("_retry", "_retry_wait", "_retry_codes", "_session")
DEFAULT_TIMEOUT = (5.0, 15.0)  # seconds: (connect, read)
CENT = Decimal("0.01")
Q9 = Decimal("0.000000001")


class TimeoutHTTPAdapter(HTTPAdapter):
    """HTTPAdapter that applies a default timeout when the caller passes none.

    ``requests`` passes ``timeout=None`` explicitly when alpaca-py omits it.
    ``max_retries`` stays at requests' default of 0 (no urllib3 retries).
    """

    def __init__(self, *args: Any, timeout: tuple[float, float] = DEFAULT_TIMEOUT, **kwargs: Any) -> None:
        self.default_timeout = timeout
        super().__init__(*args, **kwargs)

    def send(self, request, **kwargs):  # type: ignore[override]
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.default_timeout
        return super().send(request, **kwargs)


def neutralize_retries(client: Any, timeout: tuple[float, float] = DEFAULT_TIMEOUT) -> None:
    """Disable alpaca-py's automatic retries and add a request timeout."""
    missing = [a for a in RETRY_ATTRIBUTES if not hasattr(client, a)]
    if missing:
        raise RuntimeError(
            f"alpaca-py internals changed (missing {missing}); refusing to run until the "
            "retry neutralization in stocktry.execution.alpaca_broker is re-verified"
        )
    client._retry_codes = []  # NEW list: never mutate alpaca.common.constants.DEFAULT_RETRY_EXCEPTION_CODES
    client._retry = 0
    client._retry_wait = 0
    adapter = TimeoutHTTPAdapter(timeout=timeout)
    client._session.mount("https://", adapter)
    client._session.mount("http://", adapter)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _dec(x: Any, default: str = "0") -> Decimal:
    if x is None or x == "":
        return Decimal(default)
    return Decimal(str(x))


def _order(d: Mapping[str, Any]) -> Order:
    return Order(
        id=str(d["id"]),
        client_order_id=str(d.get("client_order_id") or ""),
        symbol=str(d.get("symbol") or ""),
        side=str(d.get("side") or ""),
        status=str(d.get("status") or ""),
        submitted_at=_dt(d.get("submitted_at") or d["created_at"]),
        notional=None if d.get("notional") in (None, "") else _dec(d["notional"]),
        qty=None if d.get("qty") in (None, "") else _dec(d["qty"]),
        filled_qty=_dec(d.get("filled_qty")),
        filled_avg_price=None if d.get("filled_avg_price") in (None, "") else _dec(d["filled_avg_price"]),
        time_in_force=str(d.get("time_in_force") or ""),
        order_type=str(d.get("type") or d.get("order_type") or ""),
    )


def _config(d: Mapping[str, Any]) -> AccountConfig:
    lvl = d.get("max_options_trading_level")
    return AccountConfig(
        max_margin_multiplier=str(d.get("max_margin_multiplier")),
        no_shorting=bool(d.get("no_shorting")),
        max_options_trading_level=None if lvl is None else int(lvl),
        suspend_trade=bool(d.get("suspend_trade")),
        trade_confirm_email=str(d.get("trade_confirm_email")),
        fractional_trading=bool(d.get("fractional_trading")),
        disable_overnight_trading=d.get("disable_overnight_trading"),
    )


class AlpacaBroker:
    """``Broker`` implementation over Alpaca's Trading and Market Data APIs."""

    def __init__(
        self,
        *,
        live: bool = False,
        env: Mapping[str, str] | None = None,
        timeout: tuple[float, float] = DEFAULT_TIMEOUT,
        data_feed: str | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        env = os.environ if env is None else env
        if not env.get("APCA_API_KEY_ID") or not env.get("APCA_API_SECRET_KEY"):
            raise BrokerError("APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in the environment")
        use_live = bool(live) and env.get(LIVE_ENV) == LIVE_ENV_VALUE
        if live and not use_live:
            raise BrokerError(f"live account requested but {LIVE_ENV} is not '{LIVE_ENV_VALUE}' in the environment; "
                              "refusing (a paper client is never substituted for a live request)")
        self.is_live = use_live
        self.name = "alpaca-live" if use_live else "alpaca-paper"
        self._sleep = sleep
        self._feed = data_feed or env.get("APCA_DATA_FEED") or "iex"  # paper-only accounts get IEX only
        try:
            from alpaca.data.historical.stock import StockHistoricalDataClient
            from alpaca.trading.client import TradingClient
        except ImportError as exc:  # pragma: no cover
            raise BrokerError("alpaca-py is not installed (pip install -r requirements.txt)") from exc
        self._client = TradingClient(
            env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"], paper=not use_live, raw_data=True
        )
        self._data = StockHistoricalDataClient(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"], raw_data=True)
        neutralize_retries(self._client, timeout)
        neutralize_retries(self._data, timeout)

    def __repr__(self) -> str:  # never expose client internals (which hold keys)
        return f"AlpacaBroker(name={self.name!r})"

    @property
    def base_url(self) -> str:
        u = self._client._base_url
        return str(getattr(u, "value", u))

    # ------------------------------------------------------------ transport
    def _call(self, fn: Callable[..., Any], *args: Any) -> Any:
        import requests
        from alpaca.common.exceptions import APIError

        try:
            return fn(*args)
        except APIError as exc:
            status = exc.status_code or 0
            text = str(exc)
            if DUPLICATE_CLIENT_ORDER_ID_MESSAGE in text:
                raise DuplicateClientOrderId("(see request)") from None
            raise BrokerHTTPError(status, text[:300]) from None
        except requests.Timeout:
            raise BrokerTimeout("request to Alpaca timed out") from None
        except requests.RequestException as exc:
            raise BrokerError(f"network error talking to Alpaca: {type(exc).__name__}") from None

    def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        return self._call(self._client.get, path, dict(params or {}))

    # ---------------------------------------------------------- clock/calendar
    def get_clock(self) -> Clock:
        d = self._get("/clock")
        return Clock(bool(d["is_open"]), _dt(d["next_open"]), _dt(d["next_close"]), _dt(d["timestamp"]))

    def get_calendar(self, start: date, end: date) -> list[CalendarDay]:
        rows = self._get("/calendar", {"start": start.isoformat(), "end": end.isoformat()})
        out = []
        for r in rows:
            d = date.fromisoformat(r["date"])
            o = dtime.fromisoformat(r["open"])
            c = dtime.fromisoformat(r["close"])
            out.append(CalendarDay(d, datetime.combine(d, o, ET), datetime.combine(d, c, ET)))
        return out

    # ---------------------------------------------------------------- account
    def get_account(self) -> Account:
        d = self._get("/account")
        lvl = d.get("options_trading_level")
        return Account(
            cash=_dec(d.get("cash")),
            equity=_dec(d.get("equity")),
            non_marginable_buying_power=_dec(d.get("non_marginable_buying_power")),  # missing -> 0: no buys
            buying_power=_dec(d.get("buying_power")),
            multiplier=str(d.get("multiplier")),
            shorting_enabled=bool(d.get("shorting_enabled")),
            options_level=None if lvl is None else int(lvl),
            trading_blocked=bool(d.get("trading_blocked")),
            account_blocked=bool(d.get("account_blocked")),
            trade_suspended_by_user=bool(d.get("trade_suspended_by_user")),
            status=str(d.get("status") or ""),
            currency=str(d.get("currency") or "USD"),
        )

    def get_account_configuration(self) -> AccountConfig:
        return _config(self._get("/account/configurations"))

    def set_account_configuration(self, **fields: object) -> AccountConfig:
        body = {k: v for k, v in fields.items()}
        return _config(self._call(self._client.patch, "/account/configurations", body))

    def get_positions(self) -> list[Position]:
        rows = self._get("/positions")
        return [
            Position(str(r["symbol"]), _dec(r.get("qty")), _dec(r.get("market_value")),
                     None if r.get("avg_entry_price") is None else _dec(r["avg_entry_price"]))
            for r in rows
        ]

    def get_asset(self, symbol: str) -> AssetInfo:
        d = self._get(f"/assets/{symbol}")
        return AssetInfo(symbol, bool(d.get("tradable")), bool(d.get("fractionable")))

    def get_latest_price(self, symbol: str) -> LatestPrice:
        d = self._call(self._data.get, "/stocks/trades/latest", {"symbols": symbol, "feed": self._feed})
        trade = (d.get("trades") or {}).get(symbol)
        if not trade:
            raise BrokerHTTPError(404, f"no latest trade for {symbol} on feed {self._feed}")
        return LatestPrice(symbol, _dec(trade["p"]), _dt(trade["t"]))

    def get_crypto_whitelist(self) -> list[dict] | None:
        try:
            rows = self._get("/wallets/whitelists")
        except BrokerError as exc:
            log.info("crypto whitelist endpoint unavailable (%s)", type(exc).__name__)
            return None
        return list(rows) if isinstance(rows, list) else None

    # ----------------------------------------------------------------- orders
    def submit_order(
        self,
        symbol: str,
        side: str,
        notional: Decimal | None = None,
        qty: Decimal | None = None,
        *,
        client_order_id: str,
        time_in_force: str = "day",
        order_type: str = "market",
    ) -> Order:
        if (notional is None) == (qty is None):
            raise ValueError("exactly one of notional or qty")
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
            "client_order_id": client_order_id,
        }
        if notional is not None:
            n = Decimal(notional)
            if n != n.quantize(CENT) or order_type != "market" or time_in_force != "day":
                raise ValueError("notional orders must be whole-cent market DAY orders")
            body["notional"] = str(n.quantize(CENT))
        else:
            q = Decimal(qty)  # type: ignore[arg-type]
            if q != q.quantize(Q9):
                raise ValueError("qty has more than 9 decimal places")
            body["qty"] = format(q.normalize(), "f")
        try:
            return _order(self._call(self._client.post, "/orders", body))
        except DuplicateClientOrderId:
            raise DuplicateClientOrderId(client_order_id) from None
        except Exception as exc:
            # The order may have been accepted even though we saw an error (e.g. 504
            # after acceptance, read timeout). Look it up before declaring failure.
            for i in range(3):
                found = None
                try:
                    found = self.get_order_by_client_id(client_order_id)
                except BrokerError:
                    pass
                if found is not None:
                    log.warning("submit of %s raised %s but the order exists at Alpaca; not resubmitting",
                                client_order_id, type(exc).__name__)
                    return found
                if i < 2:
                    self._sleep(1.0)
            raise

    def get_order_by_client_id(self, client_order_id: str) -> Order | None:
        try:
            d = self._get("/orders:by_client_order_id", {"client_order_id": client_order_id})
        except BrokerHTTPError as exc:
            if exc.status == 404:
                return None
            raise
        return _order(d)

    def list_orders(self, status: str = "all", after: datetime | None = None) -> list[Order]:
        out: list[Order] = []
        cursor = after
        for _ in range(20):  # 20 pages x 500 orders: far beyond a monthly strategy
            params: dict[str, Any] = {"status": status, "limit": 500, "direction": "asc", "nested": "false"}
            if cursor is not None:
                params["after"] = cursor.isoformat()
            rows = self._get("/orders", params)
            page = [_order(r) for r in rows]
            out.extend(page)
            if len(page) < 500:
                break
            cursor = page[-1].submitted_at
        seen: dict[str, Order] = {}
        for o in out:
            seen[o.id] = o
        return sorted(seen.values(), key=lambda o: (o.submitted_at, o.id))

    def cancel_order(self, order_id: str) -> None:
        self._call(self._client.delete, f"/orders/{order_id}")

    def get_activities(self, kinds: Sequence[str], after: date | None = None) -> list[Activity]:
        out: list[Activity] = []
        page_token = None
        for _ in range(50):
            params: dict[str, Any] = {"activity_types": ",".join(kinds), "direction": "asc", "page_size": 100}
            if after is not None:
                params["after"] = (after - timedelta(days=1)).isoformat()  # API 'after' is exclusive
            if page_token:
                params["page_token"] = page_token
            rows = self._get("/account/activities", params)
            for r in rows:
                out.append(self._activity(r))
            if len(rows) < 100:
                break
            page_token = rows[-1]["id"]
        return out

    @staticmethod
    def _activity(r: Mapping[str, Any]) -> Activity:
        kind = str(r.get("activity_type"))
        if kind == "FILL":
            qty, px = _dec(r.get("qty")), _dec(r.get("price"))
            return Activity(
                id=str(r["id"]), kind=kind, date=_dt(r["transaction_time"]).astimezone(ET).date(),
                amount=qty * px, symbol=r.get("symbol"), qty=qty, price=px, side=r.get("side"),
                order_id=r.get("order_id"),
            )
        return Activity(
            id=str(r["id"]), kind=kind, date=date.fromisoformat(str(r.get("date"))[:10]),
            amount=_dec(r.get("net_amount")), symbol=r.get("symbol"),
            qty=None if r.get("qty") is None else _dec(r.get("qty")),
            price=None if r.get("per_share_amount") is None else _dec(r.get("per_share_amount")),
            description=str(r.get("description") or ""),
        )
