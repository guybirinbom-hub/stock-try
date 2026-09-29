# token-economics

## SUMMARY

## Bottom line
At the capital levels this person is willing to risk ($1 to about $1k), **the only architectures that can plausibly pay for themselves are A (deterministic rules on cron, zero runtime tokens) and, at a stretch, B (a daily Haiku sanity check) or F (a monthly Opus review sent through the Batch API).** A daily Sonnet or Opus "analyst" (C) needs roughly $130–$900 of capital to break even at a generous 8% annual excess return. Agent debates in the TradingAgents style (D) and daily Claude Code sessions (E) need about $3.5k–$44k. Those break-even figures assume the LLM actually produces 8% a year of excess return. That is a very optimistic assumption: over 15 years about 90% of professional active large-cap funds trailed the S&P 500 ([SPIVA, via secondary summary](https://www.investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541); [Barber & Odean 2000](https://faculty.haas.berkeley.edu/odean/papers%20current%20versions/individual_investor_performance_final.pdf) found that retail investors who trade more earn less). **At $1 no architecture pays for itself, not even A.** Alpaca's regulatory fees round up to $0.01 per sell ([Alpaca docs](https://docs.alpaca.markets/us/docs/regulatory-fees)), which is about 1% of a $1 position per round trip. A $1 live run is only a plumbing test, never a profit test.

Runtime token cost is **fixed per day and does not depend on capital**. Scaling up capital therefore improves the cost-to-profit ratio. The risk when scaling is edge decay and market impact, not token cost. For liquid ETFs and large caps, market impact is negligible below about $100k.

## 1. Verified pricing inputs (official, fetched 2026-09-29)
From [platform.claude.com/docs/en/about-claude/pricing](https://platform.claude.com/docs/en/about-claude/pricing), in USD per million tokens:

| Model | Input | 5m cache write | 1h cache write | Cache read | Output | Batch in/out |
|---|---|---|---|---|---|---|
| Haiku 4.5 | 1 | 1.25 | 2 | 0.10 | 5 | 0.50 / 2.50 |
| Sonnet 5.5 | 2 | 2.50 | 4 | 0.20 | 10 | 1 / 5 |
| Opus 5.5 | 4 | 5 | 8 | 0.20 (0.05×) | 20 | 2 / 10 |
| Fable 5.1 | 10 | 12.50 | 20 | 0.25 (0.025×) | 50 | 5 / 25 |

Other items from the same page:
- **Batch API:** "a 50% discount on both input and output tokens". It stacks with caching.
- **Web search:** "$10 per 1,000 searches" plus tokens. Web fetch costs tokens only.
- **Managed Agents:** $0.08 per session-hour of runtime.
- **Tokenizer:** Claude 4.7 and later models use a tokenizer that "produces approximately 30% more tokens for the same text". Haiku 4.5 uses the older one. A news digest therefore costs about 1.3× as many tokens on Sonnet or Opus 5.5 as on Haiku.
- **Thinking:** thinking cannot be turned off on Opus 5.5 or Sonnet 5.5 ([Claude Code costs doc](https://code.claude.com/docs/en/costs)), and thinking tokens are billed as output. The "~2k output" assumption in C is therefore optimistic.

**Batch turnaround** ([batch docs](https://platform.claude.com/docs/en/build-with-claude/batch-processing)):
- "most batches completing within 1 hour"; batches expire if not done within 24h, and expired requests are not billed.
- Results are kept for 29 days.
- Limits are 100,000 requests or 256 MB per batch.
- With caching, "cache hits are provided on a best-effort basis… 30% to 98%".
- `max_tokens: 0` pre-warming is not allowed inside a batch.
- **Implication:** an end-of-day analysis submitted after the close and read before the next open fits the batch window well. Anything intraday does not.

**Prompt caching** ([caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)):
- Reads cost 0.1× input (0.05× on Opus 5.5, 0.025× on Fable 5.1). Writes cost 1.25× (5-minute TTL) or 2× (1-hour TTL).
- The **minimum cacheable prefix is 512 tokens** on Opus 5.5, Sonnet 5.5 and Fable 5.1, but **4,096 on Haiku 4.5**. Shorter prefixes "cannot be cached… no error is returned".
- **This is the key finding:** caching lives for at most 1 hour, so a **once-a-day call never gets a cache hit**. Marking it for caching only adds the 1.25–2× write premium. Caching helps a trading system only when several calls share a prefix within minutes: per-ticker fan-out, multi-agent debates, agent loops, or Claude Code sessions. For B, C and F, cost them uncached. For D, TradingAgents issue #750 reports about 0% cache hits across 16–22 LLM calls per run ([issue #750](https://github.com/TauricResearch/TradingAgents/issues/750)).

## 2. Assumptions (stated and justified)
- **News digest size.** One headline with a one-line summary, source and timestamp is about 100–300 tokens. Ten tickers × 10 items gives 15–30k tokens. Adding a price/indicator table and a system prompt of 5–10k tokens gives the brief's 30–60k input for C. A digest of 10 bare headlines is 1–2k tokens.
- **TradingAgents-style decision (D).** The paper reports "11 LLM calls & 20+ tool calls/prediction" and says evaluation was limited to 3 months "due to intensive LLM and tool use" ([arXiv 2412.20138](https://arxiv.org/html/2412.20138v5)). Issue #750 measured 16–22 calls. I split 200–500k tokens per decision as 90% input and 10% output (thinking plus reports), with no cache.
- **Claude Code session (E), 30–60 minutes.** Low case: 1M cache reads, 80k cache writes, 20k uncached input, 20k output. Mid case: 2M, 150k, 50k, 60k. High case: 5M, 400k, 50k, 100k. At API prices this gives Opus 5.5 at **$1.08 / $2.55 / $5.20** per session and Fable 5.1 at **$2.45 / $5.88 / $11.75**. As a cross-check, Anthropic reports enterprise Claude Code averages of "around $13 per developer per active day and $150–250 per developer per month, with costs remaining below $30 per active day for 90% of users" ([costs doc](https://code.claude.com/docs/en/costs)). My session estimates are well below a full developer day, which is consistent.
- **Excess return.** The 3%, 8% and 15% scenarios are applied to capital. Break-even capital = annual cost ÷ excess rate.

## 3. Runtime cost per architecture (252 trading days a year, 21 a month)

| Arch | Config | $/day | $/month | $/year |
|---|---|---|---|---|
| A | cron, no LLM at runtime | 0 | 0 | 0 |
| B | Haiku, 3–8k in / 300 out, no cache (below the 4,096 minimum or 24h gap) | 0.0045–0.0095 | 0.09–0.20 | 1.13–2.39 |
| B | same, Batch | 0.0023–0.0048 | 0.05–0.10 | 0.57–1.20 |
| C | Sonnet 5.5, 30–60k / 2k | 0.08–0.14 | 1.68–2.94 | 20.2–35.3 |
| C | Sonnet 5.5, Batch | 0.04–0.07 | 0.84–1.47 | 10.1–17.6 |
| C | Opus 5.5, 30–60k / 2k | 0.16–0.28 | 3.36–5.88 | 40.3–70.6 |
| C | Opus 5.5, Batch | 0.08–0.14 | 1.68–2.94 | 20.2–35.3 |
| C | Opus 5.5, 60k / 8k (realistic thinking) | 0.40 | 8.40 | 100.8 |
| D | Opus 5.5, 1×200k up to 5×500k decisions/day | 1.12–14.00 | 23.5–294 | 282–3,528 |
| D | Opus 5.5, Batch (sequential steps, slow) | 0.56–7.00 | 11.8–147 | 141–1,764 |
| D | Fable 5.1 | 2.80–35.00 | 58.8–735 | 706–8,820 |
| E | Opus 5.5 daily session (API) | 1.08–5.20 | 22.7–109 | 272–1,310 |
| E | Fable 5.1 daily session (API) | 2.45–11.75 | 51–247 | 617–2,961 |
| E | Pro subscription (flat) | – | 20 | 240 (204 if billed annually) |
| E | Max 5x / Max 20x (flat) | – | 100 / 200 | 1,200 / 2,400 |
| F | Opus 5.5 monthly review, 50–100k / 5k | 0.014–0.024 equiv. | 0.30–0.50 | 3.6–6.0 |
| F | same, Batch | 0.007–0.012 equiv. | 0.15–0.25 | 1.8–3.0 |

Arithmetic examples:
- C Opus high: 60,000×$4/1M + 2,000×$20/1M = $0.24 + $0.04 = $0.28 per day, × 252 = $70.56.
- D Opus low: 180k×4/1M + 20k×20/1M = $0.72 + $0.40 = $1.12.
- F high: 100k×4/1M + 5k×20/1M = $0.50.

Web search inside the LLM adds $0.01 per search. Ten searches a day adds $25.20 a year plus result tokens, so news should come from a free API instead.

## 4. Break-even capital (annual token cost ÷ annual excess return)

| Arch | @3% | @8% | @15% |
|---|---|---|---|
| A | $0 (tokens); see TCO below | $0 | $0 |
| B Haiku | $38–80 | $14–30 | $8–16 |
| B Haiku batch | $19–40 | $7–15 | $4–8 |
| C Sonnet | $672–1,176 | $252–441 | $134–235 |
| C Sonnet batch | $336–588 | $126–220 | $67–118 |
| C Opus | $1,344–2,352 | $504–882 | $269–470 |
| C Opus batch | $672–1,176 | $252–441 | $134–235 |
| C Opus with realistic thinking | $3,360 | $1,260 | $672 |
| D Opus | $9.4k–118k | $3.5k–44k | $1.9k–23.5k |
| D Opus batch | $4.7k–59k | $1.8k–22k | $0.9k–11.8k |
| D Fable | $23.5k–294k | $8.8k–110k | $4.7k–59k |
| E Opus API | $9.1k–43.7k | $3.4k–16.4k | $1.8k–8.7k |
| E Fable API | $20.6k–98.7k | $7.7k–37k | $4.1k–19.7k |
| E Pro sub | $8,000 | $3,000 | $1,600 |
| E Max 5x / 20x | $40k / $80k | $15k / $30k | $8k / $16k |
| F Opus | $120–200 | $45–75 | $24–40 |
| F Opus batch | $60–100 | $22–38 | $12–20 |

"Break-even" means the tokens consume 100% of the excess. A sane design keeps tokens at or below about 25% of expected excess, because the excess estimate itself has a huge standard error. With that margin, multiply the break-even capital by 4.

## 5. One-time build cost and maintenance
**Build (rough, at API prices), using this project's pattern of Fable orchestrating and judging with Opus building and checking:**
- About 8 Opus research subagents at $1.85–3.70 each: 1.5–3M cache reads × $0.20, plus 150–300k 5-minute writes × $5, plus 40–80k output × $20. Subtotal $15–30.
- A similar number of Opus verifiers: $15–30.
- Fable orchestrator/judge, $8–18: 2–5M reads × $0.25, 200–500k writes × $12.50, 100–200k output × $50.
- 4–8 Opus Claude Code build sessions at $2.5–5.2 each: $10–42.
- **Total about $50–120, call it $50–150 with rework.** If run on a Max subscription instead, one month costs $100–200 flat, subject to usage limits.

**Maintenance:**
- One Opus Claude Code session per quarter: about $10–20 a year.
- Plus F: $2–6 a year.
- **Budget about $15–30 a year.**

**Total cost of ownership for the minimal stack (A + F-batch + quarterly maintenance + build amortised over 3 years): about $30–75 a year, so break-even is about $370–$940 at 8% excess, or $1.0k–$2.5k at 3%.**

Even a zero-token runtime does not recover its design cost below roughly $1k of capital unless the edge is large. The build is better treated as tuition, not something that capital under $1k will repay.

## 6. Subscriptions (Pro/Max) versus API metering
- **Prices:** Pro is "$20 if billed monthly" or $17 a month billed annually. Max is "From $100" (5x) and $200 (20x) ([claude.com/pricing](https://claude.com/pricing), [Max page](https://claude.com/pricing/max)). Every plan has "usage limits that reset on a rolling five-hour session window" plus weekly limits.
- **Subscriptions do help the design and build phase.** A $20–200 flat fee can cover work that would cost $50–150+ at API prices, and on a subscription Claude Code uses a 1-hour cache TTL ([costs doc](https://code.claude.com/docs/en/costs)).
- **Subscriptions are a poor fit for the unattended runtime:**
  - $240 a year for Pro alone needs $3k of capital at 8% just to break even.
  - The Consumer Terms (effective 2025-10-08) forbid accessing the service "through automated or non-human means, whether through a bot, script, or otherwise" except "via an Anthropic API Key or where we otherwise explicitly permit it" ([consumer terms](https://www.anthropic.com/legal/consumer-terms)). A user reported bans from scripted `claude -p` use ([issue #36324](https://github.com/anthropics/claude-code/issues/36324), closed "not planned").
  - The terms and the product signals conflict. Anthropic planned a separate Agent SDK / `claude -p` credit (Pro $20, Max $100–200) for 2026-06-15, then paused it. `claude -p` and the Agent SDK "still draw from your subscription's usage limits" ([help center](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)), and the planned-policy text said "Teams running shared production automation should use Claude Platform with an API key".
  - **Conclusion:** a cron-driven trading bot should call the API with an API key. For B, C and F that costs cents to dollars a month, far below any subscription.

## 7. Non-token costs
- **Hosting:**
  - GitHub Actions: standard runners are free on public repos; private repos get 2,000 free minutes a month ([GitHub billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)). A daily 1–2 minute job uses about 21–44 minutes a month, so $0.
  - Caveats ([GitHub docs](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)): the schedule "can be delayed during periods of high loads… start of every hour", queued jobs can be dropped, the minimum interval is 5 minutes, and public-repo schedules are auto-disabled after 60 days without activity. Schedule off the hour, and design the job to run once and catch up if a run is missed.
  - A small VPS (Hetzner CX23, about €5.49 a month after the June 2026 price rise, per secondary sources such as [Northflank](https://northflank.com/blog/hetzner-cloud-server-price-increases)) is about $75 a year, which needs about $940 of capital at 8%. Avoid it until capital exceeds about $10k.
- **Data:**
  - Alpaca Basic is free: IEX real-time, historical data "Since 2016" with a latest-15-minutes restriction, 200 calls a minute. Algo Trader Plus is $99 a month ([Alpaca](https://docs.alpaca.markets/docs/about-market-data-api)). That $1,188 a year would need about $15k of capital at 8%, so never use it at this scale.
  - Alpha Vantage free tier is "25 API requests per day" ([support](https://www.alphavantage.co/support/)).
  - Yahoo returned 429 and stooq was cut off from this container, so rely on Alpaca.
- **Broker:**
  - Alpaca is commission-free with no stated minimum. SEC and FINRA TAF fees apply to sells, and total fees are "round[ed] up… 0.00083… to 0.01" ([Alpaca regulatory fees](https://docs.alpaca.markets/us/docs/regulatory-fees); fee schedule dated 2026-09-17, [PDF](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf)).
  - At $1 a $0.01 fee is 1% per round trip: monthly rebalancing costs about 12% a year and daily trading 250%+.
  - Non-US residency changes broker eligibility, taxes and wire fees ("varies by receiving bank"). The person's country is unknown.

## 8. Design implication by capital (8% excess assumption)

| Capital | Annual excess @8% | Max token $/day at break-even | Prudent max $/day (≤25% of excess) | Viable architectures |
|---|---|---|---|---|
| $1 | $0.08 | $0.00032 | $0.00008 | **None as a profit engine.** A only, as a paper-trading plumbing test; even the $0.01 fee dominates |
| $100 | $8 | $0.032 | $0.008 | A; B-batch ($0.57–1.20 a year, 7–15% of excess); F-batch ($1.8–3, 22–38%, borderline). Not C |
| $1k | $80 | $0.32 | $0.079 | A, B, F; C-Sonnet-batch ($10–18 a year, 13–22%) is borderline-OK; C-Opus ($40–71 a year) consumes 50–88% of excess, so no |
| $10k | $800 | $3.17 | $0.79 | A, B, C (any, even Opus with thinking at $101 a year = 13%), F; D-low only (1 decision a day ≈ $282 a year = 35%) is marginal; E-Opus-API low end is marginal; E Pro sub ($240 = 30%) is marginal |
| $100k | $8,000 | $31.7 | $7.94 | Everything except D-Fable-high and E-Fable-high. But at this capital the question is whether the LLM adds the 8%, not whether tokens are affordable |

At 3% excess, divide every "max $/day" by 2.67. At $1k the prudent budget becomes about $0.03 a day, which rules out a daily Sonnet analyst even through the Batch API.

**Recommended runtime shape for this person:**
- A deterministic core scheduled on GitHub Actions and trading through Alpaca paper, then live.
- Optionally a Haiku call for anomaly detection, which should only fire on flagged anomalies rather than daily.
- A monthly Opus review sent through the Batch API.
- Every LLM call logged with `usage` so the actual cost is measured against the P&L.
- Any LLM signal (C or D) can be added only after it has beaten the deterministic core in a costed, out-of-sample backtest plus paper-trading. TradingAgents' own evidence is 3 months, 5 mega-cap tickers, a Sharpe of 8.21 that the authors attribute to "few pullbacks", and no transaction costs ([arXiv](https://arxiv.org/html/2412.20138v5)). That is not proof of merit.

## CLAIMS

- **[C1] (high)** First-party Claude API prices (USD per million tokens): Haiku 4.5 $1 in / $5 out / $0.10 cache read; Sonnet 5.5 $2/$10/$0.20; Opus 5.5 $4/$20/$0.20; Fable 5.1 $10/$50/$0.25. 5-minute cache writes cost 1.25× input and 1-hour cache writes 2×.
  - evidence: Model pricing table on the official pricing page, fetched 2026-09-29; footnotes give 0.05× cache reads for Opus 5.5 and 0.025× for Fable 5.1.
  - sources: https://platform.claude.com/docs/en/about-claude/pricing
- **[C2] (high)** The Message Batches API gives 50% off both input and output, stacks with prompt caching, has most batches completing within 1 hour and a 24-hour expiry (expired requests not billed), and keeps results for 29 days; batch cache hits are best-effort at 30–98%.
  - evidence: Batch docs quote: 'most batches completing within 1 hour... Batches expire if processing does not complete within 24 hours'; 'Batch results are available for 29 days'; 'cache hit rates ranging from 30% to 98%'. Pricing page: 'a 50% discount on both input and output tokens'.
  - sources: https://platform.claude.com/docs/en/build-with-claude/batch-processing, https://platform.claude.com/docs/en/about-claude/pricing
- **[C3] (high)** The minimum cacheable prefix is 512 tokens on Opus 5.5, Sonnet 5.5 and Fable 5.1 but 4,096 on Haiku 4.5; shorter prefixes silently do not cache; cache lifetime is 5 minutes or 1 hour. So a once-daily LLM call gets no cache benefit and only pays the write premium.
  - evidence: Prompt caching docs list the per-model minimums and the 5m/1h TTL options. The daily-call conclusion follows because 24 hours between calls is longer than the maximum 1-hour TTL.
  - sources: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- **[C4] (high)** Claude 4.7-and-later models (including Opus 5.5 and Sonnet 5.5) use a tokenizer producing about 30% more tokens for the same text; thinking cannot be disabled on Opus 5.5 or Sonnet 5.5 and is billed as output tokens.
  - evidence: Pricing page quote: 'This tokenizer produces approximately 30% more tokens for the same text.' Claude Code costs doc: 'You can't turn off thinking on Opus 5.5, Sonnet 5.5, or the Fable models' and 'Thinking tokens are billed as output tokens'.
  - sources: https://platform.claude.com/docs/en/about-claude/pricing, https://code.claude.com/docs/en/costs
- **[C5] (medium)** Anthropic reports enterprise Claude Code costs of about $13 per developer per active day and $150–250 per month, below $30 per active day for 90% of users. This makes a daily interactive Claude Code operating session (architecture E) cost roughly $1–12 per day, or $270–3,000 a year.
  - evidence: Quote from the costs doc; the per-session $1.08–5.20 (Opus 5.5) and $2.45–11.75 (Fable 5.1) figures are my arithmetic from stated token assumptions at official prices.
  - sources: https://code.claude.com/docs/en/costs
- **[C6] (high)** TradingAgents needs 11 LLM calls and 20+ tool calls per prediction (16–22 LLM calls measured in the current code) with about 0% prompt-cache hits. Its published evidence is a 3-month backtest (Jan–Mar 2024) on 5 mega-cap stocks, with no mention of transaction costs and a Sharpe of 8.21 the authors attribute to few pullbacks.
  - evidence: arXiv 2412.20138v5 quotes; GitHub issue #750 (opened 2026-05-06): '16–22 LLM calls', 'approximately 0% LLM API prompt cache hit rate'.
  - sources: https://arxiv.org/html/2412.20138v5, https://github.com/TauricResearch/TradingAgents/issues/750
- **[C7] (medium)** Claude plans cost Pro $20/month ($17/month billed annually) and Max from $100 (5x) and $200 (20x), all including Claude Code with rolling 5-hour and weekly usage limits.
  - evidence: claude.com/pricing and the Max page. The pages show 'From $100' for both Max tiers; the $200 figure for 20x comes from the Agent SDK help-center text ('Max: $100-$200/month') and secondary sources.
  - sources: https://claude.com/pricing, https://claude.com/pricing/max, https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- **[C8] (medium)** Anthropic Consumer Terms (effective 2025-10-08) prohibit accessing the Services through automated means such as bots or scripts, except via an API key or where explicitly permitted. As of 2026-06-16, `claude -p` and Agent SDK usage still draw from subscription limits after a planned separate-credit change was paused. Unattended use of a subscription for trading automation therefore carries policy and ban risk.
  - evidence: Consumer terms clause quoted verbatim; help-center page states the pause; GitHub issue #36324 documents a user reporting bans from scripted headless use.
  - sources: https://www.anthropic.com/legal/consumer-terms, https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan, https://github.com/anthropics/claude-code/issues/36324
- **[C9] (high)** GitHub Actions standard runners are free on public repositories, and GitHub Free gets 2,000 minutes a month on private repos. Scheduled workflows can be delayed or dropped at high load (especially at the top of the hour), have a 5-minute minimum interval, and are auto-disabled in public repos after 60 days of inactivity.
  - evidence: GitHub billing doc and events-that-trigger-workflows doc quotes.
  - sources: https://docs.github.com/en/billing/concepts/product-billing/github-actions, https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- **[C10] (medium)** Alpaca charges no commission on US equities but passes through SEC and FINRA fees on sells, rounded up to $0.01, which is about 1% of a $1 position per round trip. Alpaca's free Basic data plan gives IEX real-time data and history since 2016 at 200 calls a minute; Algo Trader Plus costs $99 a month.
  - evidence: Alpaca regulatory-fees doc rounding quote ('0.00083... rounded up to 0.01'); fee schedule PDF dated 2026-09-17 (commission-free, TAF $0.01 minimum as extracted); market-data doc.
  - sources: https://docs.alpaca.markets/us/docs/regulatory-fees, https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf, https://docs.alpaca.markets/docs/about-market-data-api
- **[C11] (high)** Claude API web search costs $10 per 1,000 searches plus tokens, while web fetch costs tokens only. An LLM that searches for its own news adds about $0.01 per search.
  - evidence: Pricing page 'Web search tool' and 'Web fetch tool' sections.
  - sources: https://platform.claude.com/docs/en/about-claude/pricing
- **[C12] (medium)** The base rate for beating the benchmark is poor: about 89.5% of active US large-cap funds underperformed the S&P 500 over 15 years per SPIVA. The 8% and 15% excess-return scenarios are therefore highly optimistic for a retail LLM-driven system.
  - evidence: Secondary summary of SPIVA 2025 data; the primary S&P PDF could not be parsed from this container.
  - sources: https://www.investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541, https://www.spglobal.com/spdji/en/documents/spiva/spiva-us-mid-year-2025.pdf

## RECOMMENDATIONS

- Build architecture A as the runtime core: deterministic rules in Python, run by a GitHub Actions cron scheduled off the hour (e.g. 21:17 UTC after the US close), trading through Alpaca paper first. Runtime token cost is $0 and hosting is $0.
- If an LLM runs at runtime, use F through the Batch API (a monthly Opus 5.5 review of logs and metrics for about $0.15–0.25 a month). Optionally add B (Haiku 4.5) only when a deterministic anomaly detector flags something, not every day. Both stay under $3 a year.
- Do not use prompt caching for once-daily calls: a daily gap is longer than the 1-hour maximum TTL and Haiku 4.5 needs a 4,096-token minimum prefix. Use the Batch API for the 50% saving instead, submitting after the close and reading results before the next open.
- Enforce a hard runtime token budget in code: log `response.usage` for every call, compute the cost, and refuse to call the LLM if trailing-12-month token spend exceeds 25% of trailing realized excess P&L. Until that excess exists, the budget is only the fixed F/B allowance.
- Do not adopt C (a daily Sonnet/Opus analyst) until capital is at least about $1k (Sonnet batch) or $10k (Opus), and only after an LLM-signal ablation shows positive, costed, out-of-sample excess return over the deterministic core. Do not adopt D (a TradingAgents-style debate) below about $50–100k, and never on Fable.
- Use a Claude Pro or Max subscription only for interactive design, build and maintenance sessions. Run the unattended bot with an Anthropic API key, because the Consumer Terms prohibit scripted access except via an API key and bans have been reported.
- Treat the $1 live test as a plumbing and fee test only. Expect regulatory-fee rounding (about $0.01 per sell) to erase any profit, trade rarely (monthly at most), and judge profitability from paper trading and costed backtests, not the $1 P&L.
- Budget about $50–150 in API-equivalent tokens for the one-time research and build and about $15–30 a year for maintenance. Tell the person plainly that at 8% excess this is only recovered above about $400–$950 of capital, and at 3% above about $1–2.5k.
- Get news and prices from free APIs (Alpaca Basic, Alpha Vantage's 25 requests a day) rather than Claude web search at $10 per 1,000 searches, and never pay $99 a month for Alpaca Algo Trader Plus at this scale.
- Establish the person's country of residence before choosing a broker. Alpaca eligibility, withdrawal and wire fees, and tax treatment all depend on it.

## OPEN QUESTIONS

- The actual token counts for a TradingAgents run on Opus 5.5 were not verified. I assumed 200–500k tokens per decision, split 90/10 input/output; the $0.20–0.80-per-ticker figure seen for GPT-4o comes from a secondary source I could not trace to the repository README.
- How much hidden thinking Opus 5.5 and Sonnet 5.5 produce at low or medium effort for a 30–60k news-digest prompt is unknown; it could double or quadruple architecture C's output cost. This needs measuring with `usage.output_tokens` on real prompts.
- Exact Max 20x pricing: the public page shows 'From $100' for both Max tiers; $200 for 20x is inferred from help-center text and secondary sources.
- Whether Anthropic considers a personal, cron-driven `claude -p` job on a Pro/Max plan 'explicitly permitted' is unresolved: the Consumer Terms conflict with the help-center statement that `claude -p` draws from subscription limits.
- Alpaca's exact current SEC, FINRA TAF and CAT rates, and whether TAF or CAT apply to fractional sells under one share, could not be cleanly extracted from the 2026-09-17 fee schedule PDF. The $0.01 round-up rule is confirmed.
- Whether Alpaca's free Basic plan includes a news API usable as the digest source for architecture C was not verified.
- Alpaca's availability for non-US residents and the cost of international funding depend on the person's country, which is unknown.
- The realistic excess return of any LLM-in-the-loop retail strategy after costs is unknown. No peer-reviewed, cost-inclusive, multi-year out-of-sample evidence was found here, and the 3/8/15% scenarios are assumptions, not estimates.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** First-party Claude API prices: Haiku 4.5 $1/$5/$0.10 cache read; Sonnet 5.5 $2/$10/$0.20; Opus 5.5 $4/$20/$0.20; Fable 5.1 $10/$50/$0.25; 5m cache write 1.25x, 1h write 2x.
  - reasoning: The official pricing table, fetched 2026-09-29, matches exactly. Fable 5.1: $10 input, $12.50 5m write, $20 1h write, $0.25 hit, $50 output. Opus 5.5: $4, $5, $8, $0.20, $20. Sonnet 5.5: $2, $2.50, $4, $0.20, $10. Haiku 4.5: $1, $1.25, $2, $0.10, $5. Footnotes: 'Cache hits and refreshes on Claude Fable 5.1 ... 0.025x' and 'on Claude Opus 5.5 ... 0.05x'. The batch table matches too (Opus 5.5 $2/$10, Sonnet 5.5 $1/$5, Haiku 4.5 $0.50/$2.50, Fable 5.1 $5/$25). Two things the research left out, neither material: (a) `inference_geo: "us"` adds a 1.1x multiplier on 4.6-and-later models; (b) 'New users receive a small amount of free credits'.
- **[C2] CONFIRMED** Batch API: 50% off input and output, stacks with caching, most batches finish within 1h, 24h expiry with expired requests not billed, results kept 29 days, batch cache hits best-effort 30-98%.
  - reasoning: Batch docs quote verbatim: 'most batches completing within 1 hour'; 'Batches expire if processing does not complete within 24 hours'; for expired requests, 'You will not be billed for these requests'; 'Batch results are available for 29 days after creation'; 'cache hits are provided on a best-effort basis. Users typically experience cache hit rates ranging from 30% to 98%'; a batch is limited to '100,000 Message requests or 256 MB'; `max_tokens: 0` 'is not supported inside a batch'. The pricing page says the discounts 'stack'. One caveat for a trading design: the docs also say 'processing may be slowed down based on current demand ... you may see more requests expiring after 24 hours'. A pipeline that submits after the close and needs results before the next open must therefore handle an expired or late batch, either by falling back to no action or to a synchronous call.
- **[C3] CONFIRMED** Minimum cacheable prefix is 512 tokens on Opus 5.5, Sonnet 5.5 and Fable 5.1 and 4,096 on Haiku 4.5; shorter prefixes silently don't cache; TTL is 5m or 1h, so a once-daily call gets no cache benefit.
  - reasoning: The caching doc lists 512 tokens for 'Claude Fable 5.1, ... Claude Opus 5.5, ... Claude Sonnet 5.5' and 4,096 for 'Claude Opus 4.6, Claude Opus 4.5, Claude Haiku 4.5'. It says 'Shorter prompts cannot be cached ... No error is returned'. TTL is a 5-minute default or 1 hour optional, and a hit refreshes the entry. The logic holds: a 24-hour gap is longer than the 1-hour maximum. Caveat: if a daily job fans out per ticker (N calls sharing one system prompt inside 5 minutes), caching does help. The research acknowledges this.
- **[C4] NEEDS_QUALIFICATION** 4.7+ models use a tokenizer producing ~30% more tokens; thinking cannot be disabled on Opus 5.5 / Sonnet 5.5 and is billed as output.
  - reasoning: Tokenizer: the pricing page does say 'Claude 4.7 and later models ... use a newer tokenizer ... approximately 30% more tokens for the same text. The exact increase depends on the content'. That Haiku 4.5 uses the old tokenizer is an inference: the page names 'Sonnet 4.6 and earlier', and Haiku 4.5 predates 4.7. Also, the research's C and D token counts (30-60k, 200-500k) do not visibly apply the 1.3x factor, so those costs may be understated by up to ~30%. Thinking: the source is the Claude Code costs doc, which says 'You can't turn off thinking on Opus 5.5, Sonnet 5.5, or the Fable models' and 'Thinking tokens are billed as output tokens'. That is a statement about Claude Code. On the Messages API, 4.7+ models reject `type: enabled` and use adaptive thinking controlled by `output_config.effort`. The extended-thinking doc says 'at lower effort settings it may skip thinking entirely on easy inputs', and the API default effort is 'high'. So on the API, thinking cost can be reduced substantially by setting low effort; it is not an unremovable fixed overhead. Billing thinking as output is correct, and it can be measured via `usage.output_tokens_details.thinking_tokens`.
  - corrected: The ~30% tokenizer inflation applies to 4.7+ models (Opus/Sonnet 5.5, Fable 5.1) and should be applied to the C/D token estimates. In Claude Code, thinking cannot be turned off on Opus 5.5 / Sonnet 5.5 / Fable. On the Messages API these models use adaptive thinking: the default effort is 'high', and at low effort the model may skip thinking on easy inputs. Thinking tokens are billed as output and should be measured via usage.output_tokens_details.thinking_tokens.
- **[C5] NEEDS_QUALIFICATION** Anthropic reports enterprise Claude Code costs ~$13/dev/active day, $150-250/month, <$30/day for 90%; so a daily Claude Code operating session costs ~$1-12/day or $270-3,000/yr.
  - reasoning: The quote is verbatim from the costs doc: 'around $13 per developer per active day and $150-250 per developer per month, with costs remaining below $30 per active day for 90% of users'. The $1.08-5.20 (Opus) and $2.45-11.75 (Fable) per-session figures check out arithmetically. Opus low: 1M×0.20 + 80k×5 + 20k×4 + 20k×20 = 0.20+0.40+0.08+0.40 = $1.08. Fable high: 1.25+5.00+0.50+5.00 = $11.75. However, the enterprise figure describes full developer coding days and does not validate the session token assumptions. The anchor actually points higher ($13/day on average), and the doc warns that scheduled tasks, subagents and cache misses make usage 'climb'. The 'this makes' framing overstates what the source supports: the $1-12/day range is the researcher's assumption, not Anthropic data. It also omits the $0.08/session-hour Managed Agents runtime if that route were used (negligible).
  - corrected: Anthropic reports enterprise Claude Code averages of ~$13 per developer per active day (90% below $30). The researcher's own token assumptions give $1.08-5.20 (Opus 5.5) and $2.45-11.75 (Fable 5.1) per 30-60 min session, i.e. ~$270-3,000/yr for daily sessions. Real usage could be higher and must be measured.
- **[C6] NEEDS_QUALIFICATION** TradingAgents needs 11 LLM calls + 20+ tool calls per prediction (16-22 measured) with ~0% cache hits; evidence is a 3-month backtest on 5 mega-caps, no transaction costs, Sharpe 8.21 attributed to few pullbacks.
  - reasoning: Confirmed: the paper's footnote says 'We benchmarked TradingAgents over 3 months due to intensive LLM and tool use (11 LLM calls & 20+ tool calls/prediction)'. The period is Jan 1 to Mar 29, 2024. The Sharpe of 8.21 on AAPL is attributed to 'few pullbacks'. No commissions or slippage are mentioned. Wrong or overstated: (1) the main results table covers 3 tickers (AAPL, GOOGL, AMZN), not 5. (2) Issue #750 (opened 2026-05-06, still open) asserts '16-22 LLM calls' and '~0% cache hit rate' as an architectural analysis ('All providers affected (OpenAI, Anthropic, Google, DeepSeek)'); it does not report a measurement on a specific provider, so 'measured' overstates it. (3) The paper used OpenAI models (gpt-4o, gpt-4o-mini, o1-preview), not Claude, so the Opus/Fable cost of D is an extrapolation.
  - corrected: TradingAgents: 11 LLM calls and 20+ tool calls per prediction (paper); the current code makes 16-22 LLM calls per run, with ~0% cache hits by an architectural analysis in open issue #750. The published evidence is a ~3-month backtest (Jan to Mar 2024) with 3 tickers (AAPL, GOOGL, AMZN) in the main table, run on OpenAI models, with no transaction costs. The AAPL Sharpe of 8.21 is attributed by the authors to few pullbacks.
- **[C7] NEEDS_QUALIFICATION** Pro $20/mo ($17/mo annually), Max from $100 (5x) and $200 (20x), all include Claude Code, rolling 5h + weekly limits.
  - reasoning: claude.com/pricing: Pro '$20 if billed monthly'; '$17 Per month with annual subscription discount ($200 billed up front)'. The annual cost is therefore $200, not $204 as the research's table says. Both Max tiers show 'From $100'. The $200 price for 20x is inferred from the help-center credit table (Max 20x credit $200), not from a displayed price. The page does say 'Claude Code is included in all paid plans', and describes a 'rolling five-hour session window' plus weekly limits on paid plans.
  - corrected: Pro is $20/month, or $200/year billed up front (~$16.67/month). Max 5x starts at $100/month. Max 20x is shown only as 'From $100' and is believed to be $200/month (inferred from help-center credit amounts). All paid plans include Claude Code, with rolling 5-hour and weekly limits.
- **[C8] NEEDS_QUALIFICATION** Consumer Terms (eff. 2025-10-08) prohibit bot/script access except via API key or explicit permission; as of 2026-06-16 claude -p / Agent SDK still draw from subscription limits after the separate-credit plan was paused; issue #36324 documents a user reporting bans; so unattended subscription use carries ban risk.
  - reasoning: The terms quote is verified (effective October 8, 2025): 'through automated or non-human means, whether through a bot, script, or otherwise' except 'via an Anthropic API Key or where we otherwise explicitly permit it'. The help-center pause is verified (updated June 16, 2026): 'Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits'; 'Teams running shared production automation should use Claude Platform with an API key'. Overstated: issue #36324 is a docs request ('headless mode documentation does not warn ...'). The author says users discover the restriction after being banned but does not say they themselves were banned, and there was no maintainer response (closed 'not planned'). It is not documentation of bans. The overall recommendation (use an API key for unattended runtime) still stands. Anthropic's own help center treating `claude -p` on a plan as a supported use arguably counts as 'explicit permission' for personal use, so the ban risk is ambiguous rather than established.
  - corrected: The Consumer Terms bar scripted access except via an API key or explicit permission. Anthropic's help center (2026-06-16) says `claude -p` and the Agent SDK still draw from subscription limits and recommends an API key for production automation. Issue #36324 alleges, without first-hand evidence, that scripted headless use on a subscription can lead to bans. For an unattended trading bot, an API key is the policy-clean and cheaper choice.
- **[C9] CONFIRMED** GitHub Actions: standard runners free on public repos, 2,000 min/month on GitHub Free private repos; schedules can be delayed/dropped at high load (esp. top of hour), 5-min minimum, auto-disabled in public repos after 60 days inactivity.
  - reasoning: Verbatim from the docs: 'The use of standard GitHub-hosted runners is free: In public repositories'; GitHub Free includes '2,000' minutes; 'can be delayed during periods of high loads ... High load times include the start of every hour'; 'some queued jobs may be dropped'; 'shortest interval ... once every 5 minutes'; 'In a public repository, scheduled workflows are automatically disabled when no repository activity has occurred in 60 days'. The docs now also support IANA timezones for schedules.
- **[C10] REFUTED** Alpaca: commission-free US equities, SEC + FINRA fees on sells rounded up to $0.01, i.e. ~1% of a $1 position per round trip; Basic data free (IEX, since 2016, 200/min); Algo Trader Plus $99/mo.
  - reasoning: The fee arithmetic is wrong. The fee schedule PDF ('Revised on September 17, 2026') says: 'Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent $0.01.' Equity rates: SEC $0.0000206 × trade value (sells only); FINRA TAF $0.000195/share (sells only, max $9.79); CAT $0.000003 per executed equivalent share on BOTH buys and sells. So a $1 fractional round trip on different days pays CAT on the buy ($0.01) plus SEC, TAF and CAT on the sell ($0.03). That is about $0.04 in total, ~4% per round trip, not 1%. Monthly rebalancing of one $1 position is then ~48%/yr, not ~12%. Several positions traded the same day share the daily per-type round-up, so fees per dollar fall quickly with size: at $100 per trade day the same $0.04 is ~0.04%. Commission-free is confirmed ('does not charge commissions, except' index options, Elite Smart Router and non-retail flow). The data plans are confirmed: Basic is 'Free', IEX, 'Since 2016', 'latest 15 minutes', '200 / min', 30 websocket symbols; Algo Trader Plus is '$99 / month'. Also relevant, from the same PDF: outbound domestic wire $15, outbound international wire $35, local currency transfers 1.5% (max $40), ACH return $25, outbound ACATS $25. These funding and withdrawal costs dwarf a $1 test for a non-US user. The open question on news is answered: Alpaca's News API (history back to 2015) is available on the free plan under the same 200 calls/min limit, per Alpaca's blog and docs.
  - corrected: Alpaca charges no equity commission but passes through SEC ($0.0000206 × value, sells), FINRA TAF ($0.000195/share, sells) and CAT ($0.000003/share, buys and sells) fees. Each fee type is aggregated daily and rounded up to $0.01 separately, so a $1 round trip costs about $0.04 (~4%). The free Basic data plan (IEX real-time, history since 2016, 200 calls/min) and the free News API are sufficient; Algo Trader Plus is $99/month. Wire and withdrawal fees ($15 domestic, $35 international, 1.5% FX up to $40) make a real-money $1 test uneconomic for anyone who cannot fund by free ACH.
- **[C11] CONFIRMED** Web search $10 per 1,000 searches plus tokens; web fetch tokens only; ~$0.01 per search.
  - reasoning: Pricing page: 'Web search is available on the Claude API for $10 per 1,000 searches, plus standard token costs'; web fetch has 'no additional charges beyond standard token costs'. Note that result tokens usually cost more than the $0.01 search fee: an average page is ~2,500 tokens and a large doc page ~25,000. At Opus rates, 10 fetched pages of ~10k tokens = 100k × $4/M = $0.40 per day. That strengthens the recommendation to pre-digest news in code.
- **[C12] NEEDS_QUALIFICATION** About 89.5% of active US large-cap funds underperformed the S&P 500 over 15 years per SPIVA; 8%/15% excess scenarios are highly optimistic.
  - reasoning: The cited InvestmentNews article (2026-03-04, SPIVA year-end 2025) only gives the 1-year figure: '79% of all active large-cap U.S. equity funds underperformed the S&P 500' in 2025, versus 65% in 2024. It contains no 15-year number. A search summary of S&P's year-end 2025 SPIVA material gives 89.93% over 15 years as of 2025-12-31, so the ~90% figure is right but mis-sourced, and 89.5% does not match the cited source. SPIVA measures mutual funds net of fees against an index. It is a relevant but indirect base rate for a retail LLM system, which also faces spread, fee and tax drag, and small-sample overfitting risk. The conclusion that 8%/15% is highly optimistic is well supported and understated: the defensible base case for excess return is ~0% or negative.
  - corrected: Per SPIVA year-end 2025, 79% of active US large-cap funds trailed the S&P 500 in 2025, and ~90% (89.93%) trailed over 15 years (primary: S&P Dow Jones Indices SPIVA). For a retail LLM-driven system the base-case expected excess return should be taken as ~0% or negative. 8% and 15% are best-case sensitivities, not expectations.
- **[ARITH] NEEDS_QUALIFICATION** Runtime cost, break-even and TCO tables (sections 3, 4, 5, 8).
  - reasoning: I recomputed every row and the arithmetic is internally correct at list prices. B: 3k×$1/M + 300×$5/M = $0.0045, 8k → $0.0095, ×252 = $1.13-2.39. C Sonnet: $0.08-0.14/day, $20.2-35.3/yr. C Opus: $0.16-0.28, $40.3-70.6. C Opus 60k/8k: $0.40, $100.8. D Opus: $1.12 up to 5×$2.80 = $14.00/day, $282-3,528/yr. D Fable: $2.80-35.00. E Opus: $1.08/$2.55/$5.20. E Fable: $2.45/$5.88/$11.75. F: $0.30-0.50. Break-even divisions check. TCO: build $50-150 over 3 years ($17-50) + $15-30 maintenance ≈ $32-80/yr → $400-1,000 at 8%. Weaknesses: (a) the token-count inputs are assumptions with no measurement, and the 1.3x tokenizer factor is not applied to C/D; (b) 'excess return' is never defined against a benchmark. If it means return above a buy-and-hold index, the realistic base case (~0%) makes every non-zero cost a net loss versus just holding the index, and the whole break-even table is only a best-case bound; (c) the VPS figure (€5.49 per Northflank, effective 2026-06-15) excludes VAT and IPv4, so ~$75/yr is a slight underestimate; (d) the claim 'market impact negligible below ~$100k' is unsourced. It is plausible for SPY-class ETFs but not for small caps.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- Presenting 3%/8%/15% 'excess return' scenarios, with 8% called 'generous' but still used as the headline, anchors a novice on returns that ~90% of professional managers fail to reach over 15 years. A consumer-protection reviewer would require the base case to be 0% or negative excess over a buy-and-hold index. At that base case, no architecture 'pays for itself', including A with its build and maintenance costs. The honest default recommendation is a low-cost index fund; the project is a learning exercise.
- 'Scaling capital improves the cost-to-profit ratio' is only true if there is a positive edge. If the edge is zero or negative, scaling up multiplies losses. The person asked for assurance that expanding will not stop profits. The binding risk is the absence of an edge, overfitting and regime change, not token cost or market impact. The research should say that no amount of paper trading can guarantee that scaling preserves profit, and propose staged scaling with pre-registered kill criteria instead.
- The $1 live-test fee math is wrong: Alpaca rounds each fee type (SEC, TAF, CAT) up to $0.01 separately per day, and CAT applies to buys too. That is about 4% per $1 round trip, not 1%. Funding and withdrawal can cost $15-35 per wire for anyone without free ACH, which makes a real-money $1 test pointless for non-US users. Treat it as optional, and use paper trading for plumbing.
- Running the bot on a public GitHub repo to get free minutes exposes the strategy, and possibly positions and P&L in workflow logs, and risks misconfigured secrets. Use a private repo; 2,000 free minutes is ample. The 60-day auto-disable only affects public repos, but dropped or delayed cron runs affect both, so the job must be idempotent and must not fire an order twice after a delayed or duplicated run.
- The monthly Opus review (F) has no demonstrated benefit and creates a channel for discretionary, LLM-driven parameter tweaking. That is a classic overfitting and data-snooping path. A careful quant would make it read-only and advisory (anomaly and bug reports), forbid it from changing strategy parameters without a new costed out-of-sample test, or drop it entirely. Otherwise it is a cost with no evidence of value.
- The rule to 'refuse LLM calls if trailing-12-month token spend exceeds 25% of trailing realized excess P&L' is statistically meaningless on small samples. Realized excess over a year is mostly noise, so the rule will switch the LLM on after lucky periods. The kill switch is fine; the justification should not imply that realized P&L demonstrates an edge.
- The Haiku anomaly check (B) duplicates the deterministic anomaly detector that triggers it. There is no evidence that it adds decision value, and an LLM veto over trades adds non-reproducibility to backtests. If kept, log it and do not let it trade.
- The thresholds for adopting C ($1k Sonnet / $10k Opus) and D ($50-100k) are framed as capital gates, which implies that more capital justifies an LLM analyst. The only valid gate is statistically significant, cost-inclusive, out-of-sample outperformance of the deterministic core. Also, LLM backtests suffer look-ahead contamination: the model's training data includes the backtest period, which inflates historical LLM-signal results. That is a key reason the TradingAgents results cannot be taken as proof.
- TradingAgents evidence is misdescribed as 5 mega-caps. The main table has 3 tickers (AAPL, GOOGL, AMZN), covers ~3 months, runs on OpenAI models and includes no costs. Citing it as the reference for D's cost on Claude is extrapolation.
- The build cost estimate ($50-150) is likely low for the multi-agent research and verification workflow actually being run, with many subagents, large web fetches (10-25k tokens per page) and Fable orchestration. It should be measured from actual usage, not estimated. On a subscription the marginal cost differs anyway.
- Relying on Consumer Terms plus an unverified ban anecdote (issue #36324 is a docs request, not a documented ban) overstates the enforcement risk. The API-key recommendation is still correct on cost and clarity grounds.
- Missing legal and tax caveats a consumer lawyer would add: residency determines broker eligibility and tax treatment (short-term gains, US wash-sale rules or local equivalents, possible US withholding for non-residents); pattern-day-trader and margin rules if any intraday architecture uses a margin account; paper trading does not model real fills, queue position or partial fills, so paper results overstate live results; and no LLM output is financial advice.

## VERIFIER OVERALL

This research is mostly reliable on Anthropic API pricing and mechanics. I verified the model prices, cache multipliers and minimums, batch discount, expiry and retention, web search and fetch pricing, and the GitHub Actions limits against primary docs dated 2026-09. I also recomputed every runtime-cost and break-even row, and the arithmetic is correct. The main architectural conclusion stands: a deterministic core (A) with little or no runtime LLM use is the only design whose running cost is plausibly below any profit at $1-$1k, and daily Sonnet/Opus analysts or multi-agent debates are not.

Weight these points down or correct them:

1. **Alpaca fee claim (C10) is refuted.** The 2026-09-17 fee schedule rounds each fee type (SEC, TAF, CAT) up to $0.01 separately per day, and CAT applies to buys. A $1 round trip therefore costs about 4%, not 1%. International wire fees ($35) make a real-money $1 test uneconomic for non-US users.
2. **TradingAgents details are wrong.** The paper's main table has 3 tickers, not 5; it ran on OpenAI models; and issue #750's '16-22 calls, 0% cache' is an architectural assertion, not a measurement.
3. **'Thinking cannot be disabled' is a Claude Code statement.** On the Messages API, adaptive thinking with low effort can skip thinking. Separately, the ~1.3x tokenizer factor is not applied to the C/D costs, so those may be understated by up to ~30%.
4. **The ban evidence is weaker than presented.** Issue #36324 is a documentation request, not a documented ban.
5. **The SPIVA figure is mis-sourced.** The cited article gives only the 1-year 79%; the ~90% 15-year figure is correct but comes from S&P's own year-end 2025 SPIVA data.
6. **Minor price errors.** Pro annual billing is $200, not $204. Max 20x at $200 is inferred, not displayed.

Biggest substantive weakness: the break-even framework treats 3/8/15% 'excess return' as scenarios without defining the benchmark. The realistic base case is ~0% or negative excess over an index, and under that case every architecture, including A with build and maintenance costs, is a net cost compared with passive investing. The orchestrator should present break-even capital only as a best-case bound. The deciding criterion should be costed, out-of-sample, look-ahead-free evidence of edge, not capital thresholds.

Unsourced claims to treat as assumptions: 'market impact is negligible below ~$100k', and the token-volume inputs, including the $50-150 build estimate.

Resolved open question: Alpaca's News API is free on the Basic plan (200 calls/min, history back to 2015), so it can serve as the no-cost news source.
