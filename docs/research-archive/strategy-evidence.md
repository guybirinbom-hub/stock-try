# strategy-evidence

## SUMMARY

## Bottom line (skeptical read)

Across the evidence reviewed below, **no approach a beginner can run reliably beats a low-cost broad index fund on return after costs.** The approaches with the most credible evidence (long-horizon trend filters, diversified tactical asset allocation, factor tilts) mainly **change the risk profile**: they cut drawdowns sharply. They do not raise the long-run return, and all of them trailed the US equity index over 2006-2026. The approaches retail traders tend to be drawn to (day trading, intraday signals, ML price prediction on daily bars, LLM-as-trader, pairs and short-term reversal) have strong evidence of **failing** after costs for individuals.

Two consequences for this person:
- **The LLM cannot pay for itself.** With tiny capital, the expected *excess* profit is measured in cents, so an LLM must not sit in the run-time decision loop. Runtime should be deterministic code with near-zero token cost.
- **Paper trading cannot "prove" an edge on any short horizon.** Proof has to come from long, cost-inclusive, out-of-sample history plus an economic rationale. Paper and $1 trading can only prove that the plumbing works.

---

## 1. Benchmark: passive buy-and-hold of a broad index

- **Long-run returns.** S&P 500 total return, 1928-2025, computed from Damodaran's annual series (https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html, updated Jan 2026):
  - geometric mean **10.02%/yr**, arithmetic mean 11.86%/yr;
  - 3-month T-bills 3.37%/yr over the same years.
  - Real return is roughly **~7%/yr**, using ~3% average inflation (commonly cited; approximate).
- **Recent windows (same data, my arithmetic).**

  | Window | S&P 500 CAGR | US 60/40 (S&P / 10y Treasury) CAGR |
  |---|---|---|
  | 2006-2025 | 10.90% | 8.22% |
  | 2010-2025 | 14.00% | 9.53% |

  2014-2025 had an unusually strong US equity market, which is exactly the backdrop against which "post-publication" tactical strategies were judged.
- **Drawdowns (monthly total return, Ken French market factor, my computation):**
  - **-83.7%** in 1929-32;
  - **-50.3%** in 2007-09;
  - **-24.8%** worst drawdown in 2013-2026.

  Annual drawdowns from Damodaran: 2008 -36.6%, 2022 -18.0%.
