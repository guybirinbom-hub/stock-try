# Can an AI-assisted system make money in the stock market with tiny capital?

**Research report and build decision.** Prepared 2026-09-29 for the owner of this repository, who has no investing experience, will not risk meaningful money until a system is proven, and needs the running cost of any system to stay below what it can plausibly earn.

This document is the judgment layer over roughly 90,000 words of verified research. It states what the evidence supports, what it rejects, and what this repository builds as a result. Every numbered claim below was checked by an independent adversarial reviewer against primary sources; corrections they required are applied here and listed in section 14.

---

## 1. The short answer

1. **No approach a beginner can run reliably beats a low-cost broad index fund on return after costs.** The approaches with the best evidence (long-horizon trend filters, diversified tactical allocation) reduce drawdowns but have *lagged* the index since they were published. The approaches retail traders are drawn to (day trading, machine-learning price prediction, LLM-as-trader, pairs trading) have strong evidence of failing after costs.

2. **An LLM inside the trading loop cannot pay for itself at small capital, and probably not at any capital.** With the expected excess return over an index fund at or below zero, any recurring token spend is a pure loss. Claude is valuable for exactly three things here: designing the system, writing the code, and adversarially reviewing it. At runtime the system must be deterministic Python with **zero tokens**.

3. **A $1 live account cannot show a profit, whatever the strategy.** At Alpaca each regulatory fee type is rounded up to $0.01 per day, so a $1 round trip costs about $0.04 (4%). Fractional dividends round to $0.00. A $1 account is a smoke test of the order plumbing, nothing more. For a non-US resident, wire and currency fees make even that uneconomic; paper trading covers the same ground for free.

4. **Proof does not come from paper trading.** Statistically, six months of paper trading gives a 95% confidence interval of roughly ±2.8 on an annualized Sharpe ratio, which cannot distinguish a good strategy from a coin flip. Proof, to the extent it exists, comes from long, cost-inclusive, out-of-sample backtests with structural protection against look-ahead and a correction for the number of things tried. Paper trading proves the code runs correctly.

5. **Scaling is not limited by market capacity** for liquid ETFs (a $100k order in SPY is under 0.001% of daily volume). What changes with scale is the fee drag (falls), taxes on realized gains (rise, and depend on your country), and drawdowns in absolute dollars (rise). No tool can guarantee that scaling preserves profit, because the binding risk is that the edge was never real.

6. **The decision, and the result.** This repository builds a zero-token, deterministic foundation: an honest backtester with a strict validation suite, a buy-and-hold index benchmark as the null hypothesis, a small set of published low-turnover candidate strategies evaluated against it with costs, and a paper-trading runner with safety guards. The most likely honest outcome of that pipeline is "buy and hold a low-cost index fund, automate the contributions, and stop there." That is a valid, cheap, evidence-backed result, not a failure. The harness has now been run: every candidate strategy was rejected by the pre-registered gates, and buy-and-hold remains the benchmark nothing here beat (details at the end of section 11).

---

## 2. How this research was produced

- Six research dimensions were assigned to independent Opus researchers with web access: strategy evidence, LLM-in-the-loop evidence, tooling, validation methodology, micro-capital mechanics, and token economics.
- Each output was handed to a separate adversarial Opus fact-checker instructed to *refute* every claim by opening the cited sources. Verdicts: confirmed, needs qualification, refuted, or unverifiable.
- A completeness critic then identified gaps; four high-priority gaps (residency and tax, existing tools, a licence-compliant data pipeline, and live-execution safety) were researched and verified in a second round.
- Totals: 21 agents, about 1,200 tool calls, about 2.7 million tokens. The cost of this research is a sunk design cost, paid once. It is not charged to the trading system's running cost, per the owner's rule, but see section 5 for why it is still relevant.
- Verdict tally across 161 checked claims: 85 confirmed, 69 needs qualification, 7 refuted. Every refuted claim is corrected or removed below.

---

## 3. Approaches ranked by evidence

All returns are nominal, before tax, and hypothetical unless marked live. "Excess" means return relative to buying and holding a broad US index fund, which is the null hypothesis any system must beat.

| Rank | Approach | Evidence quality | Post-publication record | Expected excess vs index | Verdict |
|---|---|---|---|---|---|
| 1 | **Buy and hold a broad low-cost index ETF** | 98 years of data | S&P 500 total return compounded at 10.0%/yr over 1928-2025; 10.9%/yr over 2006-2025 | 0 minus the fund fee (0.03-0.2%) | **The benchmark and the default.** About 90% of professional US large-cap funds trailed it over 15 years (SPIVA). |
| 2 | **Long-horizon trend filter on the index** (10-month moving average, or 12-month return vs T-bills, checked monthly) | 100+ years; promoter (Faber) plus our own replication | Independent replication on Ken French US market data, 2006-01 to 2026-08, 10 bp per switch: **9.65%/yr vs 11.33% buy-and-hold**, volatility 10.6% vs 15.5%, max drawdown **-18.1% vs -50.3%**, about 1.45 switches per year. Over 2013-2026 it lagged by 4.1 pts/yr. | **-2 to 0%/yr** in bull markets; positive only in prolonged bears | Drawdown-control tool, not a return enhancer. The entire post-2006 risk benefit came from two years (2008 and 2022). Recent microstructure evidence (Kurth, Eisler, Rej and Bouchaud 2026) finds trend profits on equity-index futures collapsed after 2008 at all horizons. Offered here only as an optional overlay for someone who values smaller drawdowns more than return. |
| 3 | **Diversified multi-asset trend allocation** (five ETFs, each held only above its 10-month average) | Faber 2006; Concretum extension 2026 | Jan 2006 to Mar 2025, 10 bp costs: **CAGR 6.05%, Sharpe 0.68, max drawdown 11.7%**, down from 11.7% CAGR in-sample. About **220 bp/yr of performance depended only on which day of the month it rebalanced.** | -2 to -5%/yr vs the S&P 500; unmeasured vs its own matched benchmark | Lower drawdown at a real return cost. Rebalance-day luck is as large as the claimed edge, so any implementation must tranche rebalances. Included as a candidate so the harness can show the owner the trade-off honestly. |
| 4 | **Passive factor tilt via ETFs** (momentum, value, quality) | Peer-reviewed premia; long-short academic portfolios | Ken French data: momentum factor averaged 8.65%/yr before 1993, 4.80%/yr after, **-0.84%/yr since 2009** (CAGR -2.2%); value **-1.31%/yr since 2007** (CAGR -1.95%); a 50/50 value-momentum blend's Sharpe fell from 0.80 to 0.14 after 2012 | Centred near 0, with multi-year stretches of -3 to -5%/yr | Not built. Published anomalies lose 26% out-of-sample and 58% post-publication (McLean and Pontiff 2016). |
| 5 | Crypto trend following | Academic momentum evidence; vendor backtest (Sharpe above 1.5 at 10 bp costs) | No live record. A majority of retail crypto-app users in nearly all economies lost money (BIS) | Unknown | **Not built.** Wrong risk profile for a risk-averse novice; no investor protection; every switch is a taxable event in most countries. |
| — | Retail day trading and intraday strategies | Large peer-reviewed samples | Taiwan 1992-2006: **under 1%** of day traders predictably profitable net of fees. Brazil 2013-2015: **97%** of those persisting 300+ days lost money. US: the most active households earned 11.4% vs 17.9% for the market. | Strongly negative | **Rejected.** |
| — | Machine-learning price prediction on daily bars | Peer-reviewed | Profits concentrate in microcaps, distressed stocks and high-volatility episodes and deteriorate after costs (Avramov, Cheng and Metzker 2023). The best-known LSTM result (0.46%/day before costs) went to about zero after costs from 2010 by its own authors' account. | Negative after costs | **Rejected.** |
| — | Pairs trading and short-term reversal | Peer-reviewed | Profitability declined continuously; largely gone after realistic costs post-2002 (Do and Faff 2012). Needs shorting, which fractional and cash accounts do not allow. | Negative | **Rejected.** |
| — | LLM per-trade decisions | See section 4 | See section 4 | Unproven; negative after token cost | **Rejected at runtime.** |

