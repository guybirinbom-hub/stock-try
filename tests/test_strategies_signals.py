"""Strategy rules, the registry contract and the no-look-ahead property."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocktry.backtest.schedule import month_anchor_positions
from stocktry.data.rates import TBILL_COLUMN
from stocktry.strategies.base import StrategySpec, absmom_signal, sma_signal
from stocktry.strategies.gtaa import make_gtaa
from stocktry.strategies.registry import CANDIDATES, PARAMS, STRATEGIES, make_variant
from stocktry.strategies.trend import make_trend_absmom, make_trend_ensemble, make_trend_sma

from conftest import gbm_close


def frame(values: dict[str, np.ndarray], start="2015-01-01", tbill_growth=0.0):
    n = len(next(iter(values.values())))
    idx = pd.bdate_range(start, periods=n)
    df = pd.DataFrame(values, index=idx)
    df[TBILL_COLUMN] = (1 + tbill_growth / 252) ** np.arange(n)
    return df


def test_registry_contract():
    assert set(CANDIDATES) <= set(STRATEGIES)
    assert {"spy_buy_hold", "sixty_forty", "trend_sma10", "trend_absmom12", "trend_ensemble", "gtaa4",
            "gtaa5"} == set(STRATEGIES)
    for name, s in STRATEGIES.items():
        assert isinstance(s, StrategySpec) and s.name == name
        assert isinstance(s.universe, list) and all(isinstance(x, str) for x in s.universe)
        assert s.cash_symbol is None and callable(s.compute_targets)
        assert dict(PARAMS[name]) == s.params
    assert STRATEGIES["trend_sma10"].params["lookback"] == 10
    assert STRATEGIES["trend_absmom12"].params["lookback"] == 12
    assert STRATEGIES["gtaa5"].universe == ["SPY", "EFA", "IEF", "VNQ", "DBC"]
    assert STRATEGIES["sixty_forty"].rebalance_months == (12,)


def test_sma_and_absmom_primitives():
    assert sma_signal(np.arange(1.0, 11.0), 10) is True  # last 10 > mean 5.5
    assert sma_signal(np.arange(10.0, 0.0, -1), 10) is False
    assert sma_signal(np.arange(1.0, 10.0), 10) is None  # 9 values < 10
    m = np.linspace(100, 110, 13)
    assert absmom_signal(m, np.linspace(1, 1.05, 13), 12) is True  # 10 % > 5 %
    assert absmom_signal(m, np.linspace(1, 1.20, 13), 12) is False  # 10 % < 20 %
    assert absmom_signal(m[:12], np.linspace(1, 1.05, 12), 12) is None


def test_trend_in_uptrend_out_in_downtrend():
    up = frame({"SPY": np.linspace(100, 200, 500)})
    down = frame({"SPY": np.linspace(200, 100, 500)})
    for spec in (make_trend_sma(), make_trend_absmom(), make_trend_ensemble()):
        assert spec.compute_targets(up, up.index[-1]) == {"SPY": 1.0}
        assert spec.compute_targets(down, down.index[-1]) == {}


def test_absmom_uses_tbill_hurdle():
    f = frame({"SPY": np.linspace(100, 104, 500)}, tbill_growth=0.10)  # ~2 %/yr stock vs 10 % bills
    assert make_trend_absmom().compute_targets(f, f.index[-1]) == {}
    f2 = frame({"SPY": np.linspace(100, 104, 500)}, tbill_growth=0.0)
    assert make_trend_absmom().compute_targets(f2, f2.index[-1]) == {"SPY": 1.0}


def test_ensemble_fractional_exposure():
    # Rises for 8 months then falls for 4: short lookbacks turn off before long ones -> partial exposure.
    x = np.r_[np.linspace(100, 160, 170), np.linspace(160, 140, 80)]
    f = frame({"SPY": x})
    w = make_trend_ensemble().compute_targets(f, f.index[-1]).get("SPY", 0.0)
    assert 0.0 < w < 1.0
    assert (w * 14) == pytest.approx(round(w * 14))  # a multiple of 1/14


def test_gtaa_sleeves_and_cash_until_formed():
    n = 600
    f = frame({"SPY": np.linspace(100, 150, n), "EFA": np.linspace(150, 100, n),
               "IEF": np.linspace(100, 110, n), "VNQ": np.r_[np.full(n - 100, np.nan), np.linspace(50, 60, 100)],
               "DBC": np.linspace(20, 30, n)})
    w = make_gtaa().compute_targets(f, f.index[-1])
    assert w == {"SPY": 0.2, "IEF": 0.2, "DBC": 0.2}  # EFA below SMA, VNQ not yet formed -> cash
    assert sum(w.values()) <= 1.0


@pytest.mark.parametrize("name", sorted(STRATEGIES))
def test_no_lookahead_future_rows_do_not_change_targets(name):
    spec = STRATEGIES[name]
    cols = {s: gbm_close(900, seed=i + 1) for i, s in enumerate(spec.universe)}
    f = frame(cols)
    for asof in f.index[[400, 555, 700, 850]]:
        past = f.loc[:asof]
        base = spec.compute_targets(past, asof)
        tampered = f.copy()
        tampered.loc[tampered.index > asof, spec.universe] *= 3.0  # wildly different future
        assert spec.compute_targets(tampered, asof) == base  # extra rows after asof are ignored
        assert spec.compute_targets(tampered.loc[:asof], asof) == base
        w = base
        assert all(v >= 0 for v in w.values()) and sum(w.values()) <= 1.0 + 1e-12


@pytest.mark.parametrize("offset", [-1, 0, 5, 20])
def test_monthly_anchors_are_causal(offset):
    idx = pd.bdate_range("2019-01-01", "2021-12-31")
    full = month_anchor_positions(idx, offset)
    for asof_pos in full[3:]:
        trunc = month_anchor_positions(idx[: asof_pos + 1], offset)
        np.testing.assert_array_equal(trunc, full[full <= asof_pos])


def test_variants_and_offsets():
    v = make_variant("trend_sma", lookback=7)
    assert v.params["lookback"] == 7 and v.family == "trend_sma"
    g = make_variant("gtaa4", lookback=12, offset=3)
    assert g.signal_offset == 3 and g.universe == ["SPY", "EFA", "IEF", "VNQ"] and g.name == "gtaa4_L12_o3"


# ---------------------------------------------------------------- exit-to-cash declaration (R2)
def test_registry_specs_declare_exit_to_cash_explicitly():
    from stocktry.strategies.registry import STRATEGIES

    expected = {"spy_buy_hold": False, "sixty_forty": False, "trend_sma10": True, "trend_absmom12": True,
                "trend_ensemble": True, "gtaa4": True, "gtaa5": True}
    assert {k: v.allows_exit_to_cash for k, v in STRATEGIES.items()} == expected
    assert all(isinstance(v.allows_exit_to_cash, bool) for v in STRATEGIES.values())
    assert {k for k, v in STRATEGIES.items() if v.uses_tbill} == {"trend_absmom12", "trend_ensemble"}


def test_runner_reads_the_field_not_the_family_name(caplog):
    from dataclasses import replace

    from stocktry.execution.strategy_io import declares_exit_to_cash
    from stocktry.strategies.registry import STRATEGIES
    from stocktry.strategies.trend import make_trend_sma

    trend = make_trend_sma("SPY", 10)
    assert declares_exit_to_cash(trend) is True
    # a trend-family spec that does NOT declare it is not allowed (the old family allow-list is gone)
    assert declares_exit_to_cash(replace(trend, allows_exit_to_cash=False)) is False
    assert declares_exit_to_cash(STRATEGIES["sixty_forty"]) is False

    class Legacy:  # a spec object without the field: safe default and a logged warning
        name, family = "legacy", "trend_sma"

    with caplog.at_level("WARNING"):
        assert declares_exit_to_cash(Legacy()) is False
    assert "does not declare allows_exit_to_cash" in caplog.text
    with pytest.raises(TypeError):
        declares_exit_to_cash(replace(trend, allows_exit_to_cash="yes"))
