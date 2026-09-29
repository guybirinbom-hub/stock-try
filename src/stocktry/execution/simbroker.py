"""In-memory deterministic broker for tests and for owners without a paper API.

Behaviour mirrors the Alpaca rules the runner depends on:

* Fractional quantities to 9 decimal places; notional orders need a
  fractionable asset, ``market`` type and ``day`` time-in-force and at most 2
  decimal places. A notional **buy** must be at least $1.00 (Alpaca's minimum
  for buy entry orders); a notional sell at least $0.01.
* ``client_order_id`` must be unique (``DuplicateClientOrderId`` carries
  Alpaca's text ``client_order_id must be unique``), max 128 characters.
* No shorting and no margin: sells are limited to the held quantity and buys
  to ``non_marginable_buying_power`` = cash minus what open buy orders have
  reserved (as Alpaca does).
* A ``stopped`` order (a trade is guaranteed but has not happened yet) is open
  and cannot be cancelled.
* A market order submitted while the market is closed is *accepted* and left
  unfilled (Alpaca queues it for the next open). The runner's market-hours gate
  exists to make sure that never happens.
* Fills happen at the configured price map, adjusted by ``slippage_bp`` basis
  points against the trader, at submission time.
* Alpaca's regulatory fee model (per day, per fee type, rounded up to $0.01)
  is deducted from cash when ``fee_schedule`` is set (default). Set it to None
  to mimic Alpaca *paper*, which does not charge fees.

Failure injection for tests: submits that raise a 504 or time out *after* the
order was recorded (the duplicate-order hazard), timeouts before recording,
429s, lookup timeouts, stale clocks, scripted or seeded random partial fills.
All randomness comes from ``random.Random(seed)``.
"""

from __future__ import annotations

import random
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, fields, replace
from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Callable, Mapping, Sequence

from .broker import (
    OPEN_STATUSES,
    Account,
    AccountConfig,
    Activity,
    AssetInfo,
    BrokerHTTPError,
    BrokerTimeout,
    CalendarDay,
    Clock,
    DuplicateClientOrderId,
    LatestPrice,
    Order,
    OrderRejected,
    Position,
)
from .fees import DEFAULT_SCHEDULE, AlpacaFeeSchedule, FeeFill, daily_fees
from .sessions import ET, MAX_CLIENT_ORDER_ID_LEN, session_on, sim_nyse_calendar

__all__ = ["LocalSimBroker", "HARDENED_CONFIG", "SUBMIT_FAILURE_MODES"]

Q9 = Decimal("0.000000001")
CENT = Decimal("0.01")

HARDENED_CONFIG = AccountConfig(
    max_margin_multiplier="1",
    no_shorting=True,
    max_options_trading_level=0,
    suspend_trade=False,
    trade_confirm_email="all",
    fractional_trading=True,
    disable_overnight_trading=True,
)

#: Open states the simulator refuses to cancel: a ``stopped`` order has a guaranteed trade pending.
NON_CANCELABLE_STATUSES = frozenset({"stopped", "pending_cancel"})

SUBMIT_FAILURE_MODES = frozenset(
    {"http_504_after_record", "timeout_after_record", "timeout_before_record", "http_429_before_record"}
)


@dataclass
class _SimOrder:
    order: Order
    polls_until_final: int = 0
    final_status: str | None = None


def _dec(x: object) -> Decimal:
    return x if isinstance(x, Decimal) else Decimal(str(x))


