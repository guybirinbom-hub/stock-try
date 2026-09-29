# validation

## SUMMARY

# What credible proof looks like for a strategy that has not yet risked money

## 0. Bottom line

For a retail strategy, "proof" is statistical, and the statistics are harsh. The standard error of an annualized Sharpe ratio is about 1/sqrt(years). A strategy with a true Sharpe of 1.0 therefore needs about 4 years of track record to reach t=2 and about 9 years to reach t=3. At a true Sharpe of 0.5 (roughly buy-and-hold equities), those figures become about 16 and 36 years. A few weeks of paper trading proves nothing about edge. After 20 trading days, the 95% confidence interval on an annualized Sharpe is about ±7. Backtests are therefore the only place where enough data exists, but backtests are systematically inflated:
- Bank "alternative beta" products lost a median **73%** of their Sharpe ratio going live (Suhonen et al. 2017).
- Published anomalies return **26% less out-of-sample and 58% less post-publication** (McLean & Pontiff 2016).
- On 888 Quantopian algorithms, backtest Sharpe explained **R² < 0.025** of out-of-sample Sharpe (Wiecki et al. 2016).

The credible path is:
1. A small number of pre-registered, economically motivated hypotheses.
2. A cost-aware, point-in-time, next-bar backtest over at least 15 years that includes 2008, 2020 and 2022.
3. Multiple-testing correction: the Deflated Sharpe Ratio (DSR), the probability of backtest overfitting (PBO), or a t-stat above 3.
4. Walk-forward or combinatorial purged cross-validation (CPCV).
5. Paper trading, which proves plumbing rather than edge.
6. $1 live trading, which proves fills, fees and the broker round trip.
7. Geometric scaling under explicit kill-switches.

Any LLM component can only be tested forward in time. The current Claude models' training-data cutoff is **June 2026** (Anthropic docs), which leaves about 3 months of clean history as of 2026-09-29.

## 1. Backtest hygiene (each item is a known way backtests lie)

