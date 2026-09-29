# llm-in-the-loop

## SUMMARY

## Bottom line
The best peer-reviewed-quality evidence says LLMs can read news and pull out short-horizon return signals. Those signals are real but thin. They depend on short-selling, daily turnover and small caps, and they have weakened sharply since 2021. Evidence that **LLM agents making per-trade decisions** beat buy-and-hold is weak. When independent teams re-test claimed wins over longer periods, broader stock universes or live markets, the wins mostly disappear. For someone with about $1 to a few hundred dollars, any *recurring* LLM cost is larger than any plausible trading edge. The LLM belongs in one-time design, code writing and review, and rare exception-driven explanation. It does not belong in the per-trade decision loop.

---
## 1. Academic evidence on LLM return prediction

**Lopez-Lira & Tang, "Can ChatGPT Forecast Stock Price Movements?"** (arXiv 2304.07619, v6 Oct 30 2025, https://arxiv.org/abs/2304.07619). I read the full PDF. Key details:
- **Data:** headlines for 4,123 US stocks, **Oct 2021 to May 2024**. This window was chosen to fall after GPT's Sept-2021 training cutoff, which removes look-ahead bias by design.
- **Returns:** the daily long-short strategy on overnight news earns **34 bps/day before costs**. Cumulative return is about 700% before costs.
- **Costs:** with round-trip costs of **5 bps** the cumulative return is still >300%; at **10 bps** it is >100%; at **20 bps it is unprofitable**. Turnover is about **190%/day**. At 10 bps the Sharpe falls from 2.97 to 1.29.
- **Decay:** the Sharpe **fell from 6.54 (2021Q4) to 3.68 (2022), 2.33 (2023) and 1.22 (Jan–May 2024)**. The authors link this to wider LLM adoption.
- **Where the edge sits:** it is stronger in small caps and on negative news, which means the short leg. Large caps show no drift after negative news.
- **The authors' own conclusion:** exploiting it "is only feasible for market participants whose transaction costs are sufficiently low, such as market makers."

For a retail account this signal is out of reach: it needs daily rebalancing, shorting and trades at the opening/closing auctions.

**Chen, Kelly & Xiu, "Expected Returns and Large Language Models"** (SSRN 4416687, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4416687; slides https://jacobslevycenter.wharton.upenn.edu/wp-content/uploads/2024/09/Kelly-WhartonJL.pdf).
- They use LLM embeddings of news to predict the cross-section of returns and report "economically meaningful Sharpe ratios after transaction costs."
- Predictability lasts several days in small stocks and fades quickly in large stocks.
- SSRN returned 403, so I relied on search snippets and did not verify the exact Sharpe values.

**He, Lv, Manela & Wu, "Chronologically Consistent LLMs"** (arXiv 2502.21206 v3 Jul 2025, https://arxiv.org/abs/2502.21206). I read the PDF text.
- They trained models only on text available at each date. The resulting daily long-short decile portfolios reach **Sharpe 4.80–4.92** over 2008–2023.
- These are **equal-weighted, rebalanced daily, and include no transaction costs**.
- Performance is statistically no different from Llama-3.1, so they conclude "**lookahead bias is modest**" in this application.
- The WebFetch summarizer initially said the opposite. The primary text contradicts it.

**Look-ahead / memorization critiques:**
- Glasserman & Lin (2023, https://arxiv.org/abs/2309.17322): in-sample, a "distraction effect" (the model's general knowledge of well-known firms) outweighs look-ahead. Anonymizing company names helps.
- Sarkar & Vafa (ICML 2025, https://openreview.net/pdf?id=fn9cJkB86T): LLMs use COVID knowledge when "predicting" pre-2020 risk factors, even when told not to. Prompting does not fix it.
- Lopez-Lira, Tang & Zhu, "The Memorization Problem" (https://arxiv.org/abs/2504.14765): LLMs recall exact pre-cutoff economic values. Masking and instructions fail. No recall appears after the cutoff.
- Gao, Jiang & Yan (Dec 2025, https://arxiv.org/abs/2512.23847): a one-SD increase in their "Lookahead Propensity" raises the LLM return-prediction effect by 0.077%, **about 37% of the standalone effect of 0.197%/day**.
- The net picture: in-sample LLM backtests are contaminated to some degree, and the only clean test is post-cutoff or live data.

**Kim, Muhn & Nikolaev, "Financial Statement Analysis with LLMs"** (arXiv 2407.17866). This paper was widely cited for "GPT beats analysts at predicting earnings changes." It was **withdrawn on Feb 20 2025** because "a co-author identified inconsistencies in the data and analyses while attempting to replicate" (https://arxiv.org/abs/2407.17866). A separate, related Kim & Nikolaev *Journal of Accounting Research* paper ("Context-Based Interpretation of Financial Information," a deep-learning paper rather than an LLM one) was later **retracted** as non-reproducible (https://onlinelibrary.wiley.com/doi/10.1111/1475-679X.12593). Do not rely on the LLM financial-statement result.

**Strongest 2026 pro-LLM result: Chen & Pu, "Agentic AI Nowcasting"** (arXiv 2601.11958, Jan 2026, https://arxiv.org/abs/2601.11958).
- Setup: an unnamed frontier LLM with web search ranks every Russell 1000 stock daily from **Apr 2025**, and the results were collected prospectively.
- Result: the long-only top-20 portfolio has **18.4 bps/day FF5+momentum alpha and Sharpe 2.43**. It returned about 50% against 26% for the index over ~158 trading days. Turnover is 57%/day, and the authors estimate costs at <10% of gross alpha.
- The edge sits only in the long leg; bottom-ranked stocks behave like the market.
- Caveats:
  - Only about 10 months of data, in a strong market.
  - A single unnamed model, accessed through a consumer **web interface**.
  - No API cost reported.
  - The authors call the data "preliminary" and warn about anomaly decay.

## 2. LLM agent frameworks: claims and reality

| Framework | Claimed | Test window | OOS / costs | Independent check | Status 2026 |
|---|---|---|---|---|---|
| TradingAgents (Xiao et al., arXiv 2412.20138) | AAPL cum. return 26.62%, Sharpe 8.21; GOOGL 24.36%/6.39; AMZN 23.21%/5.60 | **Jan 1 – Mar 29 2024 (3 months, 3 headline tickers)** | Costs not addressed; "11 LLM calls & 20+ tool calls/prediction"; budget limited the backtest to 3 months (https://arxiv.org/html/2412.20138v7) | Hobbyist re-test (anonymized, 10 bps costs) on AAPL Mar–Jun 2026: agent −0.9% vs buy-and-hold +15.7%, about $3.70 for 13 decisions (https://github.com/Kantamaniprakash/trading-agents-lab), low-authority source | ~109k stars, v0.5.2 Sep 2026; README: "Backtest results are not guaranteed to match any published figure"; research-only (https://github.com/TauricResearch/TradingAgents) |
| FinMem | TSLA Sharpe 2.679, +61.8% (Oct 2022–Apr 2023) | 6 months, 1 ticker | — | FINSABER re-ran the same window: Sharpe 0.927, +19.9%. Bias-mitigated 2004–2024 over broad S&P 500 selections (e.g., volatility scheme): **Sharpe −0.228, AR 4.06% vs buy-and-hold 0.703 / 7.90%** | academic |
| FinAgent | similar short-window claims | — | — | FINSABER, same setup: **Sharpe 0.241, AR 4.95%** vs buy-and-hold 0.703 / 7.90% | academic |
| FINSABER itself (Li et al., KDD 2026 oral, https://arxiv.org/abs/2505.07078) | "LLM strategies are overly conservative in bull markets... and overly aggressive in bear markets"; "previously claimed superiority... largely driven by selective evaluation setups" | 2004–2024, 100+ symbols, delisted names included | Commission $0.0049/share, min $0.99/order | — | code at github.com/waylonli/FINSABER |
| virattt/ai-hedge-fund | no performance claims | — | "does not actually make any trades"; educational only | — | ~64k stars (https://github.com/virattt/ai-hedge-fund) |
| FinGPT | sentiment F1 0.882 on FPB; no trading claims | — | "NOT a recommendation to trade real money" | — | README news stops at Nov 2023, so effectively stale (https://github.com/AI4Finance-Foundation/FinGPT) |
| FinRobot | equity-research report generation; no trading claims | — | disclaimer against live trading | — | ~8k stars, active (https://github.com/AI4Finance-Foundation/FinRobot) |
| FinRL (RL, not LLM) | no headline numbers | — | academic-use disclaimer; successor FinRL-X | — | https://github.com/AI4Finance-Foundation/FinRL |
| Alpha-GPT (arXiv 2308.00016) | human-in-the-loop alpha-formula generation | — | a research-tool role, not per-trade decisions | — | EMNLP 2025 demo |
| RD-Agent(Q) (Microsoft, NeurIPS 2025) | about 2× annualized returns vs factor libraries with 70% fewer factors; "under $10" per run | China A-share (Qlib) | offline research automation | — | https://neurips.cc/virtual/2025/poster/121804 |

Meta-evidence:
- **Yao, Zheng & Li audit** (arXiv 2606.08285, https://arxiv.org/html/2606.08285v2) covered 30 LLM trading studies from 2023 to May 2026. Only **14/30** had recoverable cost/turnover treatment and only **18/30** had recoverable artifacts. Their verdict: "the field has matured faster in architecture proposals than in evaluation discipline."
- **Wang & Saxena SoK** (arXiv 2609.19705, Sep 2026, https://arxiv.org/abs/2609.19705) examined 15 academic trading-agent schemes: **80% failed at least one core robustness metric and 100% had security vulnerabilities** (poisoned news/sources, agent attacks).

## 3. Live and contamination-free evidence
- **StockBench** (arXiv 2510.02209, https://arxiv.org/html/2510.02209):
  - Setup: 20 DJIA stocks, Mar 3 to Jun 30 2025.
  - Result: buy-and-hold returned 0.4% (MDD −15.2%); the best model (Kimi-K2) returned 1.9% (MDD −11.8%); "most models struggle to outperform."
  - It models **no trading costs**.
- **LiveTradeBench** (arXiv 2511.03628, https://arxiv.org/html/2511.03628v1):
  - Setup: 21 LLMs, 50 live trading days, Aug–Oct 2025.
  - Result: the Spearman correlation between LMArena score and stock returns is **0.054**. General intelligence does not predict trading skill.
- **Nof1 Alpha Arena** (real money; secondary sources, since nof1.ai returned 429):
  - Season 1 (Oct 18 – Nov 3 2025, $10k each, crypto perpetuals): Qwen3-Max finished +22%, DeepSeek slightly positive, and GPT-5, Gemini 2.5 Pro, Grok 4 and Claude Sonnet 4.5 lost roughly 42–63% (https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/).
  - Season 1.5 (US equities, 8 models × 4 variants, $320k): reportedly **6 of 32 accounts ended positive, with an aggregate loss of about 35%**. The Season 1 winner lost in all four variants. An unreleased "Grok 4.20" averaged +12% (https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/; https://www.onedayadvisor.com/2025/12/nof1ai-alpha-arena-review-season-15.html).
  - Nof1's founder, quoted by Bloomberg via Business Standard: "LLMs can't really make money by themselves."
  - Two-week, leveraged, tiny samples make this entertainment rather than proof. The direction still matches the other evidence.
- **Institutional use:** Man Group's AlphaGPT (Bloomberg, Jul 10 2025, https://www.bloomberg.com/news/articles/2025-07-10/man-group-says-agentic-ai-is-now-devising-quant-trading-signals; Man's own note https://www.man.com/insights/what-ai-can-do-for-alpha) generates hypotheses, writes code and backtests signals. "Several dozen" signals were approved for live trading, but only after the same investment-committee review as human research. The LLM is a **research assistant, not the trader**. I found no audited public track record of an LLM making per-trade decisions profitably over a year or more.

## 4. LLM-specific failure modes and controls
1. **Training-data look-ahead.** Current Claude models (Fable 5.1, Opus 5.5, Sonnet 5.5) have a **training cutoff of Jun 2026**; Haiku 4.5's is Jul 2025 (https://platform.claude.com/docs/en/about-claude/models/overview).
   - Any backtest of Opus/Sonnet 5.5 decisions on dates before July 2026 is contaminated. Only about 3 months of clean history exist today.
   - Controls researchers use: post-cutoff-only evaluation, anonymizing tickers and dates (Glasserman–Lin), chronologically consistent models, and LAP-style tests. Instructions not to use future knowledge fail.
2. **Non-determinism.**
   - Thinking Machines (Sep 2025, https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/) got **80 unique completions from 1,000 temperature-0 runs** because of batch-size variance.
   - On Claude 4.7+ the `temperature`/`top_p`/`top_k` parameters are **deprecated and return a 400 error if set to non-default values** (https://platform.claude.com/docs/en/about-claude/model-deprecations), so you cannot even request greedy decoding.
   - AlphaForgeBench (arXiv 2602.18481) reports "extreme run-to-run variance... even under deterministic decoding" and "irrational action flipping" for per-step LLM trading. Its fix is to have LLMs write factor code that is then executed deterministically.
   - Controls: cache every response, log prompts and outputs, use majority votes (which multiply cost), or move the LLM out of the loop.
3. **Hallucinated or incorrect numbers.** BacktestBench (arXiv 2605.17937): the best model (Gemini 3 Pro) got **67.41% overall accuracy** at reproducing backtest results and **51.67%** on metric calculation. Sharpe and volatility annualization are "disaster zones." So LLM-written backtest code must be checked against known answers.
4. **Prompt and persona sensitivity.** Across 3,575 SEC filings and 12 LLMs, role and persona prompts change conclusions drawn from the same evidence; mitigations reduce this but do not remove it (arXiv 2609.03218).
5. **Model deprecation.** Anthropic gives at least 60 days' notice.
   - Observed lifetimes are about 13–16 months: Sonnet 3.5 (Jun 2024) was retired Oct 2025, and Opus 4 (May 2025) was retired Jun 2026.
   - Haiku 4.5 is only guaranteed until Oct 15 2026 (https://platform.claude.com/docs/en/about-claude/model-deprecations).
   - A strategy whose edge lives inside one model version has a built-in expiry date and must be re-validated on each migration.
6. **Cost blow-ups.** Agentic loops with tool calls grow context quickly. TradingAgents needed 11 LLM calls plus 20+ tool calls per ticker-day. Web search costs **$10 per 1,000 searches** on top of tokens (https://platform.claude.com/docs/en/about-claude/pricing).
7. **Security.** Adversarial or poisoned news can steer agents (the SoK above). A retail bot that reads free news feeds is exposed.

## 5. Token cost per role (Claude prices given; arithmetic shown)
Prices per million tokens (input/output): Haiku 4.5 $1/$5, Sonnet 5.5 $2/$10, Opus 5.5 $4/$20. Batch halves these. Break-even capital = annual LLM cost ÷ annual excess return. I use a generous 5% excess return.

- **(a) One-time strategy design and code generation.** About 2M input + 200k output on Opus 5.5 = $8 + $4 = **about $12 one-off**.
  - Evidence: Man AlphaGPT; RD-Agent(Q) at under $10 per run; AlphaForgeBench prefers code generation over per-step actions.
  - This is a sunk research cost, not a running cost. **Good fit.**
- **(b) Code review and bug finding.** About 50k input + 5k output on Opus = $0.20 + $0.10 = **about $0.30 per review**.
  - Evidence: BacktestBench error rates show LLM code needs verification. Review also catches look-ahead bugs in the person's own code.
  - **Good fit**, if it is paired with deterministic tests.
- **(c) Monitoring and anomaly explanation.** About 20k input + 2k output on Sonnet = $0.06 per call. Weekly that is about **$3/yr**; if triggered only by deterministic alerts, it is about $0.
  - Evidence: no trading-specific studies. Its value is operational (spotting broken data feeds or duplicate orders), not alpha. **Acceptable** if exception-driven.
- **(d) News and event risk filter.** About 10k input + 1k output per day on Haiku = $0.015/day; with batch that is **about $1.9/yr**.
  - Evidence: Lopez-Lira–Tang show LLMs classify headline direction well. However, earnings dates and trading halts come from deterministic calendars and feeds (e.g., Alpha Vantage EARNINGS_CALENDAR; Nasdaq halt feeds) at no token cost.
  - **Marginal.** Use deterministic rules first.
- **(e) Per-trade decision-making.** About 5k input + 300 output on Haiku = $0.0065 per ticker-day. For 10 tickers that is about $16/yr (**$8/yr with batch**), so break-even capital at 5% is about $160–$330. On Sonnet with 20k + 2k tokens: $0.06 per ticker-day, about $150/yr for 10 tickers, so break-even is **about $3,000**.
  - Evidence: FINSABER, StockBench, LiveTradeBench and Alpha Arena all show no reliable edge.
  - **Poor fit.**
- **(f) Multi-agent debate per trade (TradingAgents-style).** 11 calls × (8k input + 1.5k output) on Sonnet = 88k × $2/M + 16.5k × $10/M = $0.18 + $0.17 = **about $0.34 per ticker-day, about $86/yr per ticker**. On Opus it is about $0.68, or $171/yr.
  - Break-even at 5% excess return is about **$1,700 (Sonnet) to $3,400 (Opus) per ticker**.
  - The hobbyist re-test measured about $0.28 per decision on OpenAI models.
  - **Worst fit.**
- **Chen & Pu–style daily agentic ranking of 1,000 stocks.** Assume 3 searches ($0.03) + 30k input ($0.06) + 1k output ($0.01) on Sonnet: about $0.10 per stock-day, **about $25k/yr**.
  - For 50 stocks it is about $1,260/yr. If the reported 18.4 bps/day alpha (about 46%/yr uncompounded) survived, break-even would be about $2,700.
  - That condition is a very large "if."

**At $1 of capital, even a 50% annual edge is $0.50/yr, which is less than a single day of role (e) on 10 tickers ($0.065/day).** Any recurring LLM call is unaffordable at that size. The $1 phase must run with **zero** tokens in the loop.

## 6. Honest assessment
**Where the LLM belongs** for tiny capital:
- Offline: researching and designing rule-based strategies, writing the backtester and broker code, adversarial code review (look-ahead, survivorship, cost modeling), writing the validation protocol, and explaining results.
- Occasionally: exception-triggered diagnostics.
- These are one-time or rare costs of a few dollars to tens of dollars in total. They do not scale with the number of trades.

**Where it does not belong:**
- Per-trade buy/sell decisions and multi-agent debate on every trade.
- Any design whose edge cannot be backtested without contamination. A backtest of a mid-2026-cutoff Claude over 2020–2025 is worthless as proof.
- The news-drift strategies from the literature: they need shorting, daily turnover and ≤10 bps costs, and they have been decaying.

**Strongest counter-argument:**
- Chen & Pu (2026) is prospective, post-cutoff, long-only, on liquid Russell 1000 stocks with low spreads, and shows 18.4 bps/day alpha at Sharpe 2.43. This matches what a retail account can do: long-only, liquid names, fractional shares.
- Lopez-Lira–Tang also found a genuine post-cutoff signal.
- If one frontier model reading the web adds alpha today, then "LLM out of the loop" leaves money on the table. Costs fall about yearly, which could shrink the break-even capital to hundreds of dollars.

**Rebuttal:**
- About 10 months in a bull market, one unnamed model, no reported compute cost, and the documented decay pattern (Sharpe 6.5 → 1.2 in about 2.5 years for the earlier signal).
- Live multi-model tournaments lost money in aggregate, and general benchmark skill does not predict returns (ρ = 0.054).
- The person cannot validate such a strategy without months of forward paper trading at real token cost, and a model deprecation mid-test resets the clock.
- The rational way to test the counter-argument is a **cheap, bounded forward paper test**, for example the top-N long-only on 50 liquid names with batch Haiku or Sonnet. Run it only after a zero-token baseline exists to beat, and track API cost as a strategy cost line.

## CLAIMS

- **[C1] (high)** In Lopez-Lira & Tang, the GPT-4 headline long-short strategy earns 34 bps/day before costs over Oct 2021–May 2024, stays profitable at 5–10 bps round-trip costs, and becomes unprofitable at 20 bps round-trip costs; turnover is about 190%/day.
  - evidence: Full-text PDF v6 (Oct 30 2025): '5 bps... over 300%... 10 bps... above 100%... 20 bps round-trip makes the strategy unprofitable'; 'turnover of approximately 190% per day'.
  - sources: https://arxiv.org/abs/2304.07619, https://arxiv.org/pdf/2304.07619
- **[C2] (high)** The Lopez-Lira & Tang strategy's annualized Sharpe decayed from 6.54 (2021Q4) to 3.68 (2022), 2.33 (2023) and 1.22 (Jan–May 2024), and the drift is concentrated in small caps and negative news (the short leg).
  - evidence: Full-text PDF section on decline and size terciles: 'large-cap stocks... exhibit no drift, whereas small-cap stocks continue to drift'.
  - sources: https://arxiv.org/pdf/2304.07619
- **[C3] (high)** The Kim, Muhn & Nikolaev LLM financial-statement-analysis paper was withdrawn on Feb 20 2025 after a co-author found data and analysis inconsistencies while trying to replicate it.
  - evidence: arXiv v3 withdrawal notice quoted verbatim.
  - sources: https://arxiv.org/abs/2407.17866
- **[C4] (high)** TradingAgents' headline results (e.g., AAPL +26.62%, Sharpe 8.21) come from a 3-month backtest (Jan 1–Mar 29 2024) on a few tickers, with no transaction costs addressed and about 11 LLM calls plus 20+ tool calls per prediction.
  - evidence: arXiv HTML v7 experimental section and limitations.
  - sources: https://arxiv.org/html/2412.20138v7, https://github.com/TauricResearch/TradingAgents
- **[C5] (medium)** In FINSABER's bias-mitigated 2004–2024 evaluation (KDD 2026), LLM strategies FinMem and FinAgent underperform buy-and-hold (e.g., Sharpe −0.228 and 0.241 vs 0.703 under the volatility selection scheme), and previously claimed LLM superiority is attributed to selective evaluation setups.
  - evidence: arXiv 2505.07078 abstract and Table 4 as read via WebFetch; commission $0.0049/share, min $0.99.
  - sources: https://arxiv.org/abs/2505.07078, https://arxiv.org/html/2505.07078
- **[C6] (medium)** In an audit of 30 LLM trading studies (2023–May 2026), only 14 had recoverable cost/turnover treatment and 18 had recoverable code or artifacts.
  - evidence: Yao, Zheng & Li audit, arXiv 2606.08285v2.
  - sources: https://arxiv.org/html/2606.08285v2
- **[C7] (high)** In live and contamination-free benchmarks, most LLM agents fail to beat buy-and-hold: in StockBench (Mar–Jun 2025, 20 DJIA stocks, no costs) the best model returned 1.9% vs 0.4% passive, and in LiveTradeBench (21 LLMs, 50 live days) the correlation between LMArena score and stock returns is 0.054.
  - evidence: StockBench results table and limitations; LiveTradeBench abstract and results.
  - sources: https://arxiv.org/html/2510.02209, https://arxiv.org/html/2511.03628v1
- **[C8] (medium)** In real-money Alpha Arena Season 1.5 (US equities, $320k across 32 accounts), only 6 accounts ended positive and the aggregate loss was about 35%; in Season 1 (crypto), 4 of 6 frontier models lost roughly 40–60%.
  - evidence: Secondary news reports; nof1.ai was rate-limited (429), so not verified against the primary source.
  - sources: https://forklog.com/en/ai-model-grok-4-2-triumphs-in-trading-tournament/, https://www.gncrypto.news/news/qwen-wins-alpha-arena-season-1-with-22-percent-returns/, https://www.onedayadvisor.com/2025/12/nof1ai-alpha-arena-review-season-15.html
- **[C9] (high)** Current Claude Opus 5.5 and Sonnet 5.5 have a June 2026 training-data cutoff, so any backtest of their decisions on pre-July-2026 dates is exposed to look-ahead/memorization bias; prompting the model to ignore future knowledge does not fix this.
  - evidence: Anthropic models overview table; Sarkar & Vafa and Lopez-Lira/Tang/Zhu show instructions and masking fail to prevent recall.
  - sources: https://platform.claude.com/docs/en/about-claude/models/overview, https://openreview.net/pdf?id=fn9cJkB86T, https://arxiv.org/abs/2504.14765
- **[C10] (high)** LLM outputs are not reproducible: 1,000 temperature-0 runs gave 80 unique completions in one test, and on Claude 4.7+ temperature/top_p/top_k cannot be set to non-default values (400 error).
  - evidence: Thinking Machines blog, Sep 10 2025; Anthropic deprecations page, API parameter table.
  - sources: https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/, https://platform.claude.com/docs/en/about-claude/model-deprecations
- **[C11] (high)** Anthropic gives at least 60 days' notice before retiring a model, and observed model lifetimes are about 13–16 months (e.g., Claude Opus 4 released May 2025, retired June 15 2026); Haiku 4.5 is guaranteed only until Oct 15 2026.
  - evidence: Anthropic model deprecations page.
  - sources: https://platform.claude.com/docs/en/about-claude/model-deprecations
- **[C12] (medium)** The strongest pro-LLM evidence is Chen & Pu (Jan 2026): a web-searching LLM ranked Russell 1000 stocks daily and prospectively from Apr 2025, and the long-only top 20 earned 18.4 bps/day FF5+momentum alpha (Sharpe 2.43) over about 158 days, with no model named and no compute cost reported.
  - evidence: arXiv 2601.11958 abstract and HTML.
  - sources: https://arxiv.org/abs/2601.11958, https://arxiv.org/html/2601.11958
- **[C13] (high)** Man Group's AlphaGPT uses LLM agents to generate, code and backtest signal ideas, and every signal goes through the same human investment-committee review before live trading: the LLM is a research tool, not the per-trade decision-maker.
  - evidence: Bloomberg (Jul 10 2025) and Man Group's own insight article.
  - sources: https://www.bloomberg.com/news/articles/2025-07-10/man-group-says-agentic-ai-is-now-devising-quant-trading-signals, https://www.man.com/insights/what-ai-can-do-for-alpha
- **[C14] (medium)** LLMs frequently get backtest math wrong: the best model on BacktestBench reached only 67.41% overall accuracy and 51.67% on metric calculation, with Sharpe and volatility annualization as the main failure points.
  - evidence: BacktestBench arXiv 2605.17937.
  - sources: https://arxiv.org/html/2605.17937

## RECOMMENDATIONS

- Keep the LLM out of the per-trade decision loop during the $0–$1 phases. At $1 of capital even a 50%/yr edge is $0.50/yr, which is less than one day of per-ticker LLM calls, so the live and paper loop must use zero tokens (pure deterministic rules).
- Use Claude (Opus when in doubt) for one-time work: strategy research, writing the backtester and broker adapter, and adversarial code review for look-ahead, survivorship and cost bugs. Budget this as a sunk research cost of roughly $10–$50 in total, not a running cost.
- Never trust a backtest that uses an LLM's judgment on dates before its training cutoff (June 2026 for Opus/Sonnet 5.5). If an LLM signal is ever tested, test it only on post-cutoff dates, or better, as a prospective forward paper test with every response cached and logged.
- Verify every LLM-written metric (Sharpe, volatility, drawdown, annualization) against a hand-checked known answer or a trusted library before believing results; BacktestBench shows even top models get about one-third to one-half of these wrong.
- Before adding any LLM signal, calculate break-even capital: annual LLM cost ÷ expected annual excess return. Example: a 10-ticker daily Haiku batch at about $8/yr needs about $160 of capital at a 5% edge; TradingAgents-style debate on Sonnet at about $86/yr per ticker needs about $1,700 per ticker. Do not deploy if capital is below break-even.
- Build risk filters (skip earnings days, skip halted names) from deterministic calendars and feeds first; add a batched Haiku headline filter (about $2/yr) only if forward paper testing shows it reduces drawdowns versus the rule-only version.
- If the person later wants to test the Chen & Pu-style counter-argument, run it as a bounded, cost-tracked forward paper experiment (e.g., 50 liquid long-only names, weekly rather than daily, batch API) against a zero-token baseline for at least 6 months, with API spend recorded as a strategy cost.
- Treat every framework repo (TradingAgents, ai-hedge-fund, FinGPT, FinRobot, FinRL) as research scaffolding, not a proven money-maker: none publishes an audited, cost-inclusive, out-of-sample track record, and independent re-tests show their headline gains shrinking or vanishing.
- Pin model IDs, log model version with every decision, and plan to re-validate on each model migration: Anthropic gives at least 60 days' notice and model lifetimes are about 13–16 months.

## OPEN QUESTIONS

- Exact Sharpe after costs in Chen, Kelly & Xiu 'Expected Returns and LLMs' could not be verified (SSRN returned 403).
- Alpha Arena per-model results were only confirmed via secondary news sources; nof1.ai returned HTTP 429.
- Chen & Pu (2026) do not name the model or report compute cost, and use a consumer web interface. Whether their result survives costs at retail scale, longer samples, or other models is unknown, and no replication was found.
- No study found that measures the incremental value of an LLM news/event risk filter over a deterministic earnings-calendar and halt filter for a retail long-only strategy.
- Whether the Kim, Muhn & Nikolaev LLM financial-statement paper will be reinstated in corrected form is unknown; only the withdrawal and the retraction of a related JAR paper were confirmed.
- Token counts per role are my own estimates from typical prompt sizes and the hobbyist TradingAgents re-test (about $0.28/decision); actual Claude usage on the newer tokenizer (about 30% more tokens per text) should be measured in a pilot.
- Whether the TradingAgents paper's AAPL +26.6% in Q1 2024 (a quarter in which AAPL itself fell, by my recollection) reflects shorting or a data issue was not resolved from the paper text.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** In Lopez-Lira & Tang, the GPT-4 headline long-short strategy earns 34 bps/day before costs over Oct 2021–May 2024, stays profitable at 5–10 bps round-trip costs, and becomes unprofitable at 20 bps round-trip costs; turnover is about 190%/day.
  - reasoning: Extracted the full v6 PDF text locally. Verbatim: 'A long-short daily-rebalanced strategy based on GPT-4's assessments of overnight news generates average returns of 34 basis points (bps) per day before transaction costs'; 'Assuming a transaction cost of 5 bps round-trip, the strategy still earns a cumulative return of over 300%... 10 bps round-trip, the cumulative return is still above 100%. A transaction cost of 20 bps round-trip makes the strategy unprofitable'; 'turnover of approximately 190% per day'; the Sharpe is 2.97 before costs and 1.29 at 10 bps; the cumulative return is about 700% from 2021m10 to 2024m5; there are 4,123 companies; and the sentence 'only feasible for market participants whose transaction costs are sufficiently low, such as market makers.' One addition: execution is assumed at the opening and closing auctions, with no bid-ask spread modeled. A retail account using fractional shares or PFOF routing would not get those fills.
- **[C2] CONFIRMED** The Lopez-Lira & Tang strategy's annualized Sharpe decayed from 6.54 (2021Q4) to 3.68 (2022), 2.33 (2023) and 1.22 (Jan–May 2024), and the drift is concentrated in small caps and negative news (the short leg).
  - reasoning: Verbatim: 'the annualized Sharpe ratio declines from 6.54 in 2021Q4 to 3.68 in 2022, 2.33 in 2023, and to 1.22 over January-May 2024.' Also: 'Following negative news, large-cap stocks (e.g., the top tercile) exhibit no drift, whereas small-cap stocks continue to drift.' The legs split as follows: long leg 8 bps/day with Sharpe 0.78, short leg 26 bps/day with Sharpe 2.01, both before costs. That supports the claim that the edge sits in the short leg. The authors also say 'other factors, such as changing market conditions, could also contribute,' so the link to LLM adoption is an interpretation, not a proven cause.
- **[C3] CONFIRMED** The Kim, Muhn & Nikolaev LLM financial-statement-analysis paper was withdrawn on Feb 20 2025 after a co-author found data and analysis inconsistencies while trying to replicate it.
  - reasoning: The arXiv v3 notice is dated Thu 20 Feb 2025 and reads: 'A co-author identified inconsistencies in the data and analyses while attempting to replicate past analyses from the working paper. Accordingly, we have temporarily withdrawn...' The withdrawal is described as temporary. The related JAR paper by Kim & Nikolaev, 'Context-Based Interpretation of Financial Information,' was retracted: the Wiley retraction notice (doi 10.1111/1475-679x.70057) says the results were 'neither quantitatively nor qualitatively reproducible.'
- **[C4] CONFIRMED** TradingAgents' headline results (e.g., AAPL +26.62%, Sharpe 8.21) come from a 3-month backtest (Jan 1–Mar 29 2024) on a few tickers, with no transaction costs addressed and about 11 LLM calls plus 20+ tool calls per prediction.
  - reasoning: The v7 HTML confirms the Jan 1 – Mar 29 2024 window, AAPL 26.62%/8.21, GOOGL 24.36%/6.39, AMZN 23.21%/5.60, '11 LLM calls & 20+ tool calls/prediction', and 'We benchmarked TradingAgents over 3 months due to intensive LLM and tool use.' Transaction costs are not mentioned. This also resolves the researcher's open question: the paper's own AAPL buy-and-hold is −5.23% over the window, so the +26.6% required short or timing positions. A 3-month Sharpe of 8.21 is a red flag in itself (overfitting or selection). The repo (109.2k stars, v0.5.2 dated 2026-09-09) says: 'Backtest results are not guaranteed to match any published figure.'
- **[C5] NEEDS_QUALIFICATION** In FINSABER's bias-mitigated 2004–2024 evaluation (KDD 2026), LLM strategies FinMem and FinAgent underperform buy-and-hold (e.g., Sharpe −0.228 and 0.241 vs 0.703 under the volatility selection scheme), and previously claimed LLM superiority is attributed to selective evaluation setups.
  - reasoning: The numbers are confirmed: B&H 0.703 / 7.898%, FinMem −0.228 / 4.061%, FinAgent 0.241 / 4.954%. KDD 2026 acceptance, the $0.0049/share commission with a $0.99 minimum, and delisted names included are also confirmed. Qualifications: (1) the abstract says '100+ symbols', but each selection scheme uses 63–91 distinct symbols, and the researcher's table repeats '100+'; (2) FINSABER re-ran FinMem with GPT-4o-mini, not the original backbone, so part of the gap between the claimed 2.679 Sharpe and the re-run 0.927 comes from a cheaper model rather than from evaluation alone. The broad test therefore shows that cheap-backbone LLM agents underperform, not that all LLM agents do. The page's wording is 'previously reported LLM advantages often vanish under broader and longer evaluations.'
  - corrected: In FINSABER (KDD 2026; 2004–2024; about 63–91 historical S&P 500 symbols per selection scheme, delisted names included, IBKR-style commissions), FinMem and FinAgent re-implemented on a low-cost backbone (GPT-4o-mini) underperform buy-and-hold (volatility scheme: Sharpe −0.228 and 0.241 vs 0.703). Earlier claimed advantages largely vanish under broader and longer evaluation. Results for frontier backbones are not established.
- **[C6] CONFIRMED** In an audit of 30 LLM trading studies (2023–May 2026), only 14 had recoverable cost/turnover treatment and 18 had recoverable code or artifacts.
  - reasoning: Yao, Zheng & Li audited 30 studies from Jan 1 2023 to May 30 2026: 14/30 had recoverable cost/turnover information and 18/30 had accessible artifacts. The quote 'the field has matured faster in architecture proposals than in evaluation discipline' is verbatim. This is an arXiv preprint, not peer reviewed.
- **[C7] REFUTED** In live and contamination-free benchmarks, most LLM agents fail to beat buy-and-hold: in StockBench (Mar–Jun 2025, 20 DJIA stocks, no costs) the best model returned 1.9% vs 0.4% passive, and in LiveTradeBench (21 LLMs, 50 live days) the correlation between LMArena score and stock returns is 0.054.
  - reasoning: The individual numbers are mostly right, but the headline inference is not supported by these two sources. StockBench contradicts itself: the abstract says 'most models struggle to outperform the simple buy-and-hold baseline', while the results section says 'Most tested models outperform the passive buy-and-hold baseline, which achieves a modest 0.4% return.' Its Table 2 shows the majority beating 0.4% in raw return (8 of 14 by one reading). Several beat 1.9%: Qwen3-235B-Think 2.5%, Qwen3-235B-Ins 2.4%, GLM-4.5 2.3%, Claude-4-Sonnet 2.2%, Qwen3-30B-Think 2.1%. So Kimi-K2 at 1.9% was not 'the best model' by return; it was best on another criterion or composite. All of this is without costs, over 82 days, with margins of about 1–2 percentage points, which is statistically meaningless. LiveTradeBench (Aug 18 – Oct 24 2025, 21 LLMs) reports Spearman 0.054 between LMArena score and stock-market returns, which is confirmed, but by the summarizer's reading it does not benchmark against buy-and-hold at all. Its best US-stock model was GPT-4.1 at +6.25%.
  - corrected: Short, cost-free live or post-cutoff benchmarks are inconclusive rather than negative. In StockBench (20 DJIA stocks, Mar 3 – Jun 30 2025, no costs) roughly half or more of 14 LLMs beat a 0.4% buy-and-hold return by about 1–2 pp; the paper's abstract and body disagree on how to describe this, and the sample is far too short to separate skill from noise. LiveTradeBench (21 LLMs, 50 live days) finds general capability does not predict trading returns (Spearman 0.054 on stocks, −0.38 on prediction markets) and does not report a buy-and-hold comparison.
- **[C8] NEEDS_QUALIFICATION** In real-money Alpha Arena Season 1.5 (US equities, $320k across 32 accounts), only 6 accounts ended positive and the aggregate loss was about 35%; in Season 1 (crypto), 4 of 6 frontier models lost roughly 40–60%.
  - reasoning: Season 1.5 is corroborated by a third-party aggregator that says it compiled Nof1 primary data: 32 accounts, 6 positive, −35.2% of $320,000 (−$112,579.92), Nov 19 – Dec 3 2025, TSLA/NVDA/MSFT/AMZN/GOOGL/PLTR/NDX. Losing 35% in two weeks on mega-cap equities implies heavy leverage, so the result is not representative of an unlevered retail account. Season 1 final returns (iweaver capture): Qwen3 Max +22.3%, DeepSeek +4.89%, Claude Sonnet 4.5 −30.81%, Grok 4 −45.3%, Gemini 2.5 Pro −56.71%, GPT-5 −62.66%. The loss range is therefore about 31–63%, not 40–60% (the summary's '42–63%' is also wrong for Claude). Nof1 no longer serves Season 1 per-model pages, and I could not verify the founder quote.
  - corrected: Alpha Arena Season 1 (crypto perps, Oct 18 – Nov 3 2025, $10k each): 2 of 6 models profitable (Qwen3 Max +22.3%, DeepSeek +4.9%); the other four lost 31–63% (Claude Sonnet 4.5 −30.8%, Grok 4 −45.3%, Gemini 2.5 Pro −56.7%, GPT-5 −62.7%). Season 1.5 (US equities, Nov 19 – Dec 3 2025): 6 of 32 accounts positive, aggregate −35.2% of $320k. These are two-week, leveraged, secondary-sourced results: anecdote, not proof.
- **[C9] NEEDS_QUALIFICATION** Current Claude Opus 5.5 and Sonnet 5.5 have a June 2026 training-data cutoff, so any backtest of their decisions on pre-July-2026 dates is exposed to look-ahead/memorization bias; prompting the model to ignore future knowledge does not fix this.
  - reasoning: The Anthropic models overview confirms a Jun 2026 training and reliable-knowledge cutoff for Fable 5.1, Opus 5.5 and Sonnet 5.5, and a Jul 2025 training cutoff (Feb 2025 reliable) for Haiku 4.5. Lopez-Lira/Tang/Zhu say verbatim: 'Instructions to respect historical boundaries fail to prevent recall-level accuracy, and masking fails... Post-cutoff, we observe no recall.' Sarkar & Vafa is an ICML 2025 workshop paper (DIG-BUGS), not the main conference. It found Llama 2 mentioning COVID in >25% of Sep–Nov 2019 risk predictions and discusses the limits of prompting. Missing caveats: (1) Haiku 4.5 (cutoff Jul 2025) offers about 14 months of clean post-cutoff history (Aug 2025 – Sep 2026), much more than the 3 months for the 5.5 models, though Haiku 4.5's retirement commitment ends soon; (2) post-cutoff dates are clean only if the agent's tools (web search, news APIs) are restricted to point-in-time data, since a web-searching agent 'backtesting' past dates will retrieve future information; (3) Glasserman–Lin found the in-sample bias dominated by a 'distraction effect,' and anonymization improved in-sample results.
  - corrected: Opus/Sonnet 5.5 (training cutoff Jun 2026) cannot be backtested cleanly before about Jul 2026, and instructions or masking do not reliably prevent recall. Haiku 4.5 (training cutoff Jul 2025) allows about 14 months of post-cutoff testing, provided its tools and data are strictly point-in-time. Any agent with live web search cannot be backtested at all, only forward-tested.
- **[C10] NEEDS_QUALIFICATION** LLM outputs are not reproducible: 1,000 temperature-0 runs gave 80 unique completions in one test, and on Claude 4.7+ temperature/top_p/top_k cannot be set to non-default values (400 error).
  - reasoning: The Anthropic deprecations table confirms verbatim that `temperature`, `top_p`, `top_k` are 'Deprecated (Claude Opus 4.7 and later)' and return a 400 error when set to a non-default value. The Python SDK v1.0+ removes them entirely (TypeError). The Thinking Machines test (Sep 10 2025), however, used Qwen3-235B-A22B on their own inference stack, not Claude. Of the 1,000 completions, 992 shared the same key content and divergence began at token 103, and batch-invariant kernels made all 1,000 identical. So the '80 unique' figure is about self-hosted open models and is fixable there. It is not a measurement of Claude API variance, which is plausible but unquantified. AlphaForgeBench (revised May 27 2026) independently reports 'extreme run-to-run variance' and 'irrational action flipping' for LLM trading agents 'even under deterministic decoding.'
  - corrected: Claude 4.7+ models reject non-default sampling parameters (400 error), so greedy decoding cannot be requested; adaptive thinking adds further variability. Nondeterminism at temperature 0 is documented for self-hosted open models (Thinking Machines: 80 distinct completions in 1,000 runs of Qwen3-235B, fixable with batch-invariant kernels) and for LLM trading agents generally (AlphaForgeBench). The size of Claude-specific variance must be measured.
- **[C11] NEEDS_QUALIFICATION** Anthropic gives at least 60 days' notice before retiring a model, and observed model lifetimes are about 13–16 months (e.g., Claude Opus 4 released May 2025, retired June 15 2026); Haiku 4.5 is guaranteed only until Oct 15 2026.
  - reasoning: The 60-day notice ('at least 60 days' notice before model retirement for publicly released models') and Opus 4's retirement on June 15 2026 (deprecated Apr 14 2026) are confirmed. The '13–16 months' range is cherry-picked. From the same table: Sonnet 3.7 lasted Feb 2025 → Feb 19 2026 (about 12 months); Claude 3 Haiku Mar 2024 → Apr 20 2026 (about 25 months); Opus 3 Feb 2024 → Jan 5 2026 (about 22 months); Sonnet 3.5 Jun 2024 → Oct 28 2025 (about 16 months). The observed range is roughly 12–25 months. Haiku 4.5 is listed as Active with 'Not sooner than October 15, 2026.' That is a floor, not an end date. No deprecation notice is listed as of today, and with 60 days' notice the earliest practical retirement is late Nov 2026. There is still no newer Haiku in the lineup, so a system built on Haiku may have to move to Sonnet 5.5 at 2× the price. Sonnet 4.5's floor is today (Sep 29 2026).
  - corrected: Anthropic commits to at least 60 days' notice. Observed API lifetimes range from about 12 to 25 months (Sonnet 3.7 about 12, Opus 4 about 13, Sonnet 3.5 about 16, Opus 3 about 22, Claude 3 Haiku about 25). Haiku 4.5 is committed until at least Oct 15 2026 and is not yet deprecated. Retirement is plausible within months, and there is no cheaper successor today, so Sonnet 5.5 at $2/$10 is the realistic fallback price.
- **[C12] NEEDS_QUALIFICATION** The strongest pro-LLM evidence is Chen & Pu (Jan 2026): a web-searching LLM ranked Russell 1000 stocks daily and prospectively from Apr 2025, and the long-only top 20 earned 18.4 bps/day FF5+momentum alpha (Sharpe 2.43) over about 158 days, with no model named and no compute cost reported.
  - reasoning: The core facts are confirmed: Zefeng Chen and Darcy Pu (Peking University Guanghua); an unnamed 'state-of-the-art' LLM used through AI web interfaces; Russell 1000 from April 2025; top-20 portfolio; 158 daily observations; about 50% vs 26% for the Russell 1000; 57.4% daily turnover; spreads of 1.6–2.0 bps; costs '<10% of gross alpha'; 'This draft is preliminary'; no compute cost reported. Inconsistencies: the repo and arXiv say '18.4 bps daily Fama-French five-factor alpha'; the HTML says the six-factor model is FF5+momentum; the SSRN abstract snippet says 'value-weighted... Fama-French six-factor alpha of 15.8 basis points per day (39.8% per annum).' The headline alpha therefore differs by version and factor model (15.8 vs 18.4). The top-20 portfolio is value-weighted, which the researcher does not mention. Statistical weakness: Sharpe 2.43 over 158/252 = 0.63 years gives t ≈ 2.43 × √0.63 ≈ 1.9, not significant at 5% on the raw Sharpe. The sample starts at the April 2025 tariff-shock low, in a strong rebound. It is an unrefereed working paper. The claim that data are 'continuously updated' could not be checked, because GitHub API access to the repo was blocked.
  - corrected: Chen & Pu (unrefereed working paper, Jan 2026) report that a value-weighted top-20 Russell 1000 portfolio from daily rankings by an unnamed web-interface LLM earned about 15.8–18.4 bps/day of factor alpha (the figure differs by version and factor model) with Sharpe 2.43 over about 158 trading days from Apr 2025. That is roughly t ≈ 1.9 on the Sharpe, in a strong rebound market, with no API cost, model name or replication reported.
- **[C13] CONFIRMED** Man Group's AlphaGPT uses LLM agents to generate, code and backtest signal ideas, and every signal goes through the same human investment-committee review before live trading: the LLM is a research tool, not the per-trade decision-maker.
  - reasoning: Man's own article describes three roles (Idea Person, Implementer, Evaluator) and says: 'Whether generated by human or AI, every strategy entering live trading must pass identical thresholds,' with Investment Committee review. Man's article does not give a count. 'Several dozen' signals passing the investment committee comes from Bloomberg (Jul 10 2025) as relayed by Hedgeweek and AI-Street. The Bloomberg article itself is paywalled and was not read directly.
- **[C14] CONFIRMED** LLMs frequently get backtest math wrong: the best model on BacktestBench reached only 67.41% overall accuracy and 51.67% on metric calculation, with Sharpe and volatility annualization as the main failure points.
  - reasoning: BacktestBench: the best model is Gemini 3 Pro at 67.41% overall and 51.67% on metrics calculation. Verbatim: 'Volatility and Sharpe Ratio remain "disaster zones" across all models,' with failures in 'annualization coefficient adjustments.' Scope note: the task is NL-to-SQL plus Python end-to-end backtest reproduction, and it is unclear whether Claude Opus 5.5 was tested. That supports the 'verify against known answers' recommendation. It does not prove Claude-specific error rates.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- Arithmetic error in the key $1 argument. The research says '$0.50/yr is less than a single day of role (e) on 10 tickers ($0.065/day)'. That is false: $0.50 > $0.065. $0.50/yr buys about 7.7 days of non-batched 10-ticker Haiku calls, or about 15 days batched ($0.0325/day). The conclusion that recurring LLM calls are unaffordable at $1 still holds (the annual cost of about $8–16 is 16–33× the edge), but the orchestrator should fix the sentence before it reaches the user.
- The token cost model ignores thinking tokens. Opus 5.5 has adaptive thinking 'always on' and Sonnet 5.5 defaults to effort 'high' (models overview). Thinking is billed as output at $20 or $10/MTok, so the assumed 300–2,000 output tokens per call could be several times too low for the 5.5 models. The newer tokenizer (Claude 4.7+) also produces about 30% more tokens for the same text (pricing page). Haiku 4.5 uses the old tokenizer and optional extended thinking, so the Haiku figures are least affected. All Sonnet and Opus running-cost and break-even figures should be treated as lower bounds and measured with the token-counting endpoint in a pilot.
- The break-even formula 'annual LLM cost ÷ expected excess return' at a 'generous 5%' treats the edge as known. A careful quant would object that for a novice with an unproven strategy the expected excess return after costs is about zero or negative, so the true break-even capital is infinite until an edge is shown. The formula also leaves out non-LLM running costs (data, hosting, broker per-order minimums such as the $0.99/order that FINSABER itself assumes, which alone wipes out $1–$300 accounts at any trade frequency) and a safety margin for estimation error.
- 'Forward paper test for at least 6 months' is presented as able to validate an edge. It cannot, except for huge edges. Rough power check: a daily alpha of 18.4 bps with an assumed ~1.2% daily tracking volatility has daily IR ≈ 0.15, so t ≈ 0.15 × √126 ≈ 1.7 after 6 months, still not significant. A realistic 5 bps/day edge gives t ≈ 0.5. A 5%/yr edge at 15% tracking error needs about (2 × 0.15/0.05)² ≈ 36 years to reach t = 2. The orchestrator should tell the user plainly that paper trading can reject broken systems and measure costs and operations, but cannot prove profitability within months. Lawyers would add that presenting a 6-month paper result as 'proof' to a novice is misleading.
- The Chen & Pu test recommendation to go 'weekly rather than daily' changes the strategy. The published alpha is a daily-horizon signal with 57% daily turnover, which the paper says decays and dilutes quickly. A weekly version would test a different hypothesis, so a null result would not refute Chen & Pu and a positive one would not replicate it. Chen & Pu also used a consumer web interface. Automating a consumer chat subscription to reproduce it would likely breach consumer terms of service, and the API-plus-web-search cost (about $0.10 per stock-day at the researcher's own estimate, before thinking tokens) is not what the paper measured.
- The hobbyist TradingAgents re-test is misattributed as 'about $0.28 per decision on OpenAI models'. The repo says it used Anthropic claude-haiku-4-5 (quick) and claude-opus-4-8 (deep): about $3.70 for 104 deep and 39 quick calls, 13 decisions, 10 bps costs, AAPL Mar 1 – Jun 1 2026. That is more relevant to this user, because it is a direct Claude cost datapoint, but it has to be cited correctly. Note also that Mar–Jun 2026 is probably inside Opus 4.8's training window; the anonymization mitigates this but does not remove it.
- Relying on Haiku 4.5 for any recurring role (daily batch filter, per-ticker decisions) is fragile. Its retirement floor is Oct 15 2026, 16 days away. It is not yet deprecated, so there are at least 60 days after notice, but there is no newer Haiku, and the realistic fallback is Sonnet 5.5 at 2× the price and likely more because of thinking and the new tokenizer. Budget recurring roles at Sonnet 5.5 prices.
- The recommendations do not use the one clean backtest window that exists. Haiku 4.5's training cutoff is Jul 2025, so a Haiku-based signal can be backtested on about 14 months of post-cutoff data (Aug 2025 – Sep 2026) at a few dollars, if all inputs are point-in-time and no web search is used. That is a cheaper and faster falsification test than a 6-month forward paper test, and it should come before any forward LLM experiment.
- 'Build risk filters from Alpha Vantage EARNINGS_CALENDAR / Nasdaq halt feeds at no token cost' needs checking on the data side. Alpha Vantage's free tier is heavily rate-limited, and the retail usability of the Nasdaq halt feed is unverified in this research. 'Zero token cost' is not the same as 'zero cost or zero engineering.'
- Consumer-protection: the research never states the base rate that the large majority of retail active and day traders underperform or lose money (e.g., the Barber–Lee–Liu–Odean Taiwan studies; Chague et al., Brazil). It also never recommends that the default and benchmark be a low-cost broad index fund. Any system should have to beat that index fund after costs and taxes, not just a 'zero-token baseline' strategy.
- Consumer-protection and regulatory points missing and residency-dependent: the user's country is unknown. Shorting, which the news-drift literature needs, is unavailable in cash accounts and on fractional shares. US margin accounts with frequent day trades have historically been subject to FINRA's pattern-day-trader $25k rule, whose reform status in 2026 should be checked against FINRA and SEC primary sources before any daily-turnover design. Short-term gains are usually taxed at higher rates, and wash-sale-type rules apply. Broker API terms (Alpaca) and Anthropic's usage policy on automated financial decisions should be checked before automating. If the system is ever shared with or run for others, investment-adviser registration issues arise.
- 'Pin model IDs and re-validate on each migration' is right, but the research understates the cost. Every migration restarts the contamination-free forward-test clock. With observed lifetimes of about 12–25 months and a forward test that needs years to reach significance, an LLM-dependent edge may never become statistically verifiable before the model is retired. That is a stronger argument for keeping the LLM out of the loop than the research makes.
- '$10–$50 total one-time research cost' is presented as sunk and negligible. The current orchestrated multi-agent workflow (Fable orchestrating, several Opus researchers and checkers) probably already exceeds that. The user excluded design and research costs from the constraint, but periodic re-validation, code review after every change and migration work are recurring and belong in the running-cost ledger.

## VERIFIER OVERALL

The research is broadly reliable in direction and is unusually well sourced. Most primary numbers check out verbatim:
- Lopez-Lira & Tang: 34 bps/day, 5/10/20 bps cost thresholds, 190% turnover, Sharpe decay 6.54→1.22, small-cap and short-leg concentration, and the 'market makers' quote.
- TradingAgents: 3-month window, 11 LLM + 20 tool calls per prediction.
- FINSABER figures, the audit counts, the BacktestBench accuracy figures.
- Anthropic facts: prices, $10 per 1,000 web searches, 400 error on sampling parameters for 4.7+ models, Jun 2026 cutoffs, 60-day notice, Opus 4 retirement.
- The Kim/Muhn/Nikolaev withdrawal and the related JAR retraction.

The central conclusion survives adversarial checking: keep the LLM out of the per-trade loop at micro-capital, and use it for one-time design, coding and review. Independent sources support it: FINSABER; AlphaForgeBench's move from per-step actions to generated code; Man Group's research-assistant model; the absence of any audited long-horizon per-trade LLM track record.

Errors and overstatements the orchestrator should weight down or fix:
1. StockBench is misreported. The paper's own body and table show most models beat its 0.4% buy-and-hold (cost-free, 82 days), and Kimi-K2 was not the top return. LiveTradeBench has no buy-and-hold comparison. The 'live benchmarks show LLMs fail to beat buy-and-hold' claim should become 'short live benchmarks are inconclusive and general capability does not predict returns (ρ = 0.054).'
2. The $1 arithmetic sentence is inverted ($0.50/yr is not less than $0.065/day).
3. The hobbyist re-test used Claude Haiku 4.5 and Opus 4.8, not OpenAI.
4. Alpha Arena Season 1 losses were 31–63% (Claude −30.8%), not 40–60%.
5. Model lifetimes are about 12–25 months, not 13–16. Haiku 4.5's Oct 15 2026 date is a floor, not a guarantee end, but no cheaper successor exists.
6. Chen & Pu's alpha differs across versions (15.8 bps six-factor on SSRN vs 18.4 bps five-factor on arXiv and the repo). The portfolio is value-weighted, and the Sharpe over 0.63 years has t ≈ 1.9.
7. The Gao/Jiang/Yan figures in the summary (0.077%, 0.197%, 37%) do not match the current HTML (0.067 pp, 0.21%, about 32%). Possibly a version difference; treat as unverified.
8. Sarkar & Vafa is an ICML workshop paper.
9. The TradingAgents open question is resolved: AAPL buy-and-hold was −5.23% in the window, so the +26.6% relied on short or timing positions.

Systematic weaknesses:
- The token cost estimates omit adaptive-thinking output tokens and the 30% tokenizer inflation for the 5.5 models, so Sonnet and Opus running-cost figures are lower bounds.
- The break-even framing assumes a 5% edge that a novice has no basis for.
- The recommended 6-month forward paper test has almost no statistical power to confirm an edge. It should be framed as a falsification, operations and cost check, never as proof of profitability.
- The research misses the cheapest clean test available: Haiku 4.5's Jul 2025 cutoff gives about 14 months of post-cutoff history for a point-in-time backtest.

Chen, Kelly & Xiu's Sharpe values and RD-Agent's 'under $10 per run' remain unverified. Many cited 2026 arXiv items are unrefereed preprints and should be weighted accordingly.
