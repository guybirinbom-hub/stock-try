"""Execution layer: broker interface, simulator, Alpaca adapter, safe rebalance runner.

Deterministic Python only; nothing here calls an LLM. The Alpaca adapter is
imported explicitly (``from stocktry.execution.alpaca_broker import AlpacaBroker``)
so that importing this package never requires alpaca-py or network access.
"""

from .broker import (
    Account,
    AccountConfig,
    Activity,
    AssetInfo,
    Broker,
    BrokerError,
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
from .guards import GuardViolation, KillSwitchEngaged, Limits, LIMITS_OVERRIDE_ACK
from .planning import PriceQuote
from .preflight import harden_account
from .runner import RunConfig, RunResult, compute_due_rebalance, rebalance_once
from .simbroker import LocalSimBroker

__all__ = [
    "Account",
    "AccountConfig",
    "Activity",
    "AssetInfo",
    "Broker",
    "BrokerError",
    "BrokerHTTPError",
    "BrokerTimeout",
    "CalendarDay",
    "Clock",
    "DuplicateClientOrderId",
    "LatestPrice",
    "Order",
    "OrderRejected",
    "Position",
    "GuardViolation",
    "KillSwitchEngaged",
    "Limits",
    "LIMITS_OVERRIDE_ACK",
    "PriceQuote",
    "harden_account",
    "RunConfig",
    "RunResult",
    "compute_due_rebalance",
    "rebalance_once",
    "LocalSimBroker",
]