**The base rate that frames everything.** On 888 algorithms built by Quantopian users, the backtest Sharpe ratio explained less than 2.5% of the variance in out-of-sample Sharpe, and the more backtests a user ran, the larger the gap between backtest and out-of-sample results (Wiecki et al. 2016). Bank-marketed quantitative strategies lost a median 73% of their Sharpe ratio going live (Suhonen et al. 2017). A strategy that looks good in a backtest is, by default, overfit.

---

## 4. Where an LLM belongs, and where it does not

**What the evidence says LLMs can do.** GPT-4 headline sentiment predicted next-day returns in a clean post-training-cutoff sample: 34 basis points per day before costs (Lopez-Lira and Tang, Oct 2021 to May 2024). But the strategy needed about 190% daily turnover and short selling, became unprofitable at 20 bp round-trip costs, and its Sharpe decayed from 6.54 in late 2021 to 1.22 by 2024. The authors' own conclusion: feasible "only for market participants whose transaction costs are sufficiently low, such as market makers." That is not a retail account with fractional shares.

**What the evidence says LLM trading agents do.**
- TradingAgents (the most-starred framework, about 109k GitHub stars): headline results come from a 3-month backtest on three tickers with no transaction costs, 11 LLM calls and 20+ tool calls per decision. The repository itself states results "are not guaranteed to match any published figure."
- FINSABER (KDD 2026): re-evaluating published LLM agents over 2004-2024 on 63-91 symbols with commissions, they underperformed buy-and-hold (Sharpe -0.23 and 0.24 vs 0.70). The re-run used a cheap backbone model, so it shows cheap-model agents fail, not that every agent fails.
- An audit of 30 LLM trading studies (2023 to May 2026) found only 14 reported costs or turnover and only 18 had recoverable code.
- Real-money tournament (Alpha Arena, late 2025): US-equities season, 32 accounts, 6 ended positive, aggregate loss about 35%. Two-week, leveraged, anecdotal, but the direction matches everything else.
- A hobbyist re-test of TradingAgents on Claude Haiku 4.5 and Opus 4.8 with anonymized inputs and 10 bp costs: the agent returned -0.9% vs +15.7% buy-and-hold on AAPL over Mar-Jun 2026, at about $3.70 for 13 decisions.
- The strongest pro-LLM result (Chen and Pu, Jan 2026): an unnamed web-searching frontier model ranked Russell 1000 stocks daily from April 2025; the top-20 long-only portfolio showed 15.8-18.4 bp/day of factor alpha over about 158 trading days. That is a t-statistic of roughly 1.9 on the Sharpe ratio, in a strong rebound market, in an unrefereed preprint with no model named and no compute cost reported. It is a hypothesis, not evidence.

**The look-ahead trap.** Claude Opus 5.5, Sonnet 5.5 and Fable 5.1 have a training-data cutoff of June 2026. LLMs recall pre-cutoff market data essentially verbatim, and instructions to ignore it do not work (Lopez-Lira, Tang and Zhu 2025). Any backtest of a current model's judgment on dates before July 2026 is biased upward by an unknown amount and counts for nothing as proof. Only post-cutoff tests on strictly point-in-time inputs are clean (for the 5.5 models, in practice only forward tests), and a model retirement (Anthropic observed lifetimes: about 12 to 25 months) resets the clock. An LLM-dependent edge may never become statistically verifiable before its model is retired.

**Institutional practice.** Man Group's AlphaGPT uses LLM agents to generate, code and backtest signal ideas; every signal then passes the same human investment-committee review as human research. The LLM is a research assistant, not the trader.

**Where Claude belongs in this project:**
- Design and research: done (this document).
- Writing the backtester, strategies, validation suite and broker adapter: yes, with the output validated against known answers, because LLMs get backtest arithmetic wrong at a high rate (the best model on BacktestBench reached 67% accuracy, 52% on metric calculation).
- Adversarial code review for look-ahead, survivorship and cost bugs: yes.
- At runtime, per trade or per day: **no.** Not even a daily sanity check. Reports are generated by templated Python.

---

## 5. Token economics: what running costs, and what capital can earn

