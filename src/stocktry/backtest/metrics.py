"""Performance metrics from **monthly** returns (decimal, e.g. 0.01 = 1 %).

Annualization conventions (tested against hand-computed values):

* CAGR = (prod(1 + r)) ** (12 / n) - 1 for n monthly returns.
* Volatility = sample standard deviation (ddof = 1) of monthly returns * sqrt(12).
* Sharpe = mean(r - rf) / std(r - rf, ddof = 1) * sqrt(12), where rf is the
  monthly T-bill return on the same months (never zero unless cash earns zero).
* Sortino = mean(r - rf) / sqrt(mean(min(r - rf, 0) ** 2)) * sqrt(12)
  (downside deviation over all n months, target = T-bill).
* Tracking error = std(r - b, ddof = 1) * sqrt(12); beta = cov(r, b) / var(b)
  (both ddof = 1); correlation = Pearson.
* Max drawdown = min over time of equity / running peak - 1 (negative number),
  from the daily equity curve where available (deeper than month-end), else
  from month-end equity. Drawdown duration = the longest spell, in months,
  from a month-end peak until equity first regains it (or the sample end).
* Calmar = CAGR / |max drawdown|.
* Hit rate = share of months with r > 0.
* Regime slices compound the monthly returns of the months named, both ends
  inclusive (e.g. 2020-02..2020-04 = Feb, Mar and Apr 2020).
"""
from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

PERIODS_PER_YEAR = 12

REGIMES: tuple[tuple[str, str, str], ...] = (
    ("Dot-com bust", "2000-03", "2002-09"),
    ("Global financial crisis", "2007-10", "2009-03"),
    ("2009 rebound (momentum crash)", "2009-03", "2009-12"),
    ("COVID crash", "2020-02", "2020-04"),
    ("2022 rate shock", "2022-01", "2022-12"),
)


def _arr(x: pd.Series | np.ndarray | Iterable[float]) -> np.ndarray:
    return np.asarray(x, dtype=float)


def _excess(r: pd.Series, rf: pd.Series | float | None) -> np.ndarray:
    if rf is None:
        return _arr(r)
    if isinstance(rf, (int, float)):
        return _arr(r) - float(rf)
    if isinstance(r, pd.Series) and isinstance(rf, pd.Series):
        return _arr(r) - _arr(rf.reindex(r.index).fillna(0.0))
    return _arr(r) - _arr(rf)


