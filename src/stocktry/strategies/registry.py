"""Registry of the pre-registered strategies (contract: ``STRATEGIES: dict[str, StrategySpec]``).

Every entry uses the published default parameters; ``PARAMS`` exposes them
as plain dicts. Variants for sweeps are built with :func:`make_variant` and
are never added to ``STRATEGIES`` (the registry is built once at import and
not mutated).
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any, Callable, Mapping

from .base import StrategySpec
from .buy_and_hold import make_buy_and_hold, make_sixty_forty
from .gtaa import GTAA4_SLEEVES, GTAA5_SLEEVES, make_gtaa
from .trend import make_trend_absmom, make_trend_ensemble, make_trend_sma


def _build() -> dict[str, StrategySpec]:
    specs = [
        make_buy_and_hold("SPY", name="spy_buy_hold"),
        make_sixty_forty("SPY", "AGG", 0.6, name="sixty_forty"),
        make_trend_sma("SPY", 10),
        make_trend_absmom("SPY", 12),
        make_trend_ensemble("SPY"),
        make_gtaa(GTAA5_SLEEVES, 10),
        make_gtaa(GTAA4_SLEEVES, 10),
    ]
    return {s.name: s for s in specs}


STRATEGIES: dict[str, StrategySpec] = _build()
PARAMS: Mapping[str, Mapping[str, Any]] = MappingProxyType(
    {k: MappingProxyType(dict(v.params)) for k, v in STRATEGIES.items()}
)
BENCHMARKS: tuple[str, ...] = ("spy_buy_hold", "sixty_forty")
CANDIDATES: tuple[str, ...] = ("trend_sma10", "trend_absmom12", "trend_ensemble", "gtaa4", "gtaa5")

FACTORIES: dict[str, Callable[..., StrategySpec]] = {
    "buy_hold": make_buy_and_hold,
    "sixty_forty": make_sixty_forty,
    "trend_sma": make_trend_sma,
    "trend_absmom": make_trend_absmom,
    "trend_ensemble": make_trend_ensemble,
    "gtaa5": lambda **kw: make_gtaa(GTAA5_SLEEVES, **kw),
    "gtaa4": lambda **kw: make_gtaa(GTAA4_SLEEVES, **kw),
}


def get_strategy(name: str) -> StrategySpec:
    try:
        return STRATEGIES[name]
    except KeyError:
        raise KeyError(f"unknown strategy {name!r}; known: {sorted(STRATEGIES)}") from None


def make_variant(family: str, **params: Any) -> StrategySpec:
    """Build a parameter variant, e.g. ``make_variant('trend_sma', lookback=7)``."""
    return FACTORIES[family](**params)
