# CRITIC

COMPLETENESS CRITIQUE OF THE SIX VERIFIED DIMENSIONS (as of 2026-09-29)

WHERE THE DIMENSIONS AGREE (safe to build on)
All six dimensions reach the same core conclusions:
- No LLM in the runtime decision loop. At $1 to $1k, any recurring token spend exceeds the plausible excess return.
- Runtime logic should be deterministic, rebalance monthly or less often, and trade only liquid ETFs.
- Buy-and-hold of a low-cost broad index fund is the null benchmark. It is also the most likely honest answer.
- Paper trading and $1 live trading validate plumbing, fills and fees. They cannot validate edge: detecting a 2-5%/yr edge needs roughly 16-100 years of data.
- Market-impact capacity is irrelevant at personal scale. The real scaling risk is that no edge exists, plus taxes, behaviour and fixed per-day fees.
- Claude is useful for design, code-writing and adversarial review only.

CONTRADICTIONS AND ERRORS THE ORCHESTRATOR MUST RESOLVE (no new research needed)
1. **$1 round-trip fee at Alpaca.**
   - Token-economics says about 1% (verifier refuted this). Tooling and micro-capital say about $0.04, i.e. 4%.
   - The $0.04 figure is right: SEC, TAF and CAT are each rounded up to $0.01 per day, and CAT applies to buys too.
   - During FINRA's TAF pause (2026-10-01 to 12-31) it is about 3%, if Alpaca passes the pause through (unverified).
   - Monthly rebalancing therefore costs about 36-48%/yr of a $1 account.
2. **Primary build candidate.**
   - Strategy-evidence names the equity trend filter as primary. Its own replication shows it lagging buy-and-hold by 1.7-4.1 pts/yr post-publication, with all of the risk benefit coming from 2008 and 2022. Bouchaud 2026 shows equity-index trend degraded after 2008.
   - Verifiers and the micro-capital and token-economics pushback all say automated buy-and-hold (plus contributions) should be primary, with trend as an optional drawdown-control overlay.
   - The orchestrator must choose between these. Recommendation: follow the verifiers.
3. **Runtime LLM use conflicts with the hard cost constraint.**
   - Token-economics recommends a monthly Opus batch review (F) and a Haiku anomaly check (B), and tooling recommends a weekly or monthly Haiku review.
   - Strategy-evidence verifiers say any LLM report is a running cost that exceeds the excess return on $1-$100.
   - Resolution consistent with the user's rule: zero runtime tokens, templated deterministic reports, and Claude used only in human-initiated development sessions.
   - Haiku 4.5's retirement floor is 2026-10-15, so any Haiku-dependent recurring role is fragile.
4. **What "profit" means in the user's cost rule.**
   - Absolute profit: buy-and-hold at zero runtime cost trivially satisfies the rule.
   - Excess over benchmark: only this justifies the complexity of an active overlay.
   - The deliverable must state which definition it uses.
   - The user excluded design and research cost, but maintenance, re-validation after dependency or model changes, and code review after changes are recurring costs and belong in the running-cost ledger.
5. **Validation checklist is internally inconsistent and nearly powerless.**
   - A.5 accepts "match SPY CAGR with smaller drawdown". A.6 demands t≥3 on an undefined "excess return".
   - The kill-switch uses the LARGER of two drawdown thresholds, which could mean stopping only at a 50-70% drawdown. It should be the smaller, plus an absolute dollar cap the user chooses.
   - The "50% haircut, Harvey-Liu rule of thumb" is misattributed: Harvey and Liu call a flat 50% haircut a mistake.
   - PBO≤0.2, the ±25% plateau and the 3-10x scaling steps are the researchers' own judgement calls and must be labelled as such.
   - DSR and PBO do not detect look-ahead leakage (Gençay 2026). Structural tests are required, e.g. shift signals by one bar and confirm performance collapses.
