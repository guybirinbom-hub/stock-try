"""Hard safety guards. Every violation raises ``GuardViolation`` (never a warning).

Each guard maps to a documented loss (docs/research-report.md s.10):
Knight Capital 2012 (no automated caps, runaway orders -> order, daily and
count caps, kill switches), Citigroup 2022 (units-vs-notional field error ->
the units cross-check), duplicated orders from SDK auto-retry (-> idempotent
client_order_id checks), stale or bad data (-> freshness and jump guards).

Units: money Decimal dollars; weights fractions of equity; ``*_FRAC`` are
fractions of account equity (0.25 = 25%); turnover is one-way, i.e.
(buys + sells) / (2 x equity), so a full switch from asset A to asset B is 1.0.

Defaults are deliberately tight for a $1-$100 smoke test. Loosening any limit
requires ``limits_ack == LIMITS_OVERRIDE_ACK`` (checked by ``validate_limits``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Iterable, Mapping, Sequence

from .broker import Account, AccountConfig, CalendarDay, Clock, LatestPrice

if TYPE_CHECKING:  # pragma: no cover
    from .planning import OrderRequest, Plan, PlannedOrder, PriceQuote

__all__ = [
    "GuardViolation",
    "KillSwitchEngaged",
    "ConcurrentRunError",
    "Limits",
    "LIMITS_OVERRIDE_ACK",
    "MAX_ORDER_NOTIONAL_ABS",
    "MAX_ORDER_NOTIONAL_EQUITY_FRAC",
    "MAX_DAILY_NOTIONAL_EQUITY_FRAC",
    "MAX_ORDERS_PER_SYMBOL_PER_RUN",
    "MAX_TURNOVER_ONE_WAY",
    "MIN_ORDER_NOTIONAL",
    "MAX_PRICE_MOVE",
    "WEIGHT_SUM_TOLERANCE",
    "UNITS_TOLERANCE",
    "MAX_CLOCK_SKEW",
    "OPEN_BUFFER",
    "CLOSE_BUFFER",
    "MAX_EXPOSURE_DROP",
    "MAX_LIVE_PRICE_AGE",
    "EQUITY_MISMATCH_TOLERANCE",
    "INITIAL_DEPLOYMENT_MAX_EXPOSURE",
]

# ----------------------------------------------------------------- constants
MAX_ORDER_NOTIONAL_ABS = Decimal("50")  # dollars per order
MAX_ORDER_NOTIONAL_EQUITY_FRAC = Decimal("0.25")  # of equity, per order
MAX_DAILY_NOTIONAL_EQUITY_FRAC = Decimal("0.60")  # of equity, gross buys+sells per ET day
MAX_ORDERS_PER_SYMBOL_PER_RUN = 2  # max orders per run = 2 x number of tradable symbols
MAX_TURNOVER_ONE_WAY = Decimal("1.0")  # (buys + sells) / (2 x equity) per rebalance
MIN_ORDER_NOTIONAL = Decimal("1.00")  # Alpaca fractional minimum, dollars
MAX_PRICE_MOVE = Decimal("0.30")  # |close/prev_close - 1| and |live/close - 1|
WEIGHT_SUM_TOLERANCE = 1e-9
UNITS_TOLERANCE = Decimal("0.01")  # request dollars vs ref_price x qty_est
MAX_CLOCK_SKEW = timedelta(minutes=5)  # broker clock vs local clock
OPEN_BUFFER = timedelta(minutes=30)  # no orders in the first 30 min of a session
CLOSE_BUFFER = timedelta(minutes=30)  # ... nor in the last 30 min (early closes too)
MAX_EXPOSURE_DROP = Decimal("0.5")  # relative drop in risky exposure needing a declaration
MAX_LIVE_PRICE_AGE = timedelta(minutes=15)
EQUITY_MISMATCH_TOLERANCE = Decimal("0.02")
INITIAL_DEPLOYMENT_MAX_EXPOSURE = Decimal("0.01")  # "all cash" means < 1% invested

LIMITS_OVERRIDE_ACK = "I accept larger automated orders than the safety defaults"


class GuardViolation(Exception):
    """A hard block. ``code`` is a short stable identifier used in alerts."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.detail = message


class KillSwitchEngaged(GuardViolation):
    """A kill switch (file, env or broker-side suspend_trade) is engaged."""


class ConcurrentRunError(GuardViolation):
    """Another run holds the local lock for this strategy."""