def cagr(r: pd.Series | np.ndarray, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    a = _arr(r)
    if len(a) == 0:
        return float("nan")
    g = float(np.prod(1.0 + a))
    if g <= 0:
        return -1.0
    return g ** (periods_per_year / len(a)) - 1.0


def total_return(r: pd.Series | np.ndarray) -> float:
    return float(np.prod(1.0 + _arr(r)) - 1.0)


def annualized_vol(r: pd.Series | np.ndarray, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    a = _arr(r)
    return float(np.std(a, ddof=1) * math.sqrt(periods_per_year)) if len(a) > 1 else float("nan")


def sharpe_per_period(r: pd.Series | np.ndarray, rf: pd.Series | float | None = None) -> float:
    """Non-annualized Sharpe: mean(excess) / std(excess, ddof=1)."""
    ex = _excess(r, rf)
    if len(ex) < 2:
        return float("nan")
    sd = np.std(ex, ddof=1)
    return float(np.mean(ex) / sd) if sd > 0 else float("nan")


def sharpe(r: pd.Series | np.ndarray, rf: pd.Series | float | None = None,
           periods_per_year: int = PERIODS_PER_YEAR) -> float:
    return sharpe_per_period(r, rf) * math.sqrt(periods_per_year)


def sortino(r: pd.Series | np.ndarray, rf: pd.Series | float | None = None,
            periods_per_year: int = PERIODS_PER_YEAR) -> float:
    ex = _excess(r, rf)
    if len(ex) < 2:
        return float("nan")
    dd = math.sqrt(float(np.mean(np.minimum(ex, 0.0) ** 2)))
    return float(np.mean(ex) / dd * math.sqrt(periods_per_year)) if dd > 0 else float("nan")


def equity_from_returns(r: pd.Series | np.ndarray, start: float = 1.0) -> np.ndarray:
    """Equity path including the starting value (length n + 1)."""
    return start * np.r_[1.0, np.cumprod(1.0 + _arr(r))]


def drawdown(equity: pd.Series | np.ndarray) -> np.ndarray:
    e = _arr(equity)
    peak = np.maximum.accumulate(e)
    return e / peak - 1.0


def max_drawdown(equity: pd.Series | np.ndarray) -> float:
    e = _arr(equity)
    return float(drawdown(e).min()) if len(e) else float("nan")


def max_drawdown_from_returns(r: pd.Series | np.ndarray) -> float:
    return max_drawdown(equity_from_returns(r))


def max_drawdown_duration(equity: pd.Series | np.ndarray) -> int:
    """Longest run of consecutive periods strictly below the running peak (periods of the input)."""
    dd = drawdown(_arr(equity))
    best = cur = 0
    for x in dd:
        if x < -1e-12:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def calmar(r: pd.Series | np.ndarray, mdd: float | None = None) -> float:
    m = max_drawdown_from_returns(r) if mdd is None else mdd
    return cagr(r) / abs(m) if m and m < 0 else float("nan")


def hit_rate(r: pd.Series | np.ndarray) -> float:
    a = _arr(r)
    return float(np.mean(a > 0)) if len(a) else float("nan")


def beta(r: pd.Series, b: pd.Series) -> float:
    j = pd.concat([r, b], axis=1, join="inner").dropna().to_numpy()
    if len(j) < 2 or np.var(j[:, 1], ddof=1) == 0:
        return float("nan")
    return float(np.cov(j[:, 0], j[:, 1], ddof=1)[0, 1] / np.var(j[:, 1], ddof=1))


def correlation(r: pd.Series, b: pd.Series) -> float:
    j = pd.concat([r, b], axis=1, join="inner").dropna()
    return float(j.iloc[:, 0].corr(j.iloc[:, 1])) if len(j) > 2 else float("nan")


def tracking_error(r: pd.Series, b: pd.Series, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    j = pd.concat([r, b], axis=1, join="inner").dropna()
    d = (j.iloc[:, 0] - j.iloc[:, 1]).to_numpy()
    return float(np.std(d, ddof=1) * math.sqrt(periods_per_year)) if len(d) > 1 else float("nan")


def skew_kurtosis(x: pd.Series | np.ndarray) -> tuple[float, float]:
    """Sample skewness and **non-excess** kurtosis (normal = 3), bias-corrected."""
    a = _arr(x)
    if len(a) < 4 or np.std(a) == 0:
        return float("nan"), float("nan")
    return float(stats.skew(a, bias=False)), float(stats.kurtosis(a, fisher=False, bias=False))


def annual_returns(r: pd.Series) -> pd.Series:
    """Calendar-year compounded returns; partial first/last years are included (flag separately)."""
    g = (1.0 + r).groupby(r.index.year).prod() - 1.0
    g.index.name = "year"
    return g


def months_in_year(r: pd.Series) -> pd.Series:
    return r.groupby(r.index.year).size()


def slice_return(r: pd.Series, start: str, end: str) -> tuple[float, float, int]:
    """(compounded return, max drawdown within the slice, months) for months start..end inclusive."""
    p = r.index.to_period("M")
    sel = r[(p >= pd.Period(start, "M")) & (p <= pd.Period(end, "M"))]
    if sel.empty:
        return float("nan"), float("nan"), 0
    return total_return(sel), max_drawdown_from_returns(sel), len(sel)


def regime_table(returns: dict[str, pd.Series], regimes=REGIMES) -> pd.DataFrame:
    rows = []
    for label, a, b in regimes:
        row: dict[str, Any] = {"regime": label, "months": f"{a}..{b}"}
        for name, r in returns.items():
            tr, mdd, n = slice_return(r, a, b)
            expected = (pd.Period(b, "M") - pd.Period(a, "M")).n + 1
            row[name] = tr if n == expected else float("nan")
        rows.append(row)
    return pd.DataFrame(rows).set_index("regime")


def count_switches(rebalances: pd.DataFrame, tol: float = 1e-9) -> int:
    """Rebalances whose target weights differ from the previous rebalance's (initial buy excluded)."""
    if rebalances is None or len(rebalances) < 2:
        return 0
    prev = None
    n = 0
    for tg in rebalances["targets"]:
        if prev is not None:
            keys = set(tg) | set(prev)
            if any(abs(tg.get(k, 0.0) - prev.get(k, 0.0)) > tol for k in keys):
                n += 1
        prev = tg
    return n


def summarize(result: Any, bench: pd.Series | None = None) -> dict[str, Any]:
    """Headline metrics for a :class:`~stocktry.backtest.engine.BacktestResult`."""
    r = result.monthly_returns
    rf = result.rf_monthly
    years = len(r) / PERIODS_PER_YEAR
    mdd_daily = max_drawdown(result.equity)
    reb = result.rebalances
    turnover = float(reb["turnover"].iloc[1:].sum()) if len(reb) > 1 else 0.0
    out: dict[str, Any] = {
        "strategy": result.strategy,
        "first_month": str(r.index[0].to_period("M")) if len(r) else None,
        "last_month": str(r.index[-1].to_period("M")) if len(r) else None,
        "months": len(r),
        "cagr": cagr(r),
        "vol": annualized_vol(r),
        "sharpe": sharpe(r, rf),
        "sortino": sortino(r, rf),
        "max_dd": mdd_daily,
        "max_dd_monthly": max_drawdown(result.month_end_equity),
        "dd_duration_months": max_drawdown_duration(result.month_end_equity),
        "calmar": cagr(r) / abs(mdd_daily) if mdd_daily < 0 else float("nan"),
        "hit_rate": hit_rate(r),
        "turnover_per_year": turnover / years if years else float("nan"),
        "switches_per_year": count_switches(reb) / years if years else float("nan"),
        "exposure": float(result.exposure.iloc[1:].mean()) if len(result.exposure) > 1 else float("nan"),
        "final_equity": float(result.equity.iloc[-1]),
        "fees_total": result.total_fees,
        "spread_total": result.total_spread_cost,
        "orders": int(len(result.trades)),
        "skipped_orders": int(len(result.skipped)),
        "avg_cash_frac": float((result.cash / result.equity).iloc[1:].mean()),
    }
    sk, ku = skew_kurtosis(_excess(r, rf))
    out["skew"], out["kurtosis"] = sk, ku
    out["sharpe_monthly"] = sharpe_per_period(r, rf)
    if bench is not None:
        b = bench.reindex(r.index)
        out["beta"] = beta(r, b)
        out["correlation"] = correlation(r, b)
        out["tracking_error"] = tracking_error(r, b)
        out["excess_cagr"] = out["cagr"] - cagr(b.dropna())
    return out