Prices used (USD per million tokens, input / output, first-party API, verified 2026-09-29): Haiku 4.5 $1 / $5; Sonnet 5.5 $2 / $10; Opus 5.5 $4 / $20; Fable 5.1 $10 / $50. Batch API is 50% off. Prompt caching cannot help a once-a-day call (maximum cache lifetime is one hour). Thinking tokens are billed as output, and the 5.5-series tokenizer produces about 30% more tokens per text, so Sonnet and Opus figures below are lower bounds.

**Annual runtime token cost by architecture** (252 trading days):

| Architecture | Per day | Per year |
|---|---|---|
| A. Deterministic rules on a scheduler, no LLM at runtime | $0 | **$0** |
| B. A plus a daily Haiku sanity check (3-8k in, 300 out) | $0.005-0.010 | $1.13-2.39 |
| C. Daily Sonnet 5.5 "analyst" reading a 10-ticker news digest (30-60k in, 2k out) | $0.08-0.14 | $20-35 (batch: $10-18) |
| C. Same on Opus 5.5 with realistic thinking (60k in, 8k out) | $0.40 | $101 |
| D. TradingAgents-style multi-agent debate on Opus 5.5, 1-5 decisions/day | $1.12-14.00 | $282-3,528 |
| E. A daily interactive Claude Code session (Opus 5.5) | $1.08-5.20 | $272-1,310 |
| F. One Opus 5.5 review of logs per month, via batch | — | $1.8-3.0 |

**What capital can earn.** Expected annual profit is capital times return. The benchmark earns the *absolute* return at zero running cost, so a system must pay for itself out of *excess* return.

| Capital | 3% excess | 8% excess | 15% excess | 10% absolute (the benchmark) |
|---|---|---|---|---|
| $1 | $0.03 | $0.08 | $0.15 | $0.10 |
| $100 | $3 | $8 | $15 | $10 |
| $1,000 | $30 | $80 | $150 | $100 |
| $10,000 | $300 | $800 | $1,500 | $1,000 |
| $100,000 | $3,000 | $8,000 | $15,000 | $10,000 |

**Break-even capital** (annual token cost divided by excess return), at an 8% excess assumption: architecture C on Sonnet needs $252-441; D needs $3,500-44,000; E needs $3,400-16,400. At 3% excess, multiply by 2.67. A prudent design keeps runtime cost at or below 25% of expected excess, which multiplies these by four again.

**The honest base case.** The 8% and 15% columns are best-case sensitivities that about 90% of professional managers fail to reach over 15 years. Section 3 puts the expected excess return of every approach this owner can run at or below zero. **At an excess return of zero, break-even capital is infinite: no runtime token spend can be justified.** This is why the system is built with zero tokens at runtime.

**The one-time cost is real too.** At API prices this research and build is on the order of $50-150 or more; this session's research alone consumed about 2.7 million tokens. The owner excluded design cost from the constraint, which is reasonable, but maintenance (a code review after each dependency or model change, perhaps $10-30 a year) is a recurring cost and is budgeted in the acceptance gates. Below roughly $1,000 of capital, even a zero-token system does not recover its own design cost. This project is best understood as tuition and a validation harness, not an income engine.

**Subscriptions.** Claude Pro or Max are fine for interactive design and maintenance sessions. They are the wrong tool for an unattended bot: a flat $240/yr needs $3,000 of capital at 8% just to break even, and Anthropic's consumer terms permit scripted access only via an API key or where Anthropic explicitly permits it.

---

## 6. Trading with $1 to $100: the mechanics

Verified against Alpaca's fee schedule revised 2026-09-17.

- **Fractional orders**: minimum $1 notional on buy orders (sells have no minimum); market, limit, stop and stop-limit; time-in-force DAY only, so no opening or closing auction orders, which means fills will not equal the official close a backtest usually assumes. Not all symbols are fractionable. Fractional sells are long-only.
- **Fees**: no commission. Pass-through SEC fee ($20.60 per million on sells, from 2026-04-04), FINRA TAF ($0.000195 per share on sells; paused at $0.00 for Oct-Dec 2026, though whether Alpaca passes the pause through is unverified) and CAT ($0.000003 per share on buys and sells). **Each fee type is aggregated per day and rounded up to $0.01.** Consequences:

| Notional | Round-trip fees | All-in as % of position (fees plus a one-tick SPY spread) |
|---|---|---|
| $1 | $0.04 | **4.0%** |
| $10 | $0.04 | 0.40% |
| $100 | $0.04 | 0.04% |
| $1,000 | $0.06 | 0.0073% |
| $10,000 | $0.24 | 0.0037% |

  A $1 account rebalanced monthly pays about 36-48% of its value in fees per year. The fee floor stops mattering at roughly $100-500.
- **Dividends** on fractional positions are rounded to the nearest cent, so a $1 SPY position receives $0.00.
- **Spreads**: SPY, IWM and TLT trade at about one tick (0.1-1.3 bp; QQQ assumed similar, not measured); GLD is wider (about 1 bp median, several ticks). Negligible next to the fee floor at tiny size.
- **Market impact**: a $100k order in SPY is about 0.2 bp; irrelevant.
- **Regulation**: the pattern-day-trader $25,000 rule was replaced by intraday margin standards on 2026-06-04. Irrelevant for monthly rebalancing. Settlement is T+1.
- **Non-US residents**: Alpaca accepts many countries (Canada excluded; others "contact support"), requires a W-8BEN, and charges $35 for an outbound international wire and 1.5% (max $40) for local-currency transfers. Your own bank adds $15-50 per wire. **A $1 to $100 live test is effectively unrecoverable for a non-US person.** Do the plumbing test in paper instead.
- **Alpaca paper trading**: free, opens globally with an email, default $100k balance (create a new account at the capital you intend to use; balances cannot be changed later), fractional orders supported. It does **not** simulate slippage, market impact, regulatory fees or dividends, and paper-only accounts receive IEX-only market data. The runner keeps a shadow ledger that adds modelled fees and dividends.

**Can $1 make meaningful profit?** No. At an optimistic 10%/yr, $1 earns $0.10, and one round trip costs $0.04. The honest use of $1 to $100 of real money is a smoke test of authentication, order submission, fills, fee posting and reconciliation. All evidence of merit comes from backtests and paper trading at realistic notional.

