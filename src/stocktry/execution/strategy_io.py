"""Inputs for a paper run: targets, dated prices and dividends.

Two sources:

* ``load_targets_file`` -- a JSON file (see tests/fixtures/sample_targets.json):
  ``strategy``, ``universe``, ``cash_symbol``, ``allows_exit_to_cash``,
  ``targets`` (risky weights), optional ``prices`` ({symbol: {close, session,
  prev_close}}), optional ``dividends`` ({symbol: [[ex_date, $/share], ...]}),
  optional ``sim_initial_weights`` (simulator starting holdings as fractions
  of capital). Types are checked strictly: ``allows_exit_to_cash`` must be a
  JSON boolean (the *string* ``"false"`` is refused, never read as true),
  ``universe`` a list of symbols, ``cash_symbol`` null or a cash-like ETF.
* ``inputs_from_registry`` -- a pre-registered strategy from
  ``stocktry.strategies.registry`` evaluated on daily bars from either
  **Alpaca Market Data** (``price_source="alpaca"``, the licence-clean source
  for unattended runs; :mod:`stocktry.data.alpaca_bars`) or the local
  **research cache** (``price_source="cache"``: Yahoo, personal-use research
  data; :func:`stocktry.data.fetch.get_bars`). If Alpaca fails, a cache that
  already exists on this machine is read (never refreshed: the fallback makes
  no network call, so an unattended run never downloads from Yahoo) with a
  warning, and the fallback is recorded; with no local cache the run stops
  with a data error. Both modules belong to the core package and are
  imported lazily.

Alignment is the backtest's own (:func:`stocktry.data.panel.align_closes`):
each series is forward-filled between its first and last real bar, so one
missing vendor row cannot turn a sleeve "out" in the runner while the engine
keeps it in. Rules that read the T-bill index (``StrategySpec.uses_tbill``)
get the same ``"^TBILL"`` column the engine builds, from FRED DTB3 fetched
with the run's ``refresh`` flag and refused if it is stale.

Timing: the strategy sees adjusted closes up to and including the *decision
date* (the session before the rebalance date), exactly like the backtest's
decide-at-close-t, trade-at-t+1 rule. Sizing prices are the closes of the
*last completed session* (fresher when a trigger runs late).
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from .guards import CASH_LIKE_SYMBOLS
from .planning import PriceQuote, coerce_quotes, quotes_from_frame
from .sessions import validate_symbol

__all__ = [
    "CoreUnavailable",
    "StrategyInputs",
    "PRICE_SOURCES",
    "TBILL_MAX_AGE_DAYS",
    "declares_exit_to_cash",
    "load_targets_file",
    "load_registry_spec",
    "fetch_closes_and_dividends",
    "read_cached_closes_and_dividends",
    "fetch_closes_and_dividends_alpaca",
    "inputs_from_registry",
]

log = logging.getLogger("stocktry.execution.strategy_io")

PRICE_SOURCES = ("alpaca", "cache")
#: The DTB3 series used for the absolute-momentum hurdle must have an observation this recent
#: (calendar days before the decision date); FRED publishes with a lag of about one business day.
TBILL_MAX_AGE_DAYS = 10


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
    price_source: str = "file"  # "alpaca", "cache", "cache (fallback: ...)" or "file"
    data_feed: str | None = None  # Alpaca feed used for bars ("iex"/"sip"), None for the cache


def declares_exit_to_cash(spec: Any) -> bool:
    """The strategy's explicit ``allows_exit_to_cash`` declaration (a real bool).

    There is no family-name fallback: a spec without the field is treated as
    NOT declared (the safe value) and a warning is logged.
    """
    explicit = getattr(spec, "allows_exit_to_cash", None)
    if explicit is None:
        log.warning("strategy %r does not declare allows_exit_to_cash; treating exits to cash as NOT allowed",
                    getattr(spec, "name", "?"))
        return False
    if not isinstance(explicit, bool):
        raise TypeError(f"{getattr(spec, 'name', '?')}: allows_exit_to_cash must be a bool, got {explicit!r}")
    return explicit


def _symbol(x: Any, what: str) -> str:
    if not isinstance(x, str):
        raise ValueError(f"{what} must be a symbol string, got {x!r}")
    try:
        return validate_symbol(x)
    except ValueError:
        raise ValueError(f"{what}: invalid symbol {x!r} (upper-case tickers only, e.g. 'SPY')") from None


def _weight(x: Any, what: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{what} must be a number, got {x!r}")
    return float(x)


def load_targets_file(path: str | Path) -> StrategyInputs:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("targets file must be a JSON object")
    for key in ("strategy", "universe", "targets"):
        if key not in raw:
            raise ValueError(f"targets file is missing '{key}'")
    if not isinstance(raw["strategy"], str):
        raise ValueError("'strategy' must be a string")
    uni = raw["universe"]
    if not isinstance(uni, list) or not uni:
        raise ValueError("'universe' must be a non-empty JSON list of symbols (a string would be split into letters)")
    universe = tuple(_symbol(s, "universe entry") for s in uni)
    cash = raw.get("cash_symbol")
    if cash is not None:
        cash = _symbol(cash, "'cash_symbol'")
        if cash not in CASH_LIKE_SYMBOLS:
            raise ValueError(f"'cash_symbol' {cash!r} is not a recognised T-bill ETF {sorted(CASH_LIKE_SYMBOLS)}")
    exit_decl = raw.get("allows_exit_to_cash", False)
    if not isinstance(exit_decl, bool):
        raise ValueError(f"'allows_exit_to_cash' must be a JSON boolean (true/false), got {exit_decl!r}")
    tg = raw["targets"]
    if not isinstance(tg, dict):
        raise ValueError("'targets' must be a JSON object of {symbol: weight}")
    targets = {_symbol(k, "target symbol"): _weight(v, f"target weight for {k}") for k, v in tg.items()}
    divs = None
    if raw.get("dividends"):
        divs = {_symbol(s, "dividend symbol"): [(date.fromisoformat(d), float(a)) for d, a in rows]
                for s, rows in raw["dividends"].items()}
    init = raw.get("sim_initial_weights", {})
    if not isinstance(init, dict):
        raise ValueError("'sim_initial_weights' must be a JSON object")
    return StrategyInputs(
        strategy=raw["strategy"],
        universe=universe,
        cash_symbol=cash,
        allows_exit_to_cash=exit_decl,
        targets=targets,
        quotes=coerce_quotes(raw["prices"]) if raw.get("prices") else None,
        dividends=divs,
        sim_initial_weights={_symbol(k, "sim_initial_weights symbol"): _weight(v, f"initial weight for {k}")
                             for k, v in init.items()},
        note=str(raw.get("note", "")),
        price_source="file" if raw.get("prices") else "",
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


def _frame_and_divs(bars_by_symbol: Mapping[str, Any]):
    import pandas as pd

    closes, divs = {}, {}
    for sym, bars in bars_by_symbol.items():
        closes[sym] = bars["close"]
        if "dividend" in bars.columns:
            d = bars["dividend"]
            d = d[d > 0]
            divs[sym] = [(ts.date(), float(v)) for ts, v in d.items()]
    return pd.DataFrame(closes).sort_index(), divs


def fetch_closes_and_dividends(symbols: list[str], *, refresh: bool):
    """Research cache (Yahoo, personal use): wide adjusted-close frame and ``{symbol: [(ex_date, $/share)]}``."""
    get_bars = _get_bars_fn()
    return _frame_and_divs({sym: get_bars(sym, refresh=refresh) for sym in symbols})


def read_cached_closes_and_dividends(symbols: list[str]):
    """The research cache as it already is on disk (hash-verified), with **no network access at all**.

    The fallback when Alpaca Market Data fails: an unattended run must never download from Yahoo
    (research report s.10). Raises ``RuntimeError`` when a symbol has no local cache.
    """
    try:
        from stocktry.data.fetch import FetchError, read_bars_cache  # lazy: core package
    except ImportError as exc:
        raise CoreUnavailable(f"stocktry.data is not available ({exc})") from None
    bars = {}
    for sym in symbols:
        try:
            bars[sym] = read_bars_cache(sym.upper())[0]
        except FetchError:
            raise RuntimeError(f"Alpaca market data failed and there is no local cache for {sym}; the runner "
                               "never downloads from Yahoo as a fallback") from None
    return _frame_and_divs(bars)


def fetch_closes_and_dividends_alpaca(symbols: list[str], *, end: date, feed: str | None = None,
                                      env: Mapping[str, str] | None = None):
    """Alpaca Market Data (licence-clean): wide adjusted-close frame, dividends and the feed used."""
    try:
        from stocktry.data.alpaca_bars import get_bars_alpaca, resolve_feed  # lazy: core package
    except ImportError as exc:
        raise CoreUnavailable(f"stocktry.data is not available ({exc})") from None
    f = resolve_feed(feed, env)
    frame, divs = _frame_and_divs(get_bars_alpaca(symbols, end=end, feed=f, env=env))
    return frame, divs, f


def load_closes(symbols: list[str], *, price_source: str, refresh: bool, end: date, feed: str | None = None,
                env: Mapping[str, str] | None = None):
    """(frame, dividends, source actually used, feed) -- Alpaca with a cache fallback, or the cache.

    ``refresh`` applies to ``price_source="cache"`` only. The Alpaca fallback reads an existing local
    cache and never refreshes it (no Yahoo download from an unattended run).
    """
    if price_source not in PRICE_SOURCES:
        raise ValueError(f"unknown price source {price_source!r}; use one of {PRICE_SOURCES}")
    if price_source == "alpaca":
        try:
            frame, divs, f = fetch_closes_and_dividends_alpaca(symbols, end=end, feed=feed, env=env)
            return frame, divs, "alpaca", f
        except (CoreUnavailable, ValueError):
            raise
        except Exception as exc:  # noqa: BLE001 - fall back to the local cache (read-only), loudly
            log.warning("Alpaca market data failed (%s); FALLING BACK to the local research cache as it is on "
                        "disk (Yahoo, personal-use data; not refreshed, no download). The price freshness guard "
                        "refuses it if it is out of date. Check the keys, the feed entitlement and the network.",
                        type(exc).__name__)
            frame, divs = read_cached_closes_and_dividends(symbols)
            return frame, divs, f"cache (fallback: alpaca {type(exc).__name__}; local, not refreshed)", None
    frame, divs = fetch_closes_and_dividends(symbols, refresh=refresh)
    return frame, divs, "cache", None


def _tbill_column(index, decision_date: date, refresh: bool):
    """The engine's ``^TBILL`` index on ``index`` from FRED DTB3 fetched with ``refresh``; refuses stale data."""
    import pandas as pd

    from stocktry.data import fetch as data_fetch  # module attribute lookup at call time (patchable)
    from stocktry.data.rates import tbill_index

    y = data_fetch.get_tbill_yield(refresh=refresh)
    y = y.dropna()
    known = y[y.index <= pd.Timestamp(decision_date)]
    if known.empty:
        raise RuntimeError("no T-bill (DTB3) observation on or before the decision date")
    age = (pd.Timestamp(decision_date) - known.index[-1]).days
    if age > TBILL_MAX_AGE_DAYS:
        raise RuntimeError(f"T-bill series is stale: last DTB3 observation {known.index[-1].date()} is {age} days "
                           f"before the decision date (max {TBILL_MAX_AGE_DAYS}); rerun with --refresh-data")
    return tbill_index(index, y)


