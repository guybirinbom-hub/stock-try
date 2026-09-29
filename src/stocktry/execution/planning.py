"""Pure order planning: targets + holdings + prices -> order legs.

Nothing here does I/O. Units: weights are fractions of account equity
(0.25 = 25%); money is Decimal dollars; quantities are Decimal shares.

Rules
-----
* Targets are for risky symbols only; the remainder is cash. When the strategy
  names a ``cash_symbol`` (e.g. BIL) the remainder is bought in it instead.
* Alpaca's $1 minimum applies to **buy** entry orders only. A buy leg below
  $1 is skipped (left as drift) and recorded. A *new* position whose whole
  target value is below $1 cannot be established at all; that is an
  "impossible leg" and the runner aborts the whole rebalance rather than trade
  a distorted portfolio.
* Sells have no dollar minimum. A partial sell (trim) is a notional order in
  whole cents, sent when it rounds down to at least $0.01. Full exits (target
  weight 0 for a held symbol) sell the exact held quantity (``qty``) of any
  size, because a notional sell of the full value is rejected whenever the
  price ticks down before the fill. Every other leg is notional (dollars) with
  no ``qty``. (Same rule as the backtest engine.)
* Buys are funded only from ``min(cash, non_marginable_buying_power)`` minus a
  small cash buffer for fees; if the planned buys exceed that, they are scaled
  down pro rata. ``buying_power`` (which includes margin) is never used.
* ``qty_est`` is computed independently of the request's notional, from the
  intended dollar change divided by the reference price. The units guard
  compares the two, which catches qty/notional swaps and cents/dollars bugs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Mapping

__all__ = [
    "PriceQuote",
    "coerce_quotes",
    "quotes_from_frame",
    "PlannedOrder",
    "SkippedLeg",
    "Plan",
    "OrderRequest",
    "full_targets",
    "plan_rebalance",
    "build_order_request",
    "format_plan",
]

CENT = Decimal("0.01")
Q9 = Decimal("0.000000001")


@dataclass(frozen=True)
class PriceQuote:
    """A daily close in dollars/share, dated by its session.

    ``close`` is the close of ``session`` (for back-adjusted data the latest
    adjusted close equals the raw close). ``prev_close`` is the previous
    session's close on the same adjustment basis, used by the 30% move guard.
    ``session`` None means undated, which the freshness guard refuses.
    """

    close: float
    session: date | None
    prev_close: float | None = None


def coerce_quotes(prices: Mapping[str, object]) -> dict[str, PriceQuote]:
    """Accept PriceQuote, dict(close, session, prev_close) or bare float.

    A bare float becomes an *undated* quote, which the guards then refuse:
    freshness cannot be verified without a session date.
    """
    out: dict[str, PriceQuote] = {}
    for sym, v in prices.items():
        if isinstance(v, PriceQuote):
            out[sym] = v
        elif isinstance(v, Mapping):
            sess = v.get("session")
            if isinstance(sess, str):
                sess = date.fromisoformat(sess)
            prev = v.get("prev_close")
            out[sym] = PriceQuote(float(v["close"]), sess, None if prev is None else float(prev))
        else:
            out[sym] = PriceQuote(float(v), None, None)  # type: ignore[arg-type]
    return out


def quotes_from_frame(frame, session: date) -> dict[str, PriceQuote]:
    """Quotes from a wide close frame (columns = symbols, DatetimeIndex).

    Rows after ``session`` are ignored (so a partial intraday bar for today is
    never used). Each quote carries the date of that symbol's last valid close
    at or before ``session``; if that date is older than ``session`` the
    freshness guard will refuse it.
    """
    import pandas as pd  # local import: pandas is only needed on this path

    upto = frame.loc[: pd.Timestamp(session)]
    out: dict[str, PriceQuote] = {}
    for sym in upto.columns:
        s = upto[sym].dropna()
        if s.empty:
            out[sym] = PriceQuote(float("nan"), None, None)
            continue
        last_ts = s.index[-1]
        prev = float(s.iloc[-2]) if len(s) >= 2 else None
        out[sym] = PriceQuote(float(s.iloc[-1]), last_ts.date(), prev)
    return out


@dataclass(frozen=True)
class PlannedOrder:
    """One intended order.

    ``notional`` dollars (cents) for notional legs, else None.
    ``qty`` shares only for full-exit sells (``close_position``), else None.
    ``qty_est`` shares = intended dollars / ``ref_price`` (independent check).
    ``exempt_from_caps`` is True only for risk-reducing legs of a strategy that
    declared exits to cash allowed (full-exit sells, cash-symbol buys).
    """

    symbol: str
    side: str
    notional: Decimal | None
    qty: Decimal | None
    qty_est: Decimal
    ref_price: Decimal
    target_weight: float
    current_value: Decimal
    target_value: Decimal
    close_position: bool = False
    exempt_from_caps: bool = False

    @property
    def est_notional(self) -> Decimal:
        """Dollars this leg is expected to trade."""
        if self.notional is not None:
            return self.notional
        return (self.qty or Decimal(0)) * self.ref_price


@dataclass(frozen=True)
class SkippedLeg:
    symbol: str
    side: str
    amount: Decimal  # dollars
    reason: str


@dataclass(frozen=True)
class Plan:
    sells: list[PlannedOrder] = field(default_factory=list)
    buys: list[PlannedOrder] = field(default_factory=list)
    skipped: list[SkippedLeg] = field(default_factory=list)
    impossible: list[SkippedLeg] = field(default_factory=list)
    equity: Decimal = Decimal(0)
    current_exposure: Decimal = Decimal(0)  # risky MV / equity (excludes cash symbol)
    target_exposure: Decimal = Decimal(0)  # sum of risky target weights

    @property
    def legs(self) -> list[PlannedOrder]:
        return [*self.sells, *self.buys]


@dataclass(frozen=True)
class OrderRequest:
    """What is sent to the broker. Exactly one of notional (dollars) / qty (shares)."""

    symbol: str
    side: str
    client_order_id: str
    notional: Decimal | None = None
    qty: Decimal | None = None
    time_in_force: str = "day"
    order_type: str = "market"


def full_targets(targets: Mapping[str, float], cash_symbol: str | None) -> dict[str, float]:
    """Risky targets plus, if a cash symbol is used, the cash remainder in it."""
    full = {s: float(w) for s, w in targets.items()}
    if cash_symbol:
        rem = 1.0 - sum(full.values())
        full[cash_symbol] = max(0.0, rem) if rem > 1e-12 else 0.0
    return full


def _down(x: Decimal, q: Decimal = CENT) -> Decimal:
    return x.quantize(q, rounding=ROUND_DOWN)


def plan_rebalance(
    *,
    targets: Mapping[str, float],
    positions: Mapping[str, Decimal],
    prices: Mapping[str, Decimal],
    equity: Decimal,
    cash_available: Decimal,
    cash_buffer: Decimal,
    min_notional: Decimal,
    cash_symbol: str | None = None,
    allow_exit_to_cash: bool = False,
    sides: tuple[str, ...] = ("sell", "buy"),
    min_sell_notional: Decimal = CENT,
) -> Plan:
    """Compute order legs.

    ``positions`` shares by symbol; ``prices`` dollars/share (reference prices);
    ``equity`` dollars used to turn weights into target values;
    ``cash_available`` = min(cash, non_marginable_buying_power) *before* the
    sells of this plan fill (the planned sell proceeds are added for buys).
    ``min_notional`` is the minimum *buy*; ``min_sell_notional`` (one cent) the
    smallest partial sell. Full exits have no minimum.
    """
    tgt_full = full_targets(targets, cash_symbol)
    symbols = sorted(set(tgt_full) | {s for s, q in positions.items() if q > 0})
    sells: list[PlannedOrder] = []
    buys_raw: list[tuple[str, Decimal, Decimal, Decimal, float, Decimal]] = []
    skipped: list[SkippedLeg] = []
    impossible: list[SkippedLeg] = []

    risky_mv = Decimal(0)
    for sym in symbols:
        q = positions.get(sym, Decimal(0))
        if sym != cash_symbol and q > 0:
            risky_mv += q * prices[sym]

    for sym in symbols:
        q = positions.get(sym, Decimal(0))
        w = tgt_full.get(sym, 0.0)
        if w == 0.0 and q <= 0:
            continue  # nothing held, nothing wanted: no price needed
        px = prices[sym]
        cur = q * px
        tgt = Decimal(repr(w)) * equity
        delta = tgt - cur
        if delta < 0 and "sell" in sides:
            if w == 0.0 and q > 0:
                # full exit: a quantity sell of the whole position, any size (no minimum on sells)
                sells.append(
                    PlannedOrder(sym, "sell", None, q, q, px, w, cur, tgt, close_position=True,
                                 exempt_from_caps=allow_exit_to_cash)
                )
            elif _down(-delta) >= min_sell_notional:
                sells.append(PlannedOrder(sym, "sell", _down(-delta), None, -delta / px, px, w, cur, tgt))
            else:
                skipped.append(SkippedLeg(sym, "sell", _down(-delta), "below_one_cent"))
        elif delta > 0 and "buy" in sides:
            if q == 0 and w > 0 and tgt < min_notional:
                impossible.append(SkippedLeg(sym, "buy", _down(tgt), "target_value_below_min_notional"))
            elif delta >= min_notional:
                buys_raw.append((sym, delta, px, cur, w, tgt))
            else:
                skipped.append(SkippedLeg(sym, "buy", _down(delta), "below_min_notional"))  # $1 buy minimum

    sell_proceeds = sum((s.est_notional for s in sells), Decimal(0))
    budget = cash_available + sell_proceeds - cash_buffer
    wanted = sum((d for _, d, *_ in buys_raw), Decimal(0))
    factor = Decimal(1)
    if wanted > 0 and wanted > budget:
        factor = max(budget, Decimal(0)) / wanted
    buys: list[PlannedOrder] = []
    for sym, delta, px, cur, w, tgt in buys_raw:
        intended = delta * factor
        notional = _down(intended)
        if notional < min_notional:
            skipped.append(SkippedLeg(sym, "buy", notional, "scaled_below_min_notional_by_cash"))
            continue
        exempt = allow_exit_to_cash and sym == cash_symbol
        buys.append(PlannedOrder(sym, "buy", notional, None, intended / px, px, w, cur, tgt,
                                 exempt_from_caps=exempt))

    risky_target = Decimal(repr(sum(float(v) for s, v in targets.items() if s != cash_symbol)))
    return Plan(
        sells=sells,
        buys=buys,
        skipped=skipped,
        impossible=impossible,
        equity=equity,
        current_exposure=(risky_mv / equity) if equity > 0 else Decimal(0),
        target_exposure=risky_target,
    )


def build_order_request(leg: PlannedOrder, client_order_id: str) -> OrderRequest:
    """Turn a planned leg into a broker request (market, DAY)."""
    if leg.close_position:
        return OrderRequest(leg.symbol, leg.side, client_order_id, notional=None, qty=leg.qty)
    return OrderRequest(leg.symbol, leg.side, client_order_id, notional=leg.notional, qty=None)


def _fmt_money(x: Decimal | None) -> str:
    return "-" if x is None else f"${x:,.2f}"


def format_plan(legs: list[tuple[PlannedOrder, str]], skipped: list[SkippedLeg], header: str = "") -> str:
    """Human-readable plan table: symbol, side, notional, est. qty, client_order_id."""
    lines = []
    if header:
        lines.append(header)
    lines.append(f"{'symbol':<8}{'side':<6}{'notional':>12}{'est_qty':>16}  {'client_order_id'}")
    for leg, cid in legs:
        notional = leg.notional if leg.notional is not None else leg.est_notional.quantize(CENT)
        tag = " (close, qty)" if leg.close_position else ""
        lines.append(
            f"{leg.symbol:<8}{leg.side:<6}{_fmt_money(notional):>12}{leg.qty_est:>16.6f}  {cid}{tag}"
        )
    if not legs:
        lines.append("(no orders)")
    for s in skipped:
        lines.append(f"skipped  {s.symbol:<8}{s.side:<6}{_fmt_money(s.amount):>12}  {s.reason}")
    return "\n".join(lines)


def is_finite_positive(x: float | Decimal | None) -> bool:
    if x is None:
        return False
    try:
        f = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and f > 0
