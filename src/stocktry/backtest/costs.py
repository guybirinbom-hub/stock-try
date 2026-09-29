"""Transaction-cost model: spreads, Alpaca pass-through regulatory fees, commissions.

Units: spreads in **basis points of traded notional per side**; fees and
commissions in **dollars**; fee rates in dollars per dollar of notional (SEC)
or dollars per share (FINRA TAF, CAT). Share counts are **as-traded** shares
(notional / as-traded price), not adjusted-price units.

(a) Spread: each order pays ``notional * half_spread_bp / 1e4`` (buys fill
    that much above, sells that much below, the reference price). The
    per-instrument half-spread comes from :mod:`stocktry.data.universe`; a
    floor (``min_half_spread_bp``) and a multiplier model conservative and 2x
    cost scenarios.
(b) Alpaca regulatory fees (fee schedule rev. 2026-09-17), dated tables:
    * SEC Section 31: $27.80 per $1M of **sell** notional before 2025-05-14,
      $0 from 2025-05-14, $20.60 per $1M from 2026-04-04. Earlier history uses
      the $27.80 rate (the real historical rates differed; commissions of that
      era are not modelled).
    * FINRA TAF: $0.000195 per **sold** share, capped at $9.79 per order,
      applied to all history. The announced Oct-Dec 2026 pause ($0.00) is
      available via ``taf_q4_2026_pause=True`` and is OFF by default because
      Alpaca's pass-through of the pause is unverified.
    * CAT: $0.000003 per share on buys **and** sells.
    Each fee type is summed over all of the account's orders on a day and the
    daily total of each type is rounded **up** to the next cent. So a $1 buy
    costs $0.01 (CAT) and a $1 sell on another day $0.03 (SEC + TAF + CAT):
    a $1 round trip costs $0.04.
(c) Optional commission for other brokers: per order
    ``max(flat + bps * notional / 1e4, minimum)`` (all zero by default).
(d) Expense ratios are *not* charged here: fund price series are already net
    of fees. Index-level series (``SymbolMeta.is_index_level``) are charged
    their expense ratio daily by the engine.
Minimum order size: Alpaca documents "a minimum 1 USD notional amount for Buy
entry orders". So **buys** below ``min_notional`` dollars ($1) are skipped and
logged; **sells** have no dollar minimum. A partial sell is a notional order in
whole cents, so it is sent when it is at least ``min_sell_notional`` ($0.01); a
full exit is a quantity sell of the whole position, of any size.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from datetime import date

import pandas as pd

from ..data.universe import SymbolMeta


@dataclass(frozen=True)
class DatedRate:
    """A fee rate effective from ``start`` (inclusive; ``None`` = since forever)."""

    start: date | None
    rate: float
    cap: float | None = None


SEC_FEE_SCHEDULE: tuple[DatedRate, ...] = (
    DatedRate(None, 27.80e-6),
    DatedRate(date(2025, 5, 14), 0.0),
    DatedRate(date(2026, 4, 4), 20.60e-6),
)
TAF_SCHEDULE: tuple[DatedRate, ...] = (DatedRate(None, 0.000195, cap=9.79),)
TAF_Q4_2026_PAUSE = (date(2026, 10, 1), date(2026, 12, 31))
CAT_SCHEDULE: tuple[DatedRate, ...] = (DatedRate(None, 0.000003),)


def rate_on(schedule: tuple[DatedRate, ...], day: date) -> DatedRate:
    """The entry of ``schedule`` in force on ``day`` (schedules are sorted by start)."""
    cur = schedule[0]
    for r in schedule:
        if r.start is None or r.start <= day:
            cur = r
    return cur


def ceil_cent(x: float) -> float:
    """Round a positive dollar amount up to the next cent (0 stays 0).

    Any positive amount, however small, becomes at least $0.01. Float noise
    within 1e-10 cents of an exact cent (e.g. 0.21 stored as 0.21000000000000002)
    is not rounded up again.
    """
    if x <= 0:
        return 0.0
    c = x * 100.0
    r = round(c)
    if r > 0 and abs(c - r) < 1e-10:
        return r / 100.0
    return math.ceil(c) / 100.0


@dataclass(frozen=True)
class Order:
    """One executed order. ``notional`` is positive dollars; ``shares`` positive as-traded shares."""

    symbol: str
    side: str  # "buy" | "sell"
    notional: float
    shares: float


@dataclass(frozen=True)
class FeeBreakdown:
    sec: float = 0.0
    taf: float = 0.0
    cat: float = 0.0
    commission: float = 0.0

    @property
    def total(self) -> float:
        return self.sec + self.taf + self.cat + self.commission


@dataclass(frozen=True)
class AlpacaFeeModel:
    sec_schedule: tuple[DatedRate, ...] = SEC_FEE_SCHEDULE
    taf_schedule: tuple[DatedRate, ...] = TAF_SCHEDULE
    cat_schedule: tuple[DatedRate, ...] = CAT_SCHEDULE
    taf_q4_2026_pause: bool = False
    multiplier: float = 1.0  # scales every rate before rounding (2x-cost scenario)

    def day_fees(self, day: date | pd.Timestamp, orders: list[Order]) -> FeeBreakdown:
        """Per-type daily totals, each rounded up to the cent, for one account-day."""
        d = day.date() if isinstance(day, pd.Timestamp) else day
        sec_r = rate_on(self.sec_schedule, d).rate
        taf = rate_on(self.taf_schedule, d)
        cat_r = rate_on(self.cat_schedule, d).rate
        if self.taf_q4_2026_pause and TAF_Q4_2026_PAUSE[0] <= d <= TAF_Q4_2026_PAUSE[1]:
            taf = DatedRate(None, 0.0, taf.cap)
        m = self.multiplier
        sec = sum(o.notional for o in orders if o.side == "sell") * sec_r * m
        taf_amt = 0.0
        for o in orders:
            if o.side == "sell":
                per = o.shares * taf.rate * m
                if taf.cap is not None:
                    per = min(per, taf.cap * m)
                taf_amt += per
        cat = sum(o.shares for o in orders) * cat_r * m
        return FeeBreakdown(ceil_cent(sec), ceil_cent(taf_amt), ceil_cent(cat), 0.0)


@dataclass(frozen=True)
class CommissionModel:
    flat: float = 0.0
    bps: float = 0.0
    minimum: float = 0.0

    def order_commission(self, notional: float) -> float:
        if self.flat == 0.0 and self.bps == 0.0 and self.minimum == 0.0:
            return 0.0
        return max(self.flat + self.bps * notional / 1e4, self.minimum)


@dataclass(frozen=True)
class CostModel:
    """Everything the engine charges on a trade. See the module docstring."""

    name: str = "modelled"
    spread: bool = True
    spread_multiplier: float = 1.0
    min_half_spread_bp: float = 0.0
    alpaca: AlpacaFeeModel | None = field(default_factory=AlpacaFeeModel)
    commission: CommissionModel = field(default_factory=CommissionModel)
    min_notional: float = 1.0  # minimum BUY notional, dollars (Alpaca: buy entry orders only)
    min_sell_notional: float = 0.01  # a partial (notional) sell is whole cents; full exits are qty sells

    def half_spread_bp(self, meta: SymbolMeta) -> float:
        if not self.spread:
            return 0.0
        return max(meta.half_spread_bp, self.min_half_spread_bp) * self.spread_multiplier

    def day_fees(self, day: pd.Timestamp, orders: list[Order]) -> FeeBreakdown:
        base = self.alpaca.day_fees(day, orders) if (self.alpaca and orders) else FeeBreakdown()
        comm = sum(self.commission.order_commission(o.notional) for o in orders)
        return replace(base, commission=comm)

    def scaled(self, factor: float, name: str | None = None) -> "CostModel":
        """Same model with spreads and fee rates multiplied by ``factor``."""
        alp = replace(self.alpaca, multiplier=self.alpaca.multiplier * factor) if self.alpaca else None
        comm = CommissionModel(self.commission.flat * factor, self.commission.bps * factor,
                               self.commission.minimum * factor)
        return replace(self, name=name or f"{self.name}_x{factor:g}",
                       spread_multiplier=self.spread_multiplier * factor, alpaca=alp, commission=comm)

    # ---- named tiers -------------------------------------------------------
    @classmethod
    def zero(cls) -> "CostModel":
        """No spread, no fees, no minimum order size (identity and cross-check runs)."""
        return cls(name="zero", spread=False, alpaca=None, min_notional=0.0, min_sell_notional=0.0)

    @classmethod
    def modelled(cls) -> "CostModel":
        """Per-instrument half-spreads + Alpaca fees + $1 minimum buy order."""
        return cls(name="modelled")

    @classmethod
    def gate(cls) -> "CostModel":
        """Gate A cost tier: half-spread floored at 5 bp per side + Alpaca fees + $1 minimum buy order."""
        return cls(name="gate", min_half_spread_bp=5.0)