class LocalSimBroker:
    """Deterministic in-memory broker. Thread-safe (one re-entrant lock)."""

    is_live = False
    name = "sim"

    def __init__(
        self,
        *,
        cash: Decimal | float,
        prices: Mapping[str, Decimal | float],
        now: datetime,
        positions: Mapping[str, Decimal | float] | None = None,
        calendar: Sequence[CalendarDay] | None = None,
        slippage_bp: float = 0.0,
        partial_fill_prob: float = 0.0,
        partial_fill_range: tuple[float, float] = (0.3, 0.9),
        scripted_fill_fractions: Mapping[str, Sequence[float]] | None = None,
        partial_final_status: str | None = "done_for_day",
        partial_polls: int = 1,
        seed: int = 0,
        fee_schedule: AlpacaFeeSchedule | None = DEFAULT_SCHEDULE,
        config: AccountConfig = HARDENED_CONFIG,
        assets: Mapping[str, AssetInfo] | None = None,
        crypto_whitelist: list[dict] | None = None,
    ) -> None:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        self._lock = threading.RLock()
        self._now = now
        self._stale = timedelta(0)
        self.cash = _dec(cash)
        self.prices: dict[str, Decimal] = {s: _dec(p) for s, p in prices.items()}
        self.positions: dict[str, Decimal] = {
            s: _dec(q).quantize(Q9, rounding=ROUND_DOWN) for s, q in (positions or {}).items() if _dec(q) > 0
        }
        if calendar is None:
            local = now.astimezone(ET).date()
            start = max(date(2024, 1, 1), local - timedelta(days=400))
            end = min(date(2027, 12, 31), local + timedelta(days=120))
            calendar = sim_nyse_calendar(start, end)
        self._calendar = list(calendar)
        self.slippage_bp = float(slippage_bp)
        self.partial_fill_prob = float(partial_fill_prob)
        self.partial_fill_range = partial_fill_range
        self._scripted = {s: deque(v) for s, v in (scripted_fill_fractions or {}).items()}
        self.partial_final_status = partial_final_status
        self.partial_polls = int(partial_polls)
        self._rng = random.Random(seed)
        self.fee_schedule = fee_schedule
        self.config = config
        self._assets = dict(assets or {})
        self.crypto_whitelist: list[dict] | None = [] if crypto_whitelist is None else crypto_whitelist
        self.trading_blocked = False
        self.account_blocked = False
        self._orders: dict[str, _SimOrder] = {}
        self._by_cid: dict[str, str] = {}
        self._fills: list[FeeFill] = []
        self._fees_charged: dict[tuple[date, str], Decimal] = defaultdict(lambda: Decimal(0))
        self._activities: list[Activity] = []
        self._failures: dict[str, deque[str]] = defaultdict(deque)
        self._seq = 0
        self.submit_calls = 0
        self.before_submit_hook: Callable[[str], None] | None = None
        self.before_lookup_hook: Callable[[str], None] | None = None

    # ----------------------------------------------------------- test controls
    @property
    def now(self) -> datetime:
        return self._now

    def set_now(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        with self._lock:
            self._now = now

    def advance(self, delta: timedelta) -> None:
        with self._lock:
            self._now = self._now + delta

    def set_prices(self, prices: Mapping[str, Decimal | float]) -> None:
        with self._lock:
            self.prices.update({s: _dec(p) for s, p in prices.items()})

    def inject_failure(self, op: str, mode: str, times: int = 1) -> None:
        """Queue ``times`` failures of ``mode`` for operation ``op``.

        ``op="submit"``: modes in ``SUBMIT_FAILURE_MODES``. Other ops
        (``get_order_by_client_id``, ``list_orders``, ``get_clock``,
        ``get_account``, ``get_latest_price``, ``get_positions``): ``timeout``
        or ``http_500``.
        """
        if op == "submit" and mode not in SUBMIT_FAILURE_MODES:
            raise ValueError(f"unknown submit failure mode {mode!r}")
        with self._lock:
            self._failures[op].extend([mode] * times)

    def inject_stale_clock(self, delta: timedelta) -> None:
        """Make get_clock() report a timestamp ``delta`` in the past."""
        self._stale = delta

    def credit_dividend(self, symbol: str, per_share: Decimal | float, day: date) -> Decimal:
        """Pay a cash dividend, rounded to the nearest cent as Alpaca does."""
        with self._lock:
            qty = self.positions.get(symbol, Decimal(0))
            amount = (qty * _dec(per_share)).quantize(CENT, rounding=ROUND_HALF_UP)
            self.cash += amount
            self._seq += 1
            self._activities.append(
                Activity(id=f"act-{self._seq:06d}", kind="DIV", date=day, amount=amount, symbol=symbol, qty=qty,
                         price=_dec(per_share), description="sim dividend")
            )
            return amount

    @property
    def orders(self) -> list[Order]:
        with self._lock:
            return [so.order for so in self._orders.values()]

    def _maybe_fail(self, op: str) -> None:
        with self._lock:
            mode = self._failures[op].popleft() if self._failures[op] else None
        if mode == "timeout":
            raise BrokerTimeout(f"simulated timeout in {op}")
        if mode == "http_500":
            raise BrokerHTTPError(500, f"simulated error in {op}")

    # ------------------------------------------------------------ market data
    def _market_open_at(self, t: datetime) -> CalendarDay | None:
        s = session_on(self._calendar, t.astimezone(ET).date())
        if s is not None and s.open <= t < s.close:
            return s
        return None

    def get_clock(self) -> Clock:
        self._maybe_fail("get_clock")
        t = self._now - self._stale
        s = self._market_open_at(t)
        future = [c for c in self._calendar if c.close > t]
        if not future:
            raise BrokerHTTPError(500, "sim calendar exhausted")
        if s is not None:
            nxt = [c for c in self._calendar if c.open > t]
            next_open = nxt[0].open if nxt else s.open + timedelta(days=1)
            return Clock(True, next_open, s.close, t)
        nxt = [c for c in self._calendar if c.open > t]
        return Clock(False, nxt[0].open, nxt[0].close, t)

    def get_calendar(self, start: date, end: date) -> list[CalendarDay]:
        return [c for c in self._calendar if start <= c.date <= end]

    def get_latest_price(self, symbol: str) -> LatestPrice:
        self._maybe_fail("get_latest_price")
        with self._lock:
            if symbol not in self.prices:
                raise BrokerHTTPError(404, f"no price for {symbol}")
            return LatestPrice(symbol, self.prices[symbol], self._now)

    # ---------------------------------------------------------------- account
    def _equity(self) -> Decimal:
        return self.cash + sum((q * self.prices[s] for s, q in self.positions.items()), Decimal(0))

    def _reserved_for_open_buys(self) -> Decimal:
        """Dollars still committed to open buy orders (Alpaca deducts them from buying power)."""
        out = Decimal(0)
        for so in self._orders.values():
            o = so.order
            if o.side != "buy" or o.status not in OPEN_STATUSES:
                continue
            if o.notional is not None:
                out += max(o.notional - o.filled_notional, Decimal(0))
            elif o.qty is not None:
                out += max(o.qty - o.filled_qty, Decimal(0)) * self.prices.get(o.symbol, Decimal(0))
        return out

    def get_account(self) -> Account:
        self._maybe_fail("get_account")
        with self._lock:
            mult = Decimal(self.config.max_margin_multiplier)
            available = max(self.cash - self._reserved_for_open_buys(), Decimal(0))
            return Account(
                cash=self.cash,
                equity=self._equity(),
                non_marginable_buying_power=available,
                buying_power=available * mult,
                multiplier=self.config.max_margin_multiplier,
                shorting_enabled=not self.config.no_shorting,
                options_level=self.config.max_options_trading_level,
                trading_blocked=self.trading_blocked,
                account_blocked=self.account_blocked,
                trade_suspended_by_user=self.config.suspend_trade,
            )

    def get_account_configuration(self) -> AccountConfig:
        with self._lock:
            return self.config

    def set_account_configuration(self, **new: object) -> AccountConfig:
        allowed = {f.name for f in fields(AccountConfig)}
        unknown = set(new) - allowed
        if unknown:
            raise BrokerHTTPError(422, f"unknown configuration fields: {sorted(unknown)}")
        with self._lock:
            self.config = replace(self.config, **new)  # type: ignore[arg-type]
            return self.config

    def get_positions(self) -> list[Position]:
        self._maybe_fail("get_positions")
        with self._lock:
            return [
                Position(s, q, q * self.prices[s]) for s, q in sorted(self.positions.items()) if q > 0
            ]

    def get_asset(self, symbol: str) -> AssetInfo:
        if symbol in self._assets:
            return self._assets[symbol]
        if symbol not in self.prices:
            raise BrokerHTTPError(404, f"asset not found: {symbol}")
        return AssetInfo(symbol, True, True)

    def get_crypto_whitelist(self) -> list[dict] | None:
        return None if self.crypto_whitelist is None else list(self.crypto_whitelist)

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
        with self._lock:
            self.submit_calls += 1
        if self.before_submit_hook is not None:
            self.before_submit_hook(client_order_id)
        with self._lock:
            mode = self._failures["submit"].popleft() if self._failures["submit"] else None
        if mode == "timeout_before_record":
            raise BrokerTimeout("simulated timeout before the order reached the broker")
        if mode == "http_429_before_record":
            raise BrokerHTTPError(429, "too many requests")
        with self._lock:
            order = self._accept(symbol, side, notional, qty, client_order_id, time_in_force, order_type)
        if mode == "http_504_after_record":
            raise BrokerHTTPError(504, "Gateway Time-out")
        if mode == "timeout_after_record":
            raise BrokerTimeout("simulated read timeout after the order was recorded")
        return order

    def _accept(
        self,
        symbol: str,
        side: str,
        notional: Decimal | None,
        qty: Decimal | None,
        cid: str,
        tif: str,
        otype: str,
    ) -> Order:
        if self.trading_blocked or self.account_blocked or self.config.suspend_trade:
            raise OrderRejected("account is not allowed to trade")
        if not cid or len(cid) > MAX_CLIENT_ORDER_ID_LEN:
            raise OrderRejected("client_order_id must be 1-128 characters")
        if cid in self._by_cid:
            raise DuplicateClientOrderId(cid)
        if side not in ("buy", "sell"):
            raise OrderRejected(f"invalid side {side!r}")
        if (notional is None) == (qty is None):
            raise OrderRejected("exactly one of qty or notional is required")
        if symbol not in self.prices:
            raise OrderRejected(f"asset {symbol} not found")
        asset = self.get_asset(symbol)
        if not asset.tradable:
            raise OrderRejected(f"asset {symbol} is not tradable")
        if otype != "market":
            raise OrderRejected("simulator supports market orders only")
        if notional is not None:
            notional = _dec(notional)
            if not asset.fractionable:
                raise OrderRejected(f"asset {symbol} is not fractionable")
            if tif != "day":
                raise OrderRejected("notional orders must be DAY orders")
            if side == "buy" and notional < Decimal("1"):
                raise OrderRejected("buy order notional must be >= 1.00")
            if notional < CENT:
                raise OrderRejected("order notional must be >= 0.01")
            if notional != notional.quantize(CENT):
                raise OrderRejected("notional must have at most 2 decimal places")
        else:
            qty = _dec(qty)
            if qty <= 0:
                raise OrderRejected("qty must be > 0")
            if qty != qty.quantize(Q9):
                raise OrderRejected("qty must have at most 9 decimal places")
            if qty != qty.to_integral_value() and (not asset.fractionable or tif != "day"):
                raise OrderRejected("fractional qty orders must be DAY orders on fractionable assets")

        px = self.prices[symbol]
        slip = Decimal(str(self.slippage_bp)) / Decimal(10000)
        fill_px = px * (1 + slip) if side == "buy" else px * (1 - slip)
        if notional is not None:
            total_qty = (notional / fill_px).quantize(Q9, rounding=ROUND_DOWN)
        else:
            assert qty is not None
            total_qty = qty
        held = self.positions.get(symbol, Decimal(0))
        if side == "sell" and total_qty > held:
            raise OrderRejected("insufficient qty available for order")
        if side == "buy" and total_qty * fill_px > self.cash - self._reserved_for_open_buys():
            raise OrderRejected("insufficient buying power")

        self._seq += 1
        oid = f"sim-{self._seq:06d}"
        order = Order(
            id=oid, client_order_id=cid, symbol=symbol, side=side, status="new", submitted_at=self._now,
            notional=notional, qty=None if notional is not None else qty, time_in_force=tif, order_type=otype,
        )
        so = _SimOrder(order)
        self._orders[oid] = so
        self._by_cid[cid] = oid

        if self._market_open_at(self._now) is None:
            so.order = replace(order, status="accepted")  # queued for next open; never filled here
            return so.order

        frac = 1.0
        if symbol in self._scripted and self._scripted[symbol]:
            frac = float(self._scripted[symbol].popleft())
        elif self.partial_fill_prob > 0 and self._rng.random() < self.partial_fill_prob:
            lo, hi = self.partial_fill_range
            frac = self._rng.uniform(lo, hi)
        fill_qty = (total_qty * Decimal(str(frac))).quantize(Q9, rounding=ROUND_DOWN)
        if fill_qty > 0:
            self._apply_fill(symbol, side, fill_qty, fill_px, oid)
        if frac >= 1.0:
            so.order = replace(order, status="filled", filled_qty=fill_qty, filled_avg_price=fill_px)
        else:
            so.order = replace(
                order, status="partially_filled", filled_qty=fill_qty,
                filled_avg_price=fill_px if fill_qty > 0 else None,
            )
            so.polls_until_final = self.partial_polls
            so.final_status = self.partial_final_status
        return so.order

    def _apply_fill(self, symbol: str, side: str, qty: Decimal, px: Decimal, oid: str) -> None:
        day = self._now.astimezone(ET).date()
        if side == "buy":
            self.cash -= qty * px
            self.positions[symbol] = self.positions.get(symbol, Decimal(0)) + qty
        else:
            self.cash += qty * px
            left = self.positions.get(symbol, Decimal(0)) - qty
            if left > 0:
                self.positions[symbol] = left
            else:
                self.positions.pop(symbol, None)
        self._fills.append(FeeFill(day, side, qty, px))
        self._seq += 1
        self._activities.append(
            Activity(id=f"act-{self._seq:06d}", kind="FILL", date=day, amount=qty * px, symbol=symbol, qty=qty,
                     price=px, side=side, order_id=oid)
        )
        if self.fee_schedule is not None:
            todays = [f for f in self._fills if f.day == day]
            totals = daily_fees(todays, self.fee_schedule).get(day, {})
            for ftype in ("sec", "taf", "cat"):
                inc = totals.get(ftype, Decimal(0)) - self._fees_charged[(day, ftype)]
                if inc > 0:
                    self._fees_charged[(day, ftype)] += inc
                    self.cash -= inc
                    self._seq += 1
                    self._activities.append(
                        Activity(id=f"act-{self._seq:06d}", kind="FEE", date=day, amount=-inc,
                                 description=f"{ftype} fee")
                    )

    def _tick(self, so: _SimOrder) -> None:
        if so.order.status == "partially_filled" and so.final_status is not None:
            so.polls_until_final -= 1
            if so.polls_until_final <= 0:
                so.order = replace(so.order, status=so.final_status)

    def get_order_by_client_id(self, client_order_id: str) -> Order | None:
        if self.before_lookup_hook is not None:
            self.before_lookup_hook(client_order_id)
        self._maybe_fail("get_order_by_client_id")
        with self._lock:
            oid = self._by_cid.get(client_order_id)
            if oid is None:
                return None
            so = self._orders[oid]
            self._tick(so)
            return so.order

    def list_orders(self, status: str = "all", after: datetime | None = None) -> list[Order]:
        self._maybe_fail("list_orders")
        with self._lock:
            out = []
            for so in self._orders.values():
                o = so.order
                if after is not None and o.submitted_at <= after:
                    continue
                if status == "open" and o.status not in OPEN_STATUSES:
                    continue
                if status == "closed" and o.status in OPEN_STATUSES:
                    continue
                out.append(o)
            return sorted(out, key=lambda o: (o.submitted_at, o.id))

    def cancel_order(self, order_id: str) -> None:
        with self._lock:
            so = self._orders.get(order_id)
            if so is None:
                raise BrokerHTTPError(404, "order not found")
            if so.order.status not in OPEN_STATUSES or so.order.status in NON_CANCELABLE_STATUSES:
                raise OrderRejected("order is not cancelable")
            so.order = replace(so.order, status="canceled")

    def get_activities(self, kinds: Sequence[str], after: date | None = None) -> list[Activity]:
        """Activities of the given kinds dated on or after ``after``."""
        wanted = {k.upper() for k in kinds}
        with self._lock:
            return [a for a in self._activities if a.kind in wanted and (after is None or a.date >= after)]
