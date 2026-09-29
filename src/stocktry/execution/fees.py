"""Alpaca regulatory pass-through fee model for the shadow ledger and simulator.

Source: Alpaca fee schedule revised 2026-09-17 (see docs/research-report.md s.6).

* SEC Section 31 fee: $20.60 per $1,000,000 of *sell* notional (from 2026-04-04).
* FINRA Trading Activity Fee (TAF): $0.000195 per share *sold*, capped at
  $9.79 per order (each ``FeeFill`` is treated as one order). FINRA paused
  it at $0.00 for Oct-Dec 2026, but whether Alpaca passes the pause through is
  unverified, so this model keeps charging it (conservative: overstates cost).
* Consolidated Audit Trail (CAT) fee: $0.000003 per share, buys and sells.
* Each fee type is aggregated per calendar day and rounded UP to $0.01. So a
  $1 buy on one day and a $1 sell on another costs $0.01 + 3 x $0.01 = $0.04.

This is a small local copy. ``stocktry.backtest.costs.AlpacaFeeModel`` (owned
by the core builder) is the backtest version of the same schedule; the
execution package keeps its own so it has no import-time dependency on the
backtester. ``tests/test_execution_fees.py`` pins both to the same answers
whenever the core module is importable. The local SEC rate is the rate in
force from 2026-04-04; it is not dated, so do not use it for older fills.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from typing import Iterable, NamedTuple

__all__ = ["AlpacaFeeSchedule", "FeeFill", "daily_fees", "round_up_cent", "DEFAULT_SCHEDULE"]

CENT = Decimal("0.01")


@dataclass(frozen=True)
class AlpacaFeeSchedule:
    """Rates in dollars. ``sec_rate`` is dollars of fee per dollar sold."""

    sec_rate: Decimal = Decimal("20.60") / Decimal("1000000")
    finra_taf_per_share: Decimal = Decimal("0.000195")
    finra_taf_max_per_order: Decimal = Decimal("9.79")
    cat_per_share: Decimal = Decimal("0.000003")
    #: Charge TAF even during FINRA's Oct-Dec 2026 pause (unverified pass-through).
    charge_taf: bool = True


DEFAULT_SCHEDULE = AlpacaFeeSchedule()


class FeeFill(NamedTuple):
    """One execution: ``qty`` shares at ``price`` dollars on ``day``."""

    day: date
    side: str
    qty: Decimal
    price: Decimal


def round_up_cent(x: Decimal) -> Decimal:
    """Round a positive dollar amount up to the next cent (0 stays 0)."""
    if x <= 0:
        return Decimal("0.00")
    return x.quantize(CENT, rounding=ROUND_CEILING)


def daily_fees(
    fills: Iterable[FeeFill], schedule: AlpacaFeeSchedule = DEFAULT_SCHEDULE
) -> dict[date, dict[str, Decimal]]:
    """Fees per day and type, each rounded up to $0.01 after daily aggregation.

    Returns ``{day: {"sec": $, "taf": $, "cat": $, "total": $}}`` in dollars.
    """
    raw: dict[date, dict[str, Decimal]] = defaultdict(
        lambda: {"sec": Decimal(0), "taf": Decimal(0), "cat": Decimal(0)}
    )
    for f in fills:
        qty = abs(Decimal(f.qty))
        price = Decimal(f.price)
        bucket = raw[f.day]
        bucket["cat"] += qty * schedule.cat_per_share
        if f.side == "sell":
            bucket["sec"] += qty * price * schedule.sec_rate
            if schedule.charge_taf:
                bucket["taf"] += min(qty * schedule.finra_taf_per_share, schedule.finra_taf_max_per_order)
    out: dict[date, dict[str, Decimal]] = {}
    for day in sorted(raw):
        rounded = {k: round_up_cent(v) for k, v in raw[day].items()}
        rounded["total"] = rounded["sec"] + rounded["taf"] + rounded["cat"]
        out[day] = rounded
    return out
