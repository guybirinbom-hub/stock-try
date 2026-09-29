"""Independent cross-checks of the engine and the data.

bt cross-check
--------------
bt 1.2.3 is an independent open-source backtester. We reproduce buy-and-hold
SPY and the 10-month SMA rule in bt with:

* ``RunMonthly(run_on_first_date=False, run_on_end_of_period=False)`` -- bt
  runs on the **first trading day of each month**;
* ``SelectWhere`` on a signal frame computed independently here with pandas
  (the SMA rule evaluated every day: close > mean of the previous 9 month-end
  closes and today's close) and **lagged one row**, so the rebalance on the
  first trading day of month m uses the signal of the last trading day of m-1;
* ``WeighEqually`` + ``Rebalance``, zero commissions, ``integer_positions=False``.

bt fills at that day's close, which is exactly our engine's ``next_close``
mode (signal at month-end close, fill at the next day's close). Our engine is
run with zero costs and zero cash yield (bt's cash earns nothing).
With ``run_on_end_of_period=True`` bt trades *on* the month-end bar; with the
same lagged frame it uses the signal of the day before month-end and fills at
the month-end close -- one day earlier than our engine on both the signal and
the fill. bt cannot express "signal at the month-end close, fill on the next
day" with that option, so that variant is reported for information only and
is not gated.

Pre-registered tolerance: max |monthly return difference| <= 1 bp.

Ken French cross-check
----------------------
* SPY (VFINX-spliced before 1993-02) monthly total returns vs the CRSP market
  (Mkt-RF + RF): correlation >= 0.99 and |CAGR difference| <= 75 bp/yr over
  the overlap. (S&P 500 vs the total market differs by construction in single
  years; the per-year differences are reported, not gated.)
* Our monthly T-bill return (DTB3 daily-accrual index) vs French RF
  (1-month bill) from 1990-01: **every** month within 10 bp. The mean and
  count of exceptions are reported too.
"""
from __future__ import annotations

import pandas as pd

from ..backtest import metrics as M
from ..backtest.costs import CostModel
from ..backtest.engine import EngineConfig, run_backtest
from ..backtest.schedule import month_end_dates
from ..data.panel import PricePanel
from ..strategies.buy_and_hold import make_buy_and_hold
from ..strategies.trend import make_trend_sma

BT_TOL_MONTHLY = 1e-4  # 1 bp
FF_MIN_CORR = 0.99
FF_MAX_CAGR_DIFF = 0.0075
RF_MAX_DIFF = 0.0010  # 10 bp per month
RF_FROM = "1990-01"


def _bt_sma_signal_daily(close: pd.Series, lookback: int) -> pd.Series:
    """Independent pandas implementation of the Faber SMA rule evaluated on EVERY day.

    On day d of month m the "monthly closes" are the month-end closes of the
    previous ``lookback - 1`` months plus close(d); the signal is close(d) >
    their mean. On a month-end day this equals the engine's month-end signal.
    """
    c = close.dropna()
    per = c.index.to_period("M")
    me = c.groupby(per).last()  # month-end close per Period
    prev_sum = me.rolling(lookback - 1).sum().shift(1)  # sum of the previous L-1 month-ends
    s_prev = pd.Series(prev_sum.reindex(per).to_numpy(), index=c.index)
    sma = (s_prev + c) / lookback
    return (c > sma).where(sma.notna(), False).astype(bool)


def _run_bt(prices: pd.DataFrame, signal: pd.DataFrame, name: str, end_of_period: bool) -> pd.Series:
    import bt  # imported lazily; only needed for this check

    algos = [
        bt.algos.RunMonthly(run_on_first_date=False, run_on_end_of_period=end_of_period, run_on_last_date=False),
        bt.algos.SelectWhere(signal),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance(),
    ]
    strat = bt.Strategy(name, algos)
    test = bt.Backtest(strat, prices, initial_capital=1_000_000.0, integer_positions=False, progress_bar=False)
    res = bt.run(test)
    return res.backtests[name].strategy.values