| Bias | What goes wrong | Fix | Source |
|---|---|---|---|
| Look-ahead | Using the close to decide and filling at the same close; using revised or restated data; using an index membership that was only known later | Decide on bar t's close and fill at t+1 open (or t+1 close) with costs; use point-in-time data only | [Arnott, Harvey, Markowitz 2019 protocol](https://people.duke.edu/~charvey/Research/Published_Papers/SSRN-id3275654.pdf) |
| Survivorship | Testing on today's S&P 500 members drops bankruptcies and includes stocks before they were added | Use point-in-time constituents with delisted names, or restrict to long-lived liquid ETFs (SPY since 1993) | Practitioner estimates of +1-2%/yr to +3.7% CAGR inflation are **blog-grade**, not peer-reviewed ([priceactionlab](https://priceactionlab.substack.com/p/survivorship-bias-in-backtesting)) |
| Delisting returns | Missing delisting returns bias results upward | Researchers impute -30% (Shumway 1997), and -55% for Nasdaq (Shumway & Warther 1999) | [Shumway 1997](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1997.tb03818.x) |
| Skewed single-stock universe | Only 4.3% of US stocks (1926-2016) created all net wealth over T-bills, and 57.4% had lifetime returns below T-bills | Stock-picking backtests are highly sensitive to which names are included | [Bessembinder 2018](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2900447) |
| Dividends and adjustments | Price-only benchmark versus a total-return strategy, or the reverse; split errors | Use total-return (adjusted) series for both strategy and benchmark (SPY's dividend yield is about 1-2%/yr, a material gap) | general |
| Costs and slippage | Commission-free does not mean cost-free: spread, impact, regulatory fees (TAF/CAT) | Model at least 5 bps per side for liquid ETFs and 10-25 bps for single stocks; require a positive result at 2x costs | Alpaca lists TAF/CAT fees ([docs](https://docs.alpaca.markets/docs/regulatory-fees)); institutional impact is roughly square-root in size and smaller than older estimates ([Frazzini, Israel, Moskowitz 2018](https://www.ssrn.com/abstract=3229719)) |
| Data snooping | Trying many variants and reporting the best | Keep a trial ledger (count every variant), and apply DSR, PBO, or a t-stat above 3 | below |
| Parameter sensitivity | A sharp peak in parameter space is a sign of fit to noise | Require a plateau: ±20-50% parameter perturbation keeps most of the performance | [Bailey et al. overfitting demo](https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf) |

Arnott, Harvey and Markowitz stress an *ex-ante economic rationale* before any data is examined, and full disclosure of every trial.

## 2. Out-of-sample methods and multiple-testing corrections

- **Hold-out (train/test split).** This is necessary but not sufficient. Bailey et al. write: "the hold-out method does not control for the number of trials… one can find an 'optimal' strategy that performs well on both the In Sample and Out of Sample datasets, yet still has no substantive 'skill'" ([source](https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf)).
- **Walk-forward.** Re-fit on a rolling or expanding window and trade the next window. It has no leakage, but it produces a single historical path and is easy to overfit if you iterate on it ([Wikipedia, purged CV](https://en.wikipedia.org/wiki/Purged_cross-validation); [QuantInsti](https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/)).
- **CPCV (López de Prado, *Advances in Financial ML*, 2018).**
  - Split into N contiguous groups and test on every combination of k groups.
  - Purge training observations whose labels overlap the test set, and embargo about 1% after each test block.
  - N=6, k=2 gives C(6,2)=15 splits and k/N·C(N,k)=5 full backtest paths. The result is a *distribution* of out-of-sample Sharpe ratios rather than one number.
- **PBO / CSCV** ([Bailey, Borwein, López de Prado, Zhu, J. Comp. Finance 2016](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253)):
  - Estimates the probability that the in-sample best configuration ranks below the median out-of-sample.
  - PBO near 0 is good; PBO at or above 0.5 means selection is no better than a coin flip.
  - An R package exists ([pbo](https://cran.r-project.org/web/packages/pbo/readme/README.html)).
- **Minimum backtest length** ([Bailey et al.](https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf)): "if only five years of daily market data are available, and if 45 or more independent variations of a strategy are tried, it is more than likely that the best strategy… has a Sharpe ratio of 1.0 or better", even with zero skill. My reproduction of the formula gives these zero-skill expected best Sharpe ratios:

  | Years | N=10 | N=50 | N=100 | N=1000 |
  |---|---|---|---|---|
  | 2 | 1.11 | 1.61 | 1.79 | 2.30 |
  | 5 | 0.70 | 1.02 | 1.13 | 1.46 |
  | 10 | 0.50 | 0.72 | 0.80 | 1.03 |
  | 20 | 0.35 | 0.51 | 0.57 | 0.73 |

  Formula: E[max SR] ≈ σ_SR·[(1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))], with σ_SR = 1/√years and γ = 0.5772. MinBTL for 45 trials is 5.0 years, which matches the paper. **Implication:** an LLM that tries 100 ideas on 5 years of data will "find" a Sharpe above 1 by chance.
- **Deflated Sharpe Ratio** ([Bailey & López de Prado, JPM 2014](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)):
  - DSR = PSR(SR₀), where SR₀ is the expected-max threshold above.
  - PSR(c) = Φ[(SR̂−c)·√(T−1) / √(1 − γ₃SR̂ + (γ₄−1)/4·SR̂²)], using per-period SR, skewness γ₃ and kurtosis γ₄ ([formula summary](https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/)).
  - Accept at DSR ≥ 0.95.
  - The paper's worked example: a Sharpe 2.5 strategy over 5 years of daily data, selected after 100 trials with negatively skewed, fat-tailed returns, was *rejected* at DSR ≈ 0.90. With 46 trials it would have been accepted (0.9505).
  - The paper also argues that overfitting on series with memory produces *negative* out-of-sample expectations, not merely zero.
- **Harvey, Liu, Zhu (RFS 2016)** ([NBER](https://www.nber.org/papers/w20592); [RFS](https://academic.oup.com/rfs/article/29/1/5/1843824)): after 316 tested factors, "a new factor needs to clear a much higher hurdle, with a t-ratio greater than 3.0… most claimed research findings in financial economics are likely false."
  - Since t ≈ SR·√years, t=3 requires Sharpe 1.34 over 5 years, 0.95 over 10, 0.77 over 15, and 0.67 over 20.
- **Harvey & Liu "Backtesting" (JPM 2015)** ([PDF](https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF)): the haircut is nonlinear. "The haircut is almost always more than and sometimes much larger than 50% when the annualized Sharpe ratio is less than 0.4… when the Sharpe ratio is greater than 1.0, the haircut is at most 25%."
  - Worked example: 120 monthly observations, SR about 0.91 after autocorrelation correction, 100 tests, correlation 0.4. The BHY-adjusted SR is 0.438, a haircut of 52%.
- **White's Reality Check (Econometrica 2000)** and Hansen's SPA test ([White](https://onlinelibrary.wiley.com/doi/abs/10.1111/1468-0262.00152)) test "best of many versus benchmark" using a bootstrap.

## 3. Sample sizes: skill versus luck

Lo (2002, FAJ) ([CFA](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios)) gives the IID standard error SE(SR̂) = √((1 + ½SR²)/T) in per-period units. With skewness and kurtosis, the numerator becomes 1 − γ₃SR + (γ₄−1)/4·SR². Negative skew and fat tails widen the standard error.

Annualized with monthly data: SE ≈ √((1 + SR²/24)/Y). So t = SR·√Y, and Y = t²(1 + SR²/24)/SR².

| True annual Sharpe | Years (months) to t=2 | Years (months) to t=3 |
|---|---|---|
| 0.3 | 44.6 (535) | 100 (1205) |
| 0.5 | 16.2 (194) | 36.4 (437) |
| 1.0 | 4.2 (50) | 9.4 (113) |
| 1.5 | 1.9 (23) | 4.4 (53) |
| 2.0 | 1.2 (14) | 2.6 (32) |

95% confidence interval half-width on an annualized Sharpe estimated from d trading days (≈1.96·√(252/d)):

| Trading days | Approx. period | 95% CI half-width |
|---|---|---|
| 10 | 2 weeks | ±9.9 |
| 20 | 1 month | ±7.0 |
| 63 | 3 months | ±3.9 |
| 126 | 6 months | ±2.8 |
| 252 | 1 year | ±1.96 |
| 756 | 3 years | ±1.13 |
| 1260 | 5 years | ±0.88 |

**A few weeks, or even six months, of paper trading cannot distinguish a Sharpe 1.5 strategy from a Sharpe 0 one.**

Beating SPY is even harder, because the test is on the *difference* of Sharpe ratios (Memmel-corrected Jobson-Korkie). With monthly data, t=2 requires:
- about 18.5 years for SR 0.8 vs 0.5 at correlation 0.8;
- about 10 years for 1.0 vs 0.5 at correlation 0.7;
- about 23 years for 1.0 vs 0.5 at correlation 0.3.

MinTRL (Bailey & López de Prado 2012, [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643)) formalizes this: MinTRL = (1 − γ₃SR + (γ₄−1)/4·SR²)·(z_α/(SR−c))².

## 4. Metrics to report, and what the backtest can and cannot predict

Report the following, net of costs, on total-return data, versus buy-and-hold SPY (TR) and a 60/40 portfolio (SPY/AGG, or VBMFX before AGG's 2003 inception) over the same dates:
- CAGR, annualized volatility, Sharpe (with risk-free rate), Sortino.
- Max drawdown and its duration, and Calmar (CAGR/|MaxDD|).
- Hit rate and profit factor, average win/loss, number of trades.
- Annual turnover, and costs as a percentage of gross return.
- Exposure (% time invested) and beta/correlation to SPY.
- Alpha t-stat versus SPY.
- Skewness and kurtosis, PSR, DSR, and the trial count N.

Reference drawdowns:
- S&P 500: -56.8% (Oct 2007 to Mar 2009), -33.9% (Feb to Mar 2020), -25.4% (Jan to Oct 2022) ([Wikipedia milestones](https://en.wikipedia.org/wiki/Closing_milestones_of_the_S&P_500)).
- 60/40: fell about 16-17.5% in 2022, its worst year since 2008, with stocks and bonds both down ([Morningstar](https://www.morningstar.com/portfolios/is-6040-portfolio-good-investment-now); [CNBC](https://www.cnbc.com/2022/10/03/why-60/40-portfolio-is-on-track-for-its-worst-year-ever-says-cio.html)). Figures vary by index and source.

Critical finding from [Wiecki et al. 2016](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2745220) (888 Quantopian algorithms, at least 6 months out-of-sample; figures via [CXO](https://www.cxoadvisory.com/big-ideas/in-sample-vs-out-of-sample-performance-of-888-trading-strategies/)):
- Backtest Sharpe has almost no predictive power (R² < 0.025).
- Volatility (R² 0.67) and max drawdown (R² 0.34) *are* predictive.
- More backtesting leads to a bigger in-sample versus out-of-sample gap.

**Use the backtest to set risk expectations and kill-switches, not return expectations.** Haircut the backtest Sharpe by at least 50% (Harvey-Liu rule of thumb; Suhonen's median live deterioration was 73%) when projecting profits for the token-cost break-even calculation.

**Kill-switches from theory** ([Bailey & López de Prado, "Stop-outs… triple penance"](https://www.davidhbailey.com/dhbpapers/stop-out.pdf)):
- Under IID normal P&L, the α-quantile maximum loss is MaxQL = (z_α σ)²/(4μ), and the quantile time under water is TuW = (z_α σ/μ)². Recovery takes about 3 times as long as the fall.
- Worked numbers:

  | Case | 95% MaxQL | 95% time under water | 99% MaxQL |
  |---|---|---|---|
  | SR 1.0, vol 10% | 6.8% | 2.7 years | 13.5% |
  | SR 0.5, vol 15% | 20.3% | 10.8 years | 40.6% |

- Serial correlation can make this understate downside by up to 70%.
- Practical rule: halt when the live or paper drawdown exceeds the larger of (a) 1.25× the backtest max DD and (b) the 99th-percentile DD from a block bootstrap. Also halt when time under water exceeds the 95% TuW.

## 5. Monte Carlo, bootstrap and regimes

- **Trade-sequence reshuffling** (permute trade P&L order). This gives a drawdown distribution but destroys autocorrelation, so it understates clustered risk.
- **Block / stationary bootstrap** of daily returns ([Politis & Romano 1994, JASA](https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870)), with geometric block lengths and a mean of about 20-60 days. This preserves volatility clustering. Report the 5th/50th/95th percentiles of CAGR, Sharpe and MaxDD. Require the 5th-percentile CAGR above 0 and the 95th-percentile MaxDD within tolerance.
- **Regime slices.** Report 2007-09 (GFC), Feb to Apr 2020 (COVID), 2022 (inflation and rates; 60/40 failed), and 2009 (momentum crash).
  - Momentum strategies suffer "infrequent and persistent strings of negative returns… in panic states, following market declines and when market volatility is high… contemporaneous with market rebounds" ([Daniel & Moskowitz, JFE 2016](https://www.sciencedirect.com/science/article/pii/S0304405X16301490)).
  - A strategy that has never been tested through a rebound crash has not been stress-tested.
- **Sub-period stability.** Split the sample into non-overlapping 5-year windows. The sign of excess return should be consistent in most windows.

## 6. Evidential hierarchy: what each stage can and cannot prove

| Stage | Proves | Cannot prove |
|---|---|---|
| In-sample backtest | Idea is not obviously broken; risk profile (volatility and DD predict out-of-sample reasonably) | Edge (Sharpe R²<0.025 out-of-sample); unaffected by snooping |
| Walk-forward / CPCV + DSR/PBO | Edge survives re-fitting and multiple-testing correction on history | Future regime; execution; memorized-data effects for LLMs |
| Paper trading (Alpaca) | Code runs daily; signals match the backtest engine; order logic, scheduling, data feed, error handling | Fill quality. Alpaca paper "does NOT" simulate market impact, slippage due to latency, queue position, price improvement, regulatory fees, or **dividends**. Partial fills are random 10% of the time ([Alpaca docs](https://docs.alpaca.markets/docs/paper-trading)). Edge (sample too short) |
| $1 live (fractional; Alpaca allows "as little as $1 worth of shares for over 2,000 US equities", day orders; [docs](https://docs.alpaca.markets/docs/fractional-trading)) | Real fills, fees, fractional rounding, settlement, tax-lot reporting, account permissions (residency matters: non-US accounts, W-8BEN, local tax) | Edge (P&L is cents); capacity; impact at size; psychology at size |
| Scaled live ($100 to $10k+) | Slippage versus model at realistic order sizes; LLM/infra cost versus profit | Long-run edge until years accrue |

## 7. The LLM look-ahead trap

- **LLMs memorize history.** [Lopez-Lira, Tang, Zhu 2025](https://arxiv.org/abs/2504.14765) found that GPT-4o recalls pre-cutoff S&P 500 levels and macro figures essentially verbatim. "Instructions to respect historical boundaries fail… masking fails as LLMs reconstruct entities and dates." Forecasting skill on pre-cutoff dates is "non-identified."
- **The contamination has been measured.** [Gao, Jiang, Yan 2025/26](https://arxiv.org/abs/2512.23847) define Lookahead Propensity. It is "materially positive throughout the in-sample period and collapses essentially to zero right after the training-data cutoff," and LLM return-prediction power is concentrated in high-LAP observations. [Look-Ahead-Bench (Jan 2026)](https://arxiv.org/abs/2601.13770) finds "significant lookahead bias in standard LLMs, as measured with alpha decay."
- **Knowledge contaminates sentiment.** [Glasserman & Lin 2023](https://arxiv.org/abs/2309.17322) found anonymized headlines outperform, so the model's general firm knowledge ("distraction") also contaminates results.
- **LLM-discovered strategies failed an honest test.** [Gençay, Aug 2026](https://arxiv.org/abs/2608.27734) used leakage-safe tools and exhaustive trial-count deflation. Up to 100 candidates across two model frontiers and two universes (453 stocks, 39 ETFs) were *all* rejected, while passive benchmarks passed. A deliberately leaky oracle with Sharpe 35 passed conventional tests. This is a single-author preprint and has not been peer-reviewed.
- **Point-in-time models are the research-grade fix.** Example: ChronoBERT/ChronoGPT, trained only on text available at each date ([He, Lv, Manela, Wu 2025](https://arxiv.org/abs/2502.21206)).
- **Cutoff dates.** Per [Anthropic's models overview](https://platform.claude.com/docs/en/about-claude/models/overview), Fable 5.1, Opus 5.5 and Sonnet 5.5 have training-data cutoff **Jun 2026**. Haiku 4.5 has a training-data cutoff of Jul 2025 (reliable knowledge cutoff Feb 2025).
- **Clean design:**
  1. Never backtest any LLM judgement on dates before the model's training-data cutoff plus a buffer of at least 1 month.
  2. Feed only point-in-time inputs with timestamps, and no web or search tools during simulation, since those return post-date information.
  3. Pin the model ID. A model upgrade resets the clean window.
  4. Treat the LLM component as forward-test-only. Haiku 4.5 offers about 14 months (Aug 2025 to Sep 2026) of possibly clean history, but at a true Sharpe of 1 that has a standard error of about 0.85, which is not proof.
  5. Prefer designs where the LLM writes or reviews *code for rule-based strategies*, validated on history with DSR, rather than issuing per-date predictions.
  6. Count every LLM-generated idea in the trial ledger.
- **Cost gate:** LLM spend is a trading cost that must be included in the backtest.
  - Example: one Sonnet 5.5 call per day with 10k input and 1k output tokens costs 10,000×$2/1M + 1,000×$10/1M = $0.03/day, or $7.56/yr over 252 days ($3.78 with the Batch API).
  - At a (haircut) 3%/yr excess return, break-even capital is $7.56/0.03 = $252.
  - At $1 capital, *any* daily LLM call makes the strategy unprofitable. So $1 live can only test a rule-based strategy economically. The LLM portion must be evaluated with token cost amortized against the intended future capital.

## 8. Acceptance checklist (thresholds and rationale)

**A. Accepted for paper trading only if:**
1. **Pre-registered hypothesis.** A written economic rationale and parameter ranges fixed before testing, plus a trial ledger with N recorded. *Rationale:* DSR, PBO and HLZ all require N (Arnott-Harvey-Markowitz).
2. **Sufficient history.** At least 15 years of daily total-return data covering 2008, 2020 and 2022. At N≤10, 15 years keeps the zero-skill expected best Sharpe at about 0.4-0.5, and t=3 then needs Sharpe 0.77.
3. **Honest execution model.** Signal at close t, fill at open or close of t+1. Costs of at least 5 bps per side for ETFs and 15 bps for stocks. Still profitable at 2× costs. Costs below 30% of gross return.
4. **Clean universe.** Survivorship-free: ETF-only, or point-in-time constituents with delisting returns.
5. **Out-of-sample net Sharpe ≥ 0.5.** Measured on walk-forward/CPCV out-of-sample paths, and the median CPCV path Sharpe must exceed SPY's Sharpe over the same windows, or match SPY's CAGR within 1%/yr with MaxDD at least 30% smaller. *Rationale:* otherwise buy-and-hold SPY/60-40 dominates at zero token cost.
6. **Multiple-testing corrected.** DSR ≥ 0.95 using the logged N. PBO ≤ 0.2 (0.5 is coin-flip; 0.2 is my conservative choice). t-stat of excess return ≥ 3 if N > 10, or ≥ 2 only for a single pre-registered test (HLZ).
7. **Parameter plateau.** ±25% perturbation of each parameter keeps Sharpe at least 70% of the base value.
8. **Bootstrap robustness.** Stationary bootstrap 5th-percentile CAGR > 0. 95th-percentile MaxDD ≤ 35%, and ≤ SPY's in the same bootstrap.
9. **Regime survival.** Loses less than SPY in 2008 and 2022. Positive excess in at least 2/3 of non-overlapping 5-year windows.
10. **Token economics pass at intended capital.** Any LLM component has zero pre-cutoff evaluation credit, and its cost is included in the backtest.

**B. Accepted for $1 live only if:** A is passed, plus at least 1 month (at least 20 trading days) of paper trading with:
- 100% of signals reproduced by the backtest engine on the same data;
- no unhandled errors or missed runs;
- a paper-versus-backtest daily return tracking difference below 10 bps per day on average.

*Rationale:* $1 is an operational test, not an edge test. Its risk is trivial, so gating it on months of paper trading adds no information.

**C. Accepted for scaling to $100-$1,000 only if:**
- at least 6 months of combined paper and live forward record;
- live slippage ≤ modeled cost;
- forward Sharpe within the backtest bootstrap's 90% band (not "significantly positive", which is impossible in 6 months);
- no kill-switch hit;
- annual running cost below 20% of expected profit at the new capital, using the haircut Sharpe.

**D. Accepted for scaling to $10k+ only if:**
- at least 24 months forward;
- PSR(forward SR > 0) ≥ 0.90;
- forward SR at least 50% of the backtest SR;
- orders below 0.1% of average daily volume;
- scaling in steps of at most 3-10× with at least 6 months between steps.

*Rationale:* by the table in section 3, 24 months gives SE ≈ 0.7, so only a true Sharpe of 1.5 or more would be significant. Scaling is risk budgeting under uncertainty, not proof.

**Kill-switch (any stage):**
- DD above 1.25× the backtest MaxDD, or above the bootstrap 99th-percentile DD; or
- time under water above the 95% TuW; or
- rolling 12-month PSR(SR > 0) below 0.05; or
- running cost above realized gross profit for 3 consecutive months.

## CLAIMS

- **[C1] (high)** The IID standard error of the Sharpe ratio is sqrt((1+SR^2/2)/T) in per-period units (Lo 2002). Annualized, a true Sharpe of 1.0 needs about 4.2 years for t=2 and 9.4 years for t=3; Sharpe 0.5 needs about 16 and 36 years; Sharpe 1.5 needs about 1.9 and 4.4 years.
  - evidence: Lo, FAJ 2002 formula; arithmetic Y = t^2(1+SR^2/24)/SR^2 with monthly data, computed in Python.
  - sources: https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios, https://portfoliooptimizer.io/blog/the-probabilistic-sharpe-ratio-bias-adjustment-confidence-intervals-hypothesis-testing-and-minimum-track-record-length/
- **[C2] (high)** After 20 trading days, the 95% confidence interval on an annualized Sharpe estimate is about ±7. After 6 months it is about ±2.8 and after 1 year about ±2.0, so short paper-trading periods cannot establish edge.
  - evidence: 1.96*sqrt(252/d) for d=20, 126 and 252 gives 6.96, 2.77 and 1.96.
  - sources: https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
- **[C3] (high)** With 5 years of daily data, trying 45 or more independent strategy variants makes it likely that the best one shows a Sharpe of at least 1.0 purely by chance.
  - evidence: Bailey et al. text quoted verbatim. Reproduced MinBTL(N=45, E[max]=1) = 5.0 years.
  - sources: https://sdm.lbl.gov/oapapers/ssrn-id2507040-bailey.pdf, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- **[C4] (high)** The Deflated Sharpe Ratio corrects for selection bias across N trials and for non-normality. In the paper's example, an SR 2.5 strategy over 5 years of daily data selected from 100 trials had DSR of about 0.90 and was rejected at 95%. With N=46 it would have passed (0.9505).
  - evidence: DSR paper numerical example text extracted from PDF.
  - sources: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- **[C5] (high)** Harvey, Liu and Zhu (RFS 2016), after cataloguing 316 factors, argue that a new factor needs a t-ratio above 3.0 and that most claimed findings in financial economics are likely false.
  - evidence: Verbatim from the NBER working paper text.
  - sources: https://www.nber.org/papers/w20592, https://academic.oup.com/rfs/article/29/1/5/1843824
- **[C6] (high)** The Harvey and Liu multiple-testing haircut is nonlinear. It is usually more than 50% for Sharpe below 0.4 and at most 25% for Sharpe above 1.0. Their example (120 months, SR about 0.91, 100 tests) gives a BHY-adjusted SR of 0.438, a 52% haircut.
  - evidence: Verbatim from the JPM 2015 PDF text.
  - sources: https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
- **[C7] (high)** Across 215 bank alternative-beta strategies, the median Sharpe ratio deteriorated by 73% from backtest to live, and more complex strategies deteriorated more.
  - evidence: Suhonen, Lennkh, Perez, JPM 2017, 43(2):90-104.
  - sources: https://www.pm-research.com/content/iijpormgmt/43/2/90, https://research.aalto.fi/en/publications/quantifying-backtest-overfitting-in-alternative-beta-strategies
- **[C8] (high)** Across 97 published anomalies, returns were 26% lower out-of-sample and 58% lower post-publication.
  - evidence: McLean and Pontiff, Journal of Finance 2016, abstract.
  - sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623
- **[C9] (high)** On 888 Quantopian algorithms, backtest Sharpe predicted out-of-sample Sharpe with R² < 0.025, whereas backtest volatility (R² 0.67) and max drawdown (R² 0.34) were predictive. More backtesting was associated with a larger in-sample versus out-of-sample gap.
  - evidence: Wiecki et al. 2016 abstract; CXO summary quotes the R² values.
  - sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2745220, https://www.cxoadvisory.com/big-ideas/in-sample-vs-out-of-sample-performance-of-888-trading-strategies/
- **[C10] (high)** Alpaca paper trading does not simulate market impact, latency slippage, queue position, price improvement, regulatory fees or dividends. Paper accounts default to $100k.
  - evidence: Alpaca paper trading documentation, quoted.
  - sources: https://docs.alpaca.markets/docs/paper-trading
- **[C11] (high)** LLMs memorize pre-cutoff financial data (for example, exact S&P 500 levels). Instructions and masking do not prevent this, and measured lookahead propensity collapses to about zero right after the training cutoff. Pre-cutoff backtests of LLM judgement are therefore uninformative.
  - evidence: Lopez-Lira, Tang, Zhu 2025; Gao, Jiang, Yan 2025/2026; Look-Ahead-Bench 2026; Glasserman and Lin 2023.
  - sources: https://arxiv.org/abs/2504.14765, https://arxiv.org/abs/2512.23847, https://arxiv.org/abs/2601.13770, https://arxiv.org/abs/2309.17322
- **[C12] (high)** Claude Fable 5.1, Opus 5.5 and Sonnet 5.5 have a training data cutoff of June 2026. Haiku 4.5 has a training cutoff of July 2025 (reliable knowledge cutoff February 2025). As of 2026-09-29, only about 3 months of post-cutoff data exist for current frontier Claude models.
  - evidence: Anthropic models overview table.
  - sources: https://platform.claude.com/docs/en/about-claude/models/overview
- **[C13] (high)** Under IID normal P&L, the α-quantile maximum loss is (z_α σ)^2/(4μ) and the time under water is (z_α σ/μ)^2, so recovery takes about 3 times the time to reach the drawdown. For SR 0.5 at 15% volatility, the 95% time under water is about 10.8 years.
  - evidence: Propositions 1 and 2 extracted from the Bailey and López de Prado stop-out paper; arithmetic computed.
  - sources: https://www.davidhbailey.com/dhbpapers/stop-out.pdf, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2201302
- **[C14] (medium)** A leakage-safe, trial-count-deflated evaluation of up to 100 LLM-discovered strategies across a 453-stock and a 39-ETF universe rejected every one while certifying passive benchmarks, and a deliberately leaky oracle with Sharpe 35 passed conventional tests.
  - evidence: Gençay, arXiv 2608.27734 (August 2026). Single-author preprint, not peer-reviewed.
  - sources: https://arxiv.org/abs/2608.27734

## RECOMMENDATIONS

- Restrict the first candidate universe to a few long-lived, liquid ETFs (SPY, AGG/IEF, GLD and similar). This avoids survivorship and delisting bias and makes 20+ years of total-return history available.
- Build the backtester to decide on the close of day t and fill at t+1 (open or close). Use total-return data for both strategy and benchmark, charge at least 5 bps per side for ETFs (15 bps for stocks), and always report results at 2x costs.
- Keep a trial ledger from day one. Every variant, parameter set and LLM-suggested idea counts toward N. Compute DSR from N and do not accept anything with DSR < 0.95. Treat t < 3 as unproven when N > 10.
- Run CPCV (for example N=6 groups, k=2, which gives 5 paths) or rolling walk-forward, compute PBO with CSCV, and reject strategies with PBO > 0.2.
- Always report CAGR, volatility, Sharpe, Sortino, MaxDD and its duration, Calmar, hit rate, turnover, exposure, beta, PSR, DSR and N, alongside buy-and-hold SPY and 60/40 over identical dates. If the strategy does not beat SPY on Sharpe or materially reduce drawdown, just buy SPY.
- Use a stationary block bootstrap (mean block about 20-60 days) and regime slices (2008, 2009 rebound, 2020, 2022) to set drawdown expectations. Set kill-switches at the larger of 1.25x backtest MaxDD and the bootstrap 99th-percentile DD, and at the 95% time under water.
- Haircut the backtest Sharpe by at least 50% (up to 73%) when projecting profit for the token/infra-cost break-even calculation. Require running cost below 20% of the haircut expected profit at target capital.
- Never evaluate any LLM judgement on dates before its training-data cutoff (June 2026 for Opus/Sonnet/Fable 5.x). Pin the model ID, feed only timestamped point-in-time inputs, and disable web/search during simulation. Treat the LLM component as forward-test only.
- Prefer using Claude to write, review and audit rule-based strategy code, which can be validated on decades of history, rather than to make daily predictions. At $1-$1,000 capital, a daily LLM call (about $0.03/day or $7.56/yr for a 10k-in/1k-out Sonnet 5.5 call) can exceed plausible profit.
- Treat paper trading (at least 20 trading days) and $1 live as operational tests: signal parity with the backtest, correct fills and fees, and no missed runs. Do not interpret their P&L as evidence of edge.
- Scale geometrically (at most 3-10x per step, at least 6 months between steps). Only scale to $10k+ after at least 24 months forward with PSR(SR>0) ≥ 0.90 and forward SR at least 50% of backtest SR. Before opening a live account, confirm your residency, broker eligibility and local tax treatment.

## OPEN QUESTIONS

- The person's country of residence determines broker eligibility (Alpaca for non-US persons), fractional-share access, tax on small gains, and whether US ETFs (PRIIPs/KID rules in the EU/UK) are purchasable.
- Current exact SEC Section 31 and FINRA TAF rates were not retrieved. Alpaca's regulatory-fees page defers to its fee schedule.
- Which free data source gives reliable, survivorship-aware, dividend-adjusted daily history from this container. Yahoo is rate-limited and stooq was cut off; Alpha Vantage free-tier limits and adjustment quality need verification.
- The PBO ≤ 0.2 and ±25%-parameter-plateau thresholds are my conservative judgement calls, not published standards. The literature only establishes that PBO ≥ 0.5 is disqualifying.
- Survivorship-bias magnitudes for current-constituent stock backtests (+1-2%/yr, +3.7% CAGR in one example) come from practitioner blogs, not peer-reviewed studies.
- Whether Haiku 4.5's post-cutoff window (Aug 2025 to Sep 2026) is truly clean for news-driven tests depends on point-in-time news data availability. Even if clean, about 14 months is statistically too short to prove edge.
- The Gençay (Aug 2026) finding that all LLM-discovered strategies fail honest evaluation is a single-author preprint and needs independent replication.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** IID SE of Sharpe is sqrt((1+SR^2/2)/T) per period (Lo 2002); SR 1.0 needs ~4.2y (t=2) / 9.4y (t=3); SR 0.5 ~16/36y; SR 1.5 ~1.9/4.4y.
  - reasoning: Formula is Lo (2002)'s IID result. Annualizing from monthly data: SE_ann = sqrt(12)*sqrt((1+SR^2/24)/(12Y)) = sqrt((1+SR^2/24)/Y). Recomputed: SR1 t=2: 4*1.0417=4.17y; t=3: 9.375y. SR0.5: 4*1.0104/0.25=16.2y, 36.4y. SR0.3: 44.6y. All match. Caveats the researcher left out: (a) Lo's main point is that serial correlation changes the sqrt(12) annualization and can overstate annual Sharpe by up to ~65% for autocorrelated strategies; (b) a significance test of SR>0 should strictly use the SE under the null (SR=0), which makes the requirement slightly shorter. Neither caveat changes the conclusion.
- **[C2] CONFIRMED** 95% CI half-width on annualized Sharpe is ~±7 after 20 days, ±2.8 after 6 months, ±2.0 after 1 year.
  - reasoning: 1.96*sqrt(252/d) gives 6.96, 2.77 and 1.96. This drops the SR^2/2 term, so it slightly understates the width at high Sharpe, which only strengthens the conclusion that short paper trading cannot establish edge.
- **[C3] NEEDS_QUALIFICATION** With 5 years of daily data and 45+ independent variants, the best variant likely shows Sharpe >= 1.0 by chance.
  - reasoning: The quote is the paper's own wording. My reproduction confirms E[max]=2.2356 sigma for N=45 and MinBTL=4.998y, and the whole zero-skill table (2y/5y/10y/20y x N=10/50/100/1000) matches to 2 decimals. A Monte Carlo of 20,000 draws of max of 45 N(0,1) gives P(max >= E[max]) = 0.434, so 'more than likely' is slightly loose. The practical implication stands: an LLM trying ~100 ideas on 5 years will find Sharpe >1 by chance.
  - corrected: With 5 years of data and 45 independent zero-skill variants, the EXPECTED maximum annualized Sharpe is about 1.0 (MinBTL = 5.0y reproduced). The probability that the best variant reaches 1.0 is about 43%, not over 50%, because the max distribution is right-skewed. The result assumes independent trials. Correlated parameter variants have fewer effective trials, and correlated trials should be clustered to estimate effective N.
- **[C4] CONFIRMED** DSR example: SR 2.5, 5y daily, 100 trials, DSR ~0.90 rejected; N=46 would give 0.9505.
  - reasoning: PDF text: 'there is only a 90% chance that the true SR associated with this strategy is greater than zero. Should the strategist have made his discovery after running only N=46 independent trials... would have been 0.9505'. T=1250, and the example uses non-normal returns. HOWEVER, section 2 of the summary misdefines SR0. The paper builds the threshold from 'the variance of the SRs tested (V[{SR_n}])', the empirical cross-trial variance (0.5 annualized in the example), not sigma_SR = 1/sqrt(years) as the summary implies ('SR0 is the expected-max threshold above'). The implementation must compute V[SR_n] from the trial ledger. The paper also notes that DSR can alternatively use the Harvey-Liu threshold. There is a section 'Backtest overfitting under memory effects', consistent with the negative-OOS claim.
- **[C5] NEEDS_QUALIFICATION** HLZ (RFS 2016): new factor needs t>3.0; most claimed findings likely false.
  - reasoning: The NBER abstract confirms that the usual t>2.0 makes no sense and that most findings are likely false. The t>3.0 figure is in the paper and in the RFS abstract. The strong claim is disputed in top-journal literature the researcher did not mention. For a retail self-generated trial ledger, t>3 remains a reasonable conservative bar.
  - corrected: HLZ argue a new factor should clear t>3.0 and that most claimed findings are likely false. This is contested: Jensen, Kelly and Pedersen (JF 2023, 'Is There a Replication Crisis in Finance?') find most factors replicate, work out of sample in 93 countries, and gain credibility from the number of factors. Chen ('Do t-Statistic Hurdles Need to be Raised?') also disputes the hurdle. t>3 is a conservative convention, not settled truth.
- **[C6] CONFIRMED** Harvey-Liu haircut is nonlinear (>50% for SR<0.4, <=25% for SR>1.0); example 120 months, SR ~0.91, 100 tests, corr 0.4 gives BHY SR 0.438, 52% haircut.
  - reasoning: Verbatim: 'the haircut is almost always more than and sometimes much larger than 50% when the annualized Sharpe ratio is less than 0.4... when the Sharpe ratio is greater than 1.0, the haircut is at most 25%.' Example inputs were an annualized SR of 1.0 over 120 months with monthly autocorrelation 0.1, giving an AC-corrected 0.912, 100 tests and correlation 0.4. Under BHY the adjusted SR is 0.438, a 52.0% haircut. The summary's section 4 is wrong, though: it calls a flat 50% haircut the 'Harvey-Liu rule of thumb'. Harvey and Liu write 'it is a serious mistake to use the usual 50% haircut' and 'the 50% rule of thumb... is inappropriate'.
- **[C7] CONFIRMED** 215 bank alt-beta strategies: median 73% Sharpe deterioration backtest to live; more complex strategies deteriorated more.
  - reasoning: Aalto abstract: 'median 73% deterioration in Sharpe ratios between backtested and live performance'. The most complex strategies' reduction exceeded the simplest ones' 'by over 30 percentage points'. Robustness was reasonable for equity volatility and FX carry and weak for equity value. Caveat: these are bank-marketed index products, whose backtests have a sales incentive and include pre-launch fees and costs, so 73% is best treated as an upper-range reference rather than a universal haircut.
- **[C8] CONFIRMED** 97 anomalies: returns 26% lower out-of-sample and 58% lower post-publication.
  - reasoning: SSRN returned 403, but this is the well-known JF 2016 abstract ('97 variables... 26% lower out-of-sample and 58% lower post-publication'). Nuance: the authors attribute the 26% to statistical bias and the additional ~32% to publication-informed trading. Only the 26% is directly analogous to backtest overfitting.
- **[C9] NEEDS_QUALIFICATION** 888 Quantopian algos: backtest Sharpe R^2<0.025 for OOS Sharpe; volatility R^2 0.67, max DD R^2 0.34 predictive; more backtesting leads to a larger IS-OOS gap.
  - reasoning: CXO confirms the R^2 figures and the backtest-intensity effect, and lists caveats: a short OOS period with little variety of market conditions, unsophisticated developers, and costs. SSRN returned 403. It is unsurprising that volatility is predictable, because volatility is persistent. That does not mean the backtest is 'predictive' in the sense a novice would read.
  - corrected: On 888 Quantopian algorithms, individual backtest metrics explained OOS Sharpe with R^2 of about 0.01-0.02. Backtest volatility (R^2 0.67) and max drawdown (R^2 0.34) predicted their OOS counterparts, and a nonlinear ML model reached R^2 0.17. More backtest days were associated with a bigger IS-OOS gap. The OOS window was short (June 2015 to February 2016, a single market regime). The authors were Quantopian staff, and it is an SSRN working paper.
- **[C10] CONFIRMED** Alpaca paper does not simulate impact, latency slippage, queue position, price improvement, regulatory fees or dividends; default $100k.
  - reasoning: Verbatim from the docs: 'Market impact of your orders, Information leakage of your orders, Price slippage due to latency, Order queue position..., Price improvement received, Regulatory fees, Dividends'; '$100k balance as a default'; partial fills 'for a random size 10% of the time'. Implication the research missed: paper-versus-backtest tracking must be computed on price returns, or dividends added back, because a total-return backtest will diverge on ex-dividend days.
- **[C11] NEEDS_QUALIFICATION** LLMs memorize pre-cutoff financial data; instructions and masking don't prevent it; LAP collapses to ~0 after cutoff; pre-cutoff backtests of LLM judgement are uninformative.
  - reasoning: Lopez-Lira, Tang and Zhu (revised December 2025) is confirmed verbatim: 'Instructions to respect historical boundaries fail... masking fails'. Gao, Jiang and Yan (v2 June 2026) is confirmed verbatim: 'LAP is materially positive throughout the in-sample period and collapses essentially to zero right after the training-data cutoff'. Look-Ahead-Bench is a single author (Benhenda), a preprint, and tested open models. 'Uninformative' is stronger than the evidence supports, but the practical recommendation (no pre-cutoff credit) is sound and conservative.
  - corrected: Pre-cutoff backtests of LLM judgement are upward-biased by an unknown and model-specific amount and cannot count as evidence of edge. The bias magnitude varies: Glasserman and Lin (2023) found that in their headline-sentiment setup the 'distraction effect has a greater impact than look-ahead bias', and look-ahead was not a concern out of sample. None of the cited studies tested Claude 5.x. Look-Ahead-Bench tested Llama 3.1 and DeepSeek 3.2.
- **[C12] CONFIRMED** Fable 5.1, Opus 5.5, Sonnet 5.5 training cutoff Jun 2026; Haiku 4.5 Jul 2025 (reliable Feb 2025); ~3 months of post-cutoff data now.
  - reasoning: The models overview table matches exactly, and the pricing rows match the shared context. The research missed a critical point on the same page: retirement is 'Not sooner than October 15, 2026' for Haiku 4.5 (about 2 weeks away) and not sooner than September 1, 22 and 28, 2027 for Fable 5.1, Opus 5.5 and Sonnet 5.5. A pinned-model forward record therefore cannot run much beyond about 12 months. Under the research's own rule that a model change resets the clean window, the 24-month gate (D) is unreachable for any LLM-in-the-loop strategy. Also, with the recommended 1-month buffer, only about 2 months of clean history exist.
- **[C13] CONFIRMED** IID normal: MaxQL=(z sigma)^2/(4 mu), TuW=(z sigma/mu)^2, recovery ~3x the fall; SR0.5 at 15% vol gives 95% TuW ~10.8y.
  - reasoning: The abstract confirms the triple penance rule and that ignoring serial correlation underestimates downside 'by as much as 70%', a figure from an empirical study of hedge fund indices. Arithmetic: mu=7.5%, z=1.645: (0.24675)^2/0.3 = 20.3%, and TuW=(3.29)^2 = 10.8y. SR1 at 10% vol: 6.8%, 2.7y. 99% (z=2.326): 13.5% and 40.6%. All match. Caveat: MaxQL is the worst alpha-quantile of cumulative P&L over horizons, not the distribution of realized maximum drawdown along a path. Realized max drawdowns over long periods typically exceed it, so it is a floor, not a ceiling, for kill-switch design.
- **[C14] CONFIRMED** Gençay (Aug 2026): leakage-safe, trial-deflated evaluation rejected all of up to 100 LLM-discovered strategies across 453 stocks and 39 ETFs, certified passive benchmarks, and a leaky oracle at Sharpe 35 passed conventional tests.
  - reasoning: The abstract matches: two frontier models, search budgets up to 100, five repeated runs, realistic transaction, impact and borrow costs, and passive benchmarks certified with OOS CIs excluding zero. Precision point with design consequences: the leaky oracle 'survives Deflated Sharpe and probability-of-backtest-overfitting testing completely'. So DSR and PBO, the research's own gates, do NOT detect look-ahead leakage, and leakage must be prevented structurally (point-in-time data, next-bar fills, code review). It is a single-author preprint submitted 2026-08-27 and not peer-reviewed.
- **[S1] REFUTED** (Summary §7) Haiku 4.5's ~14-month clean window at true SR 1 gives SE ~0.85.
  - reasoning: 0.85 corresponds to about 1.38 years. The model-deprecation schedule makes the Haiku forward-test idea moot.
  - corrected: 14 months = 1.167 years gives SE = sqrt((1+1/24)/1.167) = 0.94, not 0.85. More importantly, Haiku 4.5 may be retired from October 15, 2026, so this window cannot be extended.
- **[S2] NEEDS_QUALIFICATION** (Summary §7) One Sonnet 5.5 call/day with 10k in / 1k out costs $0.03/day, $7.56/yr; break-even capital at 3% excess is $252.
  - reasoning: The models overview confirms Sonnet 5.5 thinking is 'Adaptive' with default effort 'high'. The cost example omits the non-LLM running costs the user explicitly asked to cover.
  - corrected: The arithmetic is right ($0.02 + $0.01 = $0.03/day, x252 = $7.56, /0.03 = $252), but it is a lower bound. Sonnet 5.5 has adaptive thinking with default effort 'high', and thinking tokens are billed as output. Unless effort is lowered, 1k output is unrealistic: 5k-20k output would give $0.07-$0.22/day, or $18-$55/yr. Hosting (e.g. a $5/month VPS = $60/yr) alone moves break-even capital at 3% excess to about $2,000, unless a free scheduler is used. Data costs are not included either.
- **[S3] NEEDS_QUALIFICATION** (Summary §3) MinTRL = (1 - g3 SR + (g4-1)/4 SR^2)(z/(SR-c))^2.
  - reasoning: The leading '1 +' is missing. This is minor numerically but should be right in code.
  - corrected: Bailey and López de Prado's MinTRL is 1 + (1 - g3 SR + (g4-1)/4 SR^2)(z_alpha/(SR - SR*))^2, in per-period units.
- **[S4] CONFIRMED** (Summary §3) Difference-of-Sharpe years to t=2: 18.5y (0.8 vs 0.5, rho 0.8), 10y (1.0 vs 0.5, rho 0.7), 23y (rho 0.3).
  - reasoning: Memmel-corrected JK annualized from monthly: Var = [2-2rho + (SR1^2+SR2^2-2 SR1 SR2 rho^2)/24]/Y. This gives 4*0.41575/0.09 = 18.5, 4*0.6317/0.25 = 10.1 and 4*1.4483/0.25 = 23.2. Corollary the research did not draw: t=3 on excess over SPY needs 2.25x these spans (about 42 years for 0.8 vs 0.5), so criterion A.6 read as 'excess over SPY' is unattainable.
- **[S5] CONFIRMED** (Summary §1) Bessembinder: 4.3% of stocks created all net wealth (1926-2016); 57.4% had lifetime returns below T-bills.
  - reasoning: 4.31% (1,092 of 25,332 firms), and 42.6% beat T-bills, so 57.4% did not.
- **[S6] NEEDS_QUALIFICATION** (Summary §6) Alpaca fractional: as little as $1 for over 2,000 US equities, day orders.
  - reasoning: The docs are confirmed. The research omitted funding costs, which dominate a $1 test.
  - corrected: Confirmed: '$1 worth of shares for over 2,000 US equities'. Market, limit, stop and stop-limit orders are supported with TIF=Day, and fractional trading now also works pre-market, post-market and overnight. Funding and withdrawal costs matter more than the trade size: Alpaca wires reportedly cost $25 domestic and $50 international (secondary source, BrokerChooser 2026; official fee PDF not fetched), with 'additional fees depending on your country, currency, and bank partner'. For a non-US person, a '$1 live test' may cost $25-$100+ in transfer and FX fees.
- **[S7] CONFIRMED** (Summary §2) CPCV N=6,k=2 gives 15 splits and 5 paths; t=3 needs SR 1.34/0.95/0.77/0.67 over 5/10/15/20y; N=10 over 15y gives zero-skill E[max] ~0.4-0.5.
  - reasoning: C(6,2)=15, and 2/6*15=5. 3/sqrt(Y) gives 1.342, 0.949, 0.775 and 0.671. E[max] for N=10 over 15y = 0.407.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- TRIAL COUNTING / DSR IMPLEMENTATION: 'Every variant counts toward N' combined with SR0 = sigma*E[max] with sigma = 1/sqrt(years) is a misreading of DSR. The paper uses the empirical cross-trial variance V[{SR_n}] and the number of INDEPENDENT trials. Counting highly correlated parameter tweaks as independent makes the gate too strict (false negatives), while ignoring correlation in V makes it too loose. Estimate effective N by clustering trial return series (López de Prado's recommendation) and compute V from the ledger.
- DSR/PBO ARE NOT LEAKAGE DETECTORS: Gençay (2026) shows a leaky oracle with Sharpe 35 'survives Deflated Sharpe and PBO testing completely'. The checklist leans on DSR/PBO as the main protection. Look-ahead must be prevented structurally: next-bar fills, point-in-time data, unit tests that shift signals by one bar and confirm performance collapses to about zero for leaky features, and independent code review. The recommendations should say so explicitly.
- CHECKLIST IS INTERNALLY INCONSISTENT AND HAS NEAR-ZERO POWER: A.5 allows a strategy that merely matches SPY CAGR with smaller drawdown, but A.6 demands a t-stat >= 3 of 'excess return' without saying excess over what. If it means excess over SPY, section 3's own arithmetic shows it needs about 40+ years. If it means excess over T-bills, it is a different test from A.5. A.9 (lose less than SPY in both 2008 and 2022) plus A.8 (bootstrap MaxDD <= SPY's) plus the plateau, PBO and DSR gates mean even a genuinely good strategy with true SR 0.6-0.8 will almost surely fail. The orchestrator should present this honestly: the most likely outcome of an honest pipeline is 'nothing beats a low-cost index fund'. That is a valid, cheap result, not a failure of the pipeline.
- HARVEY-LIU MISATTRIBUTION: The recommendation to 'haircut by at least 50% (Harvey-Liu rule of thumb)' is backwards. Harvey and Liu call the flat 50% haircut 'a serious mistake' and 'inappropriate'. Use DSR/BHY-derived haircuts that depend on N and the Sharpe level. Suhonen's 73% comes from bank-marketed products and should be used as a stress case, not a default.
- KILL-SWITCH IS TOO LOOSE FOR A RISK-AVERSE NOVICE: 'The larger of 1.25x backtest MaxDD and the bootstrap 99th-percentile DD' can mean a stop at a 50-70% drawdown for anything equity-like tested through 2008 (SPY's own drawdown was -56.8%). Bailey and López de Prado's MaxQL is a quantile of cumulative loss, not realized max drawdown, and they warn it understates downside by up to 70% under serial correlation. A consumer-protection framing needs an absolute dollar loss cap chosen by the person, enforced at the broker level (cash account, no margin, no options or shorting, per-order notional caps), in addition to statistical stops. Use the SMALLER of the thresholds, not the larger.
- PINNED-MODEL FORWARD TESTING IS INFEASIBLE AS SPECIFIED: Haiku 4.5 may be retired from October 15, 2026, about 2 weeks from now, so the suggested '~14 months clean Haiku window' is useless going forward. Frontier 5.x models are guaranteed only until about September 2027, so the 24-month gate D cannot be met by any single pinned model. By the research's own 'model upgrade resets the clean window' rule, an LLM-in-the-loop strategy can never reach the $10k gate. This strengthens the case for LLM-writes-code, rules-trade designs, where the traded logic does not depend on a model that will be retired.
- TOKEN COST IS UNDERSTATED: The 10k-in/1k-out Sonnet 5.5 example ignores adaptive thinking (default effort 'high', billed as output), retries, tool-use loops and agent context growth. Realistic daily agentic runs are 5-50x that cost. It also omits hosting (a $5/month VPS = $60/yr, so break-even capital at 3% excess is about $2,000), paid data, and the sunk design/research token spend the user asked to recoup. Use a free scheduler (for example cron on an existing machine or a CI free tier) and zero LLM calls at run time for the first live system.
- TAXES OMITTED: All acceptance criteria are pre-tax. For a US person, short-term gains from an active ETF rotation are taxed at ordinary income rates, versus deferred long-term gains for buy-and-hold, and wash-sale rules apply. For non-US persons: a 30% US dividend withholding (typically 15% with a treaty via W-8BEN), possible US estate-tax exposure on US-situs assets above $60k, and local capital-gains rules. A consumer-protection lawyer would insist the comparison with 'just buy an index fund' be made after tax and after all fees in the person's jurisdiction.
- 'JUST BUY SPY' AS A NAMED DEFAULT: This is jurisdiction-blind. EU/UK retail investors generally cannot buy US-domiciled ETFs like SPY or AGG because of PRIIPs KID rules, and SPY is not the cheapest S&P 500 vehicle even in the US (higher expense ratio than VOO or IVV). Phrase it as 'a low-cost, broad, diversified index fund available and tax-efficient in your jurisdiction'. Also note that naming specific securities to an inexperienced person edges toward personalized advice. Frame as education, not a recommendation.
- $1 LIVE TEST IGNORES FUNDING COSTS AND ACCOUNT FRICTIONS: Wire fees of $25 domestic and $50 international, FX spreads, and country-specific bank fees can exceed the $1 test by 25-100x. ACH is free only with a US bank. Alpaca's non-US eligibility varies by country. Before recommending Alpaca, confirm residency, eligibility, minimum deposit and the cheapest funding rail. A local broker with fractional shares may make a cheaper operational test.
- ETF-ONLY UNIVERSE HISTORY CLAIM: '20+ years of TR history' holds for SPY (1993), but AGG (2003), IEF (2002) and GLD (2004) barely cover 2008, and a small ETF universe mostly allows timing and allocation strategies, which historically rarely beat buy-and-hold after costs and taxes. Mutual-fund or index proxies are needed for longer history, with the caveat that proxies differ in costs and tracking. The data source (Yahoo rate-limited, stooq cut off) is still unresolved. Alpha Vantage free-tier limits and the correctness of its adjusted-close data must be verified before any backtest is trusted.
- PAPER-TRADING PARITY METRIC: A tracking difference below 10 bps/day computed against a total-return backtest will be contaminated on ex-dividend days, because Alpaca paper does not credit dividends. Compare on price returns, or add back dividends. The 20-day minimum is fine as a plumbing test, but it should include at least one rebalance, one market holiday and one early close to exercise the scheduling edge cases.
- PDT RULE CONTEXT: The research does not mention it. FINRA's $25k pattern-day-trader minimum was approved for elimination (SEC approval April 14, 2026, effective June 4, 2026, with broker phase-in until October 20, 2027). Brokers may still enforce the old rule during the phase-in. This matters only if intraday strategies are considered, and those should be excluded for this person anyway.
- 'PROOF' LANGUAGE: Passing DSR >= 0.95, PBO <= 0.2 and similar gates is evidence consistent with edge under stated assumptions. It is not proof of future profit. For a novice who explicitly asked for 'proof and merit', the deliverable should state the probability language plainly (for example, 'even a strategy that passes every gate has a meaningful chance of losing money over 1-3 years'), to avoid creating unjustified confidence. The PBO <= 0.2, ±25% plateau, 5-year-window and 3-10x scaling thresholds are the researcher's own judgement calls and should be labelled as such everywhere they appear.

## VERIFIER OVERALL

The statistical core of this research is reliable. Every cited paper exists and says what is claimed: Bailey et al. MinBTL, DSR, stop-out/triple penance, Harvey-Liu, Suhonen, McLean-Pontiff, Wiecki/CXO, Lopez-Lira, Gao-Jiang-Yan, Glasserman-Lin, Gençay, Alpaca docs and Anthropic model docs. I reproduced every number I checked independently: the SR-to-years table, the CI table, the zero-skill E[max] table, MinBTL(45)=5.0y, the difference-of-Sharpe spans, the MaxQL/TuW table and the CPCV path count.

Errors found:
- (1) DSR's SR0 is misdefined in the summary. The paper uses the empirical cross-trial variance of Sharpe ratios, not 1/sqrt(years).
- (2) The flat 50% haircut is attributed to Harvey-Liu, who explicitly reject it.
- (3) The Haiku SE is wrong: 0.94, not 0.85.
- (4) MinTRL is missing its leading '1 +'.
- (5) 'Pre-cutoff LLM backtests are uninformative' overstates the evidence. They are biased by an unknown amount, and no study tested Claude 5.x.
- (6) 'Most findings are false' (HLZ) is contested by Jensen-Kelly-Pedersen (JF 2023).

Material omissions:
- Haiku 4.5's retirement (not sooner than 2026-10-15) and frontier-model retirement around September 2027. These make the pinned-model 24-month gate unreachable and kill the Haiku forward-window idea.
- DSR/PBO do not detect look-ahead leakage (Gençay's leaky oracle passed both).
- Adaptive thinking makes the $0.03/day token example a floor, not an estimate.
- Hosting, taxes, and funding and wire fees are missing from the break-even. International wires are about $50 per BrokerChooser, which dwarfs a $1 test.
- The jurisdiction problem with 'just buy SPY' (PRIIPs, dividend withholding, estate tax).

What the orchestrator should weight down:
- The specific acceptance thresholds in section 8. They are judgement calls, internally inconsistent (A.5 vs A.6 vs A.9), and so low-powered that almost nothing will pass.
- The LLM cost example.
- The kill-switch rule, which is too loose for this person.
- Anything implying that an LLM-in-the-loop trader can ever be validated to the $10k stage.

What the orchestrator should weight up:
- The robust core conclusions. Weeks or months of paper trading prove only the plumbing, not edge. Backtests must be cost-aware, next-bar and survivorship-free with a trial ledger. LLMs should write and audit rule-based code rather than trade on judgement. The honest default outcome is likely a low-cost index fund, which costs almost nothing in tokens to run.