- **Why it is hard to beat.** SPIVA year-end 2024: **89.5% of US large-cap active funds underperformed the S&P 500 over 15 years** (https://www.spglobal.com/spdji/en/documents/spiva/spiva-us-year-end-2024.pdf).
- **The behaviour gap.** DALBAR: the average equity fund investor trailed the S&P 500 by 848 bp in 2024 and by 72 bp in 2025 (https://www.prnewswire.com/news-releases/dalbars-2026-qaib-report-shows-narrower-investor-gap-amid-a-complex-and-volatile-market-year-302745998.html). DALBAR's method is industry-produced and criticised; treat its figures as indicative.
- **Implication.** Any system must be judged on **excess return over this benchmark, after costs and taxes**, not on absolute profit. A system that makes 8% while the index makes 11% is a loss of 3%/yr.

## 2. Trend-following / time-series momentum on ETFs

### Faber 10-month SMA (SSRN 962461; 2013 update PDF: https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf; summary numbers at CXO: https://www.cxoadvisory.com/technical-trading/long-term-outperformance-from-trends-defined-by-moving-averages/)

| Test | Period | Return (timing vs B&H) | Volatility | Sharpe | Max drawdown |
|---|---|---|---|---|---|
| S&P 500 timing | 1901-2012 | 10.2% vs 9.3% | 12.0% vs 17.9% | 0.55 vs 0.32 | -50.3% vs -83.5% |
| 5-asset GTAA | 1973-2012 | 10.5% vs 9.9% | 7.0% vs 10.3% | — | -9.5% vs -46.0% |

- Faber's paper states that the portfolio makes **"three to four round-trip trades per year… less than one round-trip trade per asset class per year"**, with **~70% turnover**, and is in the market roughly 70% of the time.
- Results are **gross of trading frictions, fund fees and taxes** (CXO caveat).

**My independent replication of the out-of-sample record** (Ken French US market total return, monthly; signal = prior month-end total-return index vs its 10-month SMA; 10 bp per switch; cash earns T-bills; data 1926-08/2026):

| Rule | Period | Strategy CAGR / vol / MDD | Buy-and-hold CAGR / vol / MDD | Switches per year |
|---|---|---|---|---|
| SMA10 | 1927-2005 | 9.63% / 13.0% / -43.1% | 10.01% / 19.1% / -83.7% | 1.48 |
| SMA10 | **2006-2026 (post-publication)** | **9.65% / 10.6% / -18.1%** | **11.33% / 15.5% / -50.3%** | 1.45 |
| SMA10 | 2013-2026 | 10.88% / 11.0% / -18.1% | 14.98% / 14.7% / -24.8% | 1.61 |
| 12-month absolute momentum (TSMOM on market vs T-bills) | 2006-2026 | 9.38% / 12.3% / -23.6% | 11.33% / 15.5% / -50.3% | 0.77 |

What the replication shows:
- The rule **cost about 1.7-4.1 percentage points per year versus buy-and-hold since publication**.
- It **did its advertised job on risk**: drawdown fell from -50% to -18%, volatility was about 30% lower, and Sharpe was similar or slightly better.
- It is a **drawdown-control tool, not a return enhancer**.

### Faber GTAA5 out-of-sample
- Concretum Group (practitioner; also sells research) extended GTAA5 over **Jan 2006-Mar 2025**, with 10 bp costs: **CAGR 6.05%, Sharpe 0.68, max drawdown 11.7%** (https://concretumgroup.substack.com/p/global-tactical-asset-allocation). No benchmark was reported.
- Against Damodaran's US 60/40 of about 8.2% over 2006-2025, **GTAA5 lagged by roughly 2 pts/yr but with much smaller drawdowns**. The comparison is approximate: different construction, and the 2025 window only runs to March.

### Antonacci dual momentum (GEM)
- Backtests look excellent: a practitioner compilation reports 1974-2013 at **17.43% CAGR, max drawdown 22.7%**.
- Post-publication 2014-2021 was **5.89% CAGR, 16.4% volatility, max drawdown 33.7%**. This comes from a LinkedIn blog (https://www.linkedin.com/pulse/dual-momentum-pre-post-publication-performance-abdennour-aissaoui); treat it as indicative.
- Robot Wealth's author noted in 2023 that GEM "has lagged B&H SPY for several years now" (https://robotwealth.com/dual-momentum-review/).
- **Fragility.** Newfound Research (https://blog.thinknewfound.com/2019/01/fragility-case-study-dual-momentum-gem/) found:
  - a 9-month lookback returned 43.1% in total versus 146.1% for a 10-month lookback over the same sample;
  - in 2010 the 10-month version made +12.2% while the 9-month version made -9.31%.

  Averaging the 6-12 month variants improved Sharpe and reduced drawdown. **Lesson: never trust a single parameter choice; use an ensemble.**

### Moskowitz-Ooi-Pedersen time-series momentum and its limits
- **Original finding.** Moskowitz-Ooi-Pedersen (JFE 2012, https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf) found TSMOM in all 58 liquid futures they studied.
- **Very long history.** Hurst-Ooi-Pedersen (JPM 2017, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026) report positive returns in every decade since 1880, and good performance in 8 of 10 major crises.
- **Skeptical counterpoint.** Huang, Li, Wang & Zhou (JFE 2020, https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html) find "little evidence of TSM" asset by asset. The strategy's profits look much like a strategy based on historical mean returns.
- **Live CTA record.** The SG Trend Index has returned **~4.9%/yr since 2000** and posted a -15% trailing 12-month loss in mid-2025 (https://www.toptradersunplugged.com/trend-following-performance-report-june-2025/). Managed-futures funds charge ~0.85%+.
- **Short-horizon trend has died.** Bouchaud et al. (arXiv 2607.01550, July 2026, https://arxiv.org/abs/2607.01550) report that "since approximately 2009, short-term trends have ceased to deliver reliable returns", while long-term trend held up.

### Volatility targeting
- Harvey et al. (JPM 2018, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538): volatility targeting improves Sharpe for **equity/credit**, not for other assets. It reduces left-tail events for all assets.
- Cederburg et al. (JFE 2020, https://www.ssrn.com/abstract=3357038): across 103 strategies, **real-time volatility-managed portfolios do not systematically beat unmanaged ones**.
- Conclusion: modest risk benefit at best, not alpha.

### Post-publication decay in general
- McLean & Pontiff (JF 2016, https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365): returns of 97 predictors are **26% lower out-of-sample and 58% lower post-publication**.
- A reasonable prior for any published strategy is therefore **roughly half the backtested edge, minus costs**.

## 3. Cross-sectional momentum and factor tilts (value, quality, low-vol)

**Long-short factor returns, Ken French data, my computation (gross, cannot be shorted by retail):**

| Factor | Before publication | After publication | Recent |
|---|---|---|---|
| UMD (momentum) | 1927-1992: 8.65%/yr, Sharpe 0.54 | 1993-2026: 4.80%/yr, Sharpe 0.29 | 2009-2026: **-0.84%/yr**; full-sample max drawdown **-78%** |
| HML (value) | 1926-1991: 5.02%/yr, Sharpe 0.39 | 1992-2026: 2.70%/yr | 2007-2026: **-1.31%/yr** |
| RMW (profitability) | 1963-2012: 3.34%/yr, Sharpe 0.43 | 2013-2026: 1.84%/yr, Sharpe 0.22 | — |
| 50/50 value + momentum | 1963-2012: Sharpe 0.80 | 2013-2026: **Sharpe 0.14** | — |

- **Momentum crashes.** Daniel & Moskowitz (JFE 2016, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227): momentum lost about three-quarters of its value in 2009, and about 91% in Jun-Aug 1932.
- **Value's drought.** Value had a 13-year, **55% drawdown to mid-2020**, the largest since 1963 (Arnott et al., FAJ 2021, https://www.tandfonline.com/doi/full/10.1080/0015198X.2020.1842704).
- **Is the factor literature real? Evidence on both sides.**
  - Hou-Xue-Zhang (RFS 2020, https://academic.oup.com/rfs/article-abstract/33/5/2019/5236964): **65% of 452 anomalies fail |t|>1.96** once microcaps are controlled, and 82% fail t>2.78.
  - Harvey-Liu-Zhu (RFS 2016, https://academic.oup.com/rfs/article/29/1/5/1843824): new factors should clear t>3.
  - Jensen-Kelly-Pedersen (JF 2023, https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13249): most factors replicate and work in 93 countries.
  - Net read: a **handful of broad themes (value, momentum, quality/profitability, low-risk) are probably real but small and cyclical**.
- **Costs.** Novy-Marx & Velikov (RFS 2016, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2535173): anomalies with **<50% monthly one-sided turnover mostly survive costs, and few with higher turnover do**. Frazzini-Israel-Moskowitz (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719): value and momentum are implementable for institutions, while short-term reversal is the most cost-constrained.
- **Implementation for retail.**
  - Use **long-only factor ETFs**. Example: MTUM, 0.15% expense ratio; a practitioner site reports ~16.2-16.5%/yr over 10 years vs ~13.6-15.0%/yr for the S&P, which is unverified from the fact sheet and has a short, momentum-friendly window.
  - Single-stock factor portfolios with tiny capital need fractional shares and 20-50 names. The cost is fine at commission-free brokers, but tax, complexity and data (point-in-time fundamentals, delisted stocks) are hard for a beginner.
  - Expect **0 to +2%/yr** vs the market over decades, with **multi-year stretches of underperformance**.

## 4. Mean reversion: short-term reversal and pairs trading

- **Pairs trading decay.**
  - Gatev-Goetzmann-Rouwenhorst (RFS 2006, https://academic.oup.com/rfs/article-abstract/19/3/797/1646694): up to 11% annualized excess return, 1962-2002.
  - Do & Faff (FAJ 2010, https://www.tandfonline.com/doi/abs/10.2469/faj.v66.n4.1): top-20 pairs fell from **0.86%/month (1962-88) to 0.37% (1989-2002) to 0.24% (2003-09)**, before the extra costs of shorting.
- **Short-term reversal.** de Groot-Huij-Zhou (JBF 2012, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1605049) find 30-50 bp/week net, but only when restricted to large caps, with institutional cost models and optimized turnover.
- **Why retail struggles:**
  - the strategies need shorting (borrow fees, margin; not possible with $1);
  - turnover is weekly or daily, so spread and slippage dominate;
  - edges are crowded and eroded by HFT and market makers.
- **Verdict: not suitable.**

## 5. ML price prediction on daily bars

- **LSTM on S&P 500 stocks.** Fischer & Krauss (EJOR 2018, https://www.sciencedirect.com/science/article/abs/pii/S0377221717310652) report 0.46%/day **before costs**, Sharpe 5.8, 1992-2015. Performance **deteriorated sharply after 2010**, and follow-ups found <0.1%/day after 2008 (https://arxiv.org/pdf/2201.08218). Daily long-short turnover at retail spreads would erase this.
- **Deep learning on the cross-section.** Avramov-Cheng-Metzker (Management Science 2023, https://pubsonline.informs.org/doi/10.1287/mnsc.2022.4449) find the profit comes from **microcaps, distressed stocks and high-volatility episodes**. Excluding these "considerably attenuates profitability", and it "further deteriorates in the presence of reasonable trading costs".
- **LLM trading strategies.** FINSABER (KDD 2026, https://arxiv.org/abs/2505.07078) tested over 20 years and 100+ symbols. It found that "previously reported LLM advantages deteriorate significantly"; the LLM strategies were too conservative in bull markets and too aggressive in bear markets.
- **LLM news signals.** Lopez-Lira & Tang (https://arxiv.org/abs/2304.07619) find GPT-4 news signals predict drift mainly in **small stocks and negative news**, and "strategy returns decline as LLM adoption rises". These are also high-turnover and costly in tokens.
- **Verdict:** no credible evidence of after-cost profitability for a retail daily-bar ML or LLM predictor.

## 6. Retail day trading and intraday strategies

- **US discount-broker households.** Barber & Odean (JF 2000, https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00226) studied 66,465 households in 1991-96. The most active traders earned **11.4%/yr vs 17.9% for the market**.
- **Taiwan day traders, 1992-2006.**
  - Barber-Lee-Liu-Odean (JFM 2014, https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf): "**Less than 1% of the day trader population is able to predictably and reliably earn positive abnormal returns net of fees.**"
  - The companion learning paper finds "the vast majority of day traders are unprofitable" and many persist despite losses (https://faculty.haas.berkeley.edu/odean/papers/Day%20Traders/Day%20Trading%20and%20Learning%20110217.pdf).
- **Brazil mini-index futures, 2013-2015.** Chague, De-Losso & Giovannetti (https://ideas.repec.org/p/spa/wpaper/2019wpecon47.html): of those who persisted at least 300 days, "**97% of them lost money, only 0.4% earned more than a bank teller**", and there was no evidence of learning.
- **EU CFDs.** Retail regulators found **74-89% of retail CFD accounts lose money** (https://www.esma.europa.eu/press-news/esma-news/esma-agrees-prohibit-binary-options-and-restrict-cfds-protect-retail-investors).
- **Also:** short-term trend stopped paying after ~2009 (Bouchaud et al., above).
- **Verdict: avoid.**

## 7. Base rates for retail algo and quant hobbyists

- **Quantopian backtests vs live.** Wiecki et al. (J. Investing 2016, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2745220) studied 888 algorithms with at least 6 months out-of-sample:
  - backtest Sharpe predicted live Sharpe with **R² < 0.025**;
  - **the more backtests a user ran, the larger the gap** between backtest and live performance, which is direct evidence of overfitting.
- **Quantopian's own fund.** Quantopian's crowdsourced fund underperformed. It returned outside capital in Feb 2020 and the company shut down later in 2020 (https://en.wikipedia.org/wiki/Quantopian).
- **Tools against overfitting.** Bailey, Borwein, López de Prado & Zhu (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253) formalize the probability of backtest overfitting and minimum backtest length.
- **No hard base rate exists.** I found no peer-reviewed figure for "% of retail algo traders who profit". Figures on marketing blogs (e.g., "90-95% fail") are unsourced. The closest hard evidence is the day-trader data above (under 1-3% reliably profitable) and the Quantopian result that backtests do not predict live results.

## 8. Crypto spot trend-following (BTC/ETH)

- **Academic support for trend.** Liu & Tsyvinski (RFS 2021, https://academic.oup.com/rfs/article-abstract/34/6/2689/5912024) document strong time-series momentum in crypto.
- **Practitioner backtest.** Zarattini-Pagani-Barbon (SSRN 5209907, Apr 2025, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907) test an ensemble of Donchian channels with volatility sizing on the top-20 coins, survivorship-free, 2015-2025: **Sharpe ~1.58 and CAGR ~30% net of 0.10-0.50% fees**. This is a backtest from a firm that sells research; there is no live record.
- **Extreme results to discard.** Rozario et al. (arXiv 2009.12155) report 255%/yr walk-forward from bitcoin's infancy. That is not representative.
- **Risks.**
  - Buy-and-hold drawdowns: BTC about **-77%** (Nov 2021-Nov 2022), ETH about -80% (https://insights.glassnode.com/2022-bear-of-historic-proportions/).
  - BIS (Bulletin 69, Feb 2023, https://www.bis.org/publ/bisbull69.htm): **a majority of crypto-app users in nearly all economies lost money on bitcoin**; 73-81% by their estimate.
  - Exchange/custody risk, 24/7 gap risk, and fees of 0.1-0.6% per trade at retail venues.
- **Verdict.** The trend evidence is real but based on a short sample. Suitable only as a small, clearly labeled experimental sleeve, never the core.

## Proof and statistics: why "prove it with paper money" has limits

The t-statistic of an excess return is roughly `(alpha / tracking error) × sqrt(years)`.

- For alpha = 2%/yr, tracking error = 10%/yr and a target of t = 2: years = `(2 × 0.10 / 0.02)² = 100 years`.
- With tracking error = 5%: `(2 × 0.05 / 0.02)² = 25 years`.

So **months of paper trading cannot statistically confirm an edge**. They can only confirm that the execution works and that live fills match the backtest. Evidence of merit must come from:
- long, cost-inclusive, out-of-sample history (e.g., post-publication periods);
- robustness across parameters and markets;
- an economic rationale.

## Token and cost economics (why the LLM must not trade)

Example: one Sonnet 5.5 decision call with 5K input + 500 output tokens.

- Cost per call: `5,000 × $2/1M + 500 × $10/1M = $0.015`.
- Monthly cadence: `12 × $0.015 = $0.18/yr`.
- Daily cadence: `252 × $0.015 = $3.78/yr`.
- On **$1** of capital, a +2%/yr edge earns **$0.02/yr**. Even a monthly LLM call costs 9× the expected edge.
- Break-even capital for daily Sonnet calls at a 2% edge: `$3.78 / 0.02 = $189`. That assumes the edge exists, which for most approaches is doubtful.

Conclusion: **runtime decisions must be deterministic code (zero tokens)**. Use the LLM only for design, code review and occasional reporting, paid by the human as a research cost, not charged to trading profit.

## Scaling

- For the recommended ETF strategies, **market capacity is not a constraint** at personal scale. SPY-class ETFs trade tens of billions per day, and Frazzini et al. show value and momentum are scalable even for institutions.
- The real scaling risks:
  - **taxes**: trend rules turn over ~70%/yr vs ~20% for buy-and-hold (Faber);
  - **behaviour**: abandoning the rule during multi-year lag;
  - **tiny-capital frictions**: fractional share minimums, rounding, and fixed fees if not commission-free.

These can be tested explicitly by simulating the same rule at $1, $1k and $100k with realistic fees and rounding.

---

## Ranked shortlist for a beginner (tiny capital, deterministic daily/monthly cadence)

**1. Buy-and-hold a broad, low-cost index ETF (the benchmark itself)**
- *Why defensible:* 98 years of data (~10% nominal, ~7% real). It beats about 90% of professionals over 15 years (SPIVA).
- *Expected vs benchmark:* 0 minus the fee (0.03-0.2%/yr).
- *Main risks:* 50-84% drawdowns and behavioural capitulation.
- *Data:* none needed to run it; monthly prices only to report.
- *Decisions per year:* 0-12 (contributions).
- *Note:* choose a domicile-appropriate fund (US ETF vs UCITS) based on residency and tax.

**2. Long-horizon trend filter on a broad index (10-month SMA or 12-month absolute momentum, averaged over several lookbacks)**
- *Why defensible:* 100+ years of evidence and it survived post-publication at its stated job. In my replication, drawdown went from -50% to -18% over 2006-2026.
- *Expected vs benchmark:* about **-2 to 0%/yr** in strong bull markets (-1.7%/yr over 2006-2026; -4.1%/yr over 2013-2026). Possibly positive in prolonged bear markets.
- *Main risks:* whipsaw, tax drag, and lagging in V-shaped rebounds (2020).
- *Data:* monthly adjusted closes plus a T-bill rate.
- *Decisions per year:* 12 checks, about 1-1.5 switches.

**3. Diversified multi-asset tactical allocation (Faber GTAA5-style; or an equal blend of several published TAA rules and lookbacks)**
- *Why defensible:* the simplest rules, low turnover, and a transparent out-of-sample record: 2006-Mar 2025 CAGR 6.05%, Sharpe 0.68, max drawdown 11.7%.
- *Expected vs benchmark:* about **-2 to -5%/yr vs the S&P 500** and about -2%/yr vs a 60/40 in the post-2006 US-led market, with 1/3-1/4 of the drawdown.
- *Main risks:* long relative underperformance and parameter fragility (mitigate with ensembles).
- *Data:* monthly adjusted prices for 5-10 ETFs plus T-bills.
- *Decisions per year:* 12 rebalances, about 3-4 round trips.

**4. Passive factor tilt via ETFs (multi-factor or momentum/quality), rebalanced 1-4× per year**
- *Why defensible:* factor premia are replicable (JKP 2023) and low-turnover factors survive costs (Novy-Marx & Velikov).
- *Expected vs benchmark:* **0 to +2%/yr** long-run, with multi-year negative stretches. In my French-data computation, value was negative since 2007 and momentum flat since 2009.
- *Main risks:* post-publication decay (about -58%) and momentum crashes.
- *Data:* ETF prices only.
- *Decisions per year:* 1-4.

**5. (Experimental sleeve only, at most a few % of capital) Crypto BTC/ETH long-or-cash trend ensemble**
- *Why defensible:* academic TSMOM evidence (Liu-Tsyvinski) and it is accessible 24/7 with tiny sizes.
- *Expected:* highly uncertain. Backtest Sharpe was ~1.5, but live results will be far lower.
- *Main risks:* -77% crashes if the filter lags, exchange risk, and fees of 0.1-0.6% per trade.
- *Data:* daily closes.
- *Decisions per year:* 52-365 checks, about 5-20 switches.

**Reject:** day and intraday trading; ML or LLM price prediction on daily bars; pairs and short-term reversal; any LLM-in-the-loop trading at small capital.

## CLAIMS

- **[C1] (high)** S&P 500 total return 1928-2025 compounded at ~10.0%/yr nominal (arithmetic 11.9%); T-bills 3.4%/yr; 2006-2025 S&P CAGR 10.9% vs US 60/40 8.2%.
  - evidence: Computed geometric mean from Damodaran's annual return table (98 years, 1928-2025).
  - sources: https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html
- **[C2] (high)** Faber's 10-month SMA timing improved risk-adjusted returns historically (S&P 1901-2012: 10.2% vs 9.3%, max drawdown -50.3% vs -83.5%; 5-asset 1973-2012: 10.5% vs 9.9%, max drawdown -9.5% vs -46%), gross of costs, with 3-4 round-trips per year and ~70% turnover.
  - evidence: CXO Advisory summary of the Feb 2013 update; turnover text quoted from the paper PDF.
  - sources: https://www.cxoadvisory.com/technical-trading/long-term-outperformance-from-trends-defined-by-moving-averages/, https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf
- **[C3] (medium)** Post-publication (2006-2026), a 10-month SMA filter on the US market returned ~9.65%/yr vs 11.33% buy-and-hold (about -1.7 pts/yr) but cut max drawdown from -50.3% to -18.1%; over 2013-2026 it lagged by ~4.1 pts/yr.
  - evidence: My replication on Ken French monthly market plus risk-free data (through 2026-08), 10 bp per switch, signal lagged one month; ~1.5 switches per year.
  - sources: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- **[C4] (medium)** Faber GTAA5 out-of-sample Jan 2006-Mar 2025 delivered CAGR 6.05%, Sharpe 0.68, max drawdown 11.7% after 10 bp costs, which is below a US 60/40 (~8.2%) and far below the S&P 500 (~10.9%) over similar years.
  - evidence: Concretum Group extension (practitioner source; no benchmark reported); benchmark computed from Damodaran data.
  - sources: https://concretumgroup.substack.com/p/global-tactical-asset-allocation, https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/histretSP.html
- **[C5] (medium)** Dual momentum GEM is highly parameter-fragile: 9-month vs 10-month lookback produced 43.1% vs 146.1% total return, and a 21.5-point gap in 2010. Post-publication it lagged (2014-2021 CAGR 5.89%, max drawdown 33.7% per a blog analysis).
  - evidence: Newfound Research case study; LinkedIn post-publication analysis (blog, lower reliability); Robot Wealth 2023 comment that GEM lagged SPY.
  - sources: https://blog.thinknewfound.com/2019/01/fragility-case-study-dual-momentum-gem/, https://www.linkedin.com/pulse/dual-momentum-pre-post-publication-performance-abdennour-aissaoui, https://robotwealth.com/dual-momentum-review/
- **[C6] (high)** Published anomaly returns are 26% lower out-of-sample and 58% lower post-publication.
  - evidence: McLean & Pontiff, Journal of Finance 2016, 97 predictors.
  - sources: https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2156623
- **[C7] (medium)** Factor premia have weakened sharply after publication: UMD momentum averaged 8.65%/yr (Sharpe 0.54) in 1927-1992 vs 4.80%/yr after 1993 and -0.84%/yr in 2009-2026; HML value averaged -1.31%/yr in 2007-2026; a 50/50 value+momentum combination's Sharpe fell from 0.80 (1963-2012) to 0.14 (2013-2026).
  - evidence: My computation from Ken French factor files (created from the 202608 CRSP database); long-short gross returns.
  - sources: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227
- **[C8] (high)** Anomalies with under 50% monthly one-sided turnover mostly survive transaction costs; few higher-turnover strategies do.
  - evidence: Novy-Marx & Velikov, RFS 2016.
  - sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2535173
- **[C9] (high)** Pairs trading profits decayed from 0.86%/month (1962-88) to 0.24%/month (2003-09) for top-20 pairs.
  - evidence: Do & Faff, Financial Analysts Journal 2010.
  - sources: https://www.tandfonline.com/doi/abs/10.2469/faj.v66.n4.1
- **[C10] (high)** ML stock-prediction profits concentrate in microcaps, distressed stocks and high-volatility periods, and deteriorate further after reasonable trading costs; an LSTM daily S&P 500 strategy (0.46%/day before costs) decayed after 2010.
  - evidence: Avramov-Cheng-Metzker, Management Science 2023; Fischer & Krauss, EJOR 2018 and follow-up replications.
  - sources: https://pubsonline.informs.org/doi/10.1287/mnsc.2022.4449, https://www.sciencedirect.com/science/article/abs/pii/S0377221717310652, https://arxiv.org/pdf/2201.08218
- **[C11] (high)** LLM-based timing strategies' reported advantages deteriorate significantly over 20 years and 100+ symbols; they underperform passive benchmarks in bull markets and lose heavily in bear markets.
  - evidence: FINSABER, KDD 2026 (arXiv 2505.07078 v6, June 2026).
  - sources: https://arxiv.org/abs/2505.07078
- **[C12] (high)** Retail day traders overwhelmingly lose. In Taiwan (1992-2006), less than 1% predictably earn positive net abnormal returns. In Brazil (2013-2015), 97% of those persisting 300+ days lost money and only 0.4% out-earned a bank teller. US households that traded most earned 11.4% vs 17.9% for the market.
  - evidence: Barber-Lee-Liu-Odean JFM 2014 abstract (extracted from PDF); Chague-De-Losso-Giovannetti abstract; Barber & Odean JF 2000.
  - sources: https://faculty.haas.berkeley.edu/odean/papers/day%20traders/The%20Cross-Section%20of%20Speculator%20Skill.pdf, https://ideas.repec.org/p/spa/wpaper/2019wpecon47.html, https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00226
- **[C13] (high)** On 888 Quantopian algorithms, backtest Sharpe predicted out-of-sample Sharpe with R² < 0.025, and more backtesting led to larger in-sample vs out-of-sample gaps.
  - evidence: Wiecki et al., Journal of Investing 2016.
  - sources: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2745220, https://quantpedia.com/quantopians-academic-paper-about-in-vs-out-of-sample-performance-of-trading-alg/
- **[C14] (medium)** A majority of retail crypto-app users in nearly all economies lost money on bitcoin (Aug 2015-Dec 2022). BTC fell about 77% peak-to-trough in 2021-22. A survivorship-free crypto trend backtest reports Sharpe ~1.58 net of fees (2015-2025), but it is a vendor backtest with no live record.
  - evidence: BIS Bulletin 69; Glassnode; Zarattini-Pagani-Barbon SSRN 5209907.
  - sources: https://www.bis.org/publ/bisbull69.htm, https://insights.glassnode.com/2022-bear-of-historic-proportions/, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5209907

## RECOMMENDATIONS

- Adopt buy-and-hold of a broad low-cost index ETF as the mandatory benchmark. Every candidate system must report CAGR, max drawdown, Sharpe and tracking difference against it, after costs and (where known) taxes, not absolute profit.
- Make runtime decisions 100% deterministic code (a monthly-close rule) with zero LLM calls. Use Claude only for design, code review and a quarterly human-readable report. At $1 of capital, even one Sonnet call per month (~$0.18/yr) exceeds the plausible edge (~$0.02/yr at +2%).
- Primary candidate to build and paper-trade: a long-horizon trend filter on a broad equity ETF, using an ensemble of lookbacks (e.g., the average of 6-12 month absolute-momentum and 10-month SMA signals), checked monthly, falling back to a T-bill/short-Treasury ETF. Present it honestly as drawdown control, expected to lag in bull markets.
- Secondary candidate: a GTAA5-style multi-asset trend portfolio (US stocks, intl stocks, bonds, REITs, commodities; each held only when above its 10-month SMA), monthly rebalance, again as an ensemble of lookbacks to reduce the parameter fragility documented for GEM.
- Backtest rules the honest way: signal on month-end close, trade at the next open or close, 10-20 bp per trade plus the ETF expense ratio, dividends reinvested, cash earning T-bills. Test on the post-publication period (2006+) separately from pre-publication, and report parameter-sensitivity heatmaps rather than a single best parameter.
- Tell the user explicitly that paper trading or $1 trading validates plumbing and execution, not edge. Detecting a 2%/yr edge at 5-10% tracking error needs about 25-100 years of data. Rely on long out-of-sample history plus rationale, and set a pre-registered kill rule (e.g., stop if live tracking error vs backtest exceeds a threshold).
- For scaling assurance, simulate the identical rule at $1, $1k and $100k with fractional-share rounding, broker minimums and fees. For liquid ETFs, market impact is negligible at personal scale; tax drag (~70% turnover) is the main scaling cost, so prefer a tax-advantaged account where the user's jurisdiction allows.
- Do not build day-trading, intraday, pairs or short-term-reversal systems, ML or LLM daily price predictors, or leveraged/CFD products. The evidence shows under 1-3% of retail participants profit reliably and ML edges vanish after costs outside microcaps.
- If crypto is explored, cap it at a small labeled experimental sleeve using a BTC/ETH long-or-cash trend ensemble with daily checks. Budget for 0.1-0.6% per-trade fees and exchange risk, and treat vendor backtests (Sharpe ~1.5) as heavily optimistic.
- Confirm the user's country of residence before choosing instruments. US-listed ETFs may be unavailable or tax-inefficient for non-US residents (e.g., EU PRIIPs/KID rules favor UCITS ETFs), and capital-gains treatment of frequent switching varies by jurisdiction.

## OPEN QUESTIONS

- AllocateSmartly's per-strategy out-of-sample (post-publication) tables are behind its site and could not be fetched. An independent post-2014 GEM and GTAA5 record with a matched 60/40 benchmark (same data and costs) still needs to be computed from ETF price data once a working price source is confirmed.
- My SMA10/TSMOM replication uses the CRSP total-return market index with a signal on the total-return series; Faber used price-based SMAs on specific indices. Results with real ETFs (SPY/VTI), bid-ask spreads and dividend timing may differ by tens of basis points per year.
- Verified MTUM/QUAL/USMV fact-sheet returns vs the S&P 500 could not be extracted (the PDF was unreadable via fetch). The factor-ETF live track records since 2013 remain unverified from primary sources.
- No peer-reviewed base rate exists for the profitability of retail algorithmic traders specifically, as opposed to day traders; QuantConnect has published no community-wide out-of-sample statistics that I found.
- The crypto trend evidence rests largely on backtests (a 2015-2025 sample with extreme early-bitcoin returns); there is no independent live or out-of-sample track record for a simple BTC/ETH trend ensemble after retail fees and taxes.
- The user's country of residence determines instrument availability (US ETFs vs UCITS), tax drag of trend-rule turnover, and whether fractional shares at ~$1 are available. This materially changes the after-tax ranking between buy-and-hold and trend rules.
- Whether a volatility-targeted variant of the trend filter adds value in real time for a single broad ETF is unresolved: Harvey et al. 2018 are positive for equities, while Cederburg et al. 2020 are negative out-of-sample across 103 strategies.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** S&P 500 total return 1928-2025 compounded at ~10.0%/yr nominal (arithmetic 11.9%); T-bills 3.4%/yr; 2006-2025 S&P CAGR 10.9% vs US 60/40 8.2%.
  - reasoning: I downloaded Damodaran's histretSP.xls (dated 2026-01-01), sheet 'Returns by year', and recomputed 1928-2025 (98 years): geometric 10.02%, arithmetic 11.85%, 3-month T-bill geometric 3.37%. For 2006-2025: S&P 10.90% and 60/40 8.22%. For 2010-2025: S&P 13.99% and 60/40 9.53%. My 60/40 is annually rebalanced 60% S&P / 40% 10-year Treasury, which matches the claim. The '~7% real' figure is approximate and was not verified. One caveat for how it is used: a US 60/40 is the wrong benchmark for global multi-asset strategies such as GTAA5 (see C4).
- **[C2] CONFIRMED** Faber 10-month SMA timing improved risk-adjusted returns historically (S&P 1901-2012: 10.2% vs 9.3%, MDD -50.3% vs -83.5%; 5-asset 1973-2012: 10.5% vs 9.9%, MDD -9.5% vs -46%), gross of costs, 3-4 round-trips/yr, ~70% turnover.
  - reasoning: CXO quotes: S&P SMA10 10.2% (9.3%), SD 12.0% (17.9%), Sharpe 0.55 (0.32), MDD -50.3% (-83.5%). 5-asset: 10.5% (9.9%), SD 7.0% (10.3%), Sharpe 0.73 (0.44), MDD -9.5% (-46.0%). All returns are 'gross of trading frictions'. The research left the GTAA Sharpe blank; it is 0.73 vs 0.44. The Faber PDF text says 'three to four round-trip trades per year for the portfolio and less than one round-trip trade per asset class per year' and 'The system has a turnover of almost 70%'. Two nuances. (a) The 'invested ~70% of the time' figure refers to the single-asset S&P timing model; the 3-4 round-trips refer to the 5-asset portfolio. (b) The same Faber page cites Gannon & Blum: raising turnover from 20% to 70% cost 'less than 50 basis points' after tax. That weakens the research's later statement that tax drag is 'the main scaling cost'. Both sets of numbers are in-sample for the paper, and even the 1973-2012 portfolio test overlaps the original 2006 publication.
- **[C3] NEEDS_QUALIFICATION** Post-publication (2006-2026) a 10-month SMA filter on the US market returned ~9.65%/yr vs 11.33% B&H (-1.7 pts) with MDD -18.1% vs -50.3%; 2013-2026 lagged ~4.1 pts/yr.
  - reasoning: I replicated this exactly on Ken French monthly data (file built from the 202608 CRSP database). Signal: prior month-end total-return index vs its 10-month mean. Cost: 10 bp per switch. Cash earns RF. Results:
- 2006-01 to 2026-08: strategy 9.65% CAGR, vol 10.6%, MDD -18.1%; buy-and-hold 11.33%, 15.5%, -50.3%; 1.45 switches/yr.
- 2013-2026: 10.88% vs 14.98%.
- 1927-2005: 9.59% vs 9.97%. The research reports 9.63%/10.01%, a trivial difference.
- 12-month TSMOM 2006-2026: 9.38%, MDD -23.6%, 0.77 switches/yr.

Caveats the research omits:
(1) The drawdown benefit rests almost entirely on two years. By calendar year the rule beat buy-and-hold only in 2008 (+1.6% vs -36.7%) and 2022 (-10.9% vs -19.9%). It tied or lagged in every other year, e.g. 2010 +0.2% vs +17.4%, 2019 +8.9% vs +30.6%, 2023 +9.2% vs +26.7%.
(2) Excess-return Sharpe was 0.76 vs 0.66 over 2006-2026 but 0.84 vs 0.91 over 2013-2026, i.e. worse in the recent window.
(3) Tracking error vs buy-and-hold is about 10-11.5%/yr, so the result is statistically indistinguishable from zero alpha.
(4) The signal uses a CRSP total-return index; Faber's rule uses price. Real ETF results with spreads and dividend timing will differ.
(5) Contrary evidence: Kurth, Eisler, Rej & Bouchaud (arXiv 2607.01550) find post-2008 trend PnL 'collapsed on small-tick contracts across all signal horizons', and they place equity index futures in the small-tick tier. The research quoted only the 'short-term trend died' half of that paper.
  - corrected: Replication confirmed: 2006-01 to 2026-08, SMA10 on the US market returned 9.65% vs 11.33% buy-and-hold, with MDD -18.1% vs -50.3%, and lagged by 4.1 pts/yr over 2013-2026. However, the entire risk benefit came from 2008 and 2022, excess Sharpe was lower than buy-and-hold over 2013-2026, and tracking error of ~11% makes any alpha statistically undetectable. The latest microstructure evidence (Bouchaud et al. 2026) says trend PnL on equity-index futures degraded at all horizons after 2008.
- **[C4] NEEDS_QUALIFICATION** Faber GTAA5 out-of-sample Jan 2006-Mar 2025: CAGR 6.05%, Sharpe 0.68, MDD 11.7% after 10 bp costs, below US 60/40 (~8.2%) and far below the S&P 500 (~10.9%).
  - reasoning: The Concretum post (dated June 23, 2026) confirms: 'January 2006 through March 2025', Sharpe 0.68, CAGR 6.05%, MDD 11.7%, 10 bp on every notional traded (about 41 bp/yr drag), using SPY/EFA/IEF/DBC/VNQ with SHV as cash. Its in-sample figures for 1972-2005 were 11.7% CAGR and Sharpe 0.81, which shows large decay.

The research omits a critical finding from the same post: 'Nearly 220 basis points of CAGR difference between the best and worst rebalancing day'. That rebalance-timing luck is as large as the gap the research attributes to the strategy. Tranched weekly rebalancing cut it to 63 bp and roughly halved turnover.

The benchmark is mismatched. GTAA5 is a global five-asset portfolio (20% each, including commodities via DBC and REITs), so its proper benchmark is the equal-weight buy-and-hold of the same five ETFs, not a US 60/40. DBC and EFA did poorly after 2006, so GTAA5 may well have beaten its own passive benchmark on both return and risk. The research's framing ('lagged by 2 pts') mixes asset-allocation beta with timing skill. The periods also differ (through Mar 2025 vs through Dec 2025).
  - corrected: Concretum (June 2026, practitioner) reports GTAA5 over Jan 2006-Mar 2025 at CAGR 6.05%, Sharpe 0.68, MDD 11.7% after 10 bp costs, down from 11.7% CAGR in-sample. Performance swung by about 220 bp/yr depending only on which day of the month it rebalanced. It trailed a US 60/40 and the S&P 500, but those are not matched benchmarks: the relevant comparison, equal-weight buy-and-hold of SPY/EFA/IEF/DBC/VNQ, was not computed.
- **[C5] NEEDS_QUALIFICATION** Dual momentum GEM is parameter-fragile (9m vs 10m lookback 43.1% vs 146.1%; 21.5-pt gap in 2010); post-publication it lagged (2014-2021 CAGR 5.89%, MDD 33.7% per blog). Robot Wealth author noted in 2023 that GEM lagged SPY.
  - reasoning: What checks out:
- Newfound: 2010 returns of +12.2% (10-month) vs -9.31% (9-month), a 21.5-pt gap; totals of 43.1% vs 146.1%. Equal-weighting seven lookbacks gave 'a boost to realized Sharpe ratio, and a reduction in the maximum realized drawdown'.
- LinkedIn blog: 1974-2013 GEM '17.43% annual return, 12.64% standard deviation... maximum drawdown of 22.72%'; 2014-2021 '5.89%... 16.36%... 33.72%'. It reports no benchmark numbers.

What is wrong: the research misattributes the Robot Wealth quote. 'It's lagged B&H SPY for several years now' is a reader comment by Joseph Reeves (Sept 26, 2023). The author, Kris Longmore, did not confirm it; he said he had not examined the strategy recently.

Independently, the lag is real. Damodaran S&P 500 2014-2021 compounds to about 14.6%/yr (my arithmetic from annual returns: product 2.98, 8 years), against GEM's 5.89%. Also, the 1974-2013 figure is Antonacci's own backtest, largely in-sample.
  - corrected: GEM is parameter-fragile (Newfound: 9-month vs 10-month lookback 43.1% vs 146.1% total; 2010 +12.2% vs -9.31%). A blog reports 2014-2021 CAGR 5.89% (MDD 33.7%) vs about 14.6%/yr for the S&P 500 over the same years (Damodaran). The 'lagged SPY' remark on Robot Wealth is a reader comment, not the author's finding.
- **[C6] CONFIRMED** Published anomaly returns are 26% lower out-of-sample and 58% lower post-publication.
  - reasoning: This is the abstract finding of McLean & Pontiff (JF 2016) across 97 predictors. One caveat on use: the research turns it into 'a reasonable prior of roughly half the backtested edge, minus costs'. The 58% refers to long-short anomaly returns in academic portfolios, not to retail implementations, which lose further to fees and the long-only constraint. The GTAA5 decay (11.7% to 6.05% CAGR) and the GEM decay are consistent with it.
- **[C7] CONFIRMED** UMD averaged 8.65%/yr (Sharpe 0.54) 1927-1992 vs 4.80% after 1993 and -0.84% 2009-2026; HML -1.31% 2007-2026; 50/50 value+momentum Sharpe 0.80 (1963-2012) to 0.14 (2013-2026).
  - reasoning: I recomputed from the French files (202608 build). Figures are arithmetic annualized means:
- UMD 1927-1992: 8.65%, Sharpe 0.537. 1993-2026-08: 4.80%, Sharpe 0.29. 2009-2026: -0.84%. Full-sample MDD -78.4%.
- HML 1926-1991: 5.02%, Sharpe 0.39. 1992-2026: 2.70%. 2007-2026: -1.31%.
- RMW 1963-2012: 3.34%, Sharpe 0.43. 2013-2026: 1.84%, Sharpe 0.22.
- 50/50 HML+UMD: Sharpe 0.80, then 0.14.

Qualifications:
(a) These are arithmetic means. CAGRs are lower: UMD 2009-2026 is -2.19%/yr and HML 2007-2026 is -1.95%/yr. The summary's phrase 'momentum flat since 2009' understates this; it was negative.
(b) These are gross long-short, value-weighted academic portfolios, not investable by retail.
(c) Daniel & Moskowitz crash figures refer to decile WML, not UMD: UMD lost 49% in Mar-May 2009 and 74% in Jun-Aug 1932. The '~91% Jun-Aug 1932' in the text is the D&M decile figure, which I recall as July-August 1932; the SSRN page was not accessible (HTTP 403).
- **[C8] CONFIRMED** Anomalies with under 50% monthly one-sided turnover mostly survive transaction costs; few higher-turnover strategies do.
  - reasoning: This matches the Novy-Marx & Velikov abstract: 'Most anomalies with one-sided monthly turnover less than 50% continue to generate significant spreads... while few of the higher turnover strategies do.' Caveats: it uses effective-spread cost estimates for long-short academic portfolios, not retail long-only ETFs, and 'significant spreads' is not the same as beating a cap-weighted index after ETF fees.
- **[C9] NEEDS_QUALIFICATION** Pairs trading profits decayed from 0.86%/month (1962-88) to 0.24%/month (2003-09) for top-20 pairs.
  - reasoning: The tandfonline page returned 403. The Bond University repository abstract confirms 'continuing downward trend in profitability' and strong performance in turbulent periods, but it does not contain the 0.86/0.37/0.24 figures, so I could not verify those subperiod numbers. They are plausible and consistent with the abstract's direction. The abstract also notes the strategy 'performs strongly during periods of prolonged turbulence', which the research omits. Do & Faff's follow-up (J. Financial Research 2012, 'Are pairs trading profits robust to trading costs?') is the more relevant source: it found that after realistic costs simple pairs trading is largely unprofitable post-2002. That strengthens the 'reject' verdict.
  - corrected: Do & Faff (FAJ 2010) confirm a continuing decline in simple pairs-trading profitability (subperiod figures of 0.86% to 0.24%/month are not verifiable from the abstract), with strength only in turbulent periods. Their 2012 follow-up finds profits largely vanish after trading costs.
- **[C10] NEEDS_QUALIFICATION** ML stock-prediction profits concentrate in microcaps, distressed stocks and high-volatility periods and deteriorate after costs; LSTM daily S&P 500 strategy (0.46%/day before costs) decayed after 2010.
  - reasoning: Avramov-Cheng-Metzker and the Fischer & Krauss abstract are both confirmed: 0.46%/day, Sharpe 5.8 before costs, 1992-2015, and 'as of 2010, excess returns seem to have been arbitraged away with LSTM profitability fluctuating around zero after transaction costs'.

However, the research's cited 'follow-up' (arXiv 2201.08218) is miscited. It is Fjellström (2022), an LSTM ensemble on Stockholm OMX30 stocks. It reports POSITIVE results vs benchmarks and says nothing about '<0.1%/day after 2008' or about replicating Fischer & Krauss. That supporting citation should be dropped. The core claim stands on Fischer & Krauss's own abstract.
  - corrected: Avramov-Cheng-Metzker find deep-learning profits concentrated in microcaps, distressed stocks and high-volatility states, and they deteriorate further after costs. Fischer & Krauss report 0.46%/day before costs, but by their own account profitability after costs fluctuated around zero from 2010. The arXiv 2201.08218 citation does not support the decay claim and should be removed.
- **[C11] CONFIRMED** LLM-based timing strategies' reported advantages deteriorate significantly over 20 years and 100+ symbols; they underperform passive benchmarks in bull markets and lose heavily in bear markets.
  - reasoning: arXiv 2505.07078, v6 dated June 26, 2026, lists KDD 2026 Datasets & Benchmarks Track (Oral). The abstract says 'previously reported LLM advantages deteriorate significantly under broader cross-section and over a longer-term evaluation' and 'LLM strategies are overly conservative in bull markets, underperforming passive benchmarks, and overly aggressive in bear markets, incurring heavy losses'. It covers two decades and 100+ symbols. The Lopez-Lira & Tang quotes also check out (v6, Oct 28, 2025): 'especially for small stocks and negative news' and 'Strategy returns decline as LLM adoption rises'.
- **[C12] CONFIRMED** Taiwan <1% of day traders predictably earn positive net abnormal returns; Brazil 97% of 300+ day persisters lost money, only 0.4% out-earned a bank teller; most active US households earned 11.4% vs 17.9% for the market.
  - reasoning: The Brazil abstract says '97% of them lost money, only 0.4% earned more than a bank teller (US$54 per day)'. The Taiwan '<1%' figure is from the JFM 2014 abstract; the PDF text is consistent, with net returns assuming a 5 bp one-way commission plus 30 bp tax on sales. The Barber & Odean 11.4% vs 17.9% figure is the well-known abstract figure for the highest-turnover quintile, net of costs, 1991-96. Caveats: Taiwan's 30 bp transaction tax and Brazil's futures market mean costs differ from US commission-free stocks, and these studies cover discretionary day traders, not rules-based algorithms.
- **[C13] CONFIRMED** On 888 Quantopian algorithms, backtest Sharpe predicted OOS Sharpe with R² < 0.025; more backtesting led to larger IS/OOS gaps.
  - reasoning: This matches the Wiecki et al. abstract ('R² < 0.025'; the more backtesting, the larger the discrepancy). Wikipedia confirms: 'In February 2020, Quantopian announced it would return investors' money due to the underperformance of its investment strategies'; the community platform shut down on November 14, 2020, and the team joined Robinhood. Caveat: the out-of-sample periods were short (at least 6 months) and mostly paper-traded, which itself shows how little a few months of paper trading reveals.
- **[C14] NEEDS_QUALIFICATION** A majority of retail crypto-app users in nearly all economies lost money on bitcoin (Aug 2015-Dec 2022); BTC fell ~77%; survivorship-free crypto trend backtest reports Sharpe ~1.58 net of fees (2015-2025), vendor backtest with no live record.
  - reasoning: BIS Bulletin 69 (Feb 20, 2023) confirms 'a majority of crypto app users in nearly all economies made losses on their bitcoin holdings' over Aug 2015-Dec 2022. The '73-81%' figure the research attributes to it is not in the Bulletin; it comes from BIS Working Paper 1049 (Nov 2022) and news coverage of it. BTC's roughly -77% (Nov 2021 to Nov 2022) is consistent with known prices.

Zarattini-Pagani-Barbon (Concretum; SSRN returned 403): the Concretum page says the top-20 rotational portfolio had 'Sharpe ratio above 1.5' and 10.8% annualized alpha vs BTC, 'net-of-fees'. Secondary summaries give single-asset BTC figures of CAGR 30% / Sharpe 1.56 / MDD 19% net of 10 bp.

The research conflates the portfolio Sharpe with the BTC-only CAGR. Its '0.10-0.50% fees' range and 'survivorship-free' label could not be verified; the base case appears to be 10 bp, below typical retail spot fees plus spread. Concretum sells research, so treat it as a vendor source.
  - corrected: BIS Bulletin 69: a majority of crypto-app users in nearly all economies lost money on bitcoin over Aug 2015-Dec 2022 (the 73-81% estimate is from BIS WP 1049). Concretum's crypto trend ensemble reports portfolio Sharpe >1.5 net of fees, apparently at 10 bp costs (BTC-only about 30% CAGR, Sharpe 1.56). Retail fees are 0.1-0.6% plus spread, the survivorship treatment is unverified, and there is no live record.
- **[C-extra-1] NEEDS_QUALIFICATION** Bouchaud et al. (arXiv 2607.01550): short-term trend ceased after ~2009 while long-term trend held up.
  - reasoning: The paper exists: Kurth, Eisler, Rej & Bouchaud, submitted July 2, 2026, about 100 futures contracts over 1995-2025. The quote about short-term trends is correct, and the portfolio-level slowest signal still delivered Sharpe of about 0.40 post-2008. But the headline finding is that 'post-2008 trend PnL has collapsed on small-tick contracts across all signal horizons, while remaining essentially intact on large-tick ones'. Equity indices are in the small-tick tier. For an equity-index-only trend filter, this paper is evidence against persistence, not for it.
  - corrected: Bouchaud et al. (2026) find trend profits collapsed after 2008 on small-tick contracts, including equity indices, at all horizons. Long-horizon trend survives mainly through large-tick contracts (bonds/yields, most commodities). Diversified multi-asset trend is supported; equity-only trend is weakened.
- **[C-extra-2] NEEDS_QUALIFICATION** SG Trend Index ~4.9%/yr since 2000, -15% trailing 12m in mid-2025; managed-futures funds charge ~0.85%+.
  - reasoning: TTU confirms 'annualized return of 4.90% since 2000' and a 12-month trailing loss of -15.05%. The index is reported 'net of fees', so live CTA returns are already after the roughly 1-2% plus performance fees. The '~0.85%+' fund-fee figure is unsourced.
- **[C-extra-3] CONFIRMED** SPIVA YE2024: 89.5% of US large-cap funds underperformed over 15 years; DALBAR investor gap 848 bp (2024) and 72 bp (2025).
  - reasoning: SPIVA's 15-year figure of 89.50% is confirmed via secondary summaries; the S&P PDF itself returned 403. DALBAR's press release confirms '0.72% or 72 basis points' for 2025 (S&P 17.88% vs investor 17.16%) and 848 bp for 2024. The research correctly flags DALBAR's methodology as criticised.
- **[C-extra-4] NEEDS_QUALIFICATION** Token arithmetic: Sonnet 5.5 call 5K in + 500 out = $0.015; monthly $0.18/yr, daily $3.78/yr; break-even capital $189 at 2% edge. Detecting 2% alpha at 10% TE needs 100 years (25 at 5% TE).
  - reasoning: The arithmetic is correct: 5,000 × $2/1M = $0.010; 500 × $10/1M = $0.005; total $0.015. Times 12 = $0.18; times 252 = $3.78; $3.78 / 0.02 = $189. For the t-stat, years = (t·TE/α)² = (2·0.10/0.02)² = 100, and 25 at 5% TE. My SMA10 replication shows actual TE of about 10-11.5%, so 100 years applies.

The framing understates the problem. The research's own shortlist has expected excess return vs benchmark of about -5% to 0%, not +2%, so break-even capital for any runtime LLM cost is undefined (infinite). It also ignores non-LLM runtime costs: a $5/month VPS is $60/yr, more than the entire expected total return on under about $600 at a 10% market return.
  - corrected: The arithmetic is right, but the expected excess edge of the recommended strategies is ≤0, so no runtime LLM spend can be justified by excess return. Hosting and data costs must also be zero-cost (local cron, free CI scheduler, free broker paper API) for the system to meet the user's cost constraint at small capital.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- Primary candidate = long-horizon trend filter on a broad equity ETF. A quant would object that the research's own replication shows it lagged buy-and-hold by 1.7-4.1 pts/yr post-publication, with the entire benefit coming from two years (2008, 2022). Excess Sharpe was lower than buy-and-hold over 2013-2026, and Bouchaud et al. 2026 report that trend PnL on equity-index futures degraded at all horizons after 2008. For a user whose stated goal is profit, making a strategy with negative expected excess return the 'primary build' contradicts the evidence. The honest primary recommendation is automated buy-and-hold (plus scheduled contributions); a trend filter is an optional risk-preference overlay, offered only if the user values drawdown reduction more than return.
- GTAA5 secondary candidate, benchmarked against a US 60/40. This is an unmatched benchmark. GTAA5 should be judged against equal-weight buy-and-hold of its own five ETFs, or a global 60/40. The research also omits Concretum's finding of about 220 bp/yr CAGR dispersion from rebalance-day choice alone. Any build must tranche rebalances (e.g., weekly tranches or several month-offsets) or it may be measuring timing luck rather than a rule.
- Ensemble of 6-12 month lookbacks. Ensembling reduces parameter fragility but does not create edge. The ensemble itself has no independent post-publication record in the cited sources. Present it as variance reduction, not return enhancement.
- Factor ETF tilt with an expected '0 to +2%/yr'. This is too rosy given the research's own French-data results: UMD CAGR -2.2%/yr since 2009, HML CAGR -1.95%/yr since 2007, value+momentum Sharpe 0.14 since 2013. Add McLean-Pontiff decay, capture of only the long leg, and ETF fees of 0.15-0.25%. A defensible ex-ante expectation is centred near 0 with multi-year negative stretches of ±3-5%/yr tracking error. The MTUM 10-year figures were never verified.
- Crypto 'experimental sleeve'. A consumer-protection lawyer would push back hard. The user has no experience and explicitly will not risk money. The research's own evidence (BIS) says most retail crypto users lost money. Crypto has no investor-protection scheme, carries exchange/custody failure risk (FTX), and every switch is a taxable disposal in many jurisdictions. Retail availability varies by country (e.g., UK FCA financial-promotion rules, MiCA-licensed venues in the EU, US state restrictions). The supporting backtest is a vendor study at apparently 10 bp costs. Recommend omitting it, or gating it behind explicit informed consent after the core system works.
- 'Paid by the human as a research cost, not charged to trading profit' for quarterly Claude reports. This conflicts with the user's hard constraint that running costs must be below profit. A quarterly LLM report is a running cost. Either generate reports deterministically (templated Python, zero tokens) or count the tokens honestly: even one Haiku batch call is about $0.003-0.01, which exceeds the excess return on $1-$100 of capital.
- Runtime cost accounting only covers tokens. Hosting (a VPS, $4-10/month), market data subscriptions and broker fees also count. Recommend a free scheduler (the user's own machine via cron, or a free CI scheduler), free end-of-day data (the environment notes show Yahoo rate-limited and stooq cut off, so data reliability is itself a risk), and a commission-free broker. At $1 of capital, even $1/yr of infrastructure destroys the result.
- '$1 real-money test' and 'simulate at $1/$1k/$100k'. The scaling simulation is sensible. But a lawyer and a quant would both insist the user be told plainly that a $1 live test cannot show profit (10%/yr on $1 = $0.10), only that orders execute. Broker specifics matter: fractional-share orders are often market-only, restricted to regular hours, unavailable via API for some symbols, and have $1 notional minimums (Alpaca) that break equal-weight multi-ETF portfolios below about $5-10. Residency determines whether Alpaca live accounts are even available.
- Tax framing. The research says tax drag from ~70% turnover is 'the main scaling cost', but Faber (citing Gannon & Blum) estimates that raising turnover from 20% to 70% costs under 50 bp/yr after tax. Conversely, in the US, trend whipsaws often realise short-term gains taxed at ordinary rates, and in some jurisdictions (e.g., UK bed-and-breakfasting rules, deemed-disposal regimes for funds in Ireland, EU non-UCITS restrictions) the effect is very different. Treat tax as jurisdiction-specific and unquantified until residency is known, and note that tax-advantaged accounts often restrict API/automated trading or broker choice.
- Pre-registered kill rule based on 'live tracking error vs backtest'. It is reasonable to catch implementation bugs, but with monthly signals and about 1.5 switches/yr it has almost no statistical power to detect a lost edge within years. The kill rule should target implementation divergence (fills, signal mismatches, cost overruns) and a pre-registered maximum-drawdown or behavioural stop, not edge detection.
- Backtest costs of 10-20 bp per ETF trade are conservative for SPY-class ETFs (spreads about 0.3-1 bp) but may be too low for fractional orders routed with price improvement uncertainty, or for less-liquid sleeves (DBC, VNQ, intl ETFs). Model spreads per instrument rather than one flat number, and include ETF expense ratios explicitly (e.g., DBC about 0.85%).
- Ranking and claims presented to a novice should avoid any language implying the system will 'make a profit'. Consumer-protection norms (FINRA/SEC and FCA fair, clear and not misleading standards, if this were ever shared) require that backtested/hypothetical performance be labelled as hypothetical, shown with costs, and accompanied by the benchmark and worst drawdown. The research's per-strategy 'Why defensible' blurbs quote gross or in-sample figures (e.g., Faber 1901-2012, crypto Sharpe 1.5) without that labelling.

## VERIFIER OVERALL

Most of this research holds up. Nearly every core number I could check reproduces:
- Damodaran CAGRs: I recomputed 10.02%, 10.90% and 8.22% exactly.
- The Ken French factor decay table: reproduced to the second decimal.
- The SMA10 and TSMOM post-publication replication: I rebuilt it independently and got 9.65% vs 11.33%, MDD -18.1% vs -50.3%, and 1.45 switches a year.
- The Faber, Concretum GTAA5, Newfound GEM, FINSABER, Lopez-Lira, Brazil and Taiwan day-trader, DALBAR and Quantopian figures: all checked against their sources.
- The overall conclusion also stands. No beginner-runnable systematic approach reliably beats a cheap index after costs, and an LLM in the runtime loop cannot pay for itself.

**Errors to correct:**
1. **Wrong citation.** arXiv 2201.08218 is an LSTM paper on Swedish OMX30 stocks with positive results; it does not support the "<0.1%/day after 2008" decay claim. Fischer & Krauss's own abstract supports the decay.
2. **Misattributed quote.** The Robot Wealth line "has lagged B&H SPY" was a reader comment, not the author's view. The lag itself is real: GEM made about 5.9% a year over 2014-2021 versus about 14.6% for the S&P 500.
3. **Wrong source.** The 73-81% BIS loss figure comes from BIS Working Paper 1049, not Bulletin 69.
4. **Mixed-up crypto numbers.** The crypto backtest figures combine a portfolio Sharpe with the BTC-only CAGR, and the claimed 0.10-0.50% fee range and "survivorship-free" label are unverified.
5. **Half-quoted paper (the most material error).** Bouchaud et al. 2026 was quoted only for "short-term trend died". The same paper finds that trend profits on small-tick contracts, which include equity indices, collapsed after 2008 at all horizons. For an equity-only trend filter that is contrary evidence.

**Material omissions:**
- **Two-year dependence.** The trend filter's post-2006 drawdown benefit comes entirely from 2008 and 2022. It lagged or tied buy-and-hold in every other year, and its excess Sharpe was worse over 2013-2026.
- **Rebalance-day luck.** Concretum found about 220 bp a year of GTAA5 performance depends only on which day of the month it rebalances.
- **Wrong benchmark.** GTAA5 was compared with a US 60/40 instead of a buy-and-hold of its own five ETFs.
- **Tax overstated.** Faber himself estimates the extra tax cost of the higher turnover at under 50 bp a year, yet the research calls tax drag the main scaling cost.
- **Runtime costs understated.** The cost analysis covers only tokens and ignores hosting and data.

**What to weight down:**
1. The recommendation that makes a trend filter the "primary candidate". The research's own evidence gives it a negative expected excess return, so automated buy-and-hold should be primary and trend should be an optional risk overlay.
2. The "0 to +2%/yr" expectation for factor ETFs. Centre it near 0.
3. The crypto sleeve. Drop it or gate it for this risk-averse novice.
4. Any "+2% edge" in the break-even token maths. The realistic expected excess edge is at or below zero, so runtime LLM spend should be zero and reports should be templated.

**What to weight up:** the statistical point that paper trading or $1 trading can only validate plumbing, not edge. It is correct and central to the user's request for proof.

Reliability: high on the numbers, medium on citations, and medium on how the recommendations follow from the evidence.
