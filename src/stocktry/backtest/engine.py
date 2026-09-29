"""Monthly-rebalance backtest engine with structural one-bar execution lag.

Timing convention (the most important thing in this file)
---------------------------------------------------------
* The portfolio starts as cash at the **close** of ``start`` (the last trading
  day of the start month; equity there = ``initial_capital``).
* **Signal**: on each anchor date (by default the last trading day of each
  month; see :mod:`stocktry.backtest.schedule`) the strategy is called with a
  frame of adjusted closes **truncated at that date** (``iloc[:i+1]``). It
  cannot see any later row.
* **Execution**: orders fill on the **next trading day** at that day's
  adjusted **open** (``fill="next_open"``, default) or adjusted **close**
  (``fill="next_close"``). ``extra_lag_days`` delays execution further (used
  for the one-bar-shift test).
* ``same_bar_fill=True`` fills at the signal bar's own close. That is
  look-ahead by construction and exists **only** for the leakage test in
  :mod:`stocktry.validation.leakage`; results are flagged ``leaky=True`` and
  the ledger and report writers refuse them. No CLI exposes it.

Accounting
----------
* Positions are held as units of the **adjusted** (total-return) price series,
  so dividends are implicitly reinvested; the benchmark is run through the same
  engine on the same adjusted series, so both are total return.
* Order sizes are computed in **as-traded dollars and shares** using
  ``raw_factor = close_raw / close``: fractional orders are truncated to
  ``share_decimals`` (9) decimals; ``whole_shares=True`` (or a
  non-fractionable symbol) rounds target positions **down** to whole shares,
  leaving cash drag. In whole-share mode dividends between rebalances are
  still treated as reinvested (adjusted-price accounting), which slightly
  flatters whole-share results.
* Sells execute before buys. Sells are quantity orders; buys are dollar
  notional orders (fractional: rounded down to the cent) that pay the ask,
  so the half-spread shows up as fewer units. If buys exceed the cash
  available, all buys are scaled down pro rata. Share quantities are
  truncated to 9 decimals. Orders below the $1 minimum are skipped, except a
  sell that closes the whole position; skips larger than 0.01% of equity are
  logged in ``skipped`` (smaller ones are cent-level drift from fee debits). Regulatory fees are debited after the
  day's orders (as the broker posts them), so cash can dip a few cents below
  zero; negative cash accrues at the T-bill rate.
* **Cash** (``cash_symbol=None``) earns the T-bill daily accrual described in
  :mod:`stocktry.data.rates` (DTB3 of the previous trading day / 100 / 252 per
  trading day), applied to the balance at the start of each day. With a
  ``cash_symbol`` (e.g. BIL) the unallocated weight is bought as that ETF when
  it has a price; any residual cash still earns T-bills.
* Index-level series (``SymbolMeta.is_index_level``) lose ``ER / 252`` per
  trading day; real fund series are never charged their expense ratio again.

Outputs are daily equity, month-end equity/returns (monthly returns are
month-end to month-end, first month measured from the start close),
month-end weights, and per-rebalance/per-order/skipped-order records.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ..data.panel import PricePanel
from ..data.rates import TBILL_COLUMN
from ..strategies.base import StrategySpec
from .costs import CostModel, Order
from .schedule import month_anchor_positions, month_end_dates, resolve_month_end

log = logging.getLogger(__name__)

WEIGHT_TOL = 1e-9
# Sub-minimum orders smaller than this fraction of equity (e.g. cent-level drift left by fee
# debits) are dropped silently; larger ones are logged in ``skipped``.
SKIP_LOG_FRACTION = 1e-4


class EngineError(RuntimeError):
    """Invalid strategy output or configuration."""


@dataclass(frozen=True)
class EngineConfig:
    """Engine settings. Money in dollars; see the module docstring for timing."""

    initial_capital: float = 10_000.0
    fill: str = "next_open"  # "next_open" | "next_close"
    whole_shares: bool = False
    costs: CostModel = field(default_factory=CostModel.modelled)
    start: str | pd.Timestamp | None = None  # month (e.g. "1996-05") or date; resolved to that month's last trading day
    end: str | pd.Timestamp | None = None  # default: last complete month-end of the panel
    cash_yield: bool = True
    extra_lag_days: int = 0
    same_bar_fill: bool = False  # LEAKY: leakage test only
    share_decimals: int = 9

    def __post_init__(self) -> None:
        if self.fill not in ("next_open", "next_close"):
            raise EngineError(f"fill must be next_open or next_close, got {self.fill!r}")
        if self.initial_capital <= 0:
            raise EngineError("initial_capital must be positive")
        if self.extra_lag_days < 0:
            raise EngineError("extra_lag_days must be >= 0")


@dataclass
class BacktestResult:
    strategy: str
    params: dict[str, Any]
    config: EngineConfig
    equity: pd.Series  # daily, dollars, from start close to end close
    cash: pd.Series  # daily cash balance, dollars
    month_end_equity: pd.Series
    monthly_returns: pd.Series  # index = month-end trading dates
    rf_monthly: pd.Series  # T-bill monthly returns on the same dates
    weights: pd.DataFrame  # month-end weights of each held symbol (fraction of equity)
    exposure: pd.Series  # month-end risky exposure (excludes the cash ETF)
    rebalances: pd.DataFrame
    trades: pd.DataFrame
    skipped: pd.DataFrame
    leaky: bool = False

    @property
    def total_fees(self) -> float:
        return float(self.rebalances["fees"].sum()) if len(self.rebalances) else 0.0

    @property
    def total_spread_cost(self) -> float:
        return float(self.rebalances["spread_cost"].sum()) if len(self.rebalances) else 0.0

    @property
    def years(self) -> float:
        return len(self.monthly_returns) / 12.0


def signal_positions(calendar: pd.DatetimeIndex, spec: StrategySpec, i_start: int, i_end: int) -> list[int]:
    """Calendar positions at which ``spec`` is evaluated, within [i_start, i_end)."""
    pos = month_anchor_positions(calendar, spec.signal_offset)
    pos = pos[(pos >= i_start) & (pos < i_end)]
    if spec.rebalance_months is not None and len(pos):
        months = np.asarray(calendar.month)[pos]
        keep = np.isin(months, spec.rebalance_months)
        keep[0] = True  # the initial investment always happens
        pos = pos[keep]
    return [int(p) for p in pos]


def _validate_targets(targets: dict[str, float], allowed: set[str], name: str, when: pd.Timestamp) -> None:
    tot = 0.0
    for s, w in targets.items():
        if s not in allowed:
            raise EngineError(f"{name} @ {when.date()}: target for {s!r} outside universe {sorted(allowed)}")
        if not (isinstance(w, (int, float, np.floating)) and math.isfinite(w)) or w < -WEIGHT_TOL:
            raise EngineError(f"{name} @ {when.date()}: invalid weight {s}={w!r} (long-only, finite)")
        tot += w
    if tot > 1.0 + 1e-6:
        raise EngineError(f"{name} @ {when.date()}: weights sum to {tot:.6f} > 1")


def _trunc(x: float, decimals: int) -> float:
    f = 10.0**decimals
    return math.trunc(x * f) / f


def run_backtest(spec: StrategySpec, panel: PricePanel, config: EngineConfig | None = None) -> BacktestResult:
    """Run ``spec`` on ``panel`` under ``config`` (see module docstring for conventions)."""
    cfg = config or EngineConfig()
    costs = cfg.costs
    cols = list(dict.fromkeys(spec.universe + ([spec.cash_symbol] if spec.cash_symbol else [])))
    missing = [c for c in cols if c not in panel.closes.columns]
    if missing:
        raise EngineError(f"panel lacks columns {missing} needed by {spec.name}")
    cal = panel.calendar
    start_date = resolve_month_end(cal, cfg.start) if cfg.start is not None else cal[0]
    end_date = (resolve_month_end(cal, cfg.end) if cfg.end is not None else panel.last_complete_month_end())
    i0 = int(cal.get_loc(start_date))
    i1 = int(cal.get_loc(end_date))
    if i1 <= i0:
        raise EngineError("end must be after start")

    n = len(cols)
    closes = panel.closes[cols].to_numpy(dtype=float)
    opens = panel.opens[cols].to_numpy(dtype=float)
    rawf = panel.raw_factor[cols].to_numpy(dtype=float)
    rate = panel.tbill_rate.to_numpy(dtype=float) if cfg.cash_yield else np.zeros(len(cal))
    metas = [panel.meta[c] for c in cols]
    hs = np.array([costs.half_spread_bp(m) / 1e4 for m in metas])
    fractionable = np.array([m.fractionable and not cfg.whole_shares for m in metas])
    er_daily = np.array([m.expense_ratio / 252.0 if m.is_index_level else 0.0 for m in metas])
    cash_j = cols.index(spec.cash_symbol) if spec.cash_symbol else -1
    risky_mask = np.array([c != spec.cash_symbol for c in cols])
    allowed = set(spec.universe)

    strat_frame = panel.strategy_frame(cols)
    sig_pos = signal_positions(cal, spec, i0, i1)
    sig_set = set(sig_pos)

    cash = float(cfg.initial_capital)
    units = np.zeros(n)
    eq = np.full(i1 - i0 + 1, np.nan)
    cash_path = np.full(i1 - i0 + 1, np.nan)
    pending: list[tuple[int, np.ndarray, pd.Timestamp]] = []
    rebal_rows: list[dict] = []
    trade_rows: list[tuple] = []
    skip_rows: list[tuple] = []

    closes0 = np.nan_to_num(closes, nan=0.0)

    def mark(i: int) -> float:
        # Closes are forward-filled after each symbol's first bar, and execution refuses to buy a
        # symbol without a price, so held symbols always have a finite close here.
        return cash + float(closes0[i] @ units)

    def targets_vector(i: int) -> np.ndarray:
        asof = cal[i]
        tg = spec.compute_targets(strat_frame.iloc[: i + 1], asof)
        tg = {k: float(v) for k, v in (tg or {}).items()}
        _validate_targets(tg, allowed, spec.name, asof)
        tg = {k: v for k, v in tg.items() if abs(v) > WEIGHT_TOL}
        w = np.zeros(n)
        for s, v in tg.items():
            w[cols.index(s)] = max(v, 0.0)
        if cash_j >= 0:
            w[cash_j] = max(0.0, 1.0 - w[risky_mask].sum())
        return w

    def execute(i: int, w: np.ndarray, signal_date: pd.Timestamp, use_close: bool) -> None:
        nonlocal cash
        day = cal[i]
        p = closes[i] if use_close else opens[i]
        valid = np.isfinite(p) & (p > 0)
        # A target on a symbol with no price is a strategy bug -- except the cash ETF (falls back to cash).
        for j in np.flatnonzero((w > 0) & ~valid):
            if j == cash_j:
                w = w.copy()
                w[j] = 0.0
            else:
                raise EngineError(f"{spec.name}: target for {cols[j]} which has no price on {day.date()}")
        pv = np.where(valid, units * np.where(valid, p, 0.0), 0.0)
        V = cash + pv.sum()
        if V <= 0:
            log.warning("%s: non-positive equity on %s; no trades", spec.name, day.date())
            return
        rawp = np.where(valid, p * rawf[i], np.nan)
        tgt_val = w * V
        sells: list[tuple[int, float, float, bool]] = []  # (j, shares, notional, full_exit)
        buys: list[tuple[int, float]] = []  # (j, desired as-traded shares)
        for j in range(n):
            if not valid[j]:
                continue
            cur_val = pv[j]
            delta = tgt_val[j] - cur_val
            if abs(delta) < 1e-9:
                continue
            cur_sh = units[j] * p[j] / rawp[j]
            full_exit = w[j] <= 0 and units[j] > 0
            if full_exit:
                sh = -cur_sh
            elif fractionable[j]:
                # sells: quantity orders truncated to 9 decimals; buys: dollar-notional orders (see below)
                sh = _trunc(delta / rawp[j], cfg.share_decimals) if delta < 0 else delta / rawp[j]
            else:
                tgt_sh = math.floor(tgt_val[j] / rawp[j] + 1e-9)
                sh = float(tgt_sh - math.floor(cur_sh + 1e-9))
            notional = abs(sh) * rawp[j] * ((1.0 + hs[j]) if sh > 0 else 1.0)
            if notional <= 0:
                continue
            if notional < costs.min_notional and not full_exit:
                if notional >= max(0.005, SKIP_LOG_FRACTION * V):
                    skip_rows.append((day, signal_date, cols[j], "sell" if sh < 0 else "buy", notional,
                                      f"below ${costs.min_notional:g} minimum"))
                continue
            if sh < 0:
                sells.append((j, -sh, notional, full_exit))
            else:
                buys.append((j, sh))
        orders: list[Order] = []
        spread_cost = 0.0
        sold = bought = 0.0
        for j, sh, notional, full_exit in sells:
            proceeds = notional * (1.0 - hs[j])
            cash += proceeds
            spread_cost += notional * hs[j]
            units[j] = 0.0 if full_exit else max(units[j] - notional / p[j], 0.0)
            sold += notional
            orders.append(Order(cols[j], "sell", notional, sh))
            trade_rows.append((day, signal_date, cols[j], "sell", sh, rawp[j], notional, notional * hs[j]))
        if buys:
            # A buy pays its notional at the ask (mid * (1 + half-spread)); the spread shows up as fewer
            # units received. Fractional buys are dollar-notional orders rounded down to the cent (as at
            # Alpaca); whole-share buys pay shares * ask.
            pay = [sh * rawp[j] * (1.0 + hs[j]) for j, sh in buys]
            need = sum(pay)
            avail = max(cash, 0.0)
            scale = min(1.0, avail / need) if need > 0 else 0.0
            for (j, sh), x in zip(buys, pay):
                ask = rawp[j] * (1.0 + hs[j])
                if fractionable[j]:
                    x = math.floor(round(x * scale * 100.0, 6)) / 100.0
                    sh = _trunc(x / ask, cfg.share_decimals)  # the broker books at most 9 decimals
                else:
                    if scale < 1.0:
                        sh = float(math.floor(sh * scale))
                    x = sh * ask
                if x <= 0:
                    continue
                if x < costs.min_notional:
                    if x >= max(0.005, SKIP_LOG_FRACTION * V):
                        skip_rows.append((day, signal_date, cols[j], "buy", x,
                                          f"below ${costs.min_notional:g} minimum"
                                          + (" after cash scaling" if scale < 1.0 else "")))
                    continue
                mid_value = sh * rawp[j]
                fill = sh * ask  # cash actually paid for the (truncated) quantity; <= the order notional x
                cash -= fill
                spread_cost += fill - mid_value
                units[j] += mid_value / p[j]
                bought += fill
                orders.append(Order(cols[j], "buy", fill, sh))
                trade_rows.append((day, signal_date, cols[j], "buy", sh, rawp[j], fill, fill - mid_value))
        fees = costs.day_fees(day, orders)
        cash -= fees.total
        rebal_rows.append({
            "signal_date": signal_date, "exec_date": day, "equity_before": V,
            "bought": bought, "sold": sold, "turnover": (bought + sold) / V,
            "spread_cost": spread_cost, "fees": fees.total, "sec": fees.sec, "taf": fees.taf,
            "cat": fees.cat, "commission": fees.commission, "n_orders": len(orders),
            "targets": {cols[j]: round(float(w[j]), 10) for j in range(n) if w[j] > 0},
        })

    def schedule(i: int) -> None:
        w = targets_vector(i)
        if cfg.same_bar_fill:
            execute(i, w, cal[i], use_close=True)
            return
        ex = i + 1 + cfg.extra_lag_days
        if ex <= i1:
            pending.append((ex, w, cal[i]))

    me = month_end_dates(cal)
    me = me[(me >= start_date) & (me <= end_date)]
    if start_date not in me:
        me = pd.DatetimeIndex([start_date]).append(me)
    me_pos = {int(cal.get_loc(d)) for d in me}
    snapshots: dict[int, np.ndarray] = {}

    # Day i0: cash only; a signal on the start date is scheduled (never filled on the same bar).
    eq[0] = cash
    cash_path[0] = cash
    if i0 in sig_set:
        schedule(i0)
        eq[0] = mark(i0)
        cash_path[0] = cash
    snapshots[i0] = units.copy()
    for i in range(i0 + 1, i1 + 1):
        cash *= 1.0 + rate[i]
        if er_daily.any():
            units *= 1.0 - er_daily
        while pending and pending[0][0] == i:
            _, w, sd = pending.pop(0)
            execute(i, w, sd, use_close=(cfg.fill == "next_close"))
        if i in sig_set:
            schedule(i)
        eq[i - i0] = mark(i)
        cash_path[i - i0] = cash
        if i in me_pos:
            snapshots[i] = units.copy()

    dates = cal[i0: i1 + 1]
    equity = pd.Series(eq, index=dates, name=spec.name)
    cash_s = pd.Series(cash_path, index=dates, name="cash")
    me_eq = equity.reindex(me)
    monthly = me_eq.pct_change().iloc[1:]
    tb = panel.tbill_index.reindex(me)
    rf = (tb.pct_change().iloc[1:] if cfg.cash_yield else pd.Series(0.0, index=me[1:]))
    snap_pos = sorted(snapshots)
    u = np.vstack([snapshots[k] for k in snap_pos])
    px = np.nan_to_num(closes[snap_pos], nan=0.0)
    w_df = pd.DataFrame(u * px / eq[np.array(snap_pos) - i0][:, None], index=cal[snap_pos], columns=cols)
    expo = w_df.loc[:, [c for c, r in zip(cols, risky_mask) if r]].sum(axis=1)
    trades = pd.DataFrame(trade_rows, columns=["exec_date", "signal_date", "symbol", "side", "shares",
                                               "price_raw", "notional", "spread_cost"])
    skipped = pd.DataFrame(skip_rows, columns=["exec_date", "signal_date", "symbol", "side", "notional", "reason"])
    rebal = pd.DataFrame(rebal_rows)
    if rebal.empty:
        rebal = pd.DataFrame(columns=["signal_date", "exec_date", "equity_before", "bought", "sold", "turnover",
                                      "spread_cost", "fees", "sec", "taf", "cat", "commission", "n_orders", "targets"])
    return BacktestResult(
        strategy=spec.name, params=dict(spec.params), config=cfg, equity=equity, cash=cash_s,
        month_end_equity=me_eq, monthly_returns=monthly, rf_monthly=rf, weights=w_df, exposure=expo,
        rebalances=rebal, trades=trades, skipped=skipped, leaky=cfg.same_bar_fill,
    )


__all__ = ["EngineConfig", "EngineError", "BacktestResult", "run_backtest", "signal_positions", "TBILL_COLUMN"]
