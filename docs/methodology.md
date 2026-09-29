# Methodology

How the backtests in `results/` are produced, what every test does, and how to read the output. The rationale
(what the evidence supports and the pre-registered gates) is in `docs/research-report.md`. Everything described
here is deterministic Python: no language model is called anywhere at runtime.

## 1. Data

**Sources.** Daily bars come from `yfinance` (`Ticker.history(period="max", auto_adjust=False, actions=True)`),
falling back to the raw Yahoo v8 chart API (browser User-Agent, `period1=0&period2=now`, never `range=max`),
falling back to the last good cache file (with a warning). Cash yields are FRED `DTB3` (3-month T-bill, percent,
discount basis) from the keyless `fredgraph.csv` endpoint. The Ken French monthly factors (keyless zip) are used
only for cross-checks. Vendor data is personal-use research data: it is cached under `data/` (gitignored) and never
committed. `results/data_manifest.json` records each series' source, retrieval time, sha256, date range and splice
decisions (hashes only, no prices).

**Adjustment.** `close` is the vendor's adjusted close (splits and distributions reinvested); `open`, `high`, `low`
are multiplied by the same factor `Adj Close / Close`, so all four are on one total-return scale. `close_raw` is the
as-traded close and `dividend` the cash distribution on its ex-date. Each symbol is cached as one CSV plus a
manifest (source, retrieved_utc, sha256 of the file, first/last date, rows, split dates); a cache file whose hash no
longer matches its manifest is refused.

**Quality gates** (`stocktry.data.quality`; any failure raises and stops the backtest):

| check | rule |
|---|---|
| rows | at least 20 |
| dates | strictly increasing |
| prices | open/high/low/close/close_raw all positive and finite |
| jumps | no \|daily as-traded return\| > 50% unless the date carries a split flag |
| stale prices | no run of 5+ identical consecutive closes on an equity, international-equity or REIT fund |
| spacing | median gap between bars at most 1 business day |
| dividends | a regular payer has at least one distribution in every full calendar year |
| TR vs PR | per full year, total return minus price return within a band per asset class (e.g. equity -0.25%..10%, bonds -0.25%..16%); regular payers at least +0.10% |

All 17 universe series pass. The gates do **not** catch every vendor error: see the VFINX case below.

**Splicing** (`stocktry.data.universe`). An ETF's pre-inception history may be extended with a Vanguard
mutual-fund proxy *on returns*, at a month boundary: daily proxy returns are used up to and including the ETF's
first month-end, ETF returns afterwards. Each proxy daily return gets `(ER_proxy - ER_target) / 252` added, so a
21-day month carries the specification's `(ER_proxy - ER_target) / 12`. A splice is accepted only if the monthly
returns overlap for at least 36 months with correlation at least 0.995 (equity, REIT) or 0.95 (bonds), measured over
the whole overlap. Accepted: SPY<-VFINX (0.9984), VTI<-VTSMX, IEF<-VFITX (0.9822), AGG<-VBMFX (0.9777),
BND<-VBMFX, VNQ<-VGSIX (0.9994). Never spliced: EFA (VGTSX correlation 0.9845 < 0.995) and DBC (no proxy).
In the proxy sample the international sleeve uses VGTSX's own history for the whole period (a real fund, a
substitution rather than a splice). Run `scripts/fetch_data.py` to print the table.

**Excluded data.** The Ken French cross-check showed Yahoo's VFINX total return is 2.3 to 9.4 percentage points a
year short of the S&P 500 in 1981-1986 (for example 22.6% vs 31.7% in 1985), consistent with missing capital-gain
distributions. VFINX rows before 1987-01-01 are therefore dropped (`SymbolMeta.valid_from`).

**Samples** (`stocktry.backtest.samples`). Each starts in cash at the close of its first signal month-end; monthly
returns start the next month and end at the last month complete for every series (2026-08 at the time of writing).