@dataclass(frozen=True)
class Limits:
    """Tunable hard limits. See module docstring for units."""

    max_order_notional_abs: Decimal = MAX_ORDER_NOTIONAL_ABS
    max_order_notional_frac: Decimal = MAX_ORDER_NOTIONAL_EQUITY_FRAC
    max_daily_notional_frac: Decimal = MAX_DAILY_NOTIONAL_EQUITY_FRAC
    max_orders_per_symbol: int = MAX_ORDERS_PER_SYMBOL_PER_RUN
    max_turnover: Decimal = MAX_TURNOVER_ONE_WAY
    max_weight: float = 1.0
    max_exposure_drop: Decimal = MAX_EXPOSURE_DROP
    max_price_move: Decimal = MAX_PRICE_MOVE

    def loosened(self) -> list[str]:
        """Names of limits that are looser than the defaults."""
        default = Limits()
        out = []
        for f in fields(self):
            if getattr(self, f.name) > getattr(default, f.name):
                out.append(f.name)
        return out

    def order_cap(self, equity: Decimal) -> Decimal:
        """Per-order dollar cap: min(abs cap, frac x equity)."""
        return min(self.max_order_notional_abs, self.max_order_notional_frac * equity)


def validate_limits(limits: Limits, ack: str) -> None:
    loose = limits.loosened()
    if loose and ack != LIMITS_OVERRIDE_ACK:
        raise GuardViolation(
            "limits_override_unacknowledged",
            f"limits {loose} are looser than the defaults; pass the exact acknowledgement string to proceed",
        )


# ------------------------------------------------------------------- account
def check_account(account: Account, config: AccountConfig) -> None:
    """Preflight: cash account, long-only, no options, not blocked or suspended."""
    if config.suspend_trade or account.trade_suspended_by_user:
        raise KillSwitchEngaged("broker_suspend_trade", "broker-side kill switch: trading is suspended by user")
    if account.trading_blocked or account.account_blocked:
        raise GuardViolation("account_blocked", "account is trading_blocked or account_blocked")
    if account.status.upper() != "ACTIVE":
        raise GuardViolation("account_not_active", f"account status is {account.status}")
    try:
        mult_ok = Decimal(account.multiplier) == 1 and Decimal(config.max_margin_multiplier) == 1
    except Exception:
        mult_ok = False
    if not mult_ok:
        raise GuardViolation(
            "margin_enabled",
            f"margin multiplier must be '1' (account={account.multiplier!r}, "
            f"config={config.max_margin_multiplier!r}); run harden_account",
        )
    if account.shorting_enabled or not config.no_shorting:
        raise GuardViolation("shorting_enabled", "shorting must be disabled; run harden_account")
    levels = [account.options_level, config.max_options_trading_level]
    if any(lv is not None and lv > 0 for lv in levels):
        raise GuardViolation("options_enabled", f"options level must be 0 (got {levels}); run harden_account")
    if all(lv is None for lv in levels):
        raise GuardViolation("options_level_unknown", "broker did not report an options level")


def check_crypto_whitelist(entries: Sequence[dict] | None) -> str:
    """Non-empty crypto withdrawal whitelist is a hard block. None = endpoint unavailable."""
    if entries is None:
        return "unavailable"
    if len(entries) > 0:
        raise GuardViolation("crypto_whitelist_not_empty", "crypto withdrawal whitelist has entries")
    return "empty"


# ----------------------------------------------------------------- clock
def check_market_window(
    clock: Clock, session: CalendarDay | None, local_now: datetime
) -> str | None:
    """Return None if orders may be sent now, else a skip reason.

    Raises for a stale/skewed clock or a clock that contradicts the calendar.
    """
    skew = abs(clock.now - local_now)
    if skew > MAX_CLOCK_SKEW:
        raise GuardViolation("stale_clock", f"broker clock differs from local clock by {skew}")
    if not clock.is_open:
        return "market_closed" if session is not None else "no_session_today"
    if session is None:
        raise GuardViolation("clock_calendar_mismatch", "broker says open but calendar has no session today")
    if clock.now < session.open + OPEN_BUFFER:
        return "within_30_min_of_open"
    if clock.now > session.close - CLOSE_BUFFER:
        return "within_30_min_of_close"
    return None