def bt_crosscheck(panel: PricePanel, symbol: str = "SPY", start: str = "1993-12", end: str | None = None,
                  lookback: int = 10) -> pd.DataFrame:
    """Compare engine (next_close, zero cost, zero cash yield) with bt for B&H and SMA-L."""
    cfg = EngineConfig(initial_capital=1_000_000.0, fill="next_close", costs=CostModel.zero(), cash_yield=False,
                       start=start, end=end)
    rows = []
    for label, spec in (("buy_hold", make_buy_and_hold(symbol)), (f"sma{lookback}", make_trend_sma(symbol, lookback))):
        eng = run_backtest(spec, panel, cfg)
        d0, d1 = eng.equity.index[0], eng.equity.index[-1]
        close = panel.closes[symbol]
        prices = close.loc[d0:d1].to_frame(symbol)
        if label == "buy_hold":
            sig = pd.DataFrame(True, index=prices.index, columns=[symbol])
        else:
            daily = _bt_sma_signal_daily(close.loc[:d1], lookback)
            sig = daily.shift(1).fillna(False).loc[d0:d1].to_frame(symbol)  # LAGGED one row
        me = eng.month_end_equity.index
        for eop in (False, True):
            vals = _run_bt(prices, sig, f"{label}_{'eop' if eop else 'first'}", eop)
            bt_me = vals.reindex(me)
            bt_r = bt_me.pct_change().iloc[1:]
            diff = (eng.monthly_returns - bt_r).dropna()
            rows.append({
                "strategy": label, "bt_schedule": "month-end bar (run_on_end_of_period=True)" if eop
                else "first trading day (run_on_end_of_period=False)",
                "months": len(diff), "max_abs_diff_bp": float(diff.abs().max() * 1e4),
                "mean_abs_diff_bp": float(diff.abs().mean() * 1e4),
                "engine_cagr": M.cagr(eng.monthly_returns), "bt_cagr": M.cagr(bt_r.dropna()),
                "tolerance_bp": BT_TOL_MONTHLY * 1e4,
                "gated": not eop,
                "passed": bool(diff.abs().max() <= BT_TOL_MONTHLY) if not eop else None,
            })
    return pd.DataFrame(rows)


def ff_market_crosscheck(spy_close: pd.Series, ff: pd.DataFrame) -> dict:
    """SPY (or its VFINX splice) monthly total returns vs Fama-French Mkt-RF + RF."""
    me = month_end_dates(spy_close.dropna().index)
    r = spy_close.reindex(me).pct_change().dropna()
    r.index = r.index.to_period("M")
    mkt = (ff["Mkt-RF"] + ff["RF"]).copy()
    mkt.index = mkt.index.to_period("M")
    j = pd.concat([r.rename("spy"), mkt.rename("mkt")], axis=1, join="inner").dropna()
    corr = float(j["spy"].corr(j["mkt"]))
    cagr_s, cagr_m = M.cagr(j["spy"]), M.cagr(j["mkt"])
    yr = (1 + j).groupby(j.index.year).prod() - 1
    full_years = j.groupby(j.index.year).size()
    yr = yr[full_years == 12]
    return {
        "first_month": str(j.index[0]), "last_month": str(j.index[-1]), "months": len(j),
        "correlation": corr, "spy_cagr": cagr_s, "mkt_cagr": cagr_m, "cagr_diff_bp": (cagr_s - cagr_m) * 1e4,
        "mean_annual_diff_bp": float((yr["spy"] - yr["mkt"]).mean() * 1e4),
        "max_abs_annual_diff_bp": float((yr["spy"] - yr["mkt"]).abs().max() * 1e4),
        "passed_corr": corr >= FF_MIN_CORR, "passed_cagr": abs(cagr_s - cagr_m) <= FF_MAX_CAGR_DIFF,
        "annual": (yr["spy"] - yr["mkt"]),
        "worst_months": {str(k): float(v) for k, v in
                         (j["spy"] - j["mkt"]).reindex((j["spy"] - j["mkt"]).abs().sort_values(ascending=False)
                                                       .index[:5]).items()},
    }


def ff_rf_crosscheck(tbill_idx: pd.Series, ff: pd.DataFrame, since: str = RF_FROM) -> dict:
    """Monthly T-bill returns from our daily-accrual index vs French RF (both decimal per month)."""
    me = month_end_dates(tbill_idx.index)
    ours = tbill_idx.reindex(me).pct_change().dropna()
    ours.index = ours.index.to_period("M")
    rf = ff["RF"].copy()
    rf.index = rf.index.to_period("M")
    j = pd.concat([ours.rename("ours"), rf.rename("ff")], axis=1, join="inner").dropna()
    j = j[j.index >= pd.Period(since, "M")]
    d = (j["ours"] - j["ff"])
    worst = d.abs().idxmax()
    return {
        "first_month": str(j.index[0]), "last_month": str(j.index[-1]), "months": len(j),
        "mean_diff_bp": float(d.mean() * 1e4), "mean_abs_diff_bp": float(d.abs().mean() * 1e4),
        "max_abs_diff_bp": float(d.abs().max() * 1e4), "worst_month": str(worst),
        "months_over_10bp": int((d.abs() > RF_MAX_DIFF + 1e-12).sum()),
        "annualized_mean_diff_bp": float(d.mean() * 12 * 1e4),
        "passed": bool((d.abs() <= RF_MAX_DIFF + 1e-12).all()),
        "diff": d,
    }


__all__ = ["bt_crosscheck", "ff_market_crosscheck", "ff_rf_crosscheck"]