| sample | data | first signal | strategies |
|---|---|---|---|
| long | SPY (VFINX before 1993-02), AGG (VBMFX before 2003-10) | 1988-07 (all 3..18-month lookbacks formed from 1987+ data) | single-asset rules, 60/40 |
| proxy | adds VGTSX (for EFA), IEF (VFITX), VNQ (VGSIX) | 1996-05 (REIT and international funds exist) | + GTAA-4 |
| etf | ETF prices only | 2006-02 (DBC's first month-end) | + GTAA-5 |

A GTAA sleeve whose series is too short for its SMA holds cash until the SMA is formed (REIT and international
sleeves until 1997-02 in the proxy sample; DBC until 2006-11 in the ETF sample).

## 2. Timing conventions

* **Signal**: computed on the last trading day of each month using data up to and including that day's close.
  The engine passes the strategy a frame truncated at that row (`iloc[:i+1]`); strategies also drop any row after
  `asof` defensively, and a test tampers with future rows to prove they are ignored.
* **Execution**: the next trading day at its adjusted **open** (default) or adjusted **close** (`fill="next_close"`).
  `extra_lag_days` delays execution further (one-bar-shift test).
* **Same-bar fill** (`same_bar_fill=True`) fills at the signal bar's own close: that is look-ahead, and it exists only
  for the leakage tests. No command-line option can set it; results are flagged `leaky`, and the trial ledger refuses
  them.
* **Monthly anchors** (`stocktry.backtest.schedule`): offset -1 is the last trading day of the month; offset k >= 0 is
  the k-th trading day of the month (0-based, clamped to the last). Monthly lookbacks (SMA, momentum) are sampled at the
  same anchors. Both rules are causal (tested): on data truncated at an anchor they reproduce the full-data anchors up
  to that date.
* **Tranching**: GTAA is also run with the signal on each offset 0..20, and as a "tranched" portfolio of 21
  sub-accounts of 1/21 of the capital, each trading on its own day.

## 3. Accounting

* Holdings are units of the **adjusted** price series, so distributions are reinvested; the SPY benchmark runs through
  the same engine on the same adjusted series, so strategy and benchmark are both total return.
* Order sizes use **as-traded** prices (`close_raw / close` converts adjusted to as-traded dollars; 1.0 inside spliced
  proxy segments). Sells are quantity orders (fractional shares truncated to 9 decimals). Buys are dollar-notional orders,
  rounded down to the cent, that pay the ask (mid x (1 + half-spread)); the spread shows up as fewer units. Sells run
  first; if buys exceed the cash, all buys are scaled down pro rata.
* `whole_shares=True` rounds each target position **down** to whole as-traded shares; the rest stays in cash. Dividends
  between rebalances are still reinvested by the adjusted-price accounting (slightly flattering whole-share runs).
* **Cash** earns the T-bill daily accrual: on each trading day the balance grows by `DTB3(previous trading day) / 100 / 252`
  (FRED holidays forward-filled). The same T-bill index gives the monthly risk-free returns used in Sharpe ratios and
  the absolute-momentum hurdle. The discount basis slightly understates the investment yield and daily compounding
  slightly overstates it; the Ken French RF check measures the net (+0.3 bp a month on average since 1990).
* With a `cash_symbol` (e.g. BIL) the unallocated weight is bought as that ETF when it has a price (residual cash still
  earns T-bills). All registered strategies use `cash_symbol=None` (T-bill cash).
* Fund expense ratios are already inside fund prices and are never charged again. A series flagged `is_index_level`
  (none in the current universe) would lose `ER / 252` per day.

## 4. Cost model (`stocktry.backtest.costs`)

* **Spread**: per-instrument half-spread (bp per side): SPY 0.5, VTI 1.0, IEF 1.0, AGG 1.5, BND 1.5, VNQ 1.5, GLD 1.5,
  EFA 1.5, DBC 3.0, BIL 0.5, SHV 0.5; mutual-fund proxies 0.
* **Tiers**: `modelled` = the table; `gate` = the table floored at 5 bp per side (Gate A.2's minimum; the headline tier);
  `gate_x2` = twice the gate spreads and fee rates. `zero` is used only for identity and cross-checks.
* **Alpaca regulatory fees** (fee schedule rev. 2026-09-17), dated tables:
  SEC $27.80 per $1M of sell notional before 2025-05-14, $0 from 2025-05-14, $20.60 from 2026-04-04 (earlier history
  uses $27.80); FINRA TAF $0.000195 per sold share, capped at $9.79 per order (the Oct-Dec 2026 $0 pause is available
  but OFF by default because Alpaca's pass-through is unverified); CAT $0.000003 per share on buys and sells. Each fee
  type is summed over the account's orders for the day and rounded **up** to the cent. Examples (tested): a $1 round
  trip on separate days costs $0.04; a $10,000 sell of 20 shares costs SEC $0.21 + TAF $0.01 + CAT $0.01; two $1 sells
  on the same day share one cent per fee type.
* **Commissions** for other brokers: per order `max(flat + bps x notional, minimum)`; zero by default.
* **$1 minimum**: orders below $1 are skipped and logged, except a sell that closes the whole position (modelled as the
  broker's close-position request; that the minimum does not apply to it is an assumption).
* The same rule is simulated at $1, $100, $1,000, $10,000 and $100,000 (`results/scaling.md`).
* **Not modelled**: taxes, market impact (negligible for these ETFs at these sizes), dividend withholding, the rounding
  of fractional dividends to the cent, commissions of the pre-2019 era, and historical SEC/TAF rates.

## 5. Metrics (`stocktry.backtest.metrics`)

Annualized from monthly returns: CAGR = prod(1 + r)^(12/n) - 1; volatility = sample standard deviation x sqrt(12);
Sharpe = mean(r - rf) / sd(r - rf) x sqrt(12) against T-bills; Sortino uses the root mean square of negative excess
returns over all months. Max drawdown is taken from daily closes (deeper than month-end); duration is the longest spell
in months below a month-end peak. Calmar = CAGR / |MaxDD|. Beta, correlation and tracking error are against SPY
buy-and-hold. Turnover per year = (buys + sells) / equity summed per year, excluding the initial purchase. Switches per
year = rebalances whose target weights changed. Regime slices compound the named months, both ends inclusive. Every
formula is unit-tested against hand-computed numbers (`tests/test_backtest_metrics.py`).

## 6. Validation suite (`stocktry.validation`)

* **Walk-forward** (`walkforward.py`): expanding window, 60-month minimum, yearly re-selection of the lookback with the
  best in-sample Sharpe, traded for the next 12 months. Variant returns are pre-computed by the engine (each depends only
  on data before its month), so the selection is causal; the one-off cost of switching variants at a yearly boundary is
  not charged.
* **Pre-registered split** at 2006-01-01 (Faber's publication year): pre and post metrics in `summary.md`.
* **Plateau** (`plateau.py`): Sharpe and MaxDD over lookbacks 3..18 for each rule, and GTAA-4 over lookback x signal day.
  Statistic = worst Sharpe among lookbacks within +-25% of the default, divided by the default's Sharpe.
* **Bootstrap** (`bootstrap.py`): Politis-Romano stationary bootstrap, mean block 6 months, 2,000 paths, seed 20260929,
  strategy / SPY / T-bill months resampled jointly; 5th, 50th and 95th percentiles of CAGR, Sharpe and drawdown magnitude.
* **Trial ledger** (`ledger.py`, `results/trial_ledger.json`): every backtest variant run by `run_backtests.py`
  (strategy family, parameters, sample, and per configuration T, Sharpe, skew, kurtosis, CAGR, MaxDD, timestamps).
  Trials are keyed by family + parameters + sample and are never removed; re-runs only update them.
* **Deflated Sharpe ratio** (`dsr.py`): Bailey & Lopez de Prado (2014) with the empirical cross-trial variance of Sharpe
  ratios from the ledger, per-period units, skew/kurtosis adjustment, T - 1 in the square root. It reproduces the paper's
  worked example exactly (DSR 0.9004 with N = 100, 0.9505 with N = 46; `tests/test_validation_dsr.py`). Reported with N =
  all trials on the sample (used for the gate) and N = the strategy's own family.
* **PBO** (`pbo.py`): CSCV with S = 16 blocks and all 12,870 splits (vectorized, no sampling), Sharpe as the performance
  measure. Grids: SPY trend (SMA and absolute momentum, lookbacks 3..18: 32 configurations), GTAA-4 in the proxy sample
  (16 lookbacks x 22 signal days: 352), GTAA in the ETF sample (16 lookbacks + 21 signal days: 37).
* **Leakage** (`leakage.py`): (a) identity: SPY buy-and-hold through the engine at zero cost equals the SPY total-return
  series within 1 bp/yr; (b) perfect foresight of the next monthly bar: with the engine's lag the oracle's Sharpe is
  within 3 standard errors of zero on a zero-drift random walk (alpha |t| < 3 on real SPY), and only a forced same-bar
  fill makes it "huge" (> 10 standard errors, alpha t > 10); (c) foresight of the overnight gap under the default
  next-open fill: never captured through the normal path; (d) one-day extra execution delay for each candidate. A
  long-only oracle sits in cash half the time, so its Sharpe is bounded near 2.4; significance, not a fixed Sharpe
  level, defines "huge".
* **Cross-checks** (`crosscheck.py`): bt 1.2.3 reproduces buy-and-hold SPY and the 10-month SMA (first-trading-day
  schedule, independently computed lagged signal, zero cost) against the engine's next-close mode within 1 bp a month;
  SPY vs the Ken French market (correlation >= 0.99, |CAGR difference| <= 75 bp/yr); our T-bill series vs French RF
  since 1990 (every month within 10 bp). Results, including failures and their diagnosis, are in `results/crosscheck.md`.

## 7. Gate A as implemented (thresholds fixed before running)

| gate | implementation |
|---|---|
| A1 | pre-registered: published default parameters; every variant in the ledger |
| A2 | sample >= 15 years including 2008 and 2022 (and 2020); gate cost tier (>= 5 bp per side); Sharpe at 2x costs >= 90% of Sharpe at 1x |
| A3 | walk-forward Sharpe of the candidate's family >= 0.5 (for the ensemble, which has no parameter: its own Sharpe over the same out-of-sample months) **and** full-sample Sharpe > SPY's, or CAGR within 1%/yr of SPY with |MaxDD| <= 70% of SPY's |
| A4 | DSR (N = all ledger trials on the sample) >= 0.95 **and** PBO of the candidate's grid <= 0.2 |
| A5 | plateau statistic >= 0.70 (not applicable to the ensemble) |
| A6 | bootstrap 5th-percentile CAGR > 0 **and** 95th-percentile drawdown magnitude <= SPY's |
| A7 | calendar 2008 and 2022 returns above SPY's **and** CAGR above SPY's in at least 2 of the last three non-overlapping 60-month windows |
| A8 | identity and synthetic foresight/gap tests pass **and** |Sharpe change| <= 0.15 under a one-day extra execution delay |

The report's wording for A8 ("the one-bar-shift test collapses its performance toward the benchmark") is read as:
a leaky edge would collapse under an extra bar of delay, a genuine slow rule should not change; the check is that
the candidate's Sharpe does not depend on the signal bar.

Candidates are gated on their primary sample: the proxy sample for the SPY trend rules and GTAA-4, the ETF-only sample
for GTAA-5.

## 8. How to read the results

Start with `results/summary.md`: the disclosure block, the headline table per sample (always next to SPY buy-and-hold
and 60/40), then the Gate A scorecard. A rejected candidate is the expected, honest outcome (see the research report,
section 1): the trend rules reduce drawdowns, but they have not beaten buy-and-hold on return since 2006, picking the
best lookback in-sample does not carry out of sample (PBO), and rebalance-day luck alone moves GTAA's CAGR by about
2 percentage points a year. `scaling.md` shows why a $1-$100 account cannot show a profit whatever the rule. The trial
count in every disclosure block is the number of variants tried; the more variants, the more the best one is luck.

## 9. Known limitations

* Yahoo data is unlicensed for redistribution and has at least one known history error (VFINX pre-1987, excluded);
  other undetected errors are possible. The quality gates cannot catch missing capital-gain distributions.
* Proxy segments have no as-traded prices, so share counts and per-share fees there use adjusted prices.
* Mutual-fund proxies deal at the day's NAV; the "next open" of a proxy segment is the next NAV.
* Expense ratios in the table are recent published figures (approximate); historical ratios were higher, which slightly
  affects splice adjustments only.
* Historical SEC/TAF rates and pre-2019 commissions are not modelled; the Alpaca schedule is applied to all history.
* Taxes are not modelled; trend switches realize gains that buy-and-hold defers.
* The walk-forward does not charge the one-off cost of switching between variants.
* The T-bill series is the 3-month bill; French RF is the 1-month bill (they diverge in rapid rate cuts).
* Whole-share mode reinvests dividends between rebalances (adjusted-price accounting) and fractional-dividend rounding
  at the broker is not modelled, so the smallest accounts look slightly better than they would.