# ----------------------------------------------------------------- inputs
def check_weights(
    targets: Mapping[str, float], universe: Iterable[str], max_weight: float, cash_symbol: str | None
) -> None:
    uni = set(universe)
    if not uni:
        raise GuardViolation("empty_universe", "strategy universe is empty")
    total = 0.0
    for sym, w in targets.items():
        if cash_symbol and sym == cash_symbol:
            raise GuardViolation("cash_symbol_in_targets", f"{sym} is the cash symbol; targets are risky only")
        if sym not in uni:
            raise GuardViolation("symbol_not_in_universe", f"{sym!r} is not in the strategy universe")
        try:
            wf = float(w)
        except (TypeError, ValueError):
            raise GuardViolation("weight_not_numeric", f"weight for {sym} is not a number") from None
        if not math.isfinite(wf):
            raise GuardViolation("weight_not_finite", f"weight for {sym} is {w}")
        if wf < 0:
            raise GuardViolation("negative_weight", f"weight for {sym} is negative ({wf})")
        if wf > max_weight + 1e-12:
            raise GuardViolation("weight_above_max", f"weight for {sym} ({wf}) exceeds max_weight {max_weight}")
        total += wf
    if total > 1.0 + WEIGHT_SUM_TOLERANCE:
        raise GuardViolation("weights_sum_above_one", f"weights sum to {total:.12f} > 1")


def check_positions_whitelist(
    positions: Mapping[str, Decimal], universe: Iterable[str], cash_symbol: str | None
) -> None:
    allowed = set(universe) | ({cash_symbol} if cash_symbol else set())
    foreign = sorted(s for s, q in positions.items() if q != 0 and s not in allowed)
    if foreign:
        raise GuardViolation(
            "position_outside_universe", f"account holds symbols outside the strategy universe: {foreign}"
        )
    shorts = sorted(s for s, q in positions.items() if q < 0)
    if shorts:
        raise GuardViolation("short_position", f"account holds short positions: {shorts}")


def check_price_quotes(
    quotes: Mapping[str, "PriceQuote"],
    symbols: Iterable[str],
    last_session: date,
    corporate_action_symbols: Iterable[str],
    max_move: Decimal,
) -> None:
    ca = set(corporate_action_symbols)
    for sym in sorted(set(symbols)):
        q = quotes.get(sym)
        if q is None:
            raise GuardViolation("price_missing", f"no price for {sym}")
        if not _finite_pos(q.close):
            raise GuardViolation("price_invalid", f"price for {sym} is {q.close!r} (NaN, zero or negative)")
        if q.session is None:
            raise GuardViolation("price_undated", f"price for {sym} has no session date")
        if q.session != last_session:
            raise GuardViolation(
                "price_stale", f"price for {sym} is dated {q.session}, last completed session is {last_session}"
            )
        if not _finite_pos(q.prev_close):
            raise GuardViolation("price_prev_missing", f"no valid previous close for {sym}")
        move = abs(Decimal(repr(q.close)) / Decimal(repr(q.prev_close)) - 1)
        if move > max_move and sym not in ca:
            raise GuardViolation(
                "price_jump", f"{sym} moved {move:.1%} vs previous close; set the corporate-action flag if real"
            )


def check_live_prices(
    live: Mapping[str, LatestPrice],
    quotes: Mapping[str, "PriceQuote"],
    now: datetime,
    corporate_action_symbols: Iterable[str],
    max_move: Decimal,
    max_age: timedelta = MAX_LIVE_PRICE_AGE,
) -> None:
    ca = set(corporate_action_symbols)
    for sym, lp in live.items():
        if not _finite_pos(lp.price):
            raise GuardViolation("live_price_invalid", f"latest price for {sym} is {lp.price!r}")
        if now - lp.timestamp > max_age:
            raise GuardViolation("live_price_stale", f"latest trade for {sym} is older than {max_age}")
        q = quotes.get(sym)
        if q is not None and _finite_pos(q.close):
            move = abs(lp.price / Decimal(repr(q.close)) - 1)
            if move > max_move and sym not in ca:
                raise GuardViolation("live_price_jump", f"{sym} latest price is {move:.1%} away from last close")


def check_equity(computed: Decimal, reported: Decimal) -> None:
    if reported <= 0:
        raise GuardViolation("equity_non_positive", "account equity is zero or negative")
    if abs(computed / reported - 1) > EQUITY_MISMATCH_TOLERANCE:
        raise GuardViolation(
            "equity_mismatch", "equity computed from cash+positions disagrees with the broker by more than 2%"
        )


# ------------------------------------------------------------------- plan
def check_initial_deployment(current_invested_frac: Decimal) -> None:
    if current_invested_frac >= INITIAL_DEPLOYMENT_MAX_EXPOSURE:
        raise GuardViolation(
            "initial_deployment_not_all_cash",
            "initial-deployment carve-out is only valid when the account is all cash",
        )


