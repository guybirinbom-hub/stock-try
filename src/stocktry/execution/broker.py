"""Broker interface shared by the local simulator and the Alpaca adapter.

Units and conventions (apply to every type in this module):

* Money is ``decimal.Decimal`` in US dollars (never cents, never floats).
* Share quantities are ``Decimal`` shares, at most 9 decimal places (Alpaca's
  fractional precision).
* Datetimes are timezone-aware. Broker-facing session times are expressed in
  ``America/New_York``; ``Clock.now`` is whatever the broker reports (any tz).
* Order sides are the strings ``"buy"`` and ``"sell"``; order types and
  time-in-force are lower-case Alpaca strings (``"market"``, ``"day"``).

Nothing in this module performs I/O. Concrete brokers live in
``simbroker.py`` (in-memory, deterministic) and ``alpaca_broker.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import NamedTuple, Protocol, Sequence, runtime_checkable

__all__ = [
    "BUY",
    "SELL",
    "TERMINAL_STATUSES",
    "OPEN_STATUSES",
    "Clock",
    "CalendarDay",
    "Account",
    "AccountConfig",
    "Position",
    "AssetInfo",
    "LatestPrice",
    "Order",
    "Activity",
    "Broker",
    "BrokerError",
    "BrokerTimeout",
    "BrokerHTTPError",
    "DuplicateClientOrderId",
    "OrderRejected",
    "DUPLICATE_CLIENT_ORDER_ID_MESSAGE",
]

BUY = "buy"
SELL = "sell"

#: Alpaca's error text for a reused client_order_id (HTTP 422, code 40010001).
DUPLICATE_CLIENT_ORDER_ID_MESSAGE = "client_order_id must be unique"

#: Order states after which no further fills will arrive *for this order*.
#: ``done_for_day`` is not final in Alpaca's lifecycle (a GTC order could
#: resume next day) but every order this runner sends is DAY, so for a DAY
#: order it is final: the unfilled remainder will never fill.
TERMINAL_STATUSES = frozenset(
    {"filled", "canceled", "expired", "rejected", "done_for_day", "replaced", "stopped", "suspended"}
)
#: Order states that may still produce fills.
OPEN_STATUSES = frozenset(
    {
        "new",
        "accepted",
        "pending_new",
        "partially_filled",
        "pending_cancel",
        "pending_replace",
        "pending_review",
        "accepted_for_bidding",
        "calculated",
        "held",
    }
)


class BrokerError(Exception):
    """Any failure talking to a broker. Messages must never contain secrets."""


class BrokerTimeout(BrokerError):
    """The request timed out; the broker may or may not have acted on it."""


class BrokerHTTPError(BrokerError):
    """An HTTP-level error. ``status`` is the HTTP status code (e.g. 429, 504)."""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(f"HTTP {status}: {message}" if message else f"HTTP {status}")
        self.status = status


class DuplicateClientOrderId(BrokerError):
    """The broker already holds an order with this client_order_id."""

    def __init__(self, client_order_id: str) -> None:
        super().__init__(f"{DUPLICATE_CLIENT_ORDER_ID_MESSAGE}: {client_order_id}")
        self.client_order_id = client_order_id


class OrderRejected(BrokerError):
    """The broker refused the order synchronously (no order was created)."""


class Clock(NamedTuple):
    """Market clock as reported by the broker.

    ``now`` is the broker's timestamp, ``next_open``/``next_close`` are the next
    regular-session boundaries. All tz-aware.
    """

    is_open: bool
    next_open: datetime
    next_close: datetime
    now: datetime


class CalendarDay(NamedTuple):
    """One regular trading session. ``open``/``close`` are tz-aware (ET).

    Early-close days carry the early close time (e.g. 13:00 ET).
    """

    date: date
    open: datetime
    close: datetime


@dataclass(frozen=True)
class Account:
    """Subset of Alpaca's account object needed for safety checks and sizing.

    All money fields are Decimal dollars. The broker account *number* and id are
    deliberately not carried, so they cannot leak into logs or the ledger.
    ``multiplier`` is Alpaca's string (``"1"`` for a cash account).
    ``options_level`` is the effective options trading level (None = unknown).
    """

    cash: Decimal
    equity: Decimal
    non_marginable_buying_power: Decimal
    buying_power: Decimal
    multiplier: str
    shorting_enabled: bool
    options_level: int | None
    trading_blocked: bool
    account_blocked: bool
    trade_suspended_by_user: bool
    status: str = "ACTIVE"
    currency: str = "USD"


@dataclass(frozen=True)
class AccountConfig:
    """Alpaca account configuration (``/v2/account/configurations``).

    ``disable_overnight_trading`` is ``None`` when the broker does not report it.
    """

    max_margin_multiplier: str
    no_shorting: bool
    max_options_trading_level: int | None
    suspend_trade: bool
    trade_confirm_email: str
    fractional_trading: bool
    disable_overnight_trading: bool | None = None


@dataclass(frozen=True)
class Position:
    """A long position. ``qty`` in shares (<= 9 dp); ``market_value`` dollars."""

    symbol: str
    qty: Decimal
    market_value: Decimal
    avg_entry_price: Decimal | None = None


class AssetInfo(NamedTuple):
    """Tradability flags for a symbol."""

    symbol: str
    tradable: bool
    fractionable: bool


class LatestPrice(NamedTuple):
    """Most recent trade price in dollars per share, with its timestamp."""

    symbol: str
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Order:
    """A broker order. Exactly one of ``notional`` (dollars) or ``qty`` (shares)
    was requested. ``filled_qty`` shares at ``filled_avg_price`` dollars/share."""

    id: str
    client_order_id: str
    symbol: str
    side: str
    status: str
    submitted_at: datetime
    notional: Decimal | None = None
    qty: Decimal | None = None
    filled_qty: Decimal = Decimal("0")
    filled_avg_price: Decimal | None = None
    time_in_force: str = "day"
    order_type: str = "market"

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def filled_notional(self) -> Decimal:
        """Dollars actually traded (filled_qty * filled_avg_price)."""
        if self.filled_avg_price is None:
            return Decimal("0")
        return self.filled_qty * self.filled_avg_price

    @property
    def requested_notional_estimate(self) -> Decimal:
        """Requested dollars: notional if given, else qty * avg fill price (or 0)."""
        if self.notional is not None:
            return self.notional
        if self.qty is not None and self.filled_avg_price is not None:
            return self.qty * self.filled_avg_price
        return self.filled_notional


@dataclass(frozen=True)
class Activity:
    """Account activity used for reconciliation.

    ``kind`` is the Alpaca activity type (``FILL``, ``FEE``, ``DIV``...).
    ``amount`` is signed dollars for cash activities (fees negative, dividends
    positive); for fills it is the traded dollars (qty * price, unsigned).
    """

    id: str
    kind: str
    date: date
    amount: Decimal
    symbol: str | None = None
    qty: Decimal | None = None
    price: Decimal | None = None
    side: str | None = None
    order_id: str | None = None
    description: str = ""
    extra: dict = field(default_factory=dict)


@runtime_checkable
class Broker(Protocol):
    """What the rebalance runner needs from a broker.

    Implementations must be safe to call repeatedly: every read is idempotent,
    and ``submit_order`` must honour client_order_id uniqueness (raise
    ``DuplicateClientOrderId`` when the id already exists).
    """

    #: True only for a broker connected to real money.
    is_live: bool
    #: Short label for logs and the ledger ("sim", "alpaca-paper", "alpaca-live").
    name: str

    def get_clock(self) -> Clock: ...

    def get_calendar(self, start: date, end: date) -> list[CalendarDay]: ...

    def get_account(self) -> Account: ...

    def get_account_configuration(self) -> AccountConfig: ...

    def set_account_configuration(self, **fields: object) -> AccountConfig: ...

    def get_positions(self) -> list[Position]: ...

    def get_asset(self, symbol: str) -> AssetInfo: ...

    def get_latest_price(self, symbol: str) -> LatestPrice: ...

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
    ) -> Order: ...

    def get_order_by_client_id(self, client_order_id: str) -> Order | None: ...

    def list_orders(self, status: str = "all", after: datetime | None = None) -> list[Order]: ...

    def cancel_order(self, order_id: str) -> None: ...

    def get_activities(self, kinds: Sequence[str], after: date | None = None) -> list[Activity]: ...

    def get_crypto_whitelist(self) -> list[dict] | None:
        """Crypto withdrawal whitelist entries, or None if the endpoint is unavailable."""
        ...
