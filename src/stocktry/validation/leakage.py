"""Structural leakage tests (statistical corrections cannot detect look-ahead; these can).

(a) **Identity**: 100 % buy-and-hold of a symbol run through the engine, with
    zero costs, must reproduce the symbol's own total-return (adjusted close)
    monthly returns to within 1 bp/yr. The first month is excluded because the
    engine buys at the next day's open, not at the start close.

(b) **Foresight** (monthly bars, ``fill="next_close"``): an *oracle* strategy
    is handed, through a closure, the sign of the return of the bar right
    after the signal bar -- information it could never have. Through the
    engine's normal path the order fills at the close of that next bar, so the
    oracle's knowledge concerns a bar it can no longer trade: on a zero-drift
    geometric random walk its Sharpe must be within noise of zero. Only with
    ``same_bar_fill=True`` (forced internally here, never reachable from a
    CLI) does it earn the foreseen bar, and then its Sharpe is huge. The pair
    of results shows the engine's lag is what separates the two.

(c) **Gap foresight** (daily bars, default ``fill="next_open"``): the oracle
    knows the sign of the overnight gap from the signal close to the next
    open. The normal path fills at that open, so the gap is never captured
    (alpha ~ 0); same-bar fill captures it (large positive t-statistic).

(d) **One-bar shift**: each candidate is re-run with execution delayed by one
    extra trading day. A slow monthly rule should barely change; a large drop
    would indicate the result depended on information at the signal bar.

"Within noise" uses the standard error of an annualized Sharpe ratio under
the null, SE = sqrt((1 + SR^2 / 2) / years) with SR = 0 (Lo 2002, i.i.d.):
the lagged oracle must have |Sharpe| < 3 SE and |alpha t| < 3. "Huge" means
more than 10 SE and an alpha t-statistic above 10. (A long-only oracle sits
in cash half the time, so its annualized Sharpe is bounded near 2.4 whatever
the volatility; significance, not a fixed Sharpe level, is the right test.)
Alpha is the intercept of an OLS of strategy excess returns on the asset's
excess returns, which controls for the realized drift of the path.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..backtest import metrics as M
from ..backtest.costs import CostModel
from ..backtest.engine import EngineConfig, run_backtest
from ..data.panel import PricePanel, panel_from_bars
from ..strategies.base import StrategySpec
from ..strategies.buy_and_hold import make_buy_and_hold

IDENTITY_TOL_BP_PER_YEAR = 1.0


def sharpe_se(sr_annual: float, years: float) -> float:
    return math.sqrt((1.0 + sr_annual**2 / 2.0) / years) if years > 0 else float("nan")


def alpha_tstat(strategy_excess: pd.Series, asset_excess: pd.Series) -> tuple[float, float, float]:
    """OLS of strategy excess on asset excess: (monthly alpha, t-stat of alpha, beta)."""
    j = pd.concat([strategy_excess, asset_excess], axis=1, join="inner").dropna().to_numpy()
    y, x = j[:, 0], j[:, 1]
    X = np.c_[np.ones(len(x)), x]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(len(y) - 2, 1)
    s2 = resid @ resid / dof
    cov = s2 * np.linalg.inv(X.T @ X)
    return float(coef[0]), float(coef[0] / math.sqrt(cov[0, 0])) if cov[0, 0] > 0 else float("nan"), float(coef[1])


# --------------------------------------------------------------------------- (a) identity
def identity_test(panel: PricePanel, symbol: str = "SPY", start: str | None = None, end: str | None = None,
                  tol_bp_per_year: float = IDENTITY_TOL_BP_PER_YEAR) -> dict:
    spec = make_buy_and_hold(symbol)
    cfg = EngineConfig(initial_capital=1_000_000.0, costs=CostModel.zero(), start=start, end=end)
    res = run_backtest(spec, panel, cfg)
    eng = res.monthly_returns.iloc[1:]
    ref = panel.closes[symbol].reindex(res.month_end_equity.index).pct_change().reindex(eng.index)
    diff = eng - ref
    ann_bp = (M.cagr(eng) - M.cagr(ref)) * 1e4
    return {
        "symbol": symbol, "first_month": str(eng.index[0].to_period("M")), "last_month": str(eng.index[-1].to_period("M")),
        "months": len(eng), "engine_cagr": M.cagr(eng), "series_cagr": M.cagr(ref),
        "tracking_diff_bp_per_year": ann_bp, "max_abs_monthly_diff_bp": float(diff.abs().max() * 1e4),
        "tolerance_bp_per_year": tol_bp_per_year, "passed": abs(ann_bp) <= tol_bp_per_year,
    }


# --------------------------------------------------------------------------- oracle helpers
def oracle_strategy(symbol: str, signal: pd.Series, name: str = "oracle") -> StrategySpec:
    """A deliberately leaky strategy: ``signal`` (bool by date) is computed from FUTURE data."""
    sig = {pd.Timestamp(k): bool(v) for k, v in signal.items()}

    def compute_targets(closes: pd.DataFrame, asof: pd.Timestamp) -> dict[str, float]:
        return {symbol: 1.0} if sig.get(asof, False) else {}

    return StrategySpec(name=name, universe=[symbol], cash_symbol=None, compute_targets=compute_targets,
                        params={"oracle": True}, family="oracle")


def synthetic_monthly_panel(n_months: int = 600, sigma: float = 0.045, seed: int = 7, symbol: str = "SYN"
                            ) -> PricePanel:
    """Zero-drift (arithmetic mean 0) geometric random walk with ONE bar per month; cash earns 0."""
    rng = np.random.default_rng(seed)
    lr = rng.normal(-0.5 * sigma**2, sigma, n_months)
    close = 100.0 * np.exp(np.cumsum(lr))
    idx = pd.date_range("1950-01-31", periods=n_months, freq="BME")
    op = np.r_[100.0, close[:-1]]
    bars = pd.DataFrame({"open": op, "high": np.maximum(op, close), "low": np.minimum(op, close), "close": close,
                         "volume": 0, "close_raw": close, "dividend": 0.0}, index=idx)
    return panel_from_bars({symbol: bars}, None)


def synthetic_daily_panel(n_days: int = 37800, sigma_gap: float = 0.02, sigma_intraday: float = 0.002,
                          seed: int = 11, symbol: str = "SYN") -> PricePanel:
    """Zero-drift daily walk with explicit overnight gaps (open) and intraday moves (close)."""
    rng = np.random.default_rng(seed)
    g = rng.normal(-0.5 * sigma_gap**2, sigma_gap, n_days)
    d = rng.normal(-0.5 * sigma_intraday**2, sigma_intraday, n_days)
    op = 100.0 * np.exp(np.cumsum(g) + np.r_[0.0, np.cumsum(d)[:-1]])
    close = op * np.exp(d)
    idx = pd.bdate_range("1900-01-01", periods=n_days)
    bars = pd.DataFrame({"open": op, "high": np.maximum(op, close), "low": np.minimum(op, close), "close": close,
                         "volume": 0, "close_raw": close, "dividend": 0.0}, index=idx)
    return panel_from_bars({symbol: bars}, None)


def _pair(panel: PricePanel, spec: StrategySpec, fill: str, cash_yield: bool) -> tuple:
    base = dict(initial_capital=1_000_000.0, costs=CostModel.zero(), fill=fill, cash_yield=cash_yield)
    lag = run_backtest(spec, panel, EngineConfig(**base))
    leak = run_backtest(spec, panel, EngineConfig(**base, same_bar_fill=True))
    return lag, leak


# --------------------------------------------------------------------------- (b) monthly foresight
def foresight_test(panel: PricePanel, symbol: str = "SYN", cash_yield: bool = False,
                   huge_k: float = 10.0, noise_k: float = 3.0) -> dict:
    """Oracle knows sign(close[t+1]/close[t]-1) at each monthly bar t; engine fills at next close."""
    c = panel.closes[symbol]
    signal = (c.shift(-1) / c - 1.0 > 0).fillna(False)
    spec = oracle_strategy(symbol, signal)
    lag, leak = _pair(panel, spec, "next_close", cash_yield)
    years = len(lag.monthly_returns) / 12.0
    sr_lag = M.sharpe(lag.monthly_returns, lag.rf_monthly)
    sr_leak = M.sharpe(leak.monthly_returns, leak.rf_monthly)
    se = sharpe_se(0.0, years)
    asset = c.reindex(lag.month_end_equity.index).pct_change().reindex(lag.monthly_returns.index)
    rf = lag.rf_monthly
    a_lag = alpha_tstat(lag.monthly_returns - rf, asset - rf)
    a_leak = alpha_tstat(leak.monthly_returns - rf, asset - rf)
    return {
        "years": years, "sharpe_lagged": sr_lag, "sharpe_same_bar": sr_leak, "sharpe_se": se,
        "alpha_t_lagged": a_lag[1], "alpha_t_same_bar": a_leak[1],
        "cagr_lagged": M.cagr(lag.monthly_returns), "cagr_same_bar": M.cagr(leak.monthly_returns),
        "noise_band": noise_k * se, "huge_threshold": huge_k * se,
        "lagged_sharpe_within_noise": abs(sr_lag) < noise_k * se,
        "lagged_alpha_within_noise": abs(a_lag[1]) < noise_k,
        "same_bar_huge": sr_leak > huge_k * se and a_leak[1] > huge_k,
    }


# --------------------------------------------------------------------------- (c) gap foresight
def gap_foresight_test(panel: PricePanel, symbol: str = "SYN", cash_yield: bool = False,
                       t_leak_min: float = 4.0, t_lag_max: float = 3.0) -> dict:
    """Oracle knows sign(open[t+1]/close[t]-1) at each month-end t; default next-open fill."""
    c, o = panel.closes[symbol], panel.opens[symbol]
    signal = (o.shift(-1) / c - 1.0 > 0).fillna(False)
    spec = oracle_strategy(symbol, signal)
    lag, leak = _pair(panel, spec, "next_open", cash_yield)
    asset = c.reindex(lag.month_end_equity.index).pct_change().reindex(lag.monthly_returns.index)
    rf = lag.rf_monthly
    a_lag = alpha_tstat(lag.monthly_returns - rf, asset - rf)
    a_leak = alpha_tstat(leak.monthly_returns - rf, asset - rf)
    return {
        "years": len(lag.monthly_returns) / 12.0,
        "alpha_bp_per_month_lagged": a_lag[0] * 1e4, "alpha_t_lagged": a_lag[1],
        "alpha_bp_per_month_same_bar": a_leak[0] * 1e4, "alpha_t_same_bar": a_leak[1],
        "sharpe_lagged": M.sharpe(lag.monthly_returns, rf), "sharpe_same_bar": M.sharpe(leak.monthly_returns, rf),
        "lagged_no_gap_capture": abs(a_lag[1]) < t_lag_max, "same_bar_captures_gap": a_leak[1] > t_leak_min,
    }


# --------------------------------------------------------------------------- (d) one-bar shift
def one_bar_shift(spec: StrategySpec, panel: PricePanel, config: EngineConfig) -> dict:
    from dataclasses import replace

    base = run_backtest(spec, panel, config)
    shifted = run_backtest(spec, panel, replace(config, extra_lag_days=1))
    sr0 = M.sharpe(base.monthly_returns, base.rf_monthly)
    sr1 = M.sharpe(shifted.monthly_returns, shifted.rf_monthly)
    return {"strategy": spec.name, "sharpe": sr0, "sharpe_shift1": sr1, "delta_sharpe": sr1 - sr0,
            "cagr": M.cagr(base.monthly_returns), "cagr_shift1": M.cagr(shifted.monthly_returns)}


def monthly_panel_from(panel: PricePanel, symbol: str) -> PricePanel:
    """One bar per month (month-end closes) from a daily panel, for the foresight test on real data."""
    from ..backtest.schedule import month_end_dates

    me = month_end_dates(panel.calendar)
    c = panel.closes[symbol].reindex(me).dropna()
    op = c.shift(1).fillna(c.iloc[0])
    bars = pd.DataFrame({"open": op, "high": np.maximum(op, c), "low": np.minimum(op, c), "close": c,
                         "volume": 0, "close_raw": c, "dividend": 0.0})
    # Cash earns 0 here (the daily T-bill accrual convention does not apply to one bar per month);
    # the test compares alphas, which do not depend on the cash rate.
    return panel_from_bars({symbol: bars}, None)
