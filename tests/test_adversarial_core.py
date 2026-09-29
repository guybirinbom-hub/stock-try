"""Adversarial tests of the core: data, engine timing and accounting, costs, statistics, report.

Written by an adversarial review. Every test whose docstring starts with ``FINDING CORE-xx``
FAILS while the named defect is present (it is left failing on purpose so the fixer can see it
go green). Every other test is a regression guard for a suspicion that was checked and refuted
(it passes today and should keep passing).

All data is synthetic except the report-consistency tests, which read the committed files in
``results/``. No network access is needed.
"""
from __future__ import annotations

import itertools
import json
import math
import subprocess
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm, rankdata

from stocktry.backtest import metrics as M
from stocktry.backtest.costs import (
    AlpacaFeeModel,
    CostModel,
    Order,
    ceil_cent,
    rate_on,
    SEC_FEE_SCHEDULE,
)
from stocktry.backtest.engine import EngineConfig, run_backtest
from stocktry.backtest.schedule import month_anchor_positions
from stocktry.data import fetch
from stocktry.data.panel import load_series, panel_from_bars
from stocktry.data.quality import DataQualityError, run_quality_checks
from stocktry.data.rates import tbill_daily_rate
from stocktry.data.universe import SPLICES, SpliceRejected, SpliceRule, get_meta, splice_bars
from stocktry.strategies.base import StrategySpec
from stocktry.strategies.buy_and_hold import make_buy_and_hold, make_sixty_forty
from stocktry.strategies.gtaa import make_gtaa
from stocktry.strategies.trend import make_trend_absmom, make_trend_ensemble, make_trend_sma
from stocktry.validation.bootstrap import stationary_bootstrap_indices
from stocktry.validation.dsr import deflated_sharpe
from stocktry.validation.pbo import cscv_pbo
from stocktry.validation.plateau import plateau_statistic
from stocktry.validation.walkforward import walk_forward

from conftest import make_bars

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"

# =====================================================================================
# Synthetic multi-asset universe with Yahoo-style (backward, multiplicative) dividend
# adjustment, as-traded prices that differ from adjusted ones, and a time-varying DTB3.
# =====================================================================================
N_DAYS = 252 * 8
IDX = pd.bdate_range("2012-01-02", periods=N_DAYS)
ASSETS = (("SPY", 0.08, 0.18, "quarterly", 0.005), ("IEF", 0.03, 0.06, "monthly", 0.002),
          ("VNQ", 0.07, 0.22, "quarterly", 0.009))


def yahoo_adjusted(raw: np.ndarray, div: np.ndarray) -> np.ndarray:
    """Adjusted close: every price before an ex-date is multiplied by (1 - D / previous raw close)."""
    f = np.ones(len(raw))
    for k in np.flatnonzero(div > 0)[::-1]:
        f[:k] *= 1.0 - div[k] / raw[k - 1]
    return raw * f


def _raw_paths(seed: int, n: int, start_close: dict[str, float] | None = None) -> dict[str, tuple]:
    rng = np.random.default_rng(seed)
    out = {}
    for sym, mu, sig, freq, dy in ASSETS:
        lr = rng.normal((mu - 0.5 * sig**2) / 252, sig / np.sqrt(252), n)
        intraday = rng.normal(0.0, sig / np.sqrt(252) / 2, n)
        s0 = (start_close or {}).get(sym, 100.0)
        close = s0 * np.exp(np.cumsum(lr))
        open_ = close * np.exp(-intraday)
        out[sym] = (open_, close, freq, dy)
    return out


def _dividends(idx: pd.DatetimeIndex, close: np.ndarray, freq: str, dy: float) -> np.ndarray:
    div = np.zeros(len(idx))
    per = idx.to_period("Q" if freq == "quarterly" else "M")
    nth = 40 if freq == "quarterly" else 10
    pos = pd.Series(np.arange(len(idx)), index=idx).groupby(per).nth(nth).to_numpy()
    pos = pos[pos > 0]
    div[pos] = close[pos - 1] * dy
    return div


def universe_bars(tamper_after: pd.Timestamp | None = None, future_big_dividend: bool = False,
                  scale: float = 1.7) -> dict[str, pd.DataFrame]:
    """Bars for SPY/IEF/VNQ. With ``tamper_after`` every raw price and dividend after that date is
    replaced by an unrelated path (and optionally a huge dividend is added shortly after it), and the
    adjusted series is rebuilt from the full raw+dividend history -- exactly what a vendor refresh does,
    so adjusted prices *before* the cut change by a constant factor per symbol."""
    base = _raw_paths(1, N_DAYS)
    frames = {}
    for sym, (op, cl, freq, dy) in base.items():
        op, cl = op.copy(), cl.copy()
        div = _dividends(IDX, cl, freq, dy)
        if tamper_after is not None:
            k = int(IDX.get_loc(tamper_after))
            alt = _raw_paths(99, N_DAYS - k - 1, {s: v[1][k] for s, v in base.items()})[sym]
            op[k + 1:], cl[k + 1:] = alt[0] * scale, alt[1] * scale  # boom (1.7) or crash (0.3) after the cut
            div[k + 1:] = 0.0
            if future_big_dividend:
                div[k + 7] = cl[k + 6] * 0.25  # a 25% special dividend after the cut
        adj = yahoo_adjusted(cl, div)
        f = adj / cl
        frames[sym] = make_bars(adj, dates=IDX, open_=op * f, dividend=div, close_raw=cl)
    return frames


def dtb3(tamper_after: pd.Timestamp | None = None) -> pd.Series:
    y = pd.Series(2.0 + 1.5 * np.sin(np.arange(N_DAYS) / 90.0), index=IDX)
    if tamper_after is not None:
        y[y.index > tamper_after] = 9.0
    return y


def universe_panel(**kw):
    return panel_from_bars(universe_bars(**kw), dtb3(kw.get("tamper_after")))


