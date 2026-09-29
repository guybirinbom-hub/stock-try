"""Cost-model arithmetic (dollars; rates per $ or per share), including the Alpaca daily round-up."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from stocktry.backtest.costs import (
    AlpacaFeeModel,
    CommissionModel,
    CostModel,
    Order,
    ceil_cent,
    rate_on,
    SEC_FEE_SCHEDULE,
)
from stocktry.backtest.engine import EngineConfig, run_backtest
from stocktry.data.panel import panel_from_bars
from stocktry.data.universe import get_meta
from stocktry.strategies.base import StrategySpec

from conftest import make_bars

D = date(2026, 6, 1)  # SEC $20.60/M in force


def test_ceil_cent():
    assert ceil_cent(0.206) == 0.21
    assert ceil_cent(0.21) == 0.21  # float noise must not push an exact cent up
    assert ceil_cent(0.0000001) == 0.01
    assert ceil_cent(0.0) == 0.0
    assert ceil_cent(5e-9) == 0.01  # CAT on 1/600 of a share still costs a cent
    assert ceil_cent(0.1 + 0.2) == 0.30  # 0.30000000000000004 is float noise around an exact cent
    assert ceil_cent(0.3000001) == 0.31



def test_dollar_one_round_trip_costs_four_cents():
    m = AlpacaFeeModel()
    buy = m.day_fees(D, [Order("SPY", "buy", 1.0, 1.0 / 600)])
    sell = m.day_fees(date(2026, 6, 2), [Order("SPY", "sell", 1.0, 1.0 / 600)])
    assert (buy.sec, buy.taf, buy.cat) == (0.0, 0.0, 0.01)
    assert (sell.sec, sell.taf, sell.cat) == (0.01, 0.01, 0.01)
    assert buy.total + sell.total == pytest.approx(0.04)


def test_ten_thousand_dollar_sell():
    m = AlpacaFeeModel()
    f = m.day_fees(D, [Order("SPY", "sell", 10_000.0, 20.0)])  # 20 shares at $500
    assert f.sec == 0.21  # 10,000 * 20.60 / 1e6 = 0.206 -> 0.21
    assert f.taf == 0.01  # 20 * 0.000195 = 0.0039 -> 0.01
    assert f.cat == 0.01  # 20 * 0.000003 = 0.00006 -> 0.01
    assert f.total == pytest.approx(0.23)


def test_same_day_orders_share_the_round_up():
    m = AlpacaFeeModel()
    two = m.day_fees(D, [Order("SPY", "sell", 1.0, 0.002), Order("IEF", "sell", 1.0, 0.01)])
    assert (two.sec, two.taf, two.cat) == (0.01, 0.01, 0.01)  # not 0.02 each
    one_each = [m.day_fees(D, [o]) for o in (Order("SPY", "sell", 1.0, 0.002), Order("IEF", "sell", 1.0, 0.01))]
    assert sum(x.total for x in one_each) == pytest.approx(0.06)


def test_sec_dated_schedule():
    assert rate_on(SEC_FEE_SCHEDULE, date(2024, 1, 2)).rate == pytest.approx(27.80e-6)
    assert rate_on(SEC_FEE_SCHEDULE, date(2025, 5, 13)).rate == pytest.approx(27.80e-6)
    assert rate_on(SEC_FEE_SCHEDULE, date(2025, 5, 14)).rate == 0.0
    assert rate_on(SEC_FEE_SCHEDULE, date(2026, 4, 3)).rate == 0.0
    assert rate_on(SEC_FEE_SCHEDULE, date(2026, 4, 4)).rate == pytest.approx(20.60e-6)
    m = AlpacaFeeModel()
    assert m.day_fees(date(2025, 6, 2), [Order("SPY", "sell", 1e6, 2000)]).sec == 0.0
    assert m.day_fees(date(2020, 6, 2), [Order("SPY", "sell", 1e6, 2000)]).sec == pytest.approx(27.80)


def test_taf_cap_and_q4_2026_pause():
    m = AlpacaFeeModel()
    big = m.day_fees(D, [Order("SPY", "sell", 5e7, 100_000.0)])
    assert big.taf == 9.79  # 100,000 * 0.000195 = 19.50, capped per order
    two = m.day_fees(D, [Order("SPY", "sell", 5e7, 100_000.0), Order("IEF", "sell", 5e7, 100_000.0)])
    assert two.taf == pytest.approx(19.58)
    q4 = date(2026, 11, 2)
    assert m.day_fees(q4, [Order("SPY", "sell", 1000.0, 10.0)]).taf == 0.01  # pause OFF by default
    paused = AlpacaFeeModel(taf_q4_2026_pause=True)
    assert paused.day_fees(q4, [Order("SPY", "sell", 1000.0, 10.0)]).taf == 0.0
    assert paused.day_fees(date(2027, 1, 4), [Order("SPY", "sell", 1000.0, 10.0)]).taf == 0.01


def test_commission_model():
    assert CommissionModel().order_commission(1000) == 0.0
    ib = CommissionModel(flat=0.0, bps=100.0, minimum=1.0)  # 1 % with a $1 minimum
    assert ib.order_commission(10.0) == 1.0
    assert ib.order_commission(500.0) == pytest.approx(5.0)
    c = CostModel(commission=CommissionModel(flat=4.95))
    assert c.day_fees(pd.Timestamp(D), [Order("SPY", "buy", 100.0, 0.2)] * 2).commission == pytest.approx(9.90)


def test_tiers_and_scaling():
    spy = get_meta("SPY")
    assert CostModel.modelled().half_spread_bp(spy) == 0.5
    assert CostModel.gate().half_spread_bp(spy) == 5.0
    assert CostModel.gate().scaled(2).half_spread_bp(spy) == 10.0
    assert CostModel.gate().half_spread_bp(get_meta("DBC")) == 5.0
    assert CostModel.zero().half_spread_bp(spy) == 0.0
    f1 = CostModel.gate().day_fees(pd.Timestamp(D), [Order("SPY", "sell", 1e6, 2000)])
    f2 = CostModel.gate().scaled(2).day_fees(pd.Timestamp(D), [Order("SPY", "sell", 1e6, 2000)])
    assert f2.sec == pytest.approx(2 * f1.sec)


def _round_trip(capital: float):
    idx = pd.bdate_range("2026-05-01", "2026-08-31")
    panel = panel_from_bars({"SPY": make_bars(np.full(len(idx), 600.0), dates=idx)}, None)
    state = {}

    def fn(c, a):
        state[a] = a.month == 5
        return {"SPY": 1.0} if state[a] else {}

    spec = StrategySpec("rt", ["SPY"], None, fn)
    return run_backtest(spec, panel, EngineConfig(initial_capital=capital, costs=CostModel.modelled(),
                                                  start="2026-05", cash_yield=False))


def test_engine_dollar_one_round_trip():
    """$1 in, out a month later, through the engine: $0.04 of fees and the spread on both sides.

    The account starts with $1.01: buys never spend the cash the day's fees need (cash never goes
    negative, like the paper runner's cash buffer), so a $1.00 buy needs $1.00 + the $0.01 CAT fee.
    """
    res = _round_trip(1.01)
    assert len(res.trades) == 2
    buy, sell = res.trades.iloc[0], res.trades.iloc[1]
    hs = 0.5e-4
    # A $1.00 notional order at the ask (600 * (1 + hs)); quantity truncated to 9 decimals.
    assert buy["shares"] == pytest.approx(1.0 / (600 * (1 + hs)), abs=1e-9)
    assert buy["notional"] == pytest.approx(1.00, abs=1e-6)
    assert sell["shares"] == pytest.approx(buy["shares"], abs=1e-12)  # full exit, allowed below $1
    assert res.total_fees == pytest.approx(0.04)
    assert res.total_spread_cost == pytest.approx(2 * buy["shares"] * 600 * hs, rel=1e-9)
    assert res.equity.iloc[-1] == pytest.approx(1.01 - 0.04 - res.total_spread_cost, abs=1e-12)
    assert (res.cash >= 0).all()


def test_a_one_dollar_account_cannot_buy_one_dollar_and_pay_the_fee():
    """$1.00 cash: a $1.00 buy would leave -$0.01 after CAT; re-sized to $0.99 it is below the $1 buy minimum,
    so it is skipped and logged. Cash never goes negative."""
    res = _round_trip(1.00)
    assert len(res.trades) == 0 and (res.cash >= 0).all()
    assert len(res.skipped) == 1 and res.skipped.iloc[0]["side"] == "buy"
    assert "buy minimum" in res.skipped.iloc[0]["reason"] and "fees" in res.skipped.iloc[0]["reason"]


def test_sells_have_no_dollar_minimum_but_buys_do():
    """R3: Alpaca's $1 minimum applies to buy entry orders only. A $0.40 trim of an over-weight position is sold;
    the matching $0.40 top-up buy is skipped and logged."""
    idx = pd.bdate_range("2026-01-02", "2026-04-30")
    a = np.full(len(idx), 100.0)
    b = np.full(len(idx), 100.0)
    mar = idx >= pd.Timestamp("2026-03-01")
    a[mar], b[mar] = 104.0, 96.0  # after the first rebalance (filled 2026-02-02) A drifts up 4%, B down 4%
    panel = panel_from_bars({"AAA": make_bars(a, dates=idx), "BBB": make_bars(b, dates=idx)}, None)
    spec = StrategySpec("half", ["AAA", "BBB"], None, lambda c, t: {"AAA": 0.5, "BBB": 0.5})
    res = run_backtest(spec, panel, EngineConfig(initial_capital=20.0, costs=CostModel.modelled(), start="2026-01",
                                                 cash_yield=False))
    later = res.trades[res.trades["exec_date"] > pd.Timestamp("2026-03-01")]
    sells = later[later["side"] == "sell"]
    assert len(sells) >= 1 and (sells["notional"] < 1.0).all() and (sells["symbol"] == "AAA").all()
    assert not (later["side"] == "buy").any()
    sk = res.skipped[res.skipped["exec_date"] > pd.Timestamp("2026-03-01")]
    assert len(sk) >= 1 and set(sk["side"]) == {"buy"} and (sk["symbol"] == "BBB").all()
    assert (res.cash >= 0).all()


def test_sell_notional_and_sec_base_are_the_bid_proceeds():
    """CORE-13: a sell fills at the bid; its notional (and the SEC fee base) is shares x mid x (1 - half-spread)."""
    idx = pd.bdate_range("2026-05-01", "2026-08-31")
    panel = panel_from_bars({"SPY": make_bars(np.full(len(idx), 600.0), dates=idx)}, None)
    spec = StrategySpec("rt", ["SPY"], None, lambda c, a: {"SPY": 1.0} if a.month == 5 else {})
    res = run_backtest(spec, panel, EngineConfig(initial_capital=1_000_000.0, costs=CostModel.gate(),
                                                 start="2026-05", cash_yield=False))
    sell = res.trades[res.trades["side"] == "sell"].iloc[0]
    assert sell["notional"] == pytest.approx(sell["shares"] * 600.0 * (1 - 5e-4), rel=1e-12)