---

## 7. What counts as proof

**The statistics are harsh.** The standard error of an annualized Sharpe ratio is about 1 divided by the square root of the number of years. Years of track record needed to reach a t-statistic of 2 (and 3):

| True annual Sharpe | Years to t=2 | Years to t=3 |
|---|---|---|
| 0.5 (roughly buy-and-hold equities) | 16 | 36 |
| 1.0 | 4.2 | 9.4 |
| 1.5 | 1.9 | 4.4 |

Beating a benchmark is harder still, because the test is on the *difference*: detecting a 2%/yr edge at a 10% tracking error needs about 100 years. The 95% confidence interval on an annualized Sharpe after 20 trading days is about ±7; after six months, ±2.8; after one year, ±2.0.

**What each stage can and cannot prove:**

| Stage | Proves | Cannot prove |
|---|---|---|
| In-sample backtest | The idea is not obviously broken; the risk profile (volatility and drawdown do predict out-of-sample behaviour) | Edge (backtest Sharpe barely predicts live Sharpe) |
| Walk-forward and multiple-testing correction | The edge survives re-fitting and the number of trials | Future regimes; execution; look-ahead leakage |
| Paper trading | The code runs daily, signals match the backtest engine, orders and scheduling work | Fill quality, fees, dividends (not simulated); edge (sample far too short) |
| $1-$100 live | Real fills, fee posting, reconciliation, account permissions | Edge (P&L is cents); capacity |
| Scaled live | Slippage at realistic size; running cost vs profit | Long-run edge, until years accrue |

**The five things a backtest must do to be believed:**
1. Decide on the close of day t and fill on day t+1. Same-bar signal-and-fill is look-ahead.
2. Use total-return (dividend-adjusted) prices for both strategy and benchmark, and charge realistic costs: spread per instrument, the broker's fee model at the intended capital, and fund expense ratios. Report results at 2x costs too.
3. Use a survivorship-free universe. Long-lived liquid ETFs and their mutual-fund predecessors avoid the delisting problem; picking today's winners with hindsight does not.
4. Keep a trial ledger. Every variant tested counts. Correct the best result for the number of trials (deflated Sharpe ratio, using the cross-trial variance as the paper specifies; probability of backtest overfitting). With five years of data and 45 variants, the best zero-skill variant is expected to show a Sharpe of about 1.0 by chance.
5. Prevent leakage structurally, because the statistical corrections do not detect it: a deliberately leaky oracle with a Sharpe of 35 passed both deflated-Sharpe and overfitting tests (Gençay 2026, preprint). The harness therefore includes a test that shifts every signal by one bar and checks that performance collapses toward the benchmark.

**Regime slices** every candidate must report: 2007-09, the 2009 rebound (momentum crash), Feb-Apr 2020, 2022. A strategy never tested through a V-shaped rebound has not been stress-tested.

**Haircuts.** Do not apply a flat 50% haircut to a backtest Sharpe; Harvey and Liu explicitly call that a mistake. The haircut depends on the Sharpe level and the number of trials, and is usually more than 50% below a Sharpe of 0.4 and at most 25% above 1.0. Use the trial-count-adjusted figure the harness computes.

---

## 8. Scaling up: what changes and what does not

The owner asked for assurance that expanding capital will not stop profits. The honest answer:

- **Does not change**: market capacity for liquid ETFs below roughly $1-10 million; the signal logic; token cost (zero).
- **Improves**: fee drag, which has a floor of a few cents per trading day (the SEC fee itself is proportional to sale value) and shrinks as a percentage. The system is simulated at $1, $100, $1k, $10k and $100k with the real fee model so this is visible.
- **Gets worse**: taxes, because a trend switch realizes gains that buy-and-hold defers (modelled upper bound about 1 pp/yr for a US taxable account; zero inside a tax-free wrapper; depends entirely on country, see section 13); drawdowns in absolute dollars (a 50% drawdown is $50,000 on $100,000); behaviour, since abandoning a rule after years of lagging is the main documented way such plans fail.
- **Cannot be assured by any tool**: that the edge exists and persists. Post-publication decay is the norm.

The design for scaling is therefore staged, not assured: paper trading at the intended notional in parallel with any live account, a comparison of live fills against modelled costs, and pre-registered kill criteria (a drawdown limit set as the *smaller* of the backtest-derived thresholds plus an absolute dollar cap the owner chooses, enforced at the broker by disabling margin, shorting and options).

---

## 9. Existing tools versus building

The owner asked whether to use, modify, or create a tool. Findings:

- **For buy-and-hold with contributions, no code is needed.** Free recurring fractional purchases from $1 exist at Fidelity, Vanguard (its own ETFs), Robinhood, IBKR Lite (US only), Trading 212 (UK/EU) and Scalable Capital (EU). Cost: $0 plus the fund fee.
- **No broker-native recurring or pie feature automates a trend filter.** Composer (US only, $0 starter tier, $50 minimum per strategy, recently acquired by SoFi with pricing undisclosed) is the only no-code tool found that can (broker one-shot conditional orders might partially automate a switch; unverified), and it fails the $1 test.
- **Every subscription platform fails the cost test below about $10k**: M1 $36/yr, Betterment $60/yr under $24k without a $200/month deposit, Composer Advanced $120/yr, QuantConnect live roughly $400-1,000/yr, TradingView-plus-bridge roughly $650-1,200/yr. Robo-advisors charge 0.2-0.9%/yr to do what a $0 recurring plan does.
- **Open-source**: `bt` (MIT, released 2026-09-12) is the best maintained periodic-rebalance backtester and is used here as the independent cross-check engine. `vectorbt` is fast but carries a Commons Clause. `backtrader` (last release 2023) and `pylivetrader` (2022) are abandoned. `nautilus_trader` needs Python 3.12+. `Lumibot` runs backtest and live from one class but pulls in LLM SDKs, stealth-browser tooling and a proxy scraper, which is an unacceptable supply-chain surface for something holding broker keys. `alpaca-py` is the official SDK, but it auto-retries POST requests on 429 and 504 with no timeout, which can duplicate orders; the runner works around this.
- **Free backtest cross-checks**: Ken French monthly market data (1926+, keyless) for an independent index-level check; testfol.io and Portfolio Visualizer for eyeball checks only (undisclosed data construction, no cost field respectively).