TAMPER_SCALES = (1.7, 0.3)  # a boom and a crash: any signal that peeks past the cut flips under one of them


SPECS = {
    "sma10": lambda: make_trend_sma("SPY", 10),
    "absmom12": lambda: make_trend_absmom("SPY", 12),
    "ensemble": lambda: make_trend_ensemble("SPY"),
    "sixty_forty": lambda: make_sixty_forty("SPY", "IEF"),
    "gtaa3_me": lambda: make_gtaa(["SPY", "IEF", "VNQ"], 10, -1),
    "gtaa3_o0": lambda: make_gtaa(["SPY", "IEF", "VNQ"], 10, 0),
    "gtaa3_o7": lambda: make_gtaa(["SPY", "IEF", "VNQ"], 6, 7),
    "gtaa3_o20": lambda: make_gtaa(["SPY", "IEF", "VNQ"], 10, 20),
}


def cut_for(spec: StrategySpec) -> pd.Timestamp:
    """The cut sits exactly ON one of the strategy's own signal anchors (in 2017), so a leak of even
    one bar from that signal reaches tampered data."""
    anchors = month_anchor_positions(IDX, spec.signal_offset)
    if spec.rebalance_months is not None:
        anchors = anchors[np.isin(np.asarray(IDX.month)[anchors], spec.rebalance_months)]
    return IDX[int(anchors[anchors <= 1300][-1])]


def _past(res, cut):
    reb = res.rebalances
    sig = reb[reb["signal_date"] <= cut]
    ex = reb[reb["exec_date"] <= cut]
    tr = res.trades[res.trades["exec_date"] <= cut]
    return sig, ex, tr, res.equity.loc[:cut], res.cash.loc[:cut]


# =====================================================================================
# 1. Look-ahead and timing
# =====================================================================================
@pytest.mark.parametrize("name", list(SPECS))
@pytest.mark.parametrize("fill,lag,whole", [("next_open", 0, False), ("next_close", 0, False),
                                            ("next_open", 1, True), ("next_open", 3, False)])
def test_future_tampering_cannot_change_any_past_decision_or_fill(name, fill, lag, whole):
    """Rewrite every price, dividend and T-bill yield after a cut placed ON a signal date (with a
    vendor-style re-adjustment of the whole adjusted history): every signal (including the one on the
    cut date), target, order, fee and equity value up to the cut must be unchanged. Covers strategy frames, month anchors (all offsets), the T-bill column, forward fills,
    raw factors and fills."""
    cfg = EngineConfig(initial_capital=10_000.0, costs=CostModel.gate(), start="2013-07", fill=fill,
                       extra_lag_days=lag, whole_shares=whole)
    cut = cut_for(SPECS[name]())
    a = run_backtest(SPECS[name](), universe_panel(), cfg)
    sa, ea, ta, eqa, ca = _past(a, cut)
    assert sa["signal_date"].iloc[-1] == cut  # the signal ON the cut date is compared too
    assert len(sa) >= (4 if name == "sixty_forty" else 40) and len(ta) > 0
    for scale in TAMPER_SCALES:
        b = run_backtest(SPECS[name](), universe_panel(tamper_after=cut, scale=scale), cfg)
        sb, eb, tb, eqb, cb = _past(b, cut)
        assert list(sa["targets"]) == list(sb["targets"]), scale
        pd.testing.assert_frame_equal(ta.reset_index(drop=True), tb.reset_index(drop=True))
        pd.testing.assert_series_equal(eqa, eqb)
        pd.testing.assert_series_equal(ca, cb)
        assert list(ea["fees"]) == list(eb["fees"])


@pytest.mark.parametrize("name", ["sma10", "absmom12", "ensemble", "gtaa3_o7"])
def test_future_dividend_readjustment_of_history_is_invisible(name):
    """A vendor refresh after a big future dividend rescales every earlier adjusted price. Units,
    as-traded sizing (raw factor), signals and dollar equity before the cut must not move."""
    cfg = EngineConfig(initial_capital=10_000.0, costs=CostModel.gate(), start="2013-07", whole_shares=True)
    cut = cut_for(SPECS[name]())
    a = run_backtest(SPECS[name](), universe_panel(tamper_after=cut), cfg)
    b = run_backtest(SPECS[name](), universe_panel(tamper_after=cut, future_big_dividend=True), cfg)
    pa = universe_bars(tamper_after=cut)["SPY"]["close"].loc[:cut]
    pb = universe_bars(tamper_after=cut, future_big_dividend=True)["SPY"]["close"].loc[:cut]
    assert (pb / pa).iloc[0] == pytest.approx(0.75, rel=1e-9)  # history really was rescaled
    sa, _, ta, eqa, _ = _past(a, cut)
    sb, _, tb, eqb, _ = _past(b, cut)
    assert list(sa["targets"]) == list(sb["targets"])
    np.testing.assert_allclose(ta["shares"], tb["shares"], rtol=1e-12)  # same as-traded shares
    np.testing.assert_allclose(ta["price_raw"], tb["price_raw"], rtol=1e-12)
    np.testing.assert_allclose(eqa, eqb, rtol=1e-10)


@pytest.mark.parametrize("fill,lag", [("next_open", 0), ("next_close", 0), ("next_open", 2)])
def test_every_fill_is_strictly_after_its_signal_at_the_documented_price(fill, lag):
    """Each order fills exactly 1 + extra_lag trading days after its signal, at that day's as-traded
    open (or close), never on the signal bar."""
    bars = universe_bars()
    cfg = EngineConfig(costs=CostModel.gate(), start="2013-07", fill=fill, extra_lag_days=lag)
    res = run_backtest(_random_target_spec(5), panel_from_bars(bars, dtb3()), cfg)
    assert len(res.trades) > 100 and not res.leaky
    pos = {d: k for k, d in enumerate(IDX)}
    for t in res.trades.itertuples():
        assert pos[t.exec_date] - pos[t.signal_date] == 1 + lag
        b = bars[t.symbol].loc[t.exec_date]
        raw_px = b["close_raw"] if fill == "next_close" else b["open"] * b["close_raw"] / b["close"]
        assert t.price_raw == pytest.approx(raw_px, rel=1e-12)