6. **Numeric errors to fix before anything reaches the user.**
   - "$0.50/yr is less than one day of role (e) ($0.065)" is false.
   - The Haiku daily call is 12.6x the daily profit of $1 at 15%/yr, not 19x.
   - The Rule 612 half-penny tick is deferred to Nov 2027, not Nov 2026.
   - The MinTRL formula is missing its leading "1 +".
   - Haiku's clean-window SE is 0.94, not 0.85.
   - The TradingAgents hobbyist re-test used Claude Haiku 4.5 and Opus 4.8, not OpenAI models.
   - The Fischer-Krauss decay citation (arXiv 2201.08218) should be dropped.
   - TradingAgents' published evidence covers 3 tickers, not 5.
7. **Tooling disagreements.**
   - Custom pandas backtester as primary engine vs bt (MIT) as reference engine with a custom fee overlay. The verifier's version is safer, because LLM-written backtesters are exactly where look-ahead bugs hide.
   - GitHub Actions: the researchers' own cited thread (#201738, July 2026) shows odd-minute scheduling does NOT help, with runs 8-14 h late and whole days dropped.
   - Public vs private repo: use a private repo, since a public one risks leaking positions and keys through logs.
8. **Alpaca data availability is unresolved.**
   - Alpaca's free historical data is described as "since 2016" (token-economics), "~2016-2019, start not stated" (tooling), and "paper-only accounts get IEX data only" (micro-capital verifier).
   - This directly affects whether the container's one reachable market-data source can feed signals, and it is unresolved.

MISSING ENTIRELY (the gaps below)
- (a) A residency-conditional matrix. Country is unknown and it gates the broker, the instruments (UCITS), the tax on every trend switch, tax-reporting burden, FX, and whether a $1 live test is even recoverable.
- (b) An evaluation of EXISTING tools. The user explicitly asked "existing tool / modifying / creating". Broker auto-invest, robo-advisors, Composer, Lumibot and free backtesters like testfol.io were never assessed, and the honest primary recommendation (automated buy-and-hold) may need no custom code.
- (c) A verified, licence-compliant, container-reachable long-history total-return data pipeline. Tiingo needs a token and forbids redistribution. Ken French and FRED reachability should be confirmed. Simulated pre-inception ETF histories are needed for 2000-2008 coverage.
- (d) Live-trading safety engineering, the most likely source of real loss once scaled. Topics: Alpaca account configurations (no_shorting, max_margin_multiplier=1), key scope and withdrawal rights, idempotent orders via client_order_id, protection against duplicate or late runs, CI supply-chain risk, notional caps, and a reliable free scheduler.
- (e) Independent critiques of moving-average timing. Zakamulin (J. Asset Management 2014; SSRN 2743119; 2017 book) finds MA/TSMOM timing performance "highly overstated" once data-mining, look-ahead and costs are handled. International and after-tax evidence and the matched GTAA benchmark are also missing.
- (f) Small-account implementation specifics at Alpaca. Items: cash-leg yield and fractionability of the T-bill ETF, penny-rounded dividends, fractional shares on transfer-out, account and inactivity fees, whether paper-only accounts get the same data and order behaviour, and fee reconciliation from account activities.
- (g) Beginner prerequisites and fair-presentation standards for hypothetical performance. Also better behaviour-gap evidence than DALBAR (e.g. Morningstar Mind the Gap).

