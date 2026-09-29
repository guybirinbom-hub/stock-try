"""End-to-end backtest pipeline behind ``scripts/run_backtests.py``.

Runs every pre-registered strategy on every sample, the parameter sweeps,
tranching, walk-forward, plateau, PBO, bootstrap, deflated Sharpe, leakage
tests, independent cross-checks and the capital-scaling study, and writes
templated markdown / CSV / PNG files to ``results/``. Deterministic: no
network calls except filling an empty data cache, fixed seeds, no LLM.

Headline configuration (also the trial ledger's headline run): $10,000
starting capital, fractional shares, next-day-open fills, the "gate" cost
tier (per-instrument half-spread floored at 5 bp per side + Alpaca
regulatory fees + $1 minimum order). Sensitivity: 2x that cost tier.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..backtest import metrics as M
from ..backtest.costs import CostModel
from ..backtest.engine import BacktestResult, EngineConfig, run_backtest
from ..backtest.samples import SAMPLES, Sample
from ..data import fetch
from ..data.panel import PricePanel, build_panel
from ..data.universe import SPLICES, UNIVERSE
from ..strategies.base import StrategySpec
from ..strategies.registry import CANDIDATES, STRATEGIES, make_variant
from ..validation import crosscheck as X
from ..validation import leakage as L
from ..validation.bootstrap import bootstrap, percentile_table
from ..validation.dsr import deflated_sharpe
from ..validation.ledger import TrialLedger
from ..validation.pbo import cscv_pbo
from ..validation.plateau import plateau_statistic
from ..validation.walkforward import PREREGISTERED_SPLIT, split_metrics, walk_forward
from . import charts
from .disclosure import disclosure_block
from .format import bp, integer, md_table, money, num, pct, yesno


LOOKBACKS = list(range(3, 19))
OFFSETS = list(range(0, 21))
CAPITALS = (1.0, 100.0, 1_000.0, 10_000.0, 100_000.0)
HEADLINE_CAPITAL = 10_000.0
BOOT_SEED = 20260929
BOOT_PATHS = 2000
BOOT_BLOCK = 6.0
SHIFT_TOL = 0.15  # Gate A.8: |Sharpe change| under a one-day execution delay (pre-registered)
COST2X_RETAIN = 0.90  # Gate A.2: Sharpe at 2x costs must keep >= 90% of Sharpe at 1x (pre-registered)
LABELS = {
    "spy_buy_hold": "SPY buy & hold", "sixty_forty": "60/40 SPY/AGG", "trend_sma10": "SPY 10-mo SMA",
    "trend_absmom12": "SPY 12-mo abs. momentum", "trend_ensemble": "SPY trend ensemble",
    "gtaa4": "GTAA-4 (no commodities)", "gtaa5": "GTAA-5",
}
DEFAULT_LOOKBACK = {"trend_sma": 10, "trend_absmom": 12, "gtaa4": 10, "gtaa5": 10}
CAND_FAMILY = {"trend_sma10": "trend_sma", "trend_absmom12": "trend_absmom", "trend_ensemble": "trend_ensemble",
               "gtaa4": "gtaa4", "gtaa5": "gtaa5"}


def gate_costs() -> CostModel:
    return CostModel.gate()


def gate_costs_2x() -> CostModel:
    return CostModel.gate().scaled(2.0, "gate_x2")


@dataclass
class Pipeline:
    results_dir: Path
    ledger: TrialLedger
    panels: dict[str, PricePanel] = field(default_factory=dict)
    head: dict[tuple[str, str], BacktestResult] = field(default_factory=dict)
    head2x: dict[tuple[str, str], BacktestResult] = field(default_factory=dict)
    metrics: dict[tuple[str, str], dict] = field(default_factory=dict)
    grids: dict[tuple[str, str], dict[str, BacktestResult]] = field(default_factory=dict)
    out: dict[str, Any] = field(default_factory=dict)
    t0: float = field(default_factory=time.time)

    # ------------------------------------------------------------------ plumbing
    def log(self, msg: str) -> None:
        print(f"[{time.time() - self.t0:6.1f}s] {msg}", flush=True)

    def run(self, spec: StrategySpec, sample: Sample, costs: CostModel, capital: float = HEADLINE_CAPITAL,
            whole: bool = False, fill: str = "next_open", purpose: str = "backtest", record: bool = True,
            panel: PricePanel | None = None) -> BacktestResult:
        cfg = EngineConfig(initial_capital=capital, costs=costs, start=sample.first_signal, whole_shares=whole,
                           fill=fill)
        assert not cfg.same_bar_fill  # the CLI path can never produce a leaky run
        res = run_backtest(spec, panel or self.panels[sample.name], cfg)
        if record:
            r = res.monthly_returns
            sk, ku = M.skew_kurtosis(r - res.rf_monthly)
            self.ledger.record(
                strategy=spec.name, family=spec.family, params=spec.params, sample=sample.name,
                cost_tier=costs.name, capital=capital, whole_shares=whole, fill=fill, t=len(r),
                sharpe_per_period=M.sharpe_per_period(r, res.rf_monthly), skew=sk, kurtosis=ku, cagr=M.cagr(r),
                max_dd=M.max_drawdown(res.equity), first_month=str(r.index[0].to_period("M")),
                last_month=str(r.index[-1].to_period("M")), purpose=purpose, leaky=res.leaky)
        return res

    def write(self, name: str, text: str) -> None:
        (self.results_dir / name).write_text(text)

    # ------------------------------------------------------------------ data
    def load(self) -> None:
        for s in SAMPLES.values():
            self.panels[s.name] = build_panel(list(s.symbols), s.data_mode, start=s.history_start)
            self.log(f"panel {s.name}: {self.panels[s.name].calendar[0].date()}.."
                     f"{self.panels[s.name].last_complete_month_end().date()} {self.panels[s.name].sources}")
        self.panels["spy_full"] = build_panel(["SPY"], "etf")
        self.ff = fetch.get_ff_factors()

    # ------------------------------------------------------------------ 1. headline
    def headline(self) -> None:
        for s in SAMPLES.values():
            for name in s.strategies:
                spec = STRATEGIES[name]
                r1 = self.run(spec, s, gate_costs(), purpose="candidate" if name in CANDIDATES else "benchmark")
                r2 = self.run(spec, s, gate_costs_2x(), purpose="cost_sensitivity")
                self.head[(s.name, name)], self.head2x[(s.name, name)] = r1, r2
                bench = self.head[(s.name, "spy_buy_hold")].monthly_returns
                m = M.summarize(r1, bench)
                m["cagr_2x"] = M.cagr(r2.monthly_returns)
                m["sharpe_2x"] = M.sharpe(r2.monthly_returns, r2.rf_monthly)
                self.metrics[(s.name, name)] = m
            self.log(f"headline {s.name} done")

    # ------------------------------------------------------------------ 2. sweeps
    def sweeps(self) -> None:
        for s in SAMPLES.values():
            g: dict[str, BacktestResult] = {}
            for rule in ("sma", "absmom"):
                for lb in LOOKBACKS:
                    g[f"{rule}_L{lb}"] = self.run(make_variant(f"trend_{rule}", lookback=lb), s, gate_costs(),
                                                  purpose="sweep")
            self.grids[(s.name, "trend")] = g
            self.log(f"trend sweep {s.name} done")
        plan = [("proxy", "gtaa4", True), ("etf", "gtaa5", False), ("etf", "gtaa4", False)]
        for sname, fam, full in plan:
            s = SAMPLES[sname]
            g = {}
            for lb in LOOKBACKS:
                offs = [-1] + (OFFSETS if full else ([o for o in OFFSETS] if lb == 10 else []))
                for off in offs:
                    key = f"L{lb}_" + ("me" if off < 0 else f"o{off}")
                    g[key] = self.run(make_variant(fam, lookback=lb, offset=off), s, gate_costs(), purpose="sweep")
            self.grids[(sname, fam)] = g
            self.log(f"{fam} sweep {sname} done ({len(g)} variants)")

    # ------------------------------------------------------------------ 3. tranching
    def tranching(self) -> None:
        rows, detail = [], {}
        for sname, fam in (("proxy", "gtaa4"), ("etf", "gtaa4"), ("etf", "gtaa5")):
            s = SAMPLES[sname]
            g = self.grids[(sname, fam)]
            by_off = pd.Series({o: M.cagr(g[f"L10_o{o}"].monthly_returns) for o in OFFSETS})
            by_off.index.name = "signal day (k-th trading day of month, 0-based)"
            sr_off = pd.Series({o: M.sharpe(g[f"L10_o{o}"].monthly_returns, g[f"L10_o{o}"].rf_monthly)
                                for o in OFFSETS})
            # Tranched portfolio: 21 sub-accounts of capital/21, each rebalancing on its own day.
            sub = HEADLINE_CAPITAL / len(OFFSETS)
            eqs = [self.run(make_variant(fam, lookback=10, offset=o), s, gate_costs(), capital=sub,
                            purpose="tranche_subaccount").equity for o in OFFSETS]
            tot = sum(eqs)
            base = self.head[(sname, fam)]
            me = base.month_end_equity.index
            tr = tot.reindex(me).pct_change().iloc[1:]
            rf = base.rf_monthly
            sk, ku = M.skew_kurtosis(tr - rf)
            self.ledger.record(strategy=f"{fam}_tranched", family=f"{fam}_tranched", params={"lookback": 10,
                               "offsets": OFFSETS}, sample=sname, cost_tier="gate", capital=HEADLINE_CAPITAL,
                               whole_shares=False, fill="next_open", t=len(tr),
                               sharpe_per_period=M.sharpe_per_period(tr, rf), skew=sk, kurtosis=ku, cagr=M.cagr(tr),
                               max_dd=M.max_drawdown(tot), first_month=str(tr.index[0].to_period("M")),
                               last_month=str(tr.index[-1].to_period("M")), purpose="tranche")
            rows.append({"sample": sname, "strategy": fam, "month_end_cagr": M.cagr(base.monthly_returns),
                         "min_cagr": by_off.min(), "max_cagr": by_off.max(), "spread_bp": (by_off.max() - by_off.min()) * 1e4,
                         "std_bp": by_off.std(ddof=1) * 1e4, "best_day": int(by_off.idxmax()), "worst_day": int(by_off.idxmin()),
                         "tranched_cagr": M.cagr(tr), "tranched_sharpe": M.sharpe(tr, rf),
                         "tranched_max_dd": M.max_drawdown(tot)})
            detail[(sname, fam)] = (by_off, sr_off, M.cagr(tr))
            charts.bars(by_off, self.results_dir / f"tranche_{fam}_{sname}.png",
                        f"{LABELS[fam]}, {SAMPLES[sname].label}: CAGR by signal day (L=10)", "CAGR (%)",
                        highlight=M.cagr(tr), color=charts.SERIES_COLORS[fam])
        self.out["tranche"] = pd.DataFrame(rows)
        self.out["tranche_detail"] = detail
        self.log("tranching done")

    # ------------------------------------------------------------------ 4. walk-forward
    def walkforward(self) -> None:
        rows, choices = [], {}
        specs = []
        for s in SAMPLES.values():
            g = self.grids[(s.name, "trend")]
            specs += [(s.name, "trend_sma", {k: v for k, v in g.items() if k.startswith("sma_")}, "sma_L10"),
                      (s.name, "trend_absmom", {k: v for k, v in g.items() if k.startswith("absmom_")}, "absmom_L12"),
                      (s.name, "trend_all", g, None)]
        for sname, fam in (("proxy", "gtaa4"), ("etf", "gtaa5"), ("etf", "gtaa4")):
            g = self.grids[(sname, fam)]
            specs.append((sname, fam, {k: v for k, v in g.items() if k.endswith("_me")}, "L10_me"))
        for sname, fam, g, default in specs:
            rets = pd.DataFrame({k: v.monthly_returns for k, v in g.items()})
            rf = next(iter(g.values())).rf_monthly
            wf = walk_forward(rets, rf, min_train_months=60, step_months=12)
            oos = wf.oos_returns
            bh = self.head[(sname, "spy_buy_hold")].monthly_returns.reindex(oos.index)
            row = {"sample": sname, "family": fam, "variants": rets.shape[1], "oos_first": str(oos.index[0].to_period("M")),
                   "oos_months": len(oos), "wf_cagr": M.cagr(oos), "wf_sharpe": M.sharpe(oos, wf.oos_rf),
                   "wf_max_dd": M.max_drawdown_from_returns(oos), "bh_cagr": M.cagr(bh), "bh_sharpe": M.sharpe(bh, wf.oos_rf)}
            if default:
                d = rets[default].reindex(oos.index)
                row.update(default_cagr=M.cagr(d), default_sharpe=M.sharpe(d, wf.oos_rf))
            if fam == "trend_all":
                e = self.head[(sname, "trend_ensemble")].monthly_returns.reindex(oos.index)
                row.update(ensemble_cagr=M.cagr(e), ensemble_sharpe=M.sharpe(e, wf.oos_rf))
            rows.append(row)
            choices[(sname, fam)] = wf.choices
            sk, ku = M.skew_kurtosis(oos - wf.oos_rf)
            self.ledger.record(strategy=f"walkforward_{fam}", family=f"walkforward_{fam}",
                               params={"min_train": 60, "step": 12, "variants": sorted(rets.columns)}, sample=sname,
                               cost_tier="gate", capital=HEADLINE_CAPITAL, whole_shares=False, fill="next_open",
                               t=len(oos), sharpe_per_period=M.sharpe_per_period(oos, wf.oos_rf), skew=sk, kurtosis=ku,
                               cagr=M.cagr(oos), max_dd=M.max_drawdown_from_returns(oos),
                               first_month=str(oos.index[0].to_period("M")),
                               last_month=str(oos.index[-1].to_period("M")), purpose="walkforward")
        self.out["wf"] = pd.DataFrame(rows)
        self.out["wf_choices"] = choices
        self.log("walk-forward done")

    # ------------------------------------------------------------------ 5. plateau
    def plateau(self) -> None:
        rows = []
        for s in SAMPLES.values():
            g = self.grids[(s.name, "trend")]
            sh = pd.DataFrame({rule: {lb: M.sharpe(g[f"{rule}_L{lb}"].monthly_returns, g[f"{rule}_L{lb}"].rf_monthly)
                                      for lb in LOOKBACKS} for rule in ("sma", "absmom")}).T
            dd = pd.DataFrame({rule: {lb: M.max_drawdown(g[f"{rule}_L{lb}"].equity) for lb in LOOKBACKS}
                               for rule in ("sma", "absmom")}).T
            cg = pd.DataFrame({rule: {lb: M.cagr(g[f"{rule}_L{lb}"].monthly_returns) for lb in LOOKBACKS}
                               for rule in ("sma", "absmom")}).T
            for t in (sh, dd, cg):
                t.index.name, t.columns.name = "rule", "lookback (months)"
            self.out[("plateau_trend", s.name)] = (sh, dd, cg)
            charts.heatmap(sh, self.results_dir / f"plateau_trend_{s.name}_sharpe.png",
                           f"SPY trend rules, {s.label}: Sharpe by lookback", "Sharpe (annualized)")
            charts.heatmap(dd * 100, self.results_dir / f"plateau_trend_{s.name}_maxdd.png",
                           f"SPY trend rules, {s.label}: max drawdown by lookback", "Max drawdown (%)",
                           fmt="{:.0f}", reverse=True)
            for rule, fam in (("sma", "trend_sma"), ("absmom", "trend_absmom")):
                st = plateau_statistic(sh.loc[rule], DEFAULT_LOOKBACK[fam])
                rows.append({"sample": s.name, "family": fam, **st})
        for sname, fam in (("proxy", "gtaa4"), ("etf", "gtaa5"), ("etf", "gtaa4")):
            g = self.grids[(sname, fam)]
            sr_l = pd.Series({lb: M.sharpe(g[f"L{lb}_me"].monthly_returns, g[f"L{lb}_me"].rf_monthly) for lb in LOOKBACKS})
            st = plateau_statistic(sr_l, 10)
            rows.append({"sample": sname, "family": fam, **st})
            self.out[("plateau_gtaa", sname, fam)] = pd.DataFrame({
                "sharpe": sr_l,
                "cagr": pd.Series({lb: M.cagr(g[f"L{lb}_me"].monthly_returns) for lb in LOOKBACKS}),
                "max_dd": pd.Series({lb: M.max_drawdown(g[f"L{lb}_me"].equity) for lb in LOOKBACKS})})
            if sname == "proxy":
                cols = ["me"] + [f"o{o}" for o in OFFSETS]
                hm = pd.DataFrame({c: {lb: M.sharpe(g[f"L{lb}_{c}"].monthly_returns, g[f"L{lb}_{c}"].rf_monthly)
                                       for lb in LOOKBACKS} for c in cols})
                hm.index.name, hm.columns.name = "SMA lookback (months)", "signal day (me = month-end; oK = k-th trading day)"
                self.out[("plateau_gtaa_grid", sname, fam)] = hm
                charts.heatmap(hm, self.results_dir / f"plateau_{fam}_{sname}_lookback_x_day.png",
                               f"{LABELS[fam]}, {SAMPLES[sname].label}: Sharpe by lookback and signal day",
                               "Sharpe (annualized)", annotate=False)
        self.out["plateau"] = pd.DataFrame(rows)
        self.log("plateau done")

    # ------------------------------------------------------------------ 6. PBO
    def pbo(self) -> None:
        rows = []
        grids = [(s.name, "trend", self.grids[(s.name, "trend")]) for s in SAMPLES.values()]
        grids += [(sn, fam, self.grids[(sn, fam)]) for sn, fam in (("proxy", "gtaa4"), ("etf", "gtaa5"), ("etf", "gtaa4"))]
        for sname, fam, g in grids:
            rets = pd.DataFrame({k: v.monthly_returns - v.rf_monthly for k, v in g.items()}).dropna()
            res = cscv_pbo(rets.to_numpy(), s_blocks=16)
            rows.append({"sample": sname, "grid": fam, **res.to_dict()})
        self.out["pbo"] = pd.DataFrame(rows)
        self.log("PBO done")

    # ------------------------------------------------------------------ 7. bootstrap
    def bootstrap(self) -> None:
        tabs = {}
        for s in SAMPLES.values():
            df = pd.DataFrame({n: self.head[(s.name, n)].monthly_returns for n in s.strategies})
            df["rf"] = self.head[(s.name, "spy_buy_hold")].rf_monthly
            b = bootstrap(df, rf_col="rf", mean_block=BOOT_BLOCK, n_paths=BOOT_PATHS, seed=BOOT_SEED)
            tabs[s.name] = percentile_table(b)
        self.out["boot"] = tabs
        self.log("bootstrap done")

    # ------------------------------------------------------------------ 8. DSR
    def dsr(self) -> None:
        rows = []
        for s in SAMPLES.values():
            n_all = self.ledger.n_trials(s.name)
            v_all = self.ledger.sharpe_variance(s.name)
            for name in s.strategies:
                r = self.head[(s.name, name)]
                ex = r.monthly_returns - r.rf_monthly
                sr = M.sharpe_per_period(r.monthly_returns, r.rf_monthly)
                sk, ku = M.skew_kurtosis(ex)
                fam = STRATEGIES[name].family
                n_f = self.ledger.n_trials(s.name, (fam,))
                v_f = self.ledger.sharpe_variance(s.name, (fam,))
                d_all = deflated_sharpe(sr, len(ex), sk, ku, v_all, n_all)
                d_fam = deflated_sharpe(sr, len(ex), sk, ku, v_f if math.isfinite(v_f) else 0.0, n_f)
                rows.append({"sample": s.name, "strategy": name, "t_months": len(ex), "sr_annual": sr * math.sqrt(12),
                             "skew": sk, "kurtosis": ku, "n_all": n_all, "sd_sr_all_annual": math.sqrt(v_all * 12),
                             "sr0_all_annual": d_all.sr0 * math.sqrt(12), "dsr_all": d_all.dsr,
                             "family": fam, "n_family": n_f,
                             "sr0_family_annual": d_fam.sr0 * math.sqrt(12), "dsr_family": d_fam.dsr,
                             "psr_0": deflated_sharpe(sr, len(ex), sk, ku, 0.0, 1).dsr})
        self.out["dsr"] = pd.DataFrame(rows)
        self.log("DSR done")

    # ------------------------------------------------------------------ 9. leakage
    def leakage(self) -> None:
        o: dict[str, Any] = {}
        o["identity_etf"] = L.identity_test(self.panels["spy_full"], "SPY", start="1993-01")
        o["identity_proxy"] = L.identity_test(self.panels["long"], "SPY", start=SAMPLES["long"].first_signal)
        o["foresight_synthetic"] = L.foresight_test(L.synthetic_monthly_panel())
        o["foresight_real"] = L.foresight_test(L.monthly_panel_from(self.panels["spy_full"], "SPY"), "SPY")
        o["gap_synthetic"] = L.gap_foresight_test(L.synthetic_daily_panel())
        o["gap_real"] = L.gap_foresight_test(self.panels["spy_full"], "SPY", cash_yield=True)
        shifts = []
        for s in SAMPLES.values():
            for c in s.primary_for:
                cfg = EngineConfig(initial_capital=HEADLINE_CAPITAL, costs=gate_costs(), start=s.first_signal)
                shifts.append({"sample": s.name, **L.one_bar_shift(STRATEGIES[c], self.panels[s.name], cfg)})
        o["shift"] = pd.DataFrame(shifts)
        self.out["leak"] = o
        self.log("leakage done")

    # ------------------------------------------------------------------ 10. cross-checks
    def crosschecks(self) -> None:
        o: dict[str, Any] = {}
        o["bt"] = X.bt_crosscheck(self.panels["spy_full"], "SPY", start="1993-12")
        o["ff_spy_etf"] = X.ff_market_crosscheck(self.panels["spy_full"].closes["SPY"], self.ff)
        o["ff_spy_long"] = X.ff_market_crosscheck(self.panels["long"].closes["SPY"], self.ff)
        diag = {}
        for sym in ("VTI", "VTSMX"):
            diag[sym] = X.ff_market_crosscheck(build_panel([sym], "etf").closes[sym], self.ff)
        raw_vfinx = fetch.get_bars("VFINX")["close"]  # deliberately bypasses valid_from: shows why it exists
        diag["VFINX (all Yahoo history)"] = X.ff_market_crosscheck(raw_vfinx, self.ff)
        o["ff_diag"] = diag
        o["rf"] = X.ff_rf_crosscheck(self.panels["long"].tbill_index, self.ff)
        self.out["xc"] = o
        self.log("cross-checks done")

    # ------------------------------------------------------------------ 11. scaling
    def scaling(self) -> None:
        s = SAMPLES["etf"]
        rows, skipped_examples = [], {}
        for name in s.strategies:
            for cap in CAPITALS:
                for whole in (False, True):
                    r = self.run(STRATEGIES[name], s, CostModel.modelled(), capital=cap, whole=whole,
                                 purpose="scaling")
                    yrs = r.years
                    avg_eq = float(r.equity.mean())
                    rows.append({"strategy": name, "capital": cap, "shares": "whole" if whole else "fractional",
                                 "cagr": M.cagr(r.monthly_returns), "final_value": float(r.equity.iloc[-1]),
                                 "fees": r.total_fees, "fees_pct_per_year": r.total_fees / avg_eq / yrs,
                                 "spread_cost": r.total_spread_cost, "orders": len(r.trades),
                                 "skipped_below_1": len(r.skipped),
                                 "avg_cash": float((r.cash / r.equity).iloc[1:].mean()),
                                 "sharpe": M.sharpe(r.monthly_returns, r.rf_monthly)})
                    if cap in (1.0, 100.0) and not whole and len(r.skipped):
                        sk = r.skipped.sort_values("notional", ascending=False).head(4).copy()
                        sk.insert(0, "capital", f"${cap:,.0f}")
                        skipped_examples.setdefault(name, []).append(sk)
            self.log(f"scaling {name} done")
        self.out["scaling"] = pd.DataFrame(rows)
        self.out["scaling_skips"] = skipped_examples

    # ------------------------------------------------------------------ 12. gate A
    def gates(self) -> None:
        rows = []
        leak = self.out["leak"]
        structural_ok = (leak["identity_etf"]["passed"] and leak["identity_proxy"]["passed"]
                         and leak["foresight_synthetic"]["lagged_sharpe_within_noise"]
                         and leak["foresight_synthetic"]["same_bar_huge"]
                         and leak["gap_synthetic"]["lagged_no_gap_capture"]
                         and leak["gap_synthetic"]["same_bar_captures_gap"])
        for s in SAMPLES.values():
            for c in s.primary_for:
                rows.append(self._gate_row(s, c, structural_ok))
        self.out["gates"] = pd.DataFrame(rows)

    def _gate_row(self, s: Sample, c: str, structural_ok: bool) -> dict:
        m, mb = self.metrics[(s.name, c)], self.metrics[(s.name, "spy_buy_hold")]
        r, rb = self.head[(s.name, c)].monthly_returns, self.head[(s.name, "spy_buy_hold")].monthly_returns
        row: dict[str, Any] = {"sample": s.name, "candidate": c}
        years = len(r) / 12
        covers = r.index[0] <= pd.Timestamp("2008-01-31") and r.index[-1] >= pd.Timestamp("2022-12-30")
        keep = m["sharpe_2x"] >= COST2X_RETAIN * m["sharpe"] if m["sharpe"] > 0 else False
        row["A1 pre-registered"] = True
        row["A2 >=15y, 2008/20/22, >=5bp, 2x costs"] = bool(years >= 15 and covers and keep)
        fam = CAND_FAMILY[c]
        wf = self.out["wf"]
        wf_key = {"trend_ensemble": "trend_all"}.get(c, fam)
        wrow = wf[(wf["sample"] == s.name) & (wf["family"] == wf_key)].iloc[0]
        wf_sr = wrow["ensemble_sharpe"] if c == "trend_ensemble" else wrow["wf_sharpe"]
        beats = m["sharpe"] > mb["sharpe"] or (m["cagr"] >= mb["cagr"] - 0.01 and abs(m["max_dd"]) <= 0.7 * abs(mb["max_dd"]))
        row["wf_sharpe"] = wf_sr
        row["A3 WF Sharpe>=0.5 & beats B&H"] = bool(wf_sr >= 0.5 and beats)
        d = self.out["dsr"]
        dsr_v = float(d[(d["sample"] == s.name) & (d["strategy"] == c)]["dsr_all"].iloc[0])
        p = self.out["pbo"]
        grid = "trend" if c.startswith("trend") else c
        pbo_v = float(p[(p["sample"] == s.name) & (p["grid"] == grid)]["pbo"].iloc[0])
        row["dsr"], row["pbo"] = dsr_v, pbo_v
        row["A4 DSR>=0.95 & PBO<=0.2"] = bool(dsr_v >= 0.95 and pbo_v <= 0.2)
        pl = self.out["plateau"]
        sel = pl[(pl["sample"] == s.name) & (pl["family"] == fam)]
        plat = float(sel["min_retained"].iloc[0]) if len(sel) else float("nan")
        row["plateau"] = plat
        row["A5 plateau>=0.7"] = None if not math.isfinite(plat) and c == "trend_ensemble" else bool(plat >= 0.7)
        bt_ = self.out["boot"][s.name]
        row["A6 boot p5 CAGR>0 & p95 DD<=B&H"] = bool(bt_.loc[c, "cagr_p5"] > 0
                                                      and bt_.loc[c, "dd_mag_p95"] <= bt_.loc["spy_buy_hold", "dd_mag_p95"])
        ann, annb = M.annual_returns(r), M.annual_returns(rb)
        crisis = bool(ann.get(2008, np.nan) > annb.get(2008, np.nan) and ann.get(2022, np.nan) > annb.get(2022, np.nan))
        wins = 0
        n = len(r)
        for k in range(3):
            a, b = n - 60 * (3 - k), n - 60 * (2 - k)
            if a >= 0 and M.cagr(r.iloc[a:b]) > M.cagr(rb.iloc[a:b]):
                wins += 1
        row["5y windows won (of 3)"] = wins
        row["A7 2008 & 2022 & >=2/3 5y"] = bool(crisis and wins >= 2)
        sh = self.out["leak"]["shift"]
        ds = float(sh[(sh["sample"] == s.name) & (sh["strategy"] == c)]["delta_sharpe"].iloc[0])
        row["A8 leakage"] = bool(structural_ok and abs(ds) <= SHIFT_TOL)
        crit = [k for k in row if k.startswith("A")]
        failed = [k.split(" ")[0] for k in crit if row[k] is False]
        row["verdict"] = "eligible for paper trading" if not failed else "REJECTED (" + ", ".join(failed) + ")"
        return row

    # ------------------------------------------------------------------ writing
    def disclosure(self, samples_txt: str) -> str:
        worst = min(((m["max_dd"], k) for k, m in self.metrics.items()), key=lambda x: x[0])
        n_total = self.ledger.n_trials()
        per = ", ".join(f"{s}: {self.ledger.n_trials(s)}" for s in SAMPLES)
        return disclosure_block(
            samples=samples_txt,
            costs="half-spread per instrument floored at 5 bp per side (the Gate A floor), Alpaca pass-through "
                  "regulatory fees (SEC, FINRA TAF, CAT; each rounded up to the cent per day), $1 minimum order, "
                  "$10,000 starting capital, fills at the next day's open; fund expense ratios are inside fund "
                  "prices. Taxes, market impact and dividend withholding are NOT modelled. 2x-cost results are shown.",
            benchmark="SPY buy-and-hold (total return, same engine and costs); also a 60/40 SPY/AGG reference",
            worst_drawdown=f"{pct(worst[0])} ({LABELS.get(worst[1][1], worst[1][1])}, {SAMPLES[worst[1][0]].label}, "
                           "daily closes)",
            n_trials=f"{n_total} unique variants in results/trial_ledger.json ({per})",
            generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))

    def samples_txt(self) -> str:
        parts = []
        for s in SAMPLES.values():
            r = self.head[(s.name, "spy_buy_hold")].monthly_returns
            parts.append(f"{s.label} {r.index[0]:%Y-%m}..{r.index[-1]:%Y-%m}")
        return "; ".join(parts)


# ====================================================================== markdown writers
METRIC_COLS = [
    ("cagr", "CAGR", pct), ("vol", "Vol", pct), ("sharpe", "Sharpe", num), ("sortino", "Sortino", num),
    ("max_dd", "MaxDD", pct), ("dd_duration_months", "DD months", lambda x: f"{int(x)}"),
    ("calmar", "Calmar", num), ("hit_rate", "Hit rate", lambda x: pct(x, 0)),
    ("turnover_per_year", "Turnover/yr", num), ("switches_per_year", "Switches/yr", num),
    ("exposure", "Exposure", lambda x: pct(x, 0)), ("beta", "Beta", num), ("correlation", "Corr", num),
    ("tracking_error", "TE", pct), ("cagr_2x", "CAGR 2x cost", pct), ("sharpe_2x", "Sharpe 2x cost", num),
]


def metrics_table(p: Pipeline, s: Sample) -> pd.DataFrame:
    rows = {}
    for n in s.strategies:
        m = p.metrics[(s.name, n)]
        rows[LABELS[n]] = {lab: m.get(k) for k, lab, _ in METRIC_COLS}
    return pd.DataFrame(rows).T


def write_summary(p: Pipeline) -> None:
    lines = ["# Backtest summary", "", p.disclosure(p.samples_txt()), ""]
    lines += ["## Samples", "",
              "Each sample starts in cash at the close of the first signal month-end; monthly returns start the "
              "month after. Timing: signal on the last trading day's close, fill at the next day's open.", ""]
    srows = {}
    for s in SAMPLES.values():
        r = p.head[(s.name, "spy_buy_hold")].monthly_returns
        srows[s.label] = {"data": "ETF prices only" if s.data_mode == "etf" else "ETFs + validated mutual-fund proxies",
                          "first signal": s.first_signal, "returns": f"{r.index[0]:%Y-%m}..{r.index[-1]:%Y-%m}",
                          "years": f"{len(r) / 12:.1f}", "strategies": ", ".join(s.strategies)}
    lines += [md_table(pd.DataFrame(srows).T, index_label="sample"), ""]
    lines += ["Panel construction per sample:", ""]
    for s in SAMPLES.values():
        lines.append(f"- **{s.label}**: " + "; ".join(p.panels[s.name].sources.values()))
    lines += ["", "The single-asset SPY series in the long proxy sample starts in 1987 (VFINX before 1993-02): "
              "Yahoo's VFINX history before 1987 failed the Ken French cross-check (see crosscheck.md) and is not used.", ""]
    for s in SAMPLES.values():
        t = metrics_table(p, s)
        lines += [f"## Headline metrics: {s.label}", "", md_table(t, {lab: f for _, lab, f in METRIC_COLS},
                                                               index_label="strategy"), ""]
    lines += ["Column notes: CAGR/Vol/Sharpe/Sortino annualized from monthly returns (Sharpe and Sortino vs T-bills); "
              "MaxDD from daily closes; DD months = longest spell below a month-end peak; Turnover/yr = (buys + sells) / "
              "equity summed per year, excluding the initial purchase; Switches/yr = rebalances whose target weights "
              "changed; Exposure = average month-end weight in risky assets; Beta/Corr/TE vs SPY buy-and-hold.", ""]
    for sname in ("proxy", "etf", "long"):
        s = SAMPLES[sname]
        ann = pd.DataFrame({LABELS[n]: M.annual_returns(p.head[(sname, n)].monthly_returns) for n in s.strategies})
        cnt = M.months_in_year(p.head[(sname, "spy_buy_hold")].monthly_returns)
        ann.index = [f"{y}" + ("*" if cnt[y] < 12 else "") for y in ann.index]
        lines += [f"## Annual returns: {s.label}", "", "(* = partial year)", "",
                  md_table(ann, {c: pct for c in ann.columns}, index_label="year"), ""]
        ann.to_csv(p.results_dir / f"annual_returns_{sname}.csv")
    lines += ["## Regime slices", "", "Compounded return over the months listed (both ends inclusive).", ""]
    for sname in ("long", "proxy", "etf"):
        s = SAMPLES[sname]
        rt = M.regime_table({LABELS[n]: p.head[(sname, n)].monthly_returns for n in s.strategies})
        lines += [f"### {s.label}", "", md_table(rt, {c: pct for c in rt.columns if c != "months"},
                                                 index_label="regime"), ""]
    lines += ["## Post-publication split at 2006-01-01 (pre-registered: Faber's publication year)", ""]
    for sname in ("long", "proxy"):
        s = SAMPLES[sname]
        rows = {}
        for n in s.strategies:
            res = p.head[(sname, n)]
            sm = split_metrics(res.monthly_returns, res.rf_monthly, PREREGISTERED_SPLIT)
            rows[LABELS[n]] = {"pre CAGR": sm.loc["pre", "cagr"], "pre Sharpe": sm.loc["pre", "sharpe"],
                               "pre MaxDD": sm.loc["pre", "max_dd"], "post CAGR": sm.loc["post", "cagr"],
                               "post Sharpe": sm.loc["post", "sharpe"], "post MaxDD": sm.loc["post", "max_dd"]}
        t = pd.DataFrame(rows).T
        first = p.head[(sname, "spy_buy_hold")].monthly_returns.index[0]
        lines += [f"### {s.label} (pre = {first:%Y-%m}..2005-12, post = 2006-01..end; MaxDD from month-ends)", "",
                  md_table(t, {c: (num if "Sharpe" in c else pct) for c in t.columns}, index_label="strategy"), ""]
    tr = p.out["tranche"]
    lines += ["## GTAA rebalance-day luck (tranching)", "",
              "Same rule (10-month SMA), signal evaluated on each trading-day offset 0..20 of the month. "
              "'Tranched' runs 21 sub-accounts of $10,000/21, each on its own day. Details in plateau.md.", "",
              md_table(tr.set_index(["sample", "strategy"]),
                       {"month_end_cagr": pct, "min_cagr": pct, "max_cagr": pct, "spread_bp": integer,
                        "std_bp": integer, "best_day": integer, "worst_day": integer, "tranched_cagr": pct,
                        "tranched_sharpe": num, "tranched_max_dd": pct}, index_label="sample / strategy"), ""]
    g = p.out["gates"].set_index(["sample", "candidate"])
    fm = {c: yesno for c in g.columns if c.startswith("A")}
    fm.update({"wf_sharpe": num, "dsr": num, "pbo": num, "plateau": num})
    lines += ["## Gate A scorecard (pre-registered in docs/research-report.md section 12)", "",
              "A candidate may be paper-traded only if it passes every row. Definitions are in docs/methodology.md.",
              "", md_table(g, fm, index_label="sample / candidate"), ""]
    lines += ["## Charts", ""]
    for sname in ("long", "proxy", "etf"):
        lines.append(f"![{SAMPLES[sname].label}](equity_{sname}.png)")
    lines += ["", "## Other result files", "",
              "scaling.md, plateau.md, walkforward.md, bootstrap.md, dsr_pbo.md, leakage.md, crosscheck.md, "
              "trial_ledger.json, metrics_*.csv, annual_returns_*.csv, data_manifest.json.", ""]
    p.write("summary.md", "\n".join(lines))
    for s in SAMPLES.values():
        pd.DataFrame({n: p.metrics[(s.name, n)] for n in s.strategies}).T.to_csv(p.results_dir / f"metrics_{s.name}.csv")
        groups = {"": list(s.strategies)}
        series = {n: p.head[(s.name, n)].monthly_returns for n in groups[""]}
        charts.equity_and_drawdown(series, p.results_dir / f"equity_{s.name}.png",
                                   f"{s.label}: growth of $1 and drawdown (hypothetical, net of gate costs)", LABELS)


def write_scaling(p: Pipeline) -> None:
    df = p.out["scaling"]
    r_etf = p.head[("etf", "spy_buy_hold")].monthly_returns
    lines = ["# Capital scaling: $1 to $100,000 with the Alpaca fee model", "", p.disclosure(
        f"{SAMPLES['etf'].label} {r_etf.index[0]:%Y-%m}..{r_etf.index[-1]:%Y-%m}"), "",
        "Cost tier here is **modelled** (per-instrument half-spread from the universe table, no 5 bp floor) plus "
        "Alpaca SEC/TAF/CAT fees rounded up to the cent per fee type per day, and Alpaca's $1 minimum notional: "
        "orders below $1 are skipped (and logged). Whole-share mode rounds each target position down to whole "
        "shares at the as-traded price; the remainder stays in cash earning T-bills.", ""]
    for name in SAMPLES["etf"].strategies:
        t = df[df["strategy"] == name].copy()
        t.index = [f"${c:,.0f} {sh}" for c, sh in zip(t["capital"], t["shares"])]
        t = t.drop(columns=["strategy", "capital", "shares"])
        lines += [f"## {LABELS[name]}", "", md_table(t, {
            "cagr": pct, "final_value": money, "fees": money, "fees_pct_per_year": lambda x: pct(x, 2),
            "spread_cost": money, "orders": lambda x: f"{int(x)}", "skipped_below_1": lambda x: f"{int(x)}",
            "avg_cash": lambda x: pct(x, 0), "sharpe": num}, index_label="capital / shares"), ""]
    lines += ["## Largest orders skipped below the $1 minimum ($1 and $100 accounts, fractional)", ""]
    for name, parts in p.out["scaling_skips"].items():
        sk = pd.concat(parts)
        sk["notional"] = sk["notional"].map(lambda x: f"${x:.2f}")
        for c in ("exec_date", "signal_date"):
            sk[c] = pd.to_datetime(sk[c]).dt.strftime("%Y-%m-%d")
        lines += [f"**{LABELS[name]}**", "", md_table(sk.reset_index(drop=True), index=False), ""]
    notes = ["## Reading this (numbers taken from the tables above)", ""]
    for name in SAMPLES["etf"].strategies:
        t = df[(df["strategy"] == name) & (df["shares"] == "fractional")].set_index("capital")
        w = df[(df["strategy"] == name) & (df["shares"] == "whole")].set_index("capital")
        notes.append(
            f"- **{LABELS[name]}**: CAGR {pct(t.loc[1.0, 'cagr'])} at $1, {pct(t.loc[100.0, 'cagr'])} at $100, "
            f"{pct(t.loc[10_000.0, 'cagr'])} at $10,000 (fractional); fees {pct(t.loc[1.0, 'fees_pct_per_year'], 2)} "
            f"of average equity per year at $1 vs {pct(t.loc[10_000.0, 'fees_pct_per_year'], 3)} at $10,000; "
            f"{int(t.loc[1.0, 'orders'])} orders placed and {int(t.loc[1.0, 'skipped_below_1'])} skipped at $1; "
            f"whole shares at $100: CAGR {pct(w.loc[100.0, 'cagr'])} with {pct(w.loc[100.0, 'avg_cash'], 0)} "
            "average cash.")
    notes += ["",
              "- Alpaca rounds each fee type up to $0.01 per day, so a $1 round trip costs $0.04 (4%); the fee floor "
              "stops mattering in the hundreds of dollars.",
              "- Any order below $1 is skipped: multi-sleeve rules at $1 (20% sleeves = $0.20) can never trade, and a "
              "$1 account that falls below $1 of cash cannot re-enter.",
              "- Whole-share accounts smaller than one share price (SPY traded at roughly $70-$690 in this sample) sit "
              "in cash; small whole-share results depend on when the account happened to afford a share.",
              "- Fractional-share dividends at Alpaca are rounded to the cent (a $1 SPY position receives $0.00); the "
              "engine's adjusted-price accounting reinvests them exactly, so the $1-$100 rows are optimistic.",
              "- Negative average cash (e.g. -1%) is the cent-level fee debit left after a fully invested account "
              "buys; it is too small to trade back (below $1).", ""]
    lines += notes
    p.write("scaling.md", "\n".join(lines))
    df.to_csv(p.results_dir / "scaling.csv", index=False)


def write_plateau(p: Pipeline) -> None:
    lines = ["# Parameter plateaus and rebalance-day dispersion", "", p.disclosure(p.samples_txt()), "",
             "Plateau statistic: worst Sharpe among lookbacks within +-25% of the default, divided by the default's "
             "Sharpe (Gate A.5 needs >= 0.70). All runs: gate cost tier, $10,000, next-open fills.", ""]
    pl = p.out["plateau"].copy()
    pl["neighbors"] = pl["neighbors"].map(lambda x: ",".join(str(int(v)) for v in x))
    lines += [md_table(pl.set_index(["sample", "family"]), {"center_sharpe": num, "min_retained": num,
                                                           "mean_retained": num}, index_label="sample / family"), ""]
    for s in SAMPLES.values():
        sh, dd, cg = p.out[("plateau_trend", s.name)]
        lines += [f"## SPY trend rules, {s.label}", "", "Sharpe by lookback (months):", "",
                  md_table(sh, {c: num for c in sh.columns}, index_label="rule"), "", "Max drawdown:", "",
                  md_table(dd, {c: lambda x: pct(x, 0) for c in dd.columns}, index_label="rule"), "",
                  "CAGR:", "", md_table(cg, {c: pct for c in cg.columns}, index_label="rule"), "",
                  f"![Sharpe](plateau_trend_{s.name}_sharpe.png) ![MaxDD](plateau_trend_{s.name}_maxdd.png)", ""]
    for sname, fam in (("proxy", "gtaa4"), ("etf", "gtaa5"), ("etf", "gtaa4")):
        t = p.out[("plateau_gtaa", sname, fam)].T
        t.columns.name = "lookback"
        lines += [f"## {LABELS[fam]}, {SAMPLES[sname].label}: by lookback (month-end signal)", "",
                  md_table(t, {c: num for c in t.columns}, index_label="metric"), ""]
    hm = p.out[("plateau_gtaa_grid", "proxy", "gtaa4")]
    lines += ["## GTAA-4, proxy sample: Sharpe by lookback x signal day", "",
              "Rows = SMA lookback; columns = month-end ('me') or the k-th trading day of the month ('oK').", "",
              md_table(hm, {c: num for c in hm.columns}, index_label="lookback"), "",
              "![GTAA-4 grid](plateau_gtaa4_proxy_lookback_x_day.png)", ""]
    lines += ["## Rebalance-day dispersion (L = 10)", ""]
    for (sname, fam), (by_off, sr_off, tr_cagr) in p.out["tranche_detail"].items():
        t = pd.DataFrame({"CAGR": by_off, "Sharpe": sr_off}).T
        lines += [f"### {LABELS[fam]}, {SAMPLES[sname].label} (tranched CAGR {pct(tr_cagr, 2)})", "",
                  md_table(t, {c: (lambda x: f"{x * 100:.2f}%" if abs(x) < 1 and x != 0 else num(x)) for c in t.columns},
                           index_label="signal day"), "", f"![tranche](tranche_{fam}_{sname}.png)", ""]
    p.write("plateau.md", "\n".join(lines))


def write_walkforward(p: Pipeline) -> None:
    wf = p.out["wf"].set_index(["sample", "family"])
    lines = ["# Walk-forward and out-of-sample tests", "", p.disclosure(p.samples_txt()), "",
             "Expanding window: after 60 months, each year pick the lookback with the best in-sample Sharpe (vs T-bills) "
             "and trade it for the next 12 months; concatenate. 'default' = the pre-registered published lookback over "
             "the same out-of-sample months; 'bh' = SPY buy-and-hold over the same months. Switching cost between "
             "variants at the yearly boundary is not charged (at most one extra switch a year).", "",
             md_table(wf, {c: (num if "sharpe" in c else pct) for c in wf.columns if c not in ("variants", "oos_first",
                                                                                              "oos_months")},
                      index_label="sample / family"), ""]
    for (sname, fam), ch in p.out["wf_choices"].items():
        c = ch.copy()
        c["train_sharpe"] = c["train_sharpe"].map(num)
        lines += [f"### Chosen variant per year: {fam}, {SAMPLES[sname].label}", "",
                  md_table(c[["test_start", "test_end", "chosen", "train_sharpe"]], index=False), ""]
    lines += ["## Pre-registered split at 2006-01-01", "", "See summary.md, section 'Post-publication split'.", ""]
    p.write("walkforward.md", "\n".join(lines))


def write_bootstrap(p: Pipeline) -> None:
    lines = ["# Stationary block bootstrap", "", p.disclosure(p.samples_txt()), "",
             f"Politis-Romano stationary bootstrap of monthly returns: mean block {BOOT_BLOCK:g} months, "
             f"{BOOT_PATHS} paths, seed {BOOT_SEED}; strategy, SPY and T-bill months are resampled jointly. "
             "Drawdown columns are percentiles of drawdown magnitude (p95 = a bad tail).", ""]
    for sname, t in p.out["boot"].items():
        t = t.copy()
        t.index = [LABELS[i] for i in t.index]
        lines += [f"## {SAMPLES[sname].label}", "", md_table(t, {c: (num if "sharpe" in c else pct) for c in t.columns},
                                                           index_label="strategy"), ""]
        t.to_csv(p.results_dir / f"bootstrap_{sname}.csv")
    p.write("bootstrap.md", "\n".join(lines))


def write_dsr_pbo(p: Pipeline) -> None:
    d = p.out["dsr"].copy()
    d["strategy"] = d["strategy"].map(LABELS)
    lines = ["# Deflated Sharpe ratio and probability of backtest overfitting", "", p.disclosure(p.samples_txt()), "",
             "**Deflated Sharpe ratio** (Bailey & Lopez de Prado 2014): probability that the true Sharpe exceeds the "
             "Sharpe the best of N zero-skill trials would show by luck, E[max SR] = sqrt(V) * ((1-g) Z^-1(1-1/N) + "
             "g Z^-1(1-1/(N e))), with V the empirical cross-trial variance of Sharpe ratios in the trial ledger and "
             "skew/kurtosis of the candidate's monthly excess returns (T-1 in the square root; per-month units inside, "
             "annualized here for reading). 'all' uses every trial on that sample in the ledger (conservative); "
             "'family' only that strategy family's trials. psr_0 = probability the true Sharpe is above zero with no "
             "multiple-testing correction. The implementation reproduces the paper's worked example (0.9004 for "
             "N=100; 0.9505 for N=46) in tests/test_validation_dsr.py.", "",
             f"Trial ledger: {p.ledger.n_trials()} unique variants in total; per sample: "
             + ", ".join(f"{s} {p.ledger.n_trials(s)}" for s in SAMPLES) + ".", "",
             md_table(d.set_index(["sample", "strategy"]), {
                 "t_months": lambda x: f"{int(x)}", "sr_annual": num, "skew": num, "kurtosis": num,
                 "n_all": lambda x: f"{int(x)}", "sd_sr_all_annual": num, "sr0_all_annual": num, "dsr_all": num,
                 "n_family": lambda x: f"{int(x)}", "sr0_family_annual": num, "dsr_family": num, "psr_0": num},
                 index_label="sample / strategy"), ""]
    pb = p.out["pbo"].set_index(["sample", "grid"])
    lines += ["## Probability of backtest overfitting (CSCV)", "",
              "S = 16 contiguous blocks of monthly excess returns (the earliest T mod 16 months dropped), all "
              "C(16,8) = 12,870 in-sample/out-of-sample splits (no sampling), performance = Sharpe. PBO = share of "
              "splits where the in-sample best configuration ranks at or below the out-of-sample median. Grids: "
              "'trend' = SMA and absolute momentum, lookbacks 3..18 (32 configurations); 'gtaa4' in the proxy sample = "
              "lookbacks 3..18 x 22 signal days (352); ETF-sample GTAA grids = lookbacks 3..18 at month-end plus 21 "
              "signal days at L=10 (37). Gate A.4 needs PBO <= 0.2.", "",
              md_table(pb, {"pbo": num, "prob_oos_loss": num, "is_oos_slope": num, "median_logit": num,
                            "n_splits": integer, "s_blocks": integer, "n_configs": integer, "t_used": integer},
                       index_label="sample / grid"), ""]
    p.write("dsr_pbo.md", "\n".join(lines))
    p.out["dsr"].to_csv(p.results_dir / "dsr.csv", index=False)
    p.out["pbo"].to_csv(p.results_dir / "pbo.csv", index=False)


def _kv(d: dict) -> str:
    rows = {k: (num(v, 4) if isinstance(v, float) else str(v)) for k, v in d.items() if not isinstance(v, (pd.Series,
                                                                                                           pd.DataFrame))}
    return md_table(pd.DataFrame({"value": rows}), index_label="item")


def write_leakage(p: Pipeline) -> None:
    o = p.out["leak"]
    lines = ["# Structural leakage tests", "", p.disclosure(p.samples_txt()), "",
             "Look-ahead cannot be detected by statistics (a leaky oracle can pass DSR and PBO); these tests check the "
             "engine's timing directly. `same_bar_fill` exists only inside validation/leakage.py; no CLI can set it, "
             "and the ledger and report writers refuse its results.", "",
             "## (a) Identity: SPY buy-and-hold through the engine = SPY total-return series", "",
             "Zero costs; first month excluded (the engine buys at the next open). Pass: |difference| <= 1 bp/yr.", "",
             "### SPY ETF prices", "", _kv(o["identity_etf"]), "",
             "### SPY spliced with VFINX (long proxy sample)", "", _kv(o["identity_proxy"]), "",
             "## (b) Perfect foresight of the next bar, monthly bars, fill at the next close", "",
             "The oracle is told sign(close[t+1]/close[t] - 1) at bar t. Through the normal path its order fills at "
             "close[t+1], after the foreseen move; only a forced same-bar fill lets it trade the move. Pass: lagged "
             "Sharpe within 3 standard errors of 0 and alpha |t| < 3; same-bar Sharpe > 10 SE and alpha t > 10.", "",
             "### Synthetic zero-drift geometric random walk (600 months, seed 7)", "", _kv(o["foresight_synthetic"]), "",
             "### Real SPY month-end closes (1993-2026; cash earns 0 here)", "",
             "On real data the drift makes Sharpe non-zero for any half-invested strategy, so the criterion is the "
             "alpha t-statistic versus SPY.", "", _kv(o["foresight_real"]), "",
             "## (c) Foresight of the overnight gap, daily bars, default next-open fill", "",
             "The oracle is told sign(open[t+1]/close[t] - 1) at each month-end. The normal path fills at open[t+1] "
             "and cannot capture the gap. Pass: lagged alpha |t| < 3; same-bar alpha t > 4.", "",
             "### Synthetic daily walk with 2% overnight gaps (150 years, seed 11)", "", _kv(o["gap_synthetic"]), "",
             "### Real SPY daily bars", "", _kv(o["gap_real"]), "",
             "Real SPY month-end overnight gaps are small (tens of bp) relative to a month's variance, so even a "
             "same-bar fill that captures them earns only a statistically weak edge here (low power); the "
             "synthetic test above, with large gaps, is the proof. The point on real data is the lagged row: no gap "
             "is captured through the normal path.", "",
             "## (d) One-day execution delay (Gate A.8 sensitivity)", "",
             f"Each candidate re-run with fills one extra trading day later. A slow monthly rule should barely move; "
             f"pass if |change in Sharpe| <= {SHIFT_TOL}.", "",
             md_table(o["shift"].set_index(["sample", "strategy"]), {"sharpe": num, "sharpe_shift1": num,
                                                                     "delta_sharpe": num, "cagr": pct,
                                                                     "cagr_shift1": pct},
                      index_label="sample / strategy"), ""]
    p.write("leakage.md", "\n".join(lines))


def write_crosscheck(p: Pipeline) -> None:
    o = p.out["xc"]
    bt_ = o["bt"].copy()
    lines = ["# Independent cross-checks", "", p.disclosure(p.samples_txt()), "",
             "## 1. bt 1.2.3 vs this engine (buy-and-hold SPY and SPY 10-month SMA)", "",
             "bt: RunMonthly on the first trading day of each month, SelectWhere on an independently computed daily SMA "
             "signal lagged one row, WeighEqually, Rebalance, zero commissions, fractional positions. Engine: "
             "next-close fill mode, zero costs, zero cash yield. Pre-registered tolerance: max |monthly return "
             "difference| <= 1 bp. The run_on_end_of_period=True variant trades one day earlier on both signal and fill "
             "(bt cannot express 'signal at the close, fill next day' that way); it is shown for information and not "
             "gated.", "",
             md_table(bt_, {"max_abs_diff_bp": lambda x: f"{x:.2e}", "mean_abs_diff_bp": lambda x: f"{x:.2e}",
                            "engine_cagr": lambda x: pct(x, 3), "bt_cagr": lambda x: pct(x, 3),
                            "passed": lambda x: "n/a (info)" if x is None or (isinstance(x, float) and math.isnan(x))
                            else yesno(x)}, index=False), ""]
    gated = bt_[bt_["gated"]]
    lines += [f"**Result: {'PASS' if bool(gated['passed'].all()) else 'FAIL'}** (gated rows).", ""]
    lines += ["## 2. Ken French: SPY vs the CRSP market (Mkt-RF + RF)", "",
              f"Pre-registered: correlation >= {X.FF_MIN_CORR} and |CAGR difference| <= {X.FF_MAX_CAGR_DIFF * 1e4:.0f} bp/yr.", ""]
    for key, label in (("ff_spy_etf", "SPY ETF prices"), ("ff_spy_long", "SPY with VFINX before 1993-02 (from 1987)")):
        d = {k: v for k, v in o[key].items() if k not in ("annual", "worst_months")}
        lines += [f"### {label}", "", _kv(d), "",
                  f"**Correlation: {yesno(d['passed_corr'])}; CAGR difference: {yesno(d['passed_cagr'])}.**", ""]
    worst = o["ff_spy_etf"]["worst_months"]
    lines += ["### Diagnosis", "",
              "The S&P 500 is a large-cap subset of the CRSP total market, so their monthly correlation is below 1 by "
              "construction; the largest monthly gaps (SPY minus market) are "
              + ", ".join(f"{k} ({v * 1e4:+.0f} bp)" for k, v in worst.items())
              + ". Total-market funds from the "
              "same vendor pass easily, which shows the data pipeline and monthly sampling are sound and that the 0.99 "
              "threshold is tighter than the S&P 500 / total-market relationship allows:", ""]
    diag_rows = {k: {kk: v[kk] for kk in ("first_month", "months", "correlation", "cagr_diff_bp", "passed_corr",
                                           "passed_cagr")} for k, v in o["ff_diag"].items()}
    lines += [md_table(pd.DataFrame(diag_rows).T, {"correlation": lambda x: num(x, 4), "cagr_diff_bp": bp,
                                                    "passed_corr": yesno, "passed_cagr": yesno}, index_label="series"),
              "", "The full Yahoo VFINX history fails badly. Per calendar year versus the market (VFINX minus Mkt, bp):", ""]
    ann = o["ff_diag"]["VFINX (all Yahoo history)"]["annual"]
    early = (ann[ann.index <= 1992] * 1e4).round(0).to_frame("VFINX - Mkt (bp)")
    lines += [md_table(early, {"VFINX - Mkt (bp)": lambda x: f"{x:.0f}"}, index_label="year"), "",
              "In 1981-1986 VFINX trails by 2-10 percentage points a year; against commonly published S&P 500 total "
              "returns the Yahoo series is 2.3-9.4 pp/yr short in those years (for example 1985: 22.6% vs 31.7%), "
              "consistent with missing capital-gain distributions (dividends are present, so the quality gates did not "
              "catch it). From 1987 the gap is fund-like. **Action taken:** VFINX rows before 1987-01-01 are dropped "
              "(`valid_from` in src/stocktry/data/universe.py) and the long sample starts in 1988-07. The tolerance "
              "was not changed.", ""]
    rf = {k: v for k, v in o["rf"].items() if k != "diff"}
    lines += ["## 3. Ken French: our T-bill series vs French RF (from 1990)", "",
              "Pre-registered: every month within 10 bp.", "", _kv(rf), "",
              f"**Result: {yesno(rf['passed'])}** ({rf['months_over_10bp']} of {rf['months']} months above 10 bp; "
              f"mean difference {rf['mean_diff_bp']:.2f} bp/month).", "",
              "Exception months (every month above 10 bp):", ""]
    y = fetch.get_tbill_yield()
    exc = {}
    d = o["rf"]["diff"]
    ffrf = p.ff["RF"].copy()
    ffrf.index = ffrf.index.to_period("M")
    for per in d[d.abs() > X.RF_MAX_DIFF + 1e-12].index:
        ym = y[y.index.to_period("M") == per]
        exc[str(per)] = {"ours - French (bp)": d[per] * 1e4, "French RF (bp)": ffrf[per] * 1e4,
                         "DTB3 first day (%)": ym.iloc[0], "DTB3 last day (%)": ym.iloc[-1]}
    if exc:
        lines += [md_table(pd.DataFrame(exc).T, {c: (lambda x: f"{x:.1f}") for c in
                                                 ("ours - French (bp)", "French RF (bp)")} |
                           {c: (lambda x: f"{x:.2f}") for c in ("DTB3 first day (%)", "DTB3 last day (%)")},
                           index_label="month"), ""]
    lines += ["Diagnosis: French RF is the one-month holding-period return of a 1-month bill bought at the start of "
              "the month, so its yield is locked in for the month; our cash accrues daily at the prevailing 3-month "
              "rate (DTB3). In the exception months DTB3 fell within the month, as the table shows"
              + (" (the Fed's 2001-01-03 inter-meeting cut and 2001-09-17 post-9/11 cut)"
                 if set(exc) == {"2001-01", "2001-09"} else "")
              + ", while the locked-in 1-month return did not. The average difference is a fraction of a basis "
              "point per month, so Sharpe ratios and cash returns are unaffected in any material way; the tolerance "
              "was not changed.", ""]
    p.write("crosscheck.md", "\n".join(lines))
    o["bt"].to_csv(p.results_dir / "crosscheck_bt.csv", index=False)


def write_manifest(p: Pipeline) -> None:
    man = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "symbols": {}, "splices": {},
           "samples": {}, "note": "Vendor price data is cached under data/ (gitignored) and never committed."}
    for sym in UNIVERSE:
        try:
            m = fetch.read_manifest(sym)
            man["symbols"][sym] = {k: m.get(k) for k in ("source", "retrieved_utc", "sha256", "first_date", "last_date",
                                                          "rows", "dividend_events", "splits")}
            man["symbols"][sym]["valid_from"] = UNIVERSE[sym].valid_from
        except Exception:  # noqa: BLE001 - a symbol not needed by any sample may be absent
            continue
    for s in SAMPLES.values():
        man["samples"][s.name] = {"sources": p.panels[s.name].sources, "splices": p.panels[s.name].splices,
                                  "first_signal": s.first_signal}
        man["splices"].update(p.panels[s.name].splices)
    man["splice_rules"] = {k: {"proxy": r.proxy, "enabled": r.enabled, "min_corr": r.min_corr, "reason": r.reason}
                           for k, r in SPLICES.items()}
    for name in ("DTB3", "FF_FACTORS"):
        try:
            man[name] = fetch.read_manifest(name)
        except Exception:  # noqa: BLE001
            pass
    (p.results_dir / "data_manifest.json").write_text(json.dumps(man, indent=1, default=str))


def main(results_dir: Path, ledger_path: Path | None = None) -> Pipeline:
    results_dir.mkdir(parents=True, exist_ok=True)
    p = Pipeline(results_dir, TrialLedger(ledger_path or results_dir / "trial_ledger.json"))
    p.load()
    p.headline()
    p.sweeps()
    p.tranching()
    p.walkforward()
    p.plateau()
    p.pbo()
    p.bootstrap()
    p.dsr()
    p.leakage()
    p.crosschecks()
    p.scaling()
    p.gates()
    write_summary(p)
    write_scaling(p)
    write_plateau(p)
    write_walkforward(p)
    write_bootstrap(p)
    write_dsr_pbo(p)
    write_leakage(p)
    write_crosscheck(p)
    write_manifest(p)
    p.log("all results written")
    return p


__all__ = ["main", "Pipeline"]