def inputs_from_registry(
    name: str, *, decision_date: date, last_session: date, refresh: bool, price_source: str = "cache",
    feed: str | None = None, env: Mapping[str, str] | None = None,
) -> StrategyInputs:
    """Evaluate a registry strategy at ``decision_date``; quotes at ``last_session``."""
    import pandas as pd

    from stocktry.data.panel import align_closes
    from stocktry.data.rates import TBILL_COLUMN

    spec = load_registry_spec(name)
    offset = getattr(spec, "signal_offset", -1)
    if offset != -1:
        raise NotImplementedError(
            f"{name}: signal_offset={offset} (tranched rebalancing) is not supported by the paper runner"
        )
    universe = list(spec.universe)
    symbols = universe + ([spec.cash_symbol] if spec.cash_symbol else [])
    if price_source == "cache":
        frame, divs = fetch_closes_and_dividends(symbols, refresh=refresh)
        used, feed_used = "cache", None
    else:
        frame, divs, used, feed_used = load_closes(symbols, price_source=price_source, refresh=refresh,
                                                   end=last_session, feed=feed, env=env)
    frame = align_closes(frame)  # the backtest panel's alignment rule (EXEC-05)
    ts = pd.Timestamp(decision_date)
    if ts not in frame.index:
        raise RuntimeError(f"no data row for the decision date {decision_date}; refresh the data")
    months = getattr(spec, "rebalance_months", None)
    targets: dict[str, float] | None
    note = ""
    if months is not None and decision_date.month not in months:
        targets = None
        note = f"{name} rebalances only after months {tuple(months)}; holding this month"
    else:
        strat = frame[symbols].copy()
        if getattr(spec, "uses_tbill", False):
            strat[TBILL_COLUMN] = _tbill_column(strat.index, decision_date, refresh)
        raw_targets = spec.compute_targets(strat.loc[:ts], ts)
        targets = {}
        for k, v in raw_targets.items():
            fv = float(v)
            if not math.isfinite(fv):
                raise RuntimeError(f"{name}: non-finite target weight for {k}")
            targets[str(k)] = fv
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
        price_source=used,
        data_feed=feed_used,
    )
