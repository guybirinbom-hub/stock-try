"""Inputs for a paper run: targets, dated prices and dividends.

Two sources:

* ``load_targets_file`` -- a JSON file (see tests/fixtures/sample_targets.json):
  ``strategy``, ``universe``, ``cash_symbol``, ``allows_exit_to_cash``,
  ``targets`` (risky weights), optional ``prices`` ({symbol: {close, session,
  prev_close}}), optional ``dividends`` ({symbol: [[ex_date, $/share], ...]}),
  optional ``sim_initial_weights`` (simulator starting holdings as fractions
  of capital).
* ``inputs_from_registry`` -- a pre-registered strategy from
  ``stocktry.strategies.registry`` evaluated on data from
  ``stocktry.data.fetch.get_bars``. Both modules belong to the core package
  and are imported lazily, so the execution layer works (and its tests run)
  without them.

Timing: the strategy sees adjusted closes up to and including the *decision
date* (the session before the rebalance date), exactly like the backtest's
decide-at-close-t, trade-at-t+1 rule. Sizing prices are the closes of the
*last completed session* (fresher when a trigger runs late).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .planning import PriceQuote, coerce_quotes, quotes_from_frame

__all__ = [
    "CoreUnavailable",
    "StrategyInputs",
    "EXIT_TO_CASH_FAMILIES",
    "declares_exit_to_cash",
    "load_targets_file",
    "load_registry_spec",
    "inputs_from_registry",
]

#: Strategy families whose rules move to cash by design (trend filters, GTAA).
#: Used only when a StrategySpec does not carry an explicit ``allows_exit_to_cash``.
EXIT_TO_CASH_FAMILIES = frozenset({"trend_sma", "trend_absmom", "trend_ensemble", "gtaa4", "gtaa5"})


class CoreUnavailable(RuntimeError):
    """The core package (strategies or data layer) is not importable."""


@dataclass(frozen=True)
class StrategyInputs:
    strategy: str
    universe: tuple[str, ...]
    cash_symbol: str | None
    allows_exit_to_cash: bool
    targets: dict[str, float] | None  # None: not a rebalance month for this strategy (hold)
    quotes: dict[str, PriceQuote] | None
    dividends: dict[str, list[tuple[date, float]]] | None = None
    sim_initial_weights: dict[str, float] = field(default_factory=dict)
    note: str = ""


def declares_exit_to_cash(spec: Any) -> bool:
    explicit = getattr(spec, "allows_exit_to_cash", None)
    if explicit is not None:
        return bool(explicit)
    return getattr(spec, "family", "") in EXIT_TO_CASH_FAMILIES


def load_targets_file(path: str | Path) -> StrategyInputs:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("strategy", "universe", "targets"):
        if key not in raw:
            raise ValueError(f"targets file is missing '{key}'")
    divs = None
    if raw.get("dividends"):
        divs = {s: [(date.fromisoformat(d), float(a)) for d, a in rows] for s, rows in raw["dividends"].items()}
    return StrategyInputs(
        strategy=str(raw["strategy"]),
        universe=tuple(raw["universe"]),
        cash_symbol=raw.get("cash_symbol"),
        allows_exit_to_cash=bool(raw.get("allows_exit_to_cash", False)),
        targets={str(k): float(v) for k, v in raw["targets"].items()},
        quotes=coerce_quotes(raw["prices"]) if raw.get("prices") else None,
        dividends=divs,
        sim_initial_weights={str(k): float(v) for k, v in raw.get("sim_initial_weights", {}).items()},
        note=str(raw.get("note", "")),
    )


def load_registry_spec(name: str) -> Any:
    try:
        from stocktry.strategies.registry import STRATEGIES  # lazy: core package
    except ImportError as exc:
        raise CoreUnavailable(
            f"stocktry.strategies is not available ({exc}); use --targets-json instead"
        ) from None
    if name not in STRATEGIES:
        raise KeyError(f"unknown strategy {name!r}; known: {sorted(STRATEGIES)}")
    return STRATEGIES[name]


def _get_bars_fn():
    try:
        from stocktry.data.fetch import get_bars  # lazy: core package
    except ImportError as exc:
        raise CoreUnavailable(f"stocktry.data is not available ({exc}); use --targets-json with prices") from None
    return get_bars


def fetch_closes_and_dividends(symbols: list[str], *, refresh: bool):
    """Wide adjusted-close frame and ``{symbol: [(ex_date, $/share)]}`` from the data layer."""
    import pandas as pd

    get_bars = _get_bars_fn()
    closes, divs = {}, {}
    for sym in symbols:
        bars = get_bars(sym, refresh=refresh)
        closes[sym] = bars["close"]
        if "dividend" in bars.columns:
            d = bars["dividend"]
            d = d[d > 0]
            divs[sym] = [(ts.date(), float(v)) for ts, v in d.items()]
    frame = pd.DataFrame(closes).sort_index()
    return frame, divs


def inputs_from_registry(
    name: str, *, decision_date: date, last_session: date, refresh: bool
) -> StrategyInputs:
    """Evaluate a registry strategy at ``decision_date``; quotes at ``last_session``."""
    import pandas as pd

    spec = load_registry_spec(name)
    offset = getattr(spec, "signal_offset", -1)
    if offset != -1:
        raise NotImplementedError(
            f"{name}: signal_offset={offset} (tranched rebalancing) is not supported by the paper runner"
        )
    universe = list(spec.universe)
    symbols = universe + ([spec.cash_symbol] if spec.cash_symbol else [])
    frame, divs = fetch_closes_and_dividends(symbols, refresh=refresh)
    ts = pd.Timestamp(decision_date)
    if ts not in frame.index:
        raise RuntimeError(f"no data row for the decision date {decision_date}; refresh the data cache")
    months = getattr(spec, "rebalance_months", None)
    targets: dict[str, float] | None
    note = ""
    if months is not None and decision_date.month not in months:
        targets = None
        note = f"{name} rebalances only after months {tuple(months)}; holding this month"
    else:
        targets = {str(k): float(v) for k, v in spec.compute_targets(frame.loc[:ts], ts).items()}
    quotes = quotes_from_frame(frame[symbols], last_session)
    return StrategyInputs(
        strategy=spec.name,
        universe=tuple(universe),
        cash_symbol=spec.cash_symbol,
        allows_exit_to_cash=declares_exit_to_cash(spec),
        targets=targets,
        quotes=quotes,
        dividends=divs,
        note=note,
    )