Sources checked this pass:
- Zakamulin 2014 (https://link.springer.com/article/10.1057/jam.2014.25) and SSRN 2743119 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2743119).
- Alpaca AccountConfiguration fields: no_shorting, max_margin_multiplier (default 1.0 under $2k, 2.0 above), fractional_trading, pdt_check, suspend_trade, max_options_trading_level (https://alpaca.markets/sdks/python/api_reference/trading/models.html ; https://docs.alpaca.markets/us/docs/margin-and-short-selling).
- testfol.io: free backtester with 47 simulated tickers, e.g. SPYSIM back to 1886 and BNDSIM back to 1986 (https://testfol.io/simulated-tickers/ ; https://riskparitychronicles.substack.com/p/three-portfolio-backtesters-every).

## [high] Residency-conditional broker, instrument, tax and funding matrix

The person's country is unknown. It decides:
- whether Alpaca live (or any API broker) is available at all;
- whether US-domiciled ETFs are purchasable (EU/UK PRIIPs/KID rules);
- the after-tax ranking of buy-and-hold vs a trend overlay;
- the tax-reporting burden per trade (which can cost more than the profit on a small account);
- FX risk;
- whether a $1 live test is recoverable (Alpaca charges $35 for an outbound international wire).

Every live-trading recommendation so far is US-centric. The repo needs a broker-adapter abstraction and a per-country config, or the build choice is wrong for most countries.

BRIEF: CONTEXT: A beginner with no investing experience wants a small automated system that invests in ETFs via a broker API.
- The strategy is deterministic: buy-and-hold of a broad index fund, optionally with a monthly trend-filter overlay that switches between an equity index fund and a T-bill/short-bond fund about 1-1.5 times per year.
- They will first paper-trade, then possibly fund with $1-$100, then scale to $1k-$100k only if justified.
- Running costs must be near zero.
- Their country of residence is UNKNOWN.
- Today is 2026-09-29. Prefer primary sources (broker docs and fee schedules, tax authority pages, regulator pages) dated 2024-2026. Cite a URL for every claim and flag anything older or secondary.

TASK: Build a decision matrix for these jurisdictions:
- United States
- United Kingdom
- Germany
- France
- Netherlands
- Ireland
- Israel
- Canada
- Australia
- India

For EACH jurisdiction, answer:
1. Which brokers offer a documented public retail trading API usable by an individual from a script, plus a free paper/demo environment?
   - Check Alpaca (live eligibility by country; Canada reportedly excluded; the country list is 'contact support'), Interactive Brokers (TWS/Web API, IBKR Lite eligibility), Trading 212 public API (Invest/ISA, demo, order types, pies), eToro API, Tradier, Public.com, Schwab Trader API, Saxo OpenAPI, and any local broker with an API.
   - For each broker give: fractional/notional order minimum; commission and pass-through fees on a $1, $100 and $10k order; funding and withdrawal cost from a local bank (wire fee, FX spread or fee); minimum deposit; inactivity/account fees.
2. Which index-fund vehicle can a retail investor legally buy there: US-domiciled ETFs (VTI/VOO/SPY) or UCITS equivalents (e.g. Irish-domiciled VWCE, CSPX)? State the rule (PRIIPs KID; the UK Consumer Composite Investments regime in transition 2026-04-06 to 2027-06-08) and whether cross-border US brokers such as Alpaca actually block US ETFs for residents there.
3. Tax treatment of a trend-switch sale (short- vs long-term capital-gains rates; wash-sale or bed-and-breakfast rules; Irish deemed disposal and exit tax on funds; German Vorabpauschale and Teilfreistellung; Dutch Box 3; Israel's 25% real-gains rate; Canadian superficial-loss rule; Australian CGT discount; Indian STCG/LTCG on foreign ETFs). Give a rough after-tax annual drag for about 1.5 switches/yr vs buy-and-hold, with arithmetic.
4. Tax-advantaged accounts (Roth/traditional IRA, UK ISA/SIPP, Canadian TFSA, Australian super, etc.): which of them can be traded via a public API (e.g. Trading 212 ISA API), and which ban frequent or automated trading.
5. Dividend withholding on US-domiciled funds for residents (30% default; W-8BEN treaty rate) vs Irish UCITS funds (15% at fund level for US equities).
6. US estate-tax exposure for non-US persons holding US-situs assets above $60k.
7. The tax-reporting burden per realized trade, and whether an accountant or extra filing is typically needed for a foreign-broker account. Estimate the annual cost in money or time; this is a hidden running cost.
8. Investor protection that applies (SIPC, FSCS, national scheme) and dispute forum.
9. FX: the currency of account and of assets, and the typical FX conversion cost.

DELIVERABLE:
- One table per jurisdiction.
- A cross-country summary naming, for each country, the cheapest viable (a) paper-trading path, (b) $1-$100 live-test path (or 'not economical: skip live, use paper'), and (c) $10k+ path.
- A recommended broker-adapter interface (the minimal set of operations the code must abstract) so one repo can support at least Alpaca plus one EU/UK-friendly API broker.
- Clear flags wherever a claim could not be verified from a primary source.

## [high] Existing tools that may make a custom build unnecessary (or should be reused)

The user explicitly asked to use an existing tool, modify one, or create one. No dimension evaluated no-code or low-code options, and verifiers say the honest primary recommendation is automated buy-and-hold. If a broker's free recurring-investment or pie feature, or a robo-advisor, does that at zero runtime cost, the custom repo's job shrinks to a validation and backtesting harness plus an optional overlay. Existing open-source frameworks (Lumibot, bt) and free backtesters (testfol.io, with simulated histories to 1886) could replace hundreds of lines of error-prone LLM-written code. This could change what gets built.

BRIEF: CONTEXT: A beginner wants to invest small amounts ($1 to eventually $10k-$100k) using a rules-based, low-turnover approach.
- The approach is buy-and-hold of a broad index ETF with periodic contributions, optionally with a monthly trend filter that moves to a T-bill ETF when the index is below its 10-month moving average.
- Running costs (software, data, hosting, LLM tokens) must be lower than plausible profit. Excess return over buy-and-hold is expected to be near zero, so any fixed monthly fee is effectively fatal below about $10k.
- Their country is unknown, so note availability by region (US, UK, EU, other).
- Today is 2026-09-29. Use primary sources (vendor pricing pages, docs, GitHub repos, PyPI) dated 2024-2026 and cite URLs. Be skeptical of marketing and of any performance claims.

TASK: Evaluate these categories and give, for each tool: monthly or annual cost, account minimum, fractional or $1 support, countries served, whether it can run the rules above automatically, API availability, and evidence of maintenance (last release or commit date).
(A) Broker-native automation:
- recurring or auto-invest features (Schwab Stock Slices, Fidelity, Vanguard, Robinhood recurring investments, M1 Finance pies and auto-rebalance, Trading 212 Pies and AutoInvest, eToro recurring investments, Interactive Brokers recurring investments);
- whether any support conditional rules such as a trend filter.
(B) Robo-advisors:
- Betterment, Wealthfront, Vanguard Digital Advisor, Schwab Intelligent Portfolios, and UK/EU equivalents (Nutmeg, Moneyfarm, Scalable Capital, Finanzfluss/Growney);
- fees and minimums.
(C) No-code algorithmic platforms:
- Composer, Surmount, QuantConnect live, Tradetron, TradingView-to-broker bridges;
- fees, whether their backtests include costs and taxes, whether live trading at small size is allowed, and any audited live track record.
(D) Open-source frameworks usable with Python 3.11:
- Lumibot (supports Alpaca, IBKR, Tradier; backtest-and-live parity?), bt 1.2.3, vectorbt 1.1.1, alpaca-py examples, pylivetrader/others;
- licence, maintenance status, and whether each supports notional/fractional orders, a month-end rebalance schedule, and paper/live switching.
(E) Free backtest cross-check tools:
- testfol.io (free tier limits; simulated tickers such as SPYSIM and BNDSIM, and their methodology and data sources);
- Portfolio Visualizer (current free-tier limits; it went partly paid);
- Curvo backtest (UCITS);
- Ken French data library;
- state whether each can reproduce a 10-month SMA timing rule with costs.

DELIVERABLE:
- A ranked comparison table with arithmetic for annual cost at $100, $1k and $10k of capital, as a percentage of assets.
- A clear verdict on three options: (1) use an existing tool with no custom code, (2) custom code only for backtesting and validation plus broker-native automation for execution, (3) a full custom execution bot.
- Explicitly state which option meets 'running cost < plausible profit' at each capital level.

## [high] Verified, reachable, licence-compliant long-history total-return data pipeline

Every backtest-based proof depends on at least 20 years of dividend-adjusted data that covers 2000-02, 2008, 2020 and 2022. From this container:
- Yahoo returns HTTP 429.
- Stooq drops connections.
- Alpha Vantage allows 25 calls/day, and its adjusted endpoint may be premium.
- Alpaca history starts around 2016 at best. Researchers disagree on the start year, and on whether paper-only (non-KYC) accounts get SIP or only IEX data.
- Tiingo needs a user token, and its free plan is 'internal use only'. That matters if data is committed to a git repo.
- Most candidate ETFs (AGG 2003, IEF 2002, GLD 2004, DBC 2006) barely predate 2008.

Without a confirmed pipeline, the build cannot produce the proof the user asked for.

BRIEF: CONTEXT: We are building a Python 3.11 backtester and a monthly-rebalance ETF system in a Linux container.
- Known reachability from this container: Alpaca API endpoints reachable (401 without keys); Alpha Vantage reachable; Yahoo Finance chart API returned HTTP 429; stooq.com cut the connection; FRED keyless CSV (fredgraph.csv?id=DGS3MO) works; Tiingo reachable ('Please supply a token').
- The strategies need monthly (ideally daily) dividend-adjusted total-return series for: a US total-market or S&P 500 fund, an international-equity fund, intermediate Treasuries, aggregate bonds, REITs, commodities, gold, and a T-bill proxy. Ideally from 1990 or earlier, via mutual-fund or index proxies (e.g. VFINX 1976, VBMFX 1986, VGSIX 1996, VTSMX 1992, VGTSX 1996, VFITX 1991, the Ken French market factor from 1926).
- Today is 2026-09-29. Use primary documentation (vendor docs, terms of service, pricing pages) and cite URLs.

TASK:
1. For each source below, report: free-tier limits, history depth, whether dividends are included, adjustment method, point-in-time vs retroactively revised adjustments, licence and terms (personal use only? redistribution or committing to a public or private git repo allowed?), and whether a keyless or free-key request works from a cloud or datacenter IP.
   Sources: Tiingo (EOD for ETFs and mutual funds), Alpaca Market Data Basic, Ken French Data Library (direct CSV zip URLs), FRED (DGS3MO, TB3MS), Alpha Vantage (TIME_SERIES_MONTHLY_ADJUSTED vs DAILY_ADJUSTED premium status in 2026), EODHD free, Nasdaq Data Link, Shiller online data (S&P total return since 1871), Damodaran annual returns, testfol.io simulated series, Kenneth French and AQR data sets, Stooq bulk downloads, and SEC/issuer NAV history files.
2. Resolve three Alpaca questions from primary docs or support articles:
   - the earliest date for daily bars on the free Basic plan (2016? 2019?);
   - whether a PAPER-ONLY account (email sign-up, no KYC, any country) can use the market data API, and with which feed (SIP historical older than 15 minutes, or IEX only);
   - how adjustment=all handles dividends, and whether historical adjusted values change after each new dividend. That affects reproducibility of logged signals.
3. Propose a concrete pipeline with at least two independent sources per series. Specify: cross-validation tolerance (e.g. monthly return differences under 5 bp); splicing rules for mutual-fund proxies into ETF series (expense-ratio adjustment); caching to local CSV/parquet with checksums; what may and may not be committed to git under each licence.
4. List known data-quality pitfalls: missing dividends, split errors, stale NAVs, and total-return vs price-return mismatches between strategy and benchmark. For each, give a test to detect it.
5. If the container can reach them, note which endpoints a researcher should curl to confirm reachability, without keys where possible.

DELIVERABLE: a source-by-series table (series × source × start date × licence × reachability), the recommended pipeline, and explicit statements of anything unverified.

## [high] Live-execution safety engineering and reliable free scheduling

Once real money is involved, the most likely way to lose it is a software or operations failure, not a bad strategy. Examples:
- duplicate orders from delayed or retried cron runs;
- margin accidentally enabled (Alpaca defaults the margin multiplier to 2.0 above $2k equity);
- a sign or unit bug that sells everything;
- leaked API keys from CI logs or a compromised GitHub Action;
- an LLM agent with order-placement tools.

The research mentions kill-switches only statistically. GitHub Actions cron is documented to run 8-14 h late and drop days, and odd-minute scheduling did not help. A hostile reviewer would say there is no safety design at all.

BRIEF: CONTEXT: A small Python system will place real orders at Alpaca (US broker, Trading API) once a month, possibly checking daily.
- It will be triggered by a scheduler, probably GitHub Actions in a private repo or an alternative free scheduler.
- The owner is a novice and wants never to lose money through bugs, leverage or key theft.
- Capital is $1-$100 initially, later possibly $1k-$100k.
- Today is 2026-09-29. Use primary sources (Alpaca docs, alpaca-py reference, GitHub docs and security advisories, Cloudflare docs) and cite URLs.

TASK:
1. Alpaca account hardening via API and dashboard:
   - the account configuration fields (no_shorting, max_margin_multiplier, fractional_trading, pdt_check, dtbp_check, suspend_trade, trade_confirm_email, max_options_trading_level) and how to set a cash-only, long-only, no-options account;
   - whether a margin account can be converted to or opened as a cash account;
   - what the default margin multiplier is above and below $2,000 of equity.
2. API key capabilities:
   - can a Trading API key initiate withdrawals or bank transfers, or only trade?
   - are read-only or scoped keys or OAuth scopes available?
   - how are keys rotated or revoked, and is there IP allow-listing?
3. Order idempotency: client_order_id uniqueness semantics; how to detect already-submitted orders after a crash; behaviour of notional DAY orders submitted outside market hours; handling partial fills; the 'cannot replace notional orders' constraint.
4. Pre-trade guards to implement:
   - maximum notional per order and per day;
   - maximum turnover;
   - a sanity check that target weights sum to 1 and all prices are fresh;
   - refusing to trade on missing or stale data;
   - a dry-run mode;
   - a file- or env-based global kill switch;
   - an alert channel (email or push) that is free.
5. Scheduler reliability and cost for a once-daily job:
   - GitHub Actions schedule delays and drops (cite docs and 2025-2026 community reports);
   - workflow_dispatch triggered by an external free cron (cron-job.org, Cloudflare Workers Cron Triggers free tier, Google Cloud Scheduler free tier);
   - Oracle Cloud Always Free VM (and its idle-reclaim policy);
   - the user's own machine;
   - for each give reliability evidence, cost and setup complexity.
   - Design a catch-up rule so a missed or late day never double-trades.
6. Supply-chain and secret risk:
   - pinning GitHub Actions to commit SHAs (cite the 2025 tj-actions/changed-files compromise and GitHub's guidance);
   - pinning pip hashes;
   - GitHub Secrets masking limits;
   - never logging positions in public repos;
   - keeping keys out of any LLM context.
7. Documented incidents where retail or institutional automated trading lost money through bugs or duplicate orders. Use these to justify each guard.

DELIVERABLE:
- A prioritized checklist of controls, each with the exact API field or code pattern and its source URL.
- A recommended scheduler with evidence.
- A list of automated tests (e.g. a replayed duplicate trigger, stale data, a partial fill) the repo must include before any live key is used.

## [medium] Independent and international evidence on moving-average / trend timing, after tax, with matched benchmarks

The only optional overlay still on the table rests mainly on Faber (the strategy's promoter) and one in-house replication. Omitted sources:
- Zakamulin (J. Asset Management 2014; SSRN 2743119 'Revisiting the Profitability of Market Timing with Moving Averages'; 2017 book) concludes MA/TSMOM timing performance is 'highly overstated' once data-mining, look-ahead and realistic costs are handled.
- Bouchaud et al. 2026 show equity-index trend degraded after 2008.

Also missing:
- evidence outside the US;
- an after-tax comparison;
- GTAA5 compared against its matched equal-weight buy-and-hold;
- the size of 'timing luck' from the rebalance day (Concretum found about 220 bp/yr of dispersion).

This decides whether the overlay is offered at all, and how it is framed.

BRIEF: CONTEXT: A beginner's system may offer an optional overlay: hold a broad equity index fund while it is above its 10-month simple moving average (or while its 12-month return beats T-bills), otherwise hold T-bills; checked monthly.
- Promoter evidence (Faber, SSRN 962461) reports lower drawdowns and similar or higher returns.
- An in-house replication on Ken French US data found that over 2006-2026 the rule returned 9.65%/yr vs 11.33% for buy-and-hold (max drawdown -18% vs -50%), and lagged by 4.1 pts/yr over 2013-2026, with all of the benefit coming from 2008 and 2022.
- Today is 2026-09-29. Prefer peer-reviewed papers and primary data; cite URLs; separate promoter, practitioner and academic sources.

TASK:
1. Summarize critical or independent academic evidence with exact numbers, sample periods and cost assumptions:
   - Zakamulin 2014 (J. Asset Management, 'The real-life performance of market timing with moving average and time-series momentum rules');
   - Zakamulin 2016/2017 (SSRN 2743119; the book 'Market Timing with Moving Averages');
   - Glabadanidis;
   - Clare, Seaton, Smith & Thomas on trend following in equity indices;
   - Hurst-Ooi-Pedersen;
   - Huang-Li-Wang-Zhou (JFE 2020);
   - Bouchaud et al. 2026 (arXiv 2607.01550) on post-2008 equity-index trend;
   - any 2023-2026 out-of-sample updates.
2. International out-of-sample evidence: results of the 10-month SMA or 12-month absolute momentum on non-US equity indices (MSCI EAFE, Japan since 1990, UK, Germany, emerging markets) after 2006. Look especially for cases where the rule avoided long bear markets (Japan) vs where it whipsawed.
3. Whipsaw statistics: the number of false switches per decade, and the worst 12-month and 36-month relative underperformance vs buy-and-hold. Also the 2020 V-shaped rebound cost.
4. The after-tax effect for a US taxable investor (short-term gains at ordinary rates) and for a generic 25% flat capital-gains regime, vs buy-and-hold with no realization. Cite Faber's Gannon & Blum-based estimate and any better source.
5. Timing luck: evidence on rebalance-day dispersion (Newfound Research 'rebalance timing luck', Concretum GTAA5), and whether tranching (splitting capital across several month-offsets or lookbacks) removes it without reducing expected return.
6. Matched benchmark for multi-asset GTAA5 (SPY/EFA/IEF/DBC/VNQ with 10-month SMA): find or specify the equal-weight buy-and-hold of the same five assets over 2006-2025, with costs.

DELIVERABLE:
- A balanced verdict (for and against) on whether an equity-only or multi-asset trend overlay has positive expected after-tax excess return or only drawdown reduction.
- An honest one-paragraph framing suitable for a novice, and the specific tests (international indices, tranching, after-tax) the repo's backtester should run.

## [medium] Alpaca small-account mechanics: cash leg, dividends, fees reconciliation, paper vs live differences

Several implementation details could silently break the backtest-to-live mapping or cost money at small size, and none is verified:
- Can the T-bill leg (SGOV/BIL/SHV) be bought fractionally, and does idle cash earn anything?
- Dividends on fractional positions are penny-rounded, so a $1 position receives $0.00.
- Whether Alpaca passes through the Q4-2026 FINRA TAF pause.
- Whether pure buy days really incur a $0.01 CAT charge.
- Fractional shares are typically liquidated, not transferred, on an outbound ACATS transfer (a taxable exit).
- Inactivity or account fees.
- Whether paper-only accounts behave like live ones: data feed, fractionable flags, order acceptance.

The researchers disagree on some of these.

BRIEF: CONTEXT: A Python system will run a monthly ETF rebalance at Alpaca (US broker).
- It will paper-trade first, then trade $1-$100 live using fractional/notional DAY orders, possibly scaling to $10k+.
- The portfolio is a broad equity ETF (e.g. VTI or SPY) plus a T-bill/short-Treasury ETF as the defensive leg; possibly also IEF, GLD, VNQ, EFA, DBC.
- Today is 2026-09-29. Use Alpaca's primary docs, fee schedule (https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf, revision 2026-09-17), customer agreement, support articles and the alpaca-py reference. Cite URLs and quote verbatim where numbers matter.

TASK: Answer precisely:
1. For SGOV, BIL, SHV, VTI, SPY, IEF, GLD, VNQ, EFA and DBC: are they fractionable and marginable (via /v2/assets fields)? If a keyless or documented example cannot confirm this, say how to check with a key.
2. Does Alpaca pay interest on idle cash (a cash sweep or high-yield cash program) for individual US and non-US accounts? At what rate and minimum? That determines whether 'cash earns T-bills' in the backtest should be modelled as a T-bill ETF or as a sweep.
3. Dividend handling on fractional positions: rounding rules, whether DRIP is available, withholding on non-US accounts, and how dividends appear in account activities.
4. Fees:
   - confirm the per-day, per-fee-type round-up rule applies to buy-only days (CAT);
   - whether Alpaca passes through FINRA's TAF pause for trades 2026-10-01 to 2026-12-31 (SR-FINRA-2026-021);
   - which account-activity types show SEC, TAF and CAT fees, so the code can reconcile modelled vs charged fees daily;
   - any account maintenance, inactivity, paper-statement, ACATS-out, or domestic/international wire fees.
5. Transfers and closure: what happens to fractional shares on an outbound ACATS transfer or account closure (liquidation → taxable event?). Also SIPC coverage of fractional shares held on a principal or riskless-principal basis.
6. Paper vs live differences:
   - data-feed entitlements of a paper-only (non-KYC) account;
   - whether paper accepts the same fractional/notional orders and rejects OPG/CLS for fractional orders the same way;
   - how paper handles dividends and fees (reportedly not simulated);
   - how to create a new paper account at a chosen starting balance (reset was replaced by create/delete).
7. Whether whole-share MOC (CLS) orders plus a fractional DAY remainder can be combined in one account, allowing closer matching to close-price backtests once positions exceed one share.

DELIVERABLE: a table of verified facts with source URLs, a list of unverifiable items with the exact API call that would resolve each once keys exist, and the modelling implications for the backtester (cash yield, dividend rounding, fee model).

## [medium] Beginner prerequisites, fair presentation of hypothetical results, and behaviour/adherence evidence

The person has no experience and asked for 'proof and merit'. Nothing yet covers what a beginner must understand or have in place before risking even $1:
- an emergency fund and paying off high-interest debt;
- time horizon and drawdown tolerance;
- the fact that 'passes every gate' can still lose money for 1-3 years.

The deliverable will display hypothetical backtested performance. Regulators require that such results be labelled, net of costs, shown with a benchmark and worst drawdown, and not cherry-picked. Behaviour-gap evidence currently relies on DALBAR, which is methodologically criticised. Abandoning a rule after multi-year underperformance is the main documented way such plans fail.

BRIEF: CONTEXT: We are delivering a git repository to a person with no investing experience.
- It backtests and optionally automates a simple ETF strategy: buy-and-hold of a broad index fund, possibly with a monthly trend-filter overlay.
- It will show backtested (hypothetical) performance.
- Their country is unknown.
- Today is 2026-09-29. Use primary sources (SEC, FINRA, Investor.gov, FCA, MoneyHelper, ESMA, national regulators, peer-reviewed papers, Morningstar research) and cite URLs.

TASK:
1. Compile regulator-published prerequisites for a first-time investor: emergency fund, high-interest debt, time horizon, diversification, fees, risk tolerance and drawdown. Sources: Investor.gov 'Saving and Investing' roadmap, FINRA investor insights, UK FCA and MoneyHelper, ESMA investor warnings, and one non-English-speaking regulator. Distil these into a 10-15 item pre-flight checklist the repo README should present before any live-trading instructions.
2. Standards for presenting hypothetical or backtested performance:
   - SEC Marketing Rule 206(4)-1 hypothetical-performance requirements and FAQ;
   - FINRA Rule 2210 and its 2023-2025 guidance on projections and hypothetical performance;
   - FCA COBS 4.6 past and simulated past performance rules;
   - CFA Institute GIPS guidance on hypothetical performance.
   - Even though this is personal use, extract a concrete disclosure template: labelling, net of which costs, benchmark, period selection, worst drawdown, number of variants tried.
3. Behaviour-gap evidence better than DALBAR:
   - Morningstar 'Mind the Gap' (latest, 2024-2026) dollar-weighted vs time-weighted return gaps, especially for tactical-allocation funds vs index funds;
   - academic critiques of DALBAR's method;
   - evidence on investors abandoning tactical or trend strategies after multi-year underperformance (e.g. managed-futures fund flows after 2011-2019).
   - Quantify, with arithmetic, how abandonment timing changes realized returns.
4. Evidence on automated or rules-based investing reducing behavioural errors: robo-advisor studies, commitment devices, recurring-investment adherence. Include any evidence that it does not help.
5. What wording should an honest system use so a novice does not infer guaranteed profit? Provide 3-5 example sentences grounded in the sources.

DELIVERABLE: the pre-flight checklist, a disclosure template for the repo's backtest reports, a short evidence summary on behaviour gaps with numbers and sources, and recommended phrasing.