def check_exposure_drop(plan: "Plan", allow_exit_to_cash: bool, max_drop: Decimal) -> None:
    cur, tgt = plan.current_exposure, plan.target_exposure
    if cur > Decimal("0.05") and (cur - tgt) / cur > max_drop and not allow_exit_to_cash:
        raise GuardViolation(
            "sell_everything_not_declared",
            f"target risky exposure {tgt:.0%} vs current {cur:.0%}; the strategy has not declared exits to cash",
        )


def check_min_notional_feasible(plan: "Plan") -> None:
    if plan.impossible:
        syms = [s.symbol for s in plan.impossible]
        raise GuardViolation(
            "min_notional_impossible_leg",
            f"legs {syms} need a position below the $1 broker minimum; skipping the whole rebalance "
            "(add capital or trade a single-ETF strategy)",
        )


def check_plan_caps(
    legs: Sequence["PlannedOrder"],
    *,
    equity: Decimal,
    limits: Limits,
    already_today: Decimal,
    initial_deployment: bool,
    n_symbols: int,
    orders_so_far: int = 0,
) -> None:
    """Per-order cap, daily gross cap, one-way turnover cap, order-count cap."""
    cap = limits.order_cap(equity)
    for leg in legs:
        if leg.exempt_from_caps:
            continue
        if leg.est_notional > cap:
            raise GuardViolation(
                "max_order_notional",
                f"{leg.side} {leg.symbol} ${leg.est_notional:.2f} exceeds per-order cap ${cap:.2f}",
            )
    if not initial_deployment:
        gross = sum((leg.est_notional for leg in legs if not leg.exempt_from_caps), Decimal(0))
        daily_cap = limits.max_daily_notional_frac * equity
        if already_today + gross > daily_cap:
            raise GuardViolation(
                "max_daily_notional",
                f"today's gross ${already_today + gross:.2f} would exceed daily cap ${daily_cap:.2f}",
            )
        buys = sum((leg.est_notional for leg in legs if leg.side == "buy"), Decimal(0))
        sells = sum((leg.est_notional for leg in legs if leg.side == "sell"), Decimal(0))
        turnover = (buys + sells) / (2 * equity) if equity > 0 else Decimal("Infinity")
        if turnover > limits.max_turnover:
            raise GuardViolation("max_turnover", f"one-way turnover {turnover:.2f} exceeds {limits.max_turnover}")
    max_orders = limits.max_orders_per_symbol * max(n_symbols, 1)
    if orders_so_far + len(legs) > max_orders:
        raise GuardViolation("max_orders_per_run", f"{orders_so_far + len(legs)} orders exceed {max_orders}")


def check_order_request(req: "OrderRequest", leg: "PlannedOrder", held_qty: Decimal) -> None:
    """Units-vs-notional cross-check on the exact request about to be sent."""
    if req.symbol != leg.symbol or req.side != leg.side:
        raise GuardViolation("request_mismatch", "request symbol/side differs from the plan")
    if req.order_type != "market" or req.time_in_force != "day":
        raise GuardViolation("request_type", "only market DAY orders are allowed")
    if len(req.client_order_id) > 128 or not req.client_order_id:
        raise GuardViolation("client_order_id_length", "client_order_id must be 1-128 characters")
    if (req.notional is None) == (req.qty is None):
        raise GuardViolation("units_ambiguous", "exactly one of notional or qty must be set")
    if leg.close_position:
        if req.qty is None or req.side != "sell":
            raise GuardViolation("units_mismatch", "a full exit must be a qty sell")
        if req.qty != held_qty:
            raise GuardViolation("units_mismatch", f"close qty {req.qty} != held qty {held_qty}")
        implied = req.qty * leg.ref_price
    else:
        if req.qty is not None:
            raise GuardViolation("qty_on_notional_leg", "qty passed for a notional leg (units swap?)")
        assert req.notional is not None
        if req.notional < MIN_ORDER_NOTIONAL:
            raise GuardViolation("below_min_notional", f"notional ${req.notional} below $1 minimum")
        if req.notional != req.notional.quantize(Decimal("0.01")):
            raise GuardViolation("notional_precision", "notional must be whole cents")
        implied = req.notional
    expected = leg.ref_price * leg.qty_est
    if expected <= 0 or abs(implied / expected - 1) > UNITS_TOLERANCE:
        raise GuardViolation(
            "units_mismatch",
            f"request implies ${implied:.2f} but plan expects ${expected:.2f} "
            f"({leg.qty_est:.6f} sh x ${leg.ref_price}); units bug suspected",
        )


def _finite_pos(x: object) -> bool:
    if x is None:
        return False
    try:
        f = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f > 0