def test_same_bar_fill_is_not_reachable_from_the_cli():
    out = subprocess.run([sys.executable, str(REPO / "scripts" / "run_backtests.py"), "--help"],
                         capture_output=True, text=True, cwd=REPO, timeout=120)
    assert out.returncode == 0 and "same" not in out.stdout.lower() and "leak" not in out.stdout.lower()
    bad = subprocess.run([sys.executable, str(REPO / "scripts" / "run_backtests.py"), "--same-bar-fill"],
                         capture_output=True, text=True, cwd=REPO, timeout=120)
    assert bad.returncode == 2  # argparse rejects it before anything runs


@pytest.mark.parametrize("offset", [-1, 0, 1, 7, 18, 20])
def test_month_anchors_are_causal_on_irregular_calendars(offset):
    rng = np.random.default_rng(offset + 5)
    full = pd.bdate_range("2000-01-03", "2004-12-31")
    idx = full[rng.random(len(full)) > 0.25]  # drop a quarter of the days, incl. month-ends
    anchors = month_anchor_positions(idx, offset)
    for p in anchors[:-1]:
        trunc = month_anchor_positions(idx[: p + 1], offset)
        assert trunc[-1] == p
        np.testing.assert_array_equal(trunc, anchors[anchors <= p])
    # the -1 anchor is always the last row of its month
    if offset < 0:
        m = idx.to_period("M")
        assert all(m[p] != m[p + 1] for p in anchors[:-1])


# FINDING CORE-07 (fails while the defect is present)
def test_tbill_rate_before_first_observation_does_not_use_future_values():
    """FINDING CORE-07: ``tbill_daily_rate`` back-fills (``bfill``) the first DTB3 observation onto
    earlier calendar days, so the cash return on those days depends on a yield published later.
    Latent (DTB3 starts in 1954), but it is look-ahead in the one module every Sharpe ratio and the
    absolute-momentum hurdle depend on."""
    cal = pd.bdate_range("2000-01-03", periods=10)
    y1 = pd.Series([5.0, 1.0], index=[cal[4], cal[8]])
    y2 = pd.Series([9.0, 1.0], index=[cal[4], cal[8]])
    r1, r2 = tbill_daily_rate(cal, y1), tbill_daily_rate(cal, y2)
    # Day cal[0]..cal[4] accrue DTB3 of the previous trading day, which does not exist yet:
    # changing the value first observed on cal[4] must not change them.
    np.testing.assert_array_equal(r1.iloc[:5].to_numpy(), r2.iloc[:5].to_numpy())


