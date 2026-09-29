"""Engine timing, sizing, cash accrual and guards on synthetic data."""
from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from stocktry.backtest.costs import CostModel
from stocktry.backtest.engine import EngineConfig, EngineError, run_backtest
from stocktry.data.panel import panel_from_bars
from stocktry.data.universe import SymbolMeta
from stocktry.strategies.base import StrategySpec
from stocktry.strategies.buy_and_hold import make_buy_and_hold, make_sixty_forty

from conftest import make_bars


def spec_from(fn, universe=("AAA",), cash=None, **kw) -> StrategySpec:
    return StrategySpec(name="t", universe=list(universe), cash_symbol=cash, compute_targets=fn, **kw)


def jump_panel():
    """Flat 100 until the Jan month-end; the next open gaps to 150 (close 150 afterwards)."""
    idx = pd.bdate_range("2021-01-04", "2021-04-30")
    close = np.full(len(idx), 100.0)
    op = np.full(len(idx), 100.0)
    je = idx[idx.month == 1][-1]
    k = idx.get_loc(je)
    close[k + 1:] = 150.0
    op[k + 1] = 150.0
    op[k + 2:] = 150.0
    return panel_from_bars({"AAA": make_bars(close, dates=idx, open_=op)}, None), idx, k


def test_signal_at_month_end_fill_at_next_open():
    panel, idx, k = jump_panel()
    res = run_backtest(make_buy_and_hold("AAA"), panel, EngineConfig(initial_capital=1000.0, costs=CostModel.zero(),
                                                                      start="2021-01", cash_yield=False))
    t = res.trades.iloc[0]
    assert t["signal_date"] == idx[k] and t["exec_date"] == idx[k + 1]
    assert t["price_raw"] == pytest.approx(150.0)  # the open after the gap, NOT the 100 month-end close
    assert res.equity.iloc[-1] == pytest.approx(1000.0)  # bought at 150, still 150: no gain from the gap


def test_same_bar_fill_captures_gap_and_is_flagged():
    panel, idx, k = jump_panel()
    cfg = EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2021-01", cash_yield=False,
                       same_bar_fill=True)
    res = run_backtest(make_buy_and_hold("AAA"), panel, cfg)
    assert res.leaky
    assert res.equity.iloc[-1] == pytest.approx(1500.0)  # the look-ahead the normal path forbids


def test_next_close_mode_and_extra_lag():
    panel, idx, k = jump_panel()
    base = EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2021-01", cash_yield=False,
                        fill="next_close")
    r1 = run_backtest(make_buy_and_hold("AAA"), panel, base)
    assert r1.trades.iloc[0]["exec_date"] == idx[k + 1]
    r2 = run_backtest(make_buy_and_hold("AAA"), panel, replace(base, extra_lag_days=1))
    assert r2.trades.iloc[0]["exec_date"] == idx[k + 2]


def test_strategy_sees_only_data_up_to_asof(gbm):
    idx = pd.bdate_range("2015-01-01", periods=800)
    panel = panel_from_bars({"AAA": make_bars(gbm(800), dates=idx)}, pd.Series(2.0, index=idx))
    seen = []

    def fn(closes, asof):
        seen.append((closes.index[-1], asof, len(closes)))
        return {"AAA": 1.0}

    run_backtest(spec_from(fn), panel, EngineConfig(costs=CostModel.zero(), start="2015-02"))
    assert seen and all(last == asof for last, asof, _ in seen)
    assert all(last.month != (last + pd.offsets.BDay(1)).month for last, _, _ in seen)  # month-ends only
    assert all(n == idx.get_loc(a) + 1 for _, a, n in seen)


def test_min_notional_skip_logged():
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    panel = panel_from_bars({"AAA": make_bars(np.full(len(idx), 50.0), dates=idx)}, None)
    res = run_backtest(make_buy_and_hold("AAA"), panel, EngineConfig(initial_capital=0.80, costs=CostModel.modelled(),
                                                                      start="2021-01", cash_yield=False))
    assert len(res.trades) == 0 and len(res.skipped) >= 1
    assert res.skipped.iloc[0]["notional"] == pytest.approx(0.80, rel=1e-3)
    assert "minimum" in res.skipped.iloc[0]["reason"]
    assert res.equity.iloc[-1] == pytest.approx(0.80)


def test_whole_shares_round_down_and_leave_cash():
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    panel = panel_from_bars({"AAA": make_bars(np.full(len(idx), 300.0), dates=idx)}, None)
    cfg = EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2021-01", cash_yield=False,
                       whole_shares=True)
    res = run_backtest(make_buy_and_hold("AAA"), panel, cfg)
    assert res.trades.iloc[0]["shares"] == 3
    assert res.cash.iloc[-1] == pytest.approx(100.0)
    frac = run_backtest(make_buy_and_hold("AAA"), panel, replace(cfg, whole_shares=False))
    assert frac.trades.iloc[0]["shares"] == math.trunc(1000 / 300 * 1e9) / 1e9  # 9 decimals
    assert frac.trades.iloc[0]["notional"] == pytest.approx(1000.0, abs=1e-6)


