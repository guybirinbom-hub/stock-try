"""Helpers for building deterministic simulator scenarios (tests and demos).

No network, no wall clock: the run config's ``local_now`` follows the
simulator's clock and ``sleep`` is a no-op.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Mapping

from .alerts import Alerter
from .planning import PriceQuote
from .runner import RunConfig, RunResult, rebalance_once
from .sessions import ET, due_rebalance_date, make_rebalance_id, previous_session, sim_nyse_calendar
from .simbroker import LocalSimBroker

__all__ = [
    "et",
    "RecordingTransport",
    "make_sim",
    "make_cfg",
    "quotes_for",
    "rid",
    "Scenario",
    "scenario",
    "STD_PRICES",
    "STD_POSITIONS",
    "STD_CASH",
    "STD_TARGETS",
]

#: Standard scenario: $130 account, SPY overweight -> one sell and two buys,
#: all inside the default caps (per order min($50, 25% x $130) = $32.50;
#: daily 60% x $130 = $78).
STD_PRICES = {"SPY": 500.0, "IEF": 95.0, "GLD": 250.0}
STD_POSITIONS = {"SPY": 0.16, "IEF": 0.2, "GLD": 0.04}
STD_CASH = 21.0
STD_TARGETS = {"SPY": 0.5, "IEF": 0.3, "GLD": 0.2}


def et(y: int, m: int, d: int, hh: int = 11, mm: int = 0) -> datetime:
    """A tz-aware America/New_York datetime."""
    return datetime.combine(date(y, m, d), time(hh, mm), ET)


class RecordingTransport:
    """Captures would-be HTTP calls from ``Alerter`` instead of sending them."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def __call__(self, method: str, url: str, kwargs: dict) -> None:
        self.calls.append((method, url, kwargs))


def make_sim(
    *,
    cash: float = 100.0,
    prices: Mapping[str, float] | None = None,
    now: datetime | None = None,
    positions: Mapping[str, float] | None = None,
    **kw: Any,
) -> LocalSimBroker:
    prices = prices or {"SPY": 500.0, "IEF": 95.0, "GLD": 250.0}
    return LocalSimBroker(cash=cash, prices=prices, now=now or et(2026, 10, 1, 11), positions=positions, **kw)


def quotes_for(
    broker: LocalSimBroker, session: date | None = None, prev: Mapping[str, float] | None = None
) -> dict[str, PriceQuote]:
    """Quotes dated ``session`` (default: last completed session at sim now) at the sim prices."""
    if session is None:
        cal = sim_nyse_calendar(date(2026, 1, 1), date(2027, 12, 31))
        today = broker.now.astimezone(ET).date()
        done = [c.date for c in cal if c.close <= broker.now]
        session = max(done) if done else previous_session(cal, today)
    return {
        s: PriceQuote(float(p), session, float((prev or {}).get(s, float(p) * 0.995)))
        for s, p in broker.prices.items()
    }


def rid(strategy: str, d: date) -> str:
    return make_rebalance_id(strategy, d)


def make_cfg(broker: LocalSimBroker, tmp_path: Path, **overrides: Any) -> RunConfig:
    transport = RecordingTransport()
    base = RunConfig(
        strategy="demo",
        universe=("SPY", "IEF", "GLD"),
        dry_run=False,
        ledger_path=Path(tmp_path) / "ledger" / "demo.jsonl",
        kill_switch_path=Path(tmp_path) / "KILL_SWITCH",
        local_now=lambda: broker.now,
        sleep=lambda s: None,
        poll_max=3,
        env={},
        alerter=Alerter(ntfy_topic="test-topic", transport=transport),
    )
    return replace(base, **overrides)


@dataclass
class Scenario:
    broker: LocalSimBroker
    cfg: RunConfig
    targets: dict[str, float]
    quotes: dict[str, PriceQuote]
    rebalance_id: str

    @property
    def transport(self) -> RecordingTransport:
        return self.cfg.alerter.transport  # type: ignore[union-attr,return-value]

    def run(self, **kw: Any) -> RunResult:
        targets = kw.pop("targets", self.targets)
        quotes = kw.pop("prices", self.quotes)
        rebalance_id = kw.pop("rebalance_id", self.rebalance_id)
        cfg = kw.pop("cfg", self.cfg)
        return rebalance_once(targets, self.broker, cfg, prices=quotes, rebalance_id=rebalance_id, **kw)

    def refresh(self) -> None:
        """Re-date quotes and the due rebalance id after moving the sim clock."""
        self.quotes = quotes_for(self.broker)
        cal = sim_nyse_calendar(date(2026, 1, 1), date(2027, 12, 31))
        self.rebalance_id = make_rebalance_id(self.cfg.strategy, due_rebalance_date(cal, self.broker.now))


def scenario(
    tmp_path: Path,
    *,
    now: datetime | None = None,
    cash: float = STD_CASH,
    positions: Mapping[str, float] | None = None,
    prices: Mapping[str, float] | None = None,
    targets: Mapping[str, float] | None = None,
    cfg_overrides: Mapping[str, Any] | None = None,
    **sim_kw: Any,
) -> Scenario:
    broker = make_sim(
        cash=cash,
        prices=dict(prices or STD_PRICES),
        now=now or et(2026, 10, 1, 11),
        positions=dict(STD_POSITIONS if positions is None else positions),
        **sim_kw,
    )
    cfg = make_cfg(broker, tmp_path, **dict(cfg_overrides or {}))
    sc = Scenario(broker, cfg, dict(targets if targets is not None else STD_TARGETS), {}, "")
    sc.refresh()
    return sc