**Verdict: option 2.** Custom code only where existing tools genuinely lack it: an honest validation harness, and a small deterministic execution runner for paper trading. Execution of plain buy-and-hold can use a broker's free recurring-purchase feature with no code at all.

---

## 10. Tooling decisions

| Concern | Decision | Why |
|---|---|---|
| Historical data | Research backtests: one-off personal downloads via `yfinance` (works from this container; SPY from 1993, dividend-adjusted), raw Yahoo chart API as fallback, local CSV cache that is **not committed**; optional Tiingo free token as a licensed source for refreshes. Unattended paper or live runs: prices from the broker's own market-data API (Alpaca, licensed through the account; IEX feed for paper-only accounts), never from Yahoo. FRED T-bill yields for the cash return | Yahoo's terms forbid automated collection without Yahoo's express permission (and access needs a browser user agent), so it is at most a personal-use research source, not a redistributable one. Tiingo's free tier is personal-use only. Neither may be committed to git. |
| Backtester | Custom pandas engine (explicit t+1 execution, per-instrument spread, Alpaca fee model, cash yield), cross-checked against `bt` on buy-and-hold and one trend rule with a stated tolerance | LLM-written backtesters are exactly where look-ahead bugs hide; an independent engine catches them. |
| Universe | Long-lived liquid US ETFs (SPY or VTI, IEF, AGG or BND, VNQ, GLD, EFA, DBC) with Vanguard mutual-fund proxies for pre-inception history where the splice validates | Free of delisting bias by construction (the sleeves themselves were chosen with hindsight); the fund-only sample from 1996-05 covers 2000-02, 2008, 2020 and 2022 for US equity, bonds, Treasuries, REITs and cash, while the international (EFA), commodity (DBC) and gold (GLD) sleeves have no validated pre-ETF proxy history |
| Broker | Alpaca paper (free, global, fractional) for plumbing; Alpaca live only if the owner is in a supported country with cheap funding | Only free, cron-drivable paper API open globally with just an email (Trading 212's beta demo API serves only its own UK/EU/AU customers) |
| Scheduler | Not GitHub Actions cron alone: reported delays of 1-14 hours and dropped days in 2026. Use an external free trigger (Cloudflare Workers cron or cron-job.org) firing `workflow_dispatch`, or a local machine, plus a dead-man alert | The runner is idempotent so extra or late triggers are harmless |
| Safety | Broker-side: margin multiplier 1, shorting off, options off, trade-confirmation email on. Code-side: dry-run default, two independent flags for live, deterministic `client_order_id` with lookup before submit, SDK auto-retry disabled on order submission, market-hours gate, per-order and per-day notional caps, stale-data refusal, file and broker-side kill switches, no LLM in the order path, SHA-pinned CI actions, hash-pinned dependencies, private repository. Live broker keys are never stored on GitHub (on the free plan a private repository's secrets are visible to every workflow on every branch); GitHub holds paper keys only, and any live order step runs on the owner's own machine | Every one of these maps to a documented loss (Knight Capital 2012: over $460M lost after 45 minutes of runaway orders from dead code and no automated caps; Citigroup 2022: $444bn order from a units-vs-notional field error) |
| LLM at runtime | None | Section 5 |

---

## 11. What this repository builds

**Package `stocktry`** (Python 3.11, pinned dependencies):

1. `stocktry.data`: fetch and cache daily adjusted bars with fallback; FRED risk-free rate; data-quality checks (split jumps, stale prices, missing dividends, bar spacing) that gate every backtest.
2. `stocktry.backtest`: monthly-rebalance engine with next-bar execution; cost model with per-instrument spread, fund expense ratios, and the Alpaca per-day per-fee-type round-up parameterized by starting capital; metrics (CAGR, volatility, Sharpe, Sortino, max drawdown and duration, Calmar, turnover, exposure, hit rate); regime slices.
3. `stocktry.validation`: walk-forward; parameter-plateau sweep; stationary block bootstrap; trial ledger with deflated Sharpe ratio and probability of backtest overfitting; the one-bar-shift leakage test; a buy-and-hold-equals-benchmark identity test.
4. `stocktry.strategies`: buy-and-hold (the null); single-asset trend filter (10-month SMA, 12-month absolute momentum, and an ensemble of 6-12 month lookbacks); multi-asset trend allocation with tranched rebalancing. All deterministic, all monthly.
5. `stocktry.execution`: a broker interface; a local simulated broker for tests; an Alpaca adapter with the safety guards above; a rebalance runner whose default mode is dry-run and which never calls an LLM. Runner rules: a rebalance opens new positions only on the first trading session of the month (a missed first session needs the operator's explicit late-start flag and is refused in CI), later triggers in the first five sessions can only finish legs that already have an order, no order is submitted after an 8-minute run deadline or outside market hours, and any open order not placed by the runner blocks trading.
6. `stocktry.report`: templated markdown and CSV reports (zero tokens), always labelled hypothetical, always alongside the benchmark and worst drawdown, always stating the trial count.
7. `scripts/run_backtests.py` produces the results tables committed under `results/`; `scripts/paper_rebalance.py` runs one paper-trading cycle.
8. Tests with a fake broker: duplicate triggers, simulated 504 on a landed order, crash-and-restart reconciliation, out-of-hours trigger, stale data, bad weights, notional caps, units-vs-notional swap, partial fills, margin-enabled account, kill switches, dry-run default, log scrubbing.

### What the harness found (first full run, 2026-09-29)

All figures below are hypothetical backtests produced by `scripts/run_backtests.py` and reproduced in `results/`. Setup: $10,000 starting capital, fractional shares, signal at the month-end close, fill at the next day's open, half-spread floored at 5 bp per side, the Alpaca fee model with per-day rounding, Alpaca's $1 minimum on buys, dividends reinvested through total-return prices. Taxes, market impact and dividend withholding are not modelled. Cash earns the 3-month T-bill rate.

**Fund-proxy sample, June 1996 to August 2026 (30.2 years):**

| Strategy | CAGR | Volatility | Sharpe | Max drawdown | Switches/yr |
|---|---|---|---|---|---|
| SPY buy and hold (the benchmark) | 10.3% | 15.3% | 0.57 | -55.2% | 0 |
| 60/40 SPY/AGG, annual rebalance | 8.2% | 9.5% | 0.64 | -33.8% | 0 |
| SPY 10-month SMA filter | 9.1% | 11.0% | 0.64 | -24.4% | 1.4 |
| SPY 12-month absolute momentum | 10.5% | 11.9% | 0.71 | -33.7% | 0.5 |
| SPY trend ensemble (6-12 month lookbacks) | 9.6% | 10.5% | 0.71 | -21.2% | 4.4 |
| GTAA-4 (US, international, Treasuries, REITs) | 6.8% | 7.2% | 0.64 | -17.7% | 5.0 |

**ETF-only sample, March 2006 to August 2026 (20.5 years):**

| Strategy | CAGR | Volatility | Sharpe | Max drawdown |
|---|---|---|---|---|
| SPY buy and hold | 11.1% | 15.1% | 0.67 | -55.2% |
| 60/40 | 8.3% | 9.6% | 0.70 | -33.8% |
| SPY 10-month SMA | 8.3% | 10.7% | 0.64 | -24.4% |
| SPY 12-month absolute momentum | 9.3% | 11.9% | 0.67 | -33.7% |
| SPY trend ensemble | 9.0% | 10.2% | 0.74 | -21.2% |
| GTAA-4 | 5.6% | 7.3% | 0.56 | -14.2% |
| GTAA-5 (adds commodities) | 5.5% | 6.6% | 0.58 | -14.5% |

**Before and after publication** (pre-registered split at 2006-01-01, the year Faber's paper appeared; fund-proxy sample): SPY went from 8.3% to 11.2% a year; the 10-month SMA from 10.7% to 8.4%; 12-month momentum from 12.8% to 9.4%; GTAA-4 from 9.6% to 5.6%. Every trend rule beat the index before publication and lagged it afterwards, exactly the decay pattern the literature describes.

**Gate A verdict: every candidate rejected.** The five candidates (three SPY trend filters, GTAA-4, GTAA-5) all failed two gates:
- A.4, overfitting: the probability of backtest overfitting across the parameter grids was 0.49 to 0.87 against a threshold of 0.20. In every grid the parameter that looked best in-sample did worse than the median out of sample. The deflated Sharpe ratio passed for every candidate, but it also passed for SPY itself (it tests whether the Sharpe is above zero, not whether the rule beats the index), so it rejected nothing; the supplementary information ratio against SPY is negative for every candidate.
- A.7, recent record: every candidate lost to SPY in each of the last three non-overlapping 5-year windows, and the 10-month SMA also lost more than SPY in 2022 (-20.7% against -18.2%).

What the trend rules did deliver is what section 3 predicted: drawdowns of 21% to 34% against 55% for the index, at a cost of 1 to 3 points a year of return over the last twenty years. That is a risk-preference trade, not an edge.

**Rebalance-day luck.** Running the same GTAA rule with the signal read on each trading day of the month gave a CAGR spread of 173 to 209 bp across days, in line with the 220 bp the literature reports. A rule whose result depends that much on the calendar day is measuring luck as much as skill.

**Scaling.** At $1, SPY buy-and-hold compounds at the same 11.1% as at $100,000 because it trades once; every rule that trades pays the fee floor: the 10-month SMA earned 6.7% at $1 (fees 1.5% of equity a year) against 8.3% at $100 and 8.4% at $10,000; the multi-asset rules cannot invest at all at $1 because each $0.20 sleeve is below the $1 minimum; the fractional-exposure ensemble ratchets into cash at $1 (0.2% a year). With whole shares a $100 account sits mostly in cash. The fee floor stops mattering between $100 and $1,000, as section 6 said.

**Cross-checks and leakage tests.** The engine agrees with the independent `bt` library to within a millionth of a basis point per month on buy-and-hold and the 10-month rule. The buy-and-hold identity test shows zero tracking difference. A strategy given perfect foresight of next month's direction earns nothing through the engine's normal path (alpha t-statistic 0.2) and a huge return only if the engine is forced internally to fill on the signal bar (t-statistic 31), and rewriting every price after a mid-sample date changes no decision made before it. Two pre-registered data cross-checks failed for identified structural reasons and were not loosened (section 14).

**Verification.** The code was adversarially reviewed after it was built, in three rounds: 41 findings in all, of which 10 were rated medium and none higher, every one resolved and independently re-verified, with over a hundred adversarial tests left in the suite. Notable catches: a series that stopped early was silently forward-filled to the end of a backtest; a corrupted adjusted price with a clean raw price passed every quality gate; the broker SDK's automatic retry could duplicate an order after a timeout; an order in the broker's "stopped" state was treated as final and re-sent; the string `"false"` in a targets file switched a safety declaration on; and a `.gitignore` pattern had excluded the entire data package from git. The full suite is 402 tests and runs offline in about 20 seconds.

**What this means for the owner.** History, tested as honestly as this harness can manage, does not show a published low-turnover rule beating the index after costs over the last twenty to thirty years. The system is ready to paper-trade any of these rules for operational reasons, but the evidence says the rule to paper-trade first is buy-and-hold with contributions, and that a trend overlay is worth running only if smaller drawdowns matter more than return.

**Not built, on purpose:** any LLM call at runtime; day-trading or intraday logic; single-stock selection; crypto; a ten-country broker matrix (one adapter plus a simulator until the owner's country is known); a GitHub-Actions-cron-only live trader.

---

## 12. Acceptance gates, pre-registered

These thresholds are judgment calls, stated in advance so they cannot be moved after seeing results. Passing them is evidence consistent with an edge under stated assumptions, not proof of future profit. A strategy that passes every gate can still lose money for one to three years.

**Gate A: a candidate may be paper-traded only if**
1. It was pre-registered: economic rationale and parameter ranges written down before testing, and every variant recorded in the trial ledger.
2. It is tested on at least 15 years of daily total-return data covering 2008, 2020 and 2022, with next-bar execution and at least 5 bp per side for ETFs, and still holds up at 2x costs.
3. Its walk-forward net Sharpe is at least 0.5, its CAGR is within 1%/yr of buy-and-hold's, and it either beats buy-and-hold on Sharpe or has at least 30% smaller maximum drawdown. Otherwise buy-and-hold dominates at zero cost and the candidate is rejected. (Amended after the first harness run; see section 14. The amendment changes no verdict.)
4. Its deflated Sharpe ratio, computed with the ledger's trial count and cross-trial variance, is at least 0.95, and its probability of backtest overfitting is at most 0.2.
5. Perturbing each parameter by ±25% keeps at least 70% of the Sharpe ratio (no sharp peak).
6. The block-bootstrap 5th-percentile CAGR is above zero and the 95th-percentile drawdown is no worse than buy-and-hold's.
7. It loses less than buy-and-hold in both 2008 and 2022 and shows positive excess in at least two of three non-overlapping 5-year windows.
8. It passes the structural leakage tests (the buy-and-hold identity test and the perfect-foresight tests), and delaying every fill by one extra trading day changes its Sharpe ratio by at most 0.15, so the result cannot depend on seeing the fill bar.

**Gate B: paper trading is considered working only if**, over at least 20 trading days including one rebalance, one market holiday and one early close: every signal is reproduced by the backtest engine on the same data, no run is missed or duplicated, and the paper-versus-backtest price-return tracking difference averages under 10 bp per day (dividends excluded, since paper does not credit them).

**Gate C: a $1-$100 live smoke test** requires Gate B, a broker account hardened per section 10, funding that costs at most a few dollars (otherwise skip it), and is judged only on plumbing: fills, fees posted, reconciliation, alerts.

**Gate D: scaling to $1,000** requires at least six months of combined paper and live record with live slippage at or below the modelled cost, forward Sharpe inside the backtest bootstrap's 90% band, no kill-switch hit, and annual running cost (hosting, data, maintenance) under 20% of the trial-count-adjusted expected excess profit at the new capital. **Scaling to $10,000 or more** requires at least 24 months forward, a probabilistic Sharpe ratio above zero of at least 0.90, forward Sharpe at least 50% of backtest, and steps of at most 3-10x with at least six months between steps. This last gate is close to unreachable, and that is intended: at 24 months the standard error of a Sharpe ratio is about 0.7, so only a realized Sharpe near 0.9 or above would pass, which is above the plausible true Sharpe of any candidate here. Scaling to $10,000 or more should not rest on this system's evidence alone.

**Kill switch at any stage:** drawdown beyond the *smaller* of 1.25x the backtest maximum and the bootstrap 99th percentile; or beyond an absolute dollar cap the owner sets; or time under water beyond the 95th-percentile estimate; or running cost above realized gross profit for three consecutive months.

---

## 13. Things that depend on your country

Residency was not stated, and it decides more than any strategy choice. Before any live account:

- **Broker**: Alpaca (US; many other countries via support; not Canada), Trading 212 (UK and EU; public API in beta, quantity-only orders, non-idempotent endpoints), Interactive Brokers (most countries; $1 minimum or 1% on tiny orders, weekly manual re-authentication for automation), Zerodha (India; daily manual login required by regulation).
- **Instruments**: EU-regulated brokers block US-domiciled ETFs (SPY, VTI) for retail clients under PRIIPs; UK rules are in transition through June 2027 and US ETFs remain generally unavailable there. UCITS equivalents (for example CSPX, VWCE) are used instead; backtests must then be re-run on the instrument actually held.
- **Tax on each trend switch**: US short-term gains at ordinary rates with a 30-day wash-sale rule; UK CGT 18-24% with a £3,000 allowance; Germany 26.375% with a 30% equity-fund exemption and €1,000 allowance; France 31.4% flat; Ireland 38% exit tax on funds with no loss relief (the overlay is tax-hostile there); Israel 25% on real gains; Netherlands a deemed-return tax where switching has no consequence. Inside an ISA, Roth IRA or TFSA the drag is zero. Small accounts often fall under annual allowances.
- **Dividend withholding on US funds**: 15% for most treaty countries, 25% for Israel and India, 30% otherwise, via W-8BEN.
- **US estate tax**: non-US persons must file a US estate-tax return when US-situs holdings exceed $60,000, with treaty relief for some countries and (unverified) none for Israel or India. Irish-domiciled funds avoid it.
- **Reporting burden**: a foreign-broker account usually means self-assessment; an accountant's fee ($270-800 a year in some countries) can exceed the excess profit on accounts under tens of thousands of dollars.

The repository ships one broker adapter (Alpaca) and a local simulator. A second adapter is added only once the country is known.

---

## 14. Corrections applied during verification

The adversarial checks changed the following, and the text above reflects the corrected versions:

- The recommended primary strategy was changed from a trend filter to buy-and-hold. The researcher's own replication shows the trend filter's expected excess return is negative and its risk benefit comes from two years; a later microstructure paper was quoted only for its favourable half.
- The $1 Alpaca round-trip fee was corrected from about 1% to about 4% (each fee type rounds up separately, and CAT applies to buys).
- The GTAA5 comparison against a US 60/40 was flagged as an unmatched benchmark; the 220 bp/yr rebalance-day dispersion was added.
- "Pre-cutoff LLM backtests are uninformative" was softened to "biased upward by an unknown, model-specific amount"; no cited study tested Claude 5.x.
- A flat 50% Sharpe haircut attributed to Harvey and Liu was removed; they reject it.
- The deflated Sharpe ratio must use the cross-trial variance of Sharpe ratios, not 1 over the square root of years.
- The kill switch was changed from the larger to the smaller of two drawdown thresholds, plus an absolute dollar cap.
- The SEC half-penny tick change is deferred to November 2027, not November 2026.
- TradingAgents' published evidence covers three tickers, not five; the hobbyist re-test used Claude Haiku 4.5 and Opus 4.8, not OpenAI models.
- Alpha Arena Season 1 losses were 31-63%, not 40-60%; StockBench results are inconclusive rather than negative.
- Observed Anthropic model lifetimes are 12-25 months, not 13-16.
- Two supporting citations were dropped: arXiv 2201.08218 (an unrelated Swedish LSTM paper) and the "73-81% of crypto users lost" figure attributed to the wrong BIS document.
- Yahoo Finance is reachable from this container only with a browser user agent; automated collection sits outside Yahoo's terms, so it is treated as personal-use research data and never committed. FRED's terms forbid archiving its content, so FRED downloads are not committed either.
- The international-equity and commodity backfills proposed by the data researcher failed their own splice-validation rules (correlations 0.984 and 0.906) and are not used; only the 1996-05 fund-only sample is trusted.
- growney's fee at €10k is 0.68%, not 0.38%; a "GitHub Environment secrets with required reviewers on a free private repo" recommendation was removed because that feature is not available on the free plan for private repositories.

Rulings on the fact-checker's judgment points, after the first harness run:

- Gate A.3 was amended post hoc. As first written, a strategy could pass by beating buy-and-hold on Sharpe alone, which the verified replication shows a trend filter can do while lagging in return by 1.7 points a year. A.3 now also requires CAGR within 1%/yr of buy-and-hold. This is recorded as a post-hoc change; it alters no verdict, because every candidate already fails A.4 and A.7.
- The unattended runner takes prices from the broker's own data API rather than Yahoo, so automated collection outside Yahoo's terms is confined to one-off personal research downloads. Tiingo's free tier remains the licensed option for historical refreshes.
- Live broker keys are never stored on GitHub; the repository holds paper keys at most.
- The custom backtest engine stays the primary engine, against the tooling verifier's preference for `bt`, because it models per-day fee rounding that `bt` cannot; the risk the verifier raised is met by the `bt` cross-check (agreement to a millionth of a basis point on buy-and-hold and the 10-month rule), the identity test and the perfect-foresight tests.
- Gate D is now stated to be close to unreachable by design.
- Gate A.8 was strengthened post hoc after the adversarial code review showed the one-day-delay test has little power against a small leak: every candidate is now also re-run with all prices after a mid-sample date rewritten, and every decision before that date must be unchanged. All candidates pass; no verdict changed.
- Alpaca's $1 minimum applies to buy orders only; the engine and runner were changed to match, and the $1-scale rows in `results/scaling.md` reflect that.
- Two pre-registered cross-check thresholds failed for identified structural reasons and were not loosened: the S&P 500's correlation with the Ken French total-market series is 0.988 by construction (total-market funds pass at 0.999), and the daily-accrual 3-month T-bill series differs from French's locked 1-month bill by more than 10 bp in 2 of 440 months, both in 2001 when the Fed cut rates mid-month.
- A final fact-check pass corrected the verdict tally (161 claims: 85 confirmed, 69 needs qualification, 7 refuted) and the research volume (about 90,000 words), and noted that the fee table's percentages include a one-tick spread.
- Composer is the only no-code trend tool found, not proven the only one; GitHub cron delays were reported up to 14 hours, not 9; Yahoo's terms forbid, not merely restrict, automated collection.
- The 1996-05 fund-only sample covers US equity, bonds, Treasuries, REITs and cash only; the international, commodity and gold sleeves have no validated pre-ETF history.

---

## 15. Selected sources

Academic and regulatory:
- Faber, "A Quantitative Approach to Tactical Asset Allocation" (SSRN 962461, 2013 update). Concretum Group GTAA5 extension (June 2026).
- Moskowitz, Ooi, Pedersen, "Time Series Momentum," JFE 2012. Huang, Li, Wang, Zhou, JFE 2020. Kurth, Eisler, Rej, Bouchaud, arXiv 2607.01550 (2026).
- McLean and Pontiff, JF 2016. Harvey, Liu, Zhu, RFS 2016. Harvey and Liu, "Backtesting," JPM 2015. Jensen, Kelly, Pedersen, JF 2023.
- Bailey, Borwein, López de Prado, Zhu, "The Probability of Backtest Overfitting," J. Comp. Finance 2016. Bailey and López de Prado, "The Deflated Sharpe Ratio," JPM 2014. Lo, "The Statistics of Sharpe Ratios," FAJ 2002.
- Wiecki et al., "All That Glitters Is Not Gold," J. Investing 2016. Suhonen, Lennkh, Perez, JPM 2017.
- Barber, Lee, Liu, Odean (Taiwan day traders), JFM 2014. Chague, De-Losso, Giovannetti (Brazil), 2019. Barber and Odean, JF 2000.
- Avramov, Cheng, Metzker, Management Science 2023. Fischer and Krauss, EJOR 2018. Do and Faff, FAJ 2010 and JFR 2012.
- Lopez-Lira and Tang, arXiv 2304.07619 (v6, 2025). Lopez-Lira, Tang, Zhu, arXiv 2504.14765. Li et al., FINSABER, KDD 2026 (arXiv 2505.07078). Yao, Zheng, Li audit, arXiv 2606.08285. Chen and Pu, arXiv 2601.11958. Gençay, arXiv 2608.27734.
- SEC administrative order on Knight Capital (34-70694, 2013). FCA final notice, Citigroup Global Markets (2024). 17 CFR 240.15c3-5.
- FINRA Regulatory Notice 26-10 (intraday margin, PDT replacement). SEC fee rate advisory FY2026.

Vendor and platform documentation (all fetched 2026-09-29):
- Alpaca: fee schedule (rev. 2026-09-17), fractional trading, orders, paper trading, account configurations, market data plans, non-US accounts.
- Anthropic: pricing, prompt caching, batch processing, model overview and deprecations, consumer terms.
- GitHub: Actions billing, schedule events, secure use, deployments and environments. Cloudflare Workers limits. Google Cloud Scheduler.
- PyPI metadata for bt, vectorbt, backtrader, backtesting.py, zipline-reloaded, nautilus_trader, Lumibot, alpaca-py, pylivetrader.
- Ken French Data Library; FRED; Damodaran historical returns; SPIVA year-end 2024 and 2025.

The full verified research, including every claim, verdict and pushback, is in `docs/research-archive/`.