def test_whole_shares_use_as_traded_price(dividend_payer_bars):
    """Adjusted prices are below as-traded prices in the past: share counts must use the as-traded one."""
    panel = panel_from_bars({"SPY": dividend_payer_bars}, None)
    cfg = EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2005-01", cash_yield=False,
                       whole_shares=True)
    res = run_backtest(make_buy_and_hold("SPY"), panel, cfg)
    t = res.trades.iloc[0]
    raw_open = dividend_payer_bars.loc[t["exec_date"], "close_raw"]  # opens == closes in this fixture
    assert t["price_raw"] == pytest.approx(raw_open)
    assert t["shares"] == math.floor(1000.0 / raw_open)


def test_cash_accrues_tbill_daily_with_previous_day_rate():
    idx = pd.bdate_range("2021-01-04", "2021-06-30")
    y = pd.Series(5.0, index=idx)
    panel = panel_from_bars({"AAA": make_bars(np.full(len(idx), 10.0), dates=idx)}, y)
    res = run_backtest(spec_from(lambda c, a: {}), panel, EngineConfig(initial_capital=1000.0, start="2021-01"))
    n = len(res.equity) - 1
    assert res.equity.iloc[-1] == pytest.approx(1000.0 * (1 + 0.05 / 252) ** n, rel=1e-12)
    # Monthly T-bill returns used for Sharpe equal the cash growth exactly.
    np.testing.assert_allclose(res.monthly_returns.to_numpy(), res.rf_monthly.to_numpy())


def test_cash_symbol_receives_remainder():
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    frames = {"AAA": make_bars(np.full(len(idx), 10.0), dates=idx), "BIL": make_bars(np.full(len(idx), 50.0), dates=idx)}
    panel = panel_from_bars(frames, None)
    spec = spec_from(lambda c, a: {"AAA": 0.25}, cash="BIL")
    res = run_backtest(spec, panel, EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2021-01",
                                                 cash_yield=False))
    w = res.weights.iloc[1]
    assert w["AAA"] == pytest.approx(0.25) and w["BIL"] == pytest.approx(0.75)
    assert res.exposure.iloc[1] == pytest.approx(0.25)


@pytest.mark.parametrize("bad", [{"AAA": 0.7, "BBB": 0.7}, {"AAA": -0.1}, {"ZZZ": 0.5}, {"AAA": float("nan")}])
def test_invalid_targets_raise(bad):
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    frames = {s: make_bars(np.full(len(idx), 10.0), dates=idx) for s in ("AAA", "BBB")}
    panel = panel_from_bars(frames, None)
    with pytest.raises(EngineError):
        run_backtest(spec_from(lambda c, a: bad, universe=("AAA", "BBB")), panel, EngineConfig(start="2021-01"))


def test_target_without_price_raises():
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    frames = {"AAA": make_bars(np.full(len(idx), 10.0), dates=idx),
              "BBB": make_bars(np.full(len(idx) - 40, 10.0), dates=idx[40:])}
    panel = panel_from_bars(frames, None)
    with pytest.raises(EngineError):
        run_backtest(spec_from(lambda c, a: {"BBB": 0.5}, universe=("AAA", "BBB")), panel,
                     EngineConfig(start="2021-01"))


def test_annual_rebalance_only_in_december(gbm):
    idx = pd.bdate_range("2018-01-01", "2021-12-31")
    frames = {"SPY": make_bars(gbm(len(idx), seed=1), dates=idx), "AGG": make_bars(gbm(len(idx), 0.03, 0.04, 2),
                                                                                    dates=idx)}
    panel = panel_from_bars(frames, None)
    res = run_backtest(make_sixty_forty("SPY", "AGG"), panel, EngineConfig(costs=CostModel.zero(), start="2018-03"))
    months = [d.month for d in res.rebalances["signal_date"]]
    assert months[0] == 3 and set(months[1:]) == {12}


def test_index_level_series_charged_expense_ratio():
    idx = pd.bdate_range("2021-01-04", "2021-12-31")
    meta = {"IDX": SymbolMeta("IDX", "index", "us_equity", "2000-01-01", 0.01, 0.0, True, is_index_level=True)}
    panel = panel_from_bars({"IDX": make_bars(np.full(len(idx), 100.0), dates=idx)}, None, meta=meta)
    res = run_backtest(make_buy_and_hold("IDX"), panel, EngineConfig(initial_capital=1000.0, costs=CostModel.zero(),
                                                                      start="2021-01", cash_yield=False))
    days = len(res.equity) - 2  # held from the first execution day's close onward
    assert res.equity.iloc[-1] == pytest.approx(1000.0 * (1 - 0.01 / 252) ** days, rel=1e-6)


def test_turnover_and_rebalance_records(gbm):
    idx = pd.bdate_range("2019-01-01", "2020-12-31")
    panel = panel_from_bars({"AAA": make_bars(gbm(len(idx)), dates=idx)}, None)

    def fn(c, a):  # in on even months, out on odd months: a full switch every month
        return {"AAA": 1.0} if a.month % 2 == 0 else {}

    res = run_backtest(spec_from(fn), panel, EngineConfig(initial_capital=10_000.0, costs=CostModel.gate(),
                                                          start="2019-01"))
    trades = res.rebalances[res.rebalances["n_orders"] > 0]
    assert (trades["turnover"] > 0.95).all() and (trades["turnover"] < 1.05).all()
    assert (res.rebalances["spread_cost"] >= 0).all() and res.total_fees > 0