# =====================================================================================
# 2. Accounting
# =====================================================================================
def _random_target_spec(seed: int, zero_prob: float = 0.3) -> StrategySpec:
    def fn(closes, asof):
        rng = np.random.default_rng([seed, int(asof.value // 86_400_000_000_000)])
        w = rng.dirichlet(np.ones(4))[:3] * rng.uniform(0.3, 1.0)
        w[rng.random(3) < zero_prob] = 0.0
        return {s: float(x) for s, x in zip(("SPY", "IEF", "VNQ"), w) if x > 0}

    return StrategySpec("random", ["SPY", "IEF", "VNQ"], None, fn, family="random")


@pytest.mark.parametrize("whole", [False, True])
@pytest.mark.parametrize("capital", [150.0, 10_000.0, 2_000_000.0])
def test_value_is_conserved_at_every_execution(whole, capital):
    """With fills at the next close, equity at the execution close must equal the pre-trade value
    minus the spread and fees charged -- no money created or destroyed by share rounding, raw factors,
    sell-before-buy ordering, cash scaling or the $1 minimum."""
    cfg = EngineConfig(initial_capital=capital, costs=CostModel.gate(), start="2013-07", fill="next_close",
                       whole_shares=whole)
    res = run_backtest(_random_target_spec(3), universe_panel(), cfg)
    reb = res.rebalances
    assert len(reb) > 50 and reb["n_orders"].sum() > (10 if capital < 1000 else 50)
    for row in reb.itertuples():
        after = res.equity.loc[row.exec_date]
        assert after == pytest.approx(row.equity_before - row.spread_cost - row.fees, abs=1e-6, rel=1e-12)
        # cash can only go negative by the fees debited after the buys
        assert res.cash.loc[row.exec_date] >= -row.fees - 1e-9


def test_dividend_goes_to_the_holder_not_to_a_buyer_at_the_ex_date_open():
    """Raw close 100 up to month-end; next day (ex-date) opens at 90 after a $10 dividend and closes at
    99. A buyer at the ex-date open earns +10% (99/90), not the dividend; a holder earns the dividend."""
    idx = pd.bdate_range("2021-01-04", "2021-03-31")
    raw_c = np.full(len(idx), 100.0)
    raw_o = np.full(len(idx), 100.0)
    je = int(np.flatnonzero(idx.month == 1)[-1])
    ex = je + 1
    raw_o[ex:], raw_c[ex:] = 90.0, 99.0
    raw_o[ex + 1:] = 99.0
    div = np.zeros(len(idx))
    div[ex] = 10.0
    adj = yahoo_adjusted(raw_c, div)
    bars = make_bars(adj, dates=idx, open_=raw_o * adj / raw_c, dividend=div, close_raw=raw_c)
    panel = panel_from_bars({"SPY": bars}, None)
    cfg = EngineConfig(initial_capital=1000.0, costs=CostModel.zero(), start="2021-01", cash_yield=False)
    buyer = run_backtest(make_buy_and_hold("SPY"), panel, cfg)
    t = buyer.trades.iloc[0]
    assert t["exec_date"] == idx[ex] and t["price_raw"] == pytest.approx(90.0)
    assert buyer.equity.loc[idx[ex]] == pytest.approx(1100.0)
    # holder: bought at the Dec month-end close, still holding over the ex-date
    cfg_h = replace(cfg, start="2020-12")
    bars_h = pd.concat([make_bars([90.0] * 5, dates=pd.bdate_range("2020-12-24", periods=5), close_raw=[100.0] * 5),
                        bars])
    bars_h = bars_h[~bars_h.index.duplicated(keep="last")]
    holder = run_backtest(make_buy_and_hold("SPY"), panel_from_bars({"SPY": bars_h}, None), cfg_h)
    before = holder.equity.loc[idx[je]]
    assert holder.equity.loc[idx[ex]] == pytest.approx(before * 99.0 / 90.0)  # (99 + 10 reinvested) / 100


def test_sell_proceeds_fund_same_day_buys():
    """Switch 100% SPY -> 100% IEF on one day: the IEF buy must be funded by the SPY sale."""
    def fn(closes, asof):
        return {"SPY": 1.0} if asof < pd.Timestamp("2014-06-01") else {"IEF": 1.0}

    spec = StrategySpec("switch", ["SPY", "IEF"], None, fn)
    res = run_backtest(spec, universe_panel(), EngineConfig(costs=CostModel.gate(), start="2013-07",
                                                            end="2014-12"))
    day = res.trades[res.trades["symbol"] == "IEF"]["exec_date"].iloc[0]
    tr = res.trades[res.trades["exec_date"] == day]
    assert set(tr["side"]) == {"sell", "buy"}
    buy = tr[tr["side"] == "buy"]["notional"].iloc[0]
    sell = tr[tr["side"] == "sell"]["notional"].iloc[0]
    assert buy == pytest.approx(sell * (1 - 5e-4), rel=1e-3)  # ~ all proceeds re-invested


# =====================================================================================
# 3. Cost model
# =====================================================================================
def test_engine_fees_are_the_daily_aggregate_of_its_own_orders():
    """Recompute SEC/TAF/CAT for every rebalance from the engine's own trades: per-type sum over the
    day's orders (sells only for SEC/TAF, both sides for CAT, TAF capped per order), then one ceil."""
    cfg = EngineConfig(initial_capital=250_000.0, costs=CostModel.gate(), start="2013-07")
    res = run_backtest(_random_target_spec(11, zero_prob=0.5), universe_panel(), cfg)
    multi_sell_days = 0
    for row in res.rebalances.itertuples():
        tr = res.trades[res.trades["exec_date"] == row.exec_date]
        sells = tr[tr["side"] == "sell"]
        multi_sell_days += len(sells) >= 2
        d = row.exec_date.date()
        sec = ceil_cent(sells["notional"].sum() * rate_on(SEC_FEE_SCHEDULE, d).rate)
        taf = ceil_cent(sum(min(s * 0.000195, 9.79) for s in sells["shares"]))
        cat = ceil_cent(tr["shares"].sum() * 0.000003)
        assert (row.sec, row.taf, row.cat) == (sec, taf, cat)
    assert multi_sell_days > 5  # same-day multi-symbol aggregation really exercised


@pytest.mark.parametrize("offset,expect_zero", [(8, True), (7, False)])
def test_sec_rate_is_taken_on_the_execution_date(offset, expect_zero):
    """SEC is $0 from 2025-05-14. Offset 8 signals on 2025-05-13 and fills on 2025-05-14 (SEC 0);
    offset 7 fills on 2025-05-13 ($27.80 per $1M)."""
    idx = pd.bdate_range("2024-12-02", "2025-07-31")
    panel = panel_from_bars({"SPY": make_bars(np.linspace(100, 110, len(idx)), dates=idx)}, None)

    def fn(closes, asof):
        return {"SPY": 1.0} if asof.month % 2 == 0 else {}  # buy in April, sell in May

    spec = StrategySpec("alt", ["SPY"], None, fn, signal_offset=offset)
    res = run_backtest(spec, panel, EngineConfig(initial_capital=1_000_000.0, costs=CostModel.gate(),
                                                  start="2025-03", end="2025-06"))
    may = res.rebalances[res.rebalances["exec_date"].dt.month == 5].iloc[0]
    assert may["sold"] > 900_000
    assert bool(may["sec"] == 0.0) == expect_zero


def test_taf_cap_applies_per_order_and_pause_flag_only_in_q4_2026():
    m = AlpacaFeeModel()
    two = m.day_fees(date(2026, 6, 1), [Order("SPY", "sell", 5e7, 100_000.0), Order("IEF", "sell", 5e7, 100_000.0)])
    assert two.taf == pytest.approx(19.58)
    p = AlpacaFeeModel(taf_q4_2026_pause=True)
    o = [Order("SPY", "sell", 1e4, 20.0)]
    assert p.day_fees(date(2026, 10, 1), o).taf == 0.0 and p.day_fees(date(2026, 12, 31), o).taf == 0.0
    assert p.day_fees(date(2026, 9, 30), o).taf == 0.01 and p.day_fees(date(2027, 1, 4), o).taf == 0.01
    assert m.day_fees(date(2026, 10, 1), o).taf == 0.01  # OFF by default
    buy_only = m.day_fees(date(2026, 6, 1), [Order("SPY", "buy", 1e6, 2000.0)])
    assert (buy_only.sec, buy_only.taf, buy_only.cat) == (0.0, 0.0, 0.01)


# =====================================================================================
# 4. Statistics
# =====================================================================================
def _bruteforce_pbo(x: np.ndarray, s: int) -> np.ndarray:
    t, n = x.shape
    m = t // s
    xb = x[t - m * s:]
    blocks = [xb[i * m:(i + 1) * m] for i in range(s)]

    def sr(a):
        return a.mean(0) / a.std(0, ddof=1)

    out = []
    for c in itertools.combinations(range(s), s // 2):
        IS = np.vstack([blocks[i] for i in c])
        OOS = np.vstack([blocks[i] for i in range(s) if i not in c])
        best = int(np.argmax(sr(IS)))
        w = rankdata(sr(OOS))[best] / (n + 1)
        out.append(math.log(w / (1 - w)))
    return np.array(out)


@pytest.mark.parametrize("t,n,s,seed", [(103, 7, 6, 3), (97, 12, 8, 4), (64, 3, 4, 5)])
def test_pbo_matches_bruteforce_cscv(t, n, s, seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.002, 0.03, (t, n))
    x[:, 1] += 0.003
    res = cscv_pbo(x, s_blocks=s)
    lg = _bruteforce_pbo(x, s)
    assert res.n_splits == math.comb(s, s // 2)
    np.testing.assert_allclose(np.sort(res.logits), np.sort(lg), rtol=1e-9)
    assert res.pbo == pytest.approx(np.mean(lg <= 0))
    assert res.t_used == (t // s) * s


def test_pbo_ignores_only_the_earliest_rows():
    rng = np.random.default_rng(8)
    x = rng.normal(0, 0.03, (100, 5))
    y = x.copy()
    y[:4] = 1e3  # 100 mod 16 = 4 earliest rows are dropped
    assert cscv_pbo(x, 16).pbo == cscv_pbo(y, 16).pbo
    z = x.copy()
    z[-1, 0] += 0.5  # the latest row is used
    assert not np.allclose(cscv_pbo(x, 16).logits, cscv_pbo(z, 16).logits)


def test_stationary_bootstrap_geometric_blocks_and_wraparound():
    t, b = 300, 6.0
    idx = stationary_bootstrap_indices(t, 600, b, np.random.default_rng(1))
    cont = idx[:, 1:] == (idx[:, :-1] + 1) % t
    # P(continue) = 1 - 1/b (+ a 1/t chance that a fresh draw equals the next index)
    assert cont.mean() == pytest.approx(1 - 1 / b + 1 / (b * t), abs=0.005)
    assert ((idx[:, :-1] == t - 1) & (idx[:, 1:] == 0)).sum() > 50  # wraps around the end
    counts = np.bincount(idx.ravel(), minlength=t)
    assert counts.std() / counts.mean() < 0.1  # every month equally likely


def test_dsr_matches_closed_form_with_t_minus_one_and_gamma():
    g = 0.5772156649015329
    for sr, t, sk, ku, v, n in [(0.2, 240, -0.5, 4.5, 0.004, 50), (0.1, 60, 0.3, 3.0, 0.01, 2),
                                (0.35, 400, -1.2, 8.0, 0.002, 1000)]:
        sr0 = math.sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / n) + g * norm.ppf(1 - 1 / (n * math.e)))
        z = (sr - sr0) * math.sqrt(t - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr**2)
        assert deflated_sharpe(sr, t, sk, ku, v, n).dsr == pytest.approx(norm.cdf(z), rel=1e-12)


def test_walk_forward_selection_does_not_peek_at_the_test_year():
    rng = np.random.default_rng(2)
    months = pd.date_range("2000-01-31", periods=180, freq="ME")
    df = pd.DataFrame(rng.normal(0.006, 0.04, (180, 4)), index=months, columns=list("abcd"))
    rf = pd.Series(0.002, index=months)
    base = walk_forward(df, rf)
    for k0 in (60, 72, 100, 150):
        t = df.copy()
        t.iloc[k0:, 3] = 0.5  # variant d becomes absurdly good from month k0 on
        alt = walk_forward(t, rf)
        known = base.choices["train_end"] < months[k0].date()
        pd.testing.assert_frame_equal(base.choices[known], alt.choices[known])


# FINDING CORE-04 (fails while the defect is present)
def test_turnover_excludes_the_initial_purchase_even_when_the_rule_starts_in_cash():
    """FINDING CORE-04: methodology s.5 defines turnover as (buys + sells) / equity "excluding the initial
    purchase", but ``summarize`` drops the first *rebalance row*. A rule that starts in cash (e.g. the
    12-month absolute momentum rule in the long sample, out in 1988-07) has an empty first row, so its
    real initial purchase is counted. A strategy that buys once and holds must show zero turnover."""
    idx = pd.bdate_range("2010-01-04", periods=252 * 3)
    panel = panel_from_bars({"SPY": make_bars(np.linspace(100, 130, len(idx)), dates=idx)}, None)
    first: dict = {}

    def fn(closes, asof):
        first.setdefault("d", asof)
        return {} if asof == first["d"] else {"SPY": 1.0}

    res = run_backtest(StrategySpec("late_bh", ["SPY"], None, fn), panel,
                       EngineConfig(costs=CostModel.zero(), start="2010-01", cash_yield=False))
    assert res.rebalances["n_orders"].iloc[0] == 0 and res.rebalances["turnover"].iloc[1] == pytest.approx(1.0)
    assert M.summarize(res)["turnover_per_year"] == pytest.approx(0.0, abs=1e-9)


def test_plateau_neighbourhood_is_plus_minus_25_percent():
    s = pd.Series({lb: 1.0 for lb in range(3, 19)})
    s[8] = 0.69
    assert plateau_statistic(s, 12)["neighbors"] == [9, 10, 11, 12, 13, 14, 15]
    st = plateau_statistic(s, 10)
    assert st["neighbors"] == [8, 9, 10, 11, 12] and st["min_retained"] == pytest.approx(0.69)


# =====================================================================================
# 5. Data layer
# =====================================================================================
# FINDING CORE-01 (fails while the defect is present)
def test_quality_gates_reject_a_corrupted_adjusted_close(dividend_payer_bars):
    """FINDING CORE-01: every price check (jumps, staleness) runs on ``close_raw``; the adjusted
    ``close`` the engine actually trades and marks is only checked once a year (TR-PR gap on year-end
    values). A vendor error that triples the adjusted OHLC on one month-end, with a clean as-traded
    close, passes every gate -- and would flip trend signals and inject +200%/-67% monthly returns."""
    bad = dividend_payer_bars.copy()
    d = bad.index[(bad.index.year == 2009) & (bad.index.month == 6)][-1]
    for c in ("open", "high", "low", "close"):
        bad.loc[d, c] *= 3.0
    with pytest.raises(DataQualityError):
        run_quality_checks(bad, "SPY", get_meta("SPY"))


# FINDING CORE-02 (fails while the defect is present)
def test_quality_gates_reject_a_two_month_hole(dividend_payer_bars):
    """FINDING CORE-02: the spacing gate checks only the *median* gap, so a series missing 40 consecutive
    business days (two months) passes. In a one-symbol panel the missing months vanish from the calendar
    (a two-month return is booked as one month); in a multi-symbol panel the hole is forward-filled into
    a flat, stale segment that the stale-price gate never sees."""
    hole = dividend_payer_bars.drop(dividend_payer_bars.index[1000:1040])
    with pytest.raises(DataQualityError):
        run_quality_checks(hole, "SPY", get_meta("SPY"))


FF_TEXT = """This file was created by CMPT_ME_BEME_RETS using the 202608 CRSP database.
The 1-month TBill return is from Ibbotson and Associates, Inc.

,Mkt-RF,SMB,HML,RF
192607,    2.96,   -2.56,   -2.43,    0.22
192608,    2.64,   -1.17,    3.82,    0.25
192609,  -99.99,   -1.40,    0.13,    0.23

 Annual Factors: January-December
,Mkt-RF,SMB,HML,RF
  1927,   29.47,   -2.04,   -4.54,    3.12

Copyright 2026 Eugene F. Fama and Kenneth R. French
"""


def test_ff_parser_reads_only_the_monthly_block():
    df = fetch.parse_ff_factors_csv(FF_TEXT.replace("-99.99", "  1.00"))
    assert list(df.index.strftime("%Y-%m")) == ["1926-07", "1926-08", "1926-09"]
    assert df.loc["1926-07-31", "Mkt-RF"] == pytest.approx(0.0296) and df.loc["1926-08-31", "RF"] == pytest.approx(0.0025)


# FINDING CORE-05 (fails while the defect is present)
def test_ff_parser_treats_the_minus_99_99_missing_code_as_missing():
    """FINDING CORE-05: Ken French files use -99.99 (and -999) for missing values; the parser turns
    them into a -99.99% monthly return instead of NaN or an error."""
    try:
        df = fetch.parse_ff_factors_csv(FF_TEXT)
    except fetch.FetchError:
        return  # refusing the file is an acceptable fix
    assert not df.loc["1926-09-30", "Mkt-RF"] == pytest.approx(-0.9999)
    assert np.isnan(df.loc["1926-09-30", "Mkt-RF"])


# FINDING CORE-06 (fails while the defect is present)
def test_ff_cache_is_refused_when_its_hash_does_not_match(tmp_path, monkeypatch):
    """FINDING CORE-06: bars and DTB3 caches are refused on a sha256 mismatch, but ``get_ff_factors``
    reads its cache without checking the manifest hash it wrote (and the DTB3 stale-fallback path
    also skips the check). A tampered or truncated Ken French file silently feeds the cross-checks."""
    monkeypatch.setenv("STOCKTRY_DATA_DIR", str(tmp_path))
    cdir = fetch.cache_dir()
    cdir.mkdir(parents=True)
    (cdir / "FF_FACTORS.csv").write_bytes(FF_TEXT.replace("-99.99", "  1.00").encode("latin-1"))
    (cdir / "FF_FACTORS.manifest.json").write_text(json.dumps({"sha256": fetch.sha256_bytes(b"other")}))
    with pytest.raises(fetch.CacheIntegrityError):
        fetch.get_ff_factors()


def test_bars_cache_hash_mismatch_is_refused(tmp_path):
    df = make_bars(np.linspace(10, 20, 30))
    fetch.write_bars_cache("SPY", df, "test", cdir=tmp_path)
    p = tmp_path / "SPY.csv"
    p.write_bytes(p.read_bytes().replace(b"10,", b"11,", 1))
    with pytest.raises(fetch.CacheIntegrityError):
        fetch.read_bars_cache("SPY", tmp_path)


def test_fred_parser_handles_missing_dots_and_new_header():
    s = fetch.parse_fred_csv("observation_date,DTB3\n2020-01-02,1.52\n2020-01-03,.\n2020-01-06,1.50\n", "DTB3")
    assert list(s.values) == [1.52, 1.50] and s.index[1] == pd.Timestamp("2020-01-06")


def _correlated_pair(seed=0, noise=0.0005):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("1995-01-02", "2008-12-31")
    r = rng.normal(0.0003, 0.01, len(idx))
    proxy = make_bars(100 * np.cumprod(1 + r), dates=idx)
    t_idx = idx[idx >= pd.Timestamp("2003-09-29")]
    rt = r[idx >= pd.Timestamp("2003-09-29")] + rng.normal(0, noise, len(t_idx))
    target = make_bars(50 * np.cumprod(1 + rt), dates=t_idx, close_raw=60 * np.cumprod(1 + rt))
    return target, proxy


def test_splice_uses_proxy_returns_through_first_month_end_then_target_returns():
    target, proxy = _correlated_pair()
    rule = SpliceRule("AGG", "VBMFX", True, 0.95)
    out, info = splice_bars(target, proxy, rule)
    er = (get_meta("VBMFX").expense_ratio - get_meta("AGG").expense_ratio) / 252
    b = pd.Timestamp("2003-09-30")
    assert info.boundary == "2003-09-30" and out.index[0] == proxy.index[0]
    r = out["close"].pct_change()
    pr = proxy["close"].pct_change()
    seg = r.index[(r.index > out.index[0]) & (r.index <= b)]
    np.testing.assert_allclose(r[seg], pr[seg] + er, rtol=0, atol=1e-12)
    after = r.index[r.index > b]
    np.testing.assert_allclose(r[after], target["close"].pct_change()[after], rtol=0, atol=1e-12)
    assert out.loc[b, "close"] == pytest.approx(target.loc[b, "close"])
    assert out.loc[:pd.Timestamp("2003-09-29"), "close_raw"].isna().all()


def test_splice_rejected_on_low_correlation_or_short_overlap():
    target, proxy = _correlated_pair(noise=0.01)
    with pytest.raises(SpliceRejected):
        splice_bars(target, proxy, SpliceRule("SPY", "VFINX", True, 0.995))
    target, proxy = _correlated_pair()
    short = target.loc[:"2006-06-30"]  # ~33 months of overlap
    with pytest.raises(SpliceRejected):
        splice_bars(short, proxy, SpliceRule("AGG", "VBMFX", True, 0.95))
    with pytest.raises(SpliceRejected):
        splice_bars(target, proxy, SPLICES["EFA"])  # disabled rule


def _loader(frames):
    return lambda sym: (frames[sym], {"splits": []})


def test_valid_from_is_applied_in_every_mode_including_as_a_splice_proxy():
    rng = np.random.default_rng(4)
    idx = pd.bdate_range("1984-01-02", "2000-12-29")
    r = rng.normal(0.0004, 0.01, len(idx))
    vfinx = make_bars(100 * np.cumprod(1 + r), dates=idx)
    t_idx = idx[idx >= pd.Timestamp("1993-01-29")]
    spy = make_bars(40 * np.cumprod(1 + r[idx >= pd.Timestamp("1993-01-29")]), dates=t_idx)
    ld = _loader({"VFINX": vfinx, "SPY": spy})
    df, *_ = load_series("VFINX", "etf", ld, run_quality=False)
    assert df.index[0] >= pd.Timestamp("1987-01-01")
    df, desc, info, _ = load_series("SPY", "proxy", ld, run_quality=False)
    assert "VFINX" in desc and df.index[0] >= pd.Timestamp("1987-01-01")


def test_efa_is_substituted_by_vgtsx_only_in_proxy_mode():
    a = make_bars(np.linspace(50, 60, 40), start="2001-08-27")
    b = make_bars(np.linspace(10, 12, 40), start="1996-04-29")
    ld = _loader({"EFA": a, "VGTSX": b})
    df, desc, info, meta = load_series("EFA", "proxy", ld, run_quality=False)
    assert df.equals(b) and meta.symbol == "VGTSX" and info is None and "substituted" in desc
    df, desc, info, meta = load_series("EFA", "etf", ld, run_quality=False)
    assert df.equals(a) and meta.symbol == "EFA"


# FINDING CORE-09 (fails while the defect is present)
def test_a_series_that_stops_early_truncates_the_backtest_instead_of_being_forward_filled():
    """FINDING CORE-09: ``PricePanel.last_complete_month_end`` takes the minimum of ``last_valid_index()``
    over the *forward-filled* closes, which is always the last calendar date, so its "complete in every
    column" rule never fires. A series that ends early (stale-cache fallback after a failed refresh --
    the manifest ``stale`` flag is never consulted -- a lagging vendor, or a closed share class such as
    the VGTSX substitute) is carried flat to the panel end: here AGG stops on 2021-06-30 but the 60/40
    runs to 2021-08-31 with AGG frozen, silently."""
    ia = pd.bdate_range("2019-01-01", "2021-06-30")
    ib = pd.bdate_range("2019-01-01", "2021-09-30")
    p = panel_from_bars({"AGG": make_bars(np.linspace(100, 150, len(ia)), dates=ia),
                         "SPY": make_bars(np.linspace(50, 60, len(ib)), dates=ib)}, None)
    end = p.last_complete_month_end()
    assert end <= pd.Timestamp("2021-06-30")
    res = run_backtest(make_sixty_forty("SPY", "AGG"), p, EngineConfig(costs=CostModel.zero(), start="2019-01"))
    assert res.monthly_returns.index[-1] <= pd.Timestamp("2021-06-30")


# =====================================================================================
# 6. Reproducibility and leaky-result refusal
# =====================================================================================
# FINDING CORE-08 (fails while the defect is present)
def test_report_layer_refuses_leaky_results():
    """FINDING CORE-08: engine.py and results/leakage.md state that "the ledger and report writers
    refuse" same-bar-fill results, but only ``TrialLedger.record`` does (and only if the caller passes
    ``leaky=``). ``metrics.summarize`` -- the entry point of every report table -- accepts them."""
    idx = pd.bdate_range("2010-01-04", periods=300)
    panel = panel_from_bars({"SPY": make_bars(np.linspace(100, 120, len(idx)), dates=idx)}, None)
    res = run_backtest(make_buy_and_hold("SPY"), panel,
                       EngineConfig(costs=CostModel.zero(), start="2010-01", same_bar_fill=True))
    assert res.leaky
    with pytest.raises((ValueError, RuntimeError, AssertionError)):
        M.summarize(res)


# =====================================================================================
# 7. Committed report correctness (reads results/)
# =====================================================================================
def _md_table_after(text: str, heading: str) -> pd.DataFrame:
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == heading)
    rows = []
    for l in lines[i + 1:]:
        if l.startswith("|"):
            rows.append([c.strip() for c in l.strip().strip("|").split("|")])
        elif rows:
            break
    return pd.DataFrame(rows[2:], columns=rows[0]).set_index(rows[0][0])


def test_every_results_markdown_file_starts_with_the_disclosure_block():
    for p in sorted(RESULTS.glob("*.md")):
        head = p.read_text().split("\n## ")[0]
        assert "hypothetical backtested performance" in head, p.name
        for item in ("Costs modelled", "Sample period", "Benchmark shown", "Worst drawdown",
                     "Number of variants tried", "Past performance does not indicate future results"):
            assert item in head, (p.name, item)


# FINDING CORE-03 (fails while the defect is present)
def test_scaling_disclosure_states_the_cost_tier_and_capital_actually_used():
    """FINDING CORE-03: the disclosure block is one fixed text. In results/scaling.md it says costs are
    the half-spread "floored at 5 bp per side", "$10,000 starting capital" and "2x-cost results are
    shown", while every number in that file uses the *modelled* tier (no floor), $1-$100,000 and no 2x
    rows; its worst drawdown is attributed to the Proxy sample, which scaling.md does not contain.
    (leakage.md and crosscheck.md likewise say "results are net of these" above zero-cost tables.)"""
    text = (RESULTS / "scaling.md").read_text()
    costs_line = next(l for l in text.splitlines() if "Costs modelled" in l)
    worst_line = next(l for l in text.splitlines() if "Worst drawdown" in l)
    assert "floored at 5 bp" not in costs_line and "$10,000 starting capital" not in costs_line
    assert "Proxy sample" not in worst_line


@pytest.mark.parametrize("sample", ["long", "proxy", "etf"])
def test_summary_headline_tables_match_metrics_csv(sample):
    from stocktry.backtest.samples import SAMPLES
    from stocktry.report.pipeline import LABELS, METRIC_COLS

    text = (RESULTS / "summary.md").read_text()
    t = _md_table_after(text, f"## Headline metrics: {SAMPLES[sample].label}")
    csv = pd.read_csv(RESULTS / f"metrics_{sample}.csv", index_col=0)
    assert list(t.index) == [LABELS[n] for n in SAMPLES[sample].strategies]
    for name in SAMPLES[sample].strategies:
        for key, lab, f in METRIC_COLS:
            assert t.loc[LABELS[name], lab] == f(csv.loc[name, key]), (sample, name, lab)


def test_gate_scorecard_is_consistent_with_the_csvs_and_methodology():
    from stocktry.backtest.samples import SAMPLES

    text = (RESULTS / "summary.md").read_text()
    g = _md_table_after(text, "## Gate A scorecard (pre-registered in docs/research-report.md section 12)")
    dsr = pd.read_csv(RESULTS / "dsr.csv")
    pbo = pd.read_csv(RESULTS / "pbo.csv")
    assert len(g) == sum(len(s.primary_for) for s in SAMPLES.values())
    for key, row in g.iterrows():
        sname, cand = [x.strip() for x in key.split("/")]
        m = pd.read_csv(RESULTS / f"metrics_{sname}.csv", index_col=0)
        boot = pd.read_csv(RESULTS / f"bootstrap_{sname}.csv", index_col=0)
        c, b = m.loc[cand], m.loc["spy_buy_hold"]
        # A2 (cost part)
        keep = c["sharpe_2x"] >= 0.9 * c["sharpe"] if c["sharpe"] > 0 else False
        years_ok = c["months"] >= 180 and c["first_month"] <= "2008-01" and c["last_month"] >= "2022-12"
        assert (row["A2 >=15y, 2008/20/22, >=5bp, 2x costs"] == "PASS") == bool(keep and years_ok)
        # A3 as amended 2026-09-29: WF Sharpe >= 0.5 AND CAGR >= B&H - 1 point AND (Sharpe > B&H OR
        # |MaxDD| <= 0.7 x B&H). The full-sample half is decided exactly from the csv; WF Sharpe is shown rounded.
        rel = c["cagr"] >= b["cagr"] - 0.01 and (c["sharpe"] > b["sharpe"]
                                                 or abs(c["max_dd"]) <= 0.7 * abs(b["max_dd"]))
        a3 = row["A3 WF Sharpe>=0.5 & CAGR>=B&H-1% & (Sharpe>B&H or DD<=0.7xB&H)"]
        if a3 == "PASS":
            assert rel and float(row["wf_sharpe"]) >= 0.5
        if not rel or float(row["wf_sharpe"]) < 0.495:
            assert a3 == "FAIL"
        # A4 from dsr.csv / pbo.csv
        d = float(dsr[(dsr["sample"] == sname) & (dsr["strategy"] == cand)]["dsr_all"].iloc[0])
        grid = "trend" if cand.startswith("trend") else cand
        p = float(pbo[(pbo["sample"] == sname) & (pbo["grid"] == grid)]["pbo"].iloc[0])
        assert row["dsr"] == f"{d:.2f}" and row["pbo"] == f"{p:.2f}"
        assert (row["A4 DSR>=0.95 & PBO<=0.2"] == "PASS") == (d >= 0.95 and p <= 0.2)
        # A6 from bootstrap csv
        from stocktry.report.pipeline import LABELS
        bc, bb = boot.loc[LABELS[cand]], boot.loc[LABELS["spy_buy_hold"]]
        a6 = bc["cagr_p5"] > 0 and bc["dd_mag_p95"] <= bb["dd_mag_p95"]
        assert (row["A6 boot p5 CAGR>0 & p95 DD<=B&H"] == "PASS") == bool(a6)
        # A7: the calendar-year half is necessary for a PASS
        ann = pd.read_csv(RESULTS / f"annual_returns_{sname}.csv", index_col=0)
        ann.index = [str(i).rstrip("*") for i in ann.index]
        crisis = all(ann.loc[y, LABELS[cand]] > ann.loc[y, LABELS["spy_buy_hold"]] for y in ("2008", "2022"))
        if row["A7 2008 & 2022 & >=2/3 5y"] == "PASS":
            assert crisis
        # verdict lists exactly the failed gates
        failed = [k.split(" ")[0] for k in row.index if k.startswith("A") and row[k] == "FAIL"]
        assert row["verdict"] == ("eligible for paper trading" if not failed
                                  else "REJECTED (" + ", ".join(failed) + ")")
