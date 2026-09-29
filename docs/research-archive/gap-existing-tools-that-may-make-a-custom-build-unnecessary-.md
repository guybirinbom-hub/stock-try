# gap: Existing tools that may make a custom build unnecessary (or should be reused)

## SUMMARY

## Bottom line (read first)

For the strategy the verifiers already settled on (buy-and-hold a broad index ETF with periodic contributions, plus an optional monthly 10-month-SMA switch into T-bills), **the core job needs no custom code and costs $0 a year to run** in almost every region. Several brokers offer free recurring fractional purchases from $1: Fidelity, Vanguard (Vanguard ETFs only), Robinhood, Schwab (mutual-fund AIP), IBKR Lite, Trading 212, and Scalable Capital savings plans. **No broker-native recurring or pie feature I found supports a conditional rule such as a trend filter.** The only no-code tool that can run the SMA switch automatically for free is Composer's Starter tier. It serves the US only, requires $50 per strategy and recommends $2,500, so it fails the "$1 test" and non-US users.

Every subscription product fails the "running cost < plausible profit" test below roughly $10k, and most fail well above that. Examples are M1 ($3/mo), Betterment ($5/mo under $24k), Composer Advanced ($10/mo), Surmount ($5-30/mo), QuantConnect live (~$34-84/mo), TradingView webhook bridges (~$100/mo) and testfol.io Pro ($12.50/mo).

The custom repo's job therefore shrinks to three things:
1. A backtest and validation harness built on existing libraries (bt, vectorbt), cross-checked against free web backtesters.
2. Optionally, a deterministic monthly signal check that tells the human whether to flip the allocation.
3. Optionally, a small execution bot, and only where the broker has a free API (Alpaca, IBKR, Trading 212).

An LLM is not needed in the monthly loop.

---

## (A) Broker-native automation

| Tool | Platform/commission cost | Min / fractional | Countries | Conditional (trend) rules? | API | Notes |
|---|---|---|---|---|---|---|
| Fidelity recurring fractional | $0 commission, $0 account fee | "as little as $1", NMS stocks and ETFs | US persons only | No | No retail trading API | [fidelity.com/trading/fractional-shares](https://www.fidelity.com/trading/fractional-shares) |
| Vanguard auto-invest ETFs | $0 commission | $1 to $25,000, **Vanguard ETFs only**, must already hold the fund | US | No | No | Launched Oct 2024 ([mymoneyblog, secondary](https://www.mymoneyblog.com/vanguard-automatic-recurring-etf-investments.html)) |
| Schwab | Stock Slices $5 min, S&P 500 stocks only, ETFs not eligible per [StockBrokers.com Jun 2026](https://www.stockbrokers.com/guides/fractional-shares-brokers). Automatic Investment Plan is **mutual funds only**, $1 min (e.g. SWPPX, no fund minimum) | $1 via AIP | US | No | Schwab API exists (Lumibot/QuantConnect support it) | schwab.com returned 403 to me, so these facts come from secondary sources and have medium confidence |
| Robinhood recurring | $0; dollar-based orders only | Fractional; share price >$1 and market cap >$25M; leveraged/inverse ETPs excluded | US (plus PR, USVI, DC) | No | No official stock API | [robinhood support](https://robinhood.com/us/en/support/articles/recurring-investments/) |
| M1 Finance pies + auto-rebalance | **$3/month platform fee** unless ≥$10k in M1 assets for one day of the 30-day cycle ("Updated May 2026") | $100 to open a brokerage account (secondary) | US | No (target-weight pies only) | No | [M1 platform fee disclosure](https://m1.com/legal/disclosures/platform-fee-disclosure/) |
| Trading 212 Pies & AutoInvest | $0 commission; **0.15% FX fee** on cross-currency orders, pies included | €1/£1; daily to six-monthly schedules; "self-balancing" contributions | UK Ltd, EU GmbH (not US) | No | Public API (beta): live and demo market/limit orders for Invest/ISA. **Pies API endpoints are marked deprecated** (1 req/30s) | [T212 help: Pies intro](https://helpcentre.trading212.com/hc/en-us/articles/30661163244317-Pies-AutoInvest-Introduction), [FX fee](https://helpcentre.trading212.com/hc/en-us/articles/360018769897-Is-there-an-FX-Conversion-Fee-for-AutoInvest), [API docs](https://docs.trading212.com/api/pies-(deprecated)/getall) |
| Scalable Capital savings plans (DE/EU) | FREE Broker €0/month; **savings plan executions €0 from €1**; manual trades €0.99 under €250; PRIME+ €4.99/month | €1 | EU (DE-centric page) | No | No public trading API | [scalable trading-costs](https://de.scalable.capital/en/trading-costs) |
| eToro recurring | $0 commission on stocks/ETFs; **0.5% currency conversion**; a conversion waiver for non-USD deposits ran only "until March 31, 2026" | **$25 minimum**, monthly only | "over 75 countries" | No | No | [etoro.com/investing/recurring](https://www.etoro.com/investing/recurring/) |
| IBKR Recurring Investments | IBKR Lite: $0 US stocks. **IBKR Pro Fixed: $0.005/share, $1 minimum, capped at 1% of trade value**, so a $100 recurring buy can cost $1 (1%) | $1 fractional; daily, weekly or monthly; US, Canadian and EU stocks and ETFs | Most countries (Lite mainly US; Pro elsewhere) | No | Yes (TWS / Client Portal API) | IBKR pages returned 403; figures are from [IBKR fractional search snippet](https://www.interactivebrokers.com/en/trading/fractional-trading.php) and a secondary source ([brokerchooser](https://brokerchooser.com/broker-reviews/interactive-brokers-review/fractional-share-trading)). Medium confidence. |

**Finding:** none of these support "hold X unless index < 10-month SMA, then hold T-bill ETF". The trend filter needs one of three things:
- a human acting monthly on a signal;
- Composer (US);
- an API bot (Alpaca, IBKR, or Trading 212's beta API).

## (B) Robo-advisors

| Robo | Fee | Minimum | Region | Can run trend rule? |
|---|---|---|---|---|
| Betterment Digital | 0.25%/yr; **$5/month if balance < $24k** unless there is a ≥$200/month recurring deposit | None stated | US | No |
| Wealthfront | 0.25%/yr | $500 (commonly cited; the support page returned 403) | US | No |
| Vanguard Digital Advisor | "no more than $20 per $10,000" (≤0.20%), about $15-16 for all-index | $100 | US residents only | No |
| Schwab Intelligent Portfolios | 0% advisory | $5,000 | US | No; **6%-22.5% cash allocation** (typically 6-10%) is a hidden drag; Premium discontinued 2026 |
| J.P. Morgan Personal Investing (ex-Nutmeg) | Fixed allocation 0.45% up to £100k (managed 0.75%), plus fund costs ~0.17-0.31% (secondary) | £500 (secondary) | UK | No |
| Moneyfarm | 0.45% management + 0.25% platform = 0.70% at £20k, plus funds up to 0.21% = ~0.91% | not stated | UK | No |
| Scalable Wealth | 0.75%/yr (secondary reviews) | higher than broker | EU | No (its own risk model) |
| growney | 0.68% at €5k, 0.38% at €10k, 0.25% at €100k | €500 lump / €25/month plan | DE | No. No Finanzfluss partnership found in the source |

Sources:
- [betterment.com/pricing](https://www.betterment.com/pricing)
- [wealthfront.com/pricing](https://www.wealthfront.com/pricing)
- [Vanguard Digital Advisor](https://investor.vanguard.com/advice/digital-advisor)
- [NerdWallet SIP review, Dec 2025](https://www.nerdwallet.com/blog/investing/schwab-intelligent-advisory-review/)
- [JPM Personal Investing fee schedule, eff. 17 Jun 2025](https://www.personalinvesting.jpmorgan.com/legal/schedule-of-fees-and-charges)
- [Moneyfarm pricing](https://www.moneyfarm.com/uk/pricing/)
- [extraETF growney test 09/2026](https://extraetf.com/de/robo-advisor/growney-test)

**Takeaway:** robos charge 0.20-0.9% a year to do what a $0 recurring plan into one ETF does. For a one-fund strategy they add cost without adding the trend rule. Their value is mainly tax-loss harvesting and behaviour management, which is irrelevant at $100-$1k. Several also have minimums above $100.

## (C) No-code algorithmic platforms

- **Composer (acquired by SoFi, announced 23 Jun 2026; branded "Composer by SoFi").**
  - Plans: Starter $0 ("Automate your first strategy", unlimited backtests), Advanced $10/month (5 automated strategies), Pro $32/month ($384/yr, API access).
  - Execution is through Alpaca Securities and Apex; "No commissions on trades"; US only.
  - Minimum is $50 per symphony, with **$2,500 recommended** because non-fractionable assets otherwise sit in cash (updated Jun 2025).
  - Backtests use daily adjusted closes with a **default slippage of 1 bp** plus SEC/FINRA fees. The subscription cost is excluded by default. Taxes are not modelled.
  - The help article on backtests mentions an optional "$40 monthly" subscription estimate, which conflicts with the current $10/$32 plans, so the docs are stale.
  - Post-acquisition pricing is not disclosed and may move into SoFi Plus.
  - Sources: [pricing](https://www.composer.trade/pricing), [backtest basics](https://help.composer.trade/article/67-backtest-basics), [minimum](https://help.composer.trade/article/74-minimum-to-invest), [SoFi IR](https://investors.sofi.com/news/news-details/2026/Introducing-Composer-by-SoFi-AI-Powered-Investing-From-Idea-to-Execution/default.aspx).
  - **This is the only $0 no-code option that can execute an SMA switch automatically**, but only for US residents with meaningful capital. Platform-change risk after the acquisition is real.
- **Surmount.** Free / Core $5/month / Plus $10/month / Pro $30/month. Connects external brokerages; minimums are not published ([surmount.ai/pricing](https://surmount.ai/pricing)).
- **QuantConnect.**
  - The Free tier allows unlimited backtests and paper trading, but live trading requires a paid tier ([tier features](https://www.quantconnect.com/docs/v2/cloud-platform/organizations/tier-features)).
  - Prices conflict between sources. A Mar 2026 review lists Researcher at $60/month plus live nodes from $24/month ([newtrading.io](https://www.newtrading.io/quantconnect-review/)); another snippet says "Quant Researcher $10/month". So live trading costs roughly $34-84/month (low confidence on the exact figure; the official pricing page did not render numbers).
- **Tradetron.** The free plan allows paper trading only, with no live auto-execution. Live starts at ₹300/month for Indian brokers ([help](https://help.tradetron.tech/en/article/tradetron-pricing-plans-upgrade-refund-policy-7oisc0/), [pricing](https://tradetron.tech/pages/pricing)). Alpaca is integrated, but USD pricing was not visible to me.
- **TradingView to broker bridges.**
  - Webhook alerts require Premium ($59.95/month) per the comparison chart ([tradingview.com/pricing](https://www.tradingview.com/pricing/)).
  - TradersPost live auto-submit starts at $41.65/month; the free tier is a 7-day trial, with paper-only automation ([traderspost.io/pricing](https://traderspost.io/pricing)).
  - The combined ~$101.60/month is absurd for this strategy.
- **Audited live track records:** none of the pricing pages or docs I reviewed claim an audited live track record. Composer's public "symphony" statistics are backtests. Treat all platform performance displays as hypothetical.

## (D) Open-source frameworks (checked against PyPI JSON on 2026-09-29; container runs Python 3.11.15)

| Library | Latest | Licence | Py 3.11 | Maintenance | Fit for this strategy |
|---|---|---|---|---|---|
| **bt** | 1.2.3 (2026-09-12) | MIT | ≥3.9 ✔ | Active (1.2.0 Apr 2026, then 1.2.1-1.2.3 in Sep) | Has `RunMonthly`, `SelectWhere` (feed a boolean SMA frame), `WeighTarget`, `CapitalFlow` (contributions) and commissions/cost_model. **Best fit for the validation harness.** Backtest only, no live trading. |
| **vectorbt** | 1.1.1 (2026-09-26) | **Apache 2.0 + Commons Clause** (no selling a product or service derived from it) | 3.11-3.14 ✔ | Active | `Portfolio.from_signals/from_orders` with `fees`, `slippage`, `size_type='value'/'targetpercent'`. Fast, good for parameter sweeps and robustness checks. Backtest only. |
| **Lumibot** | 4.6.2 (2026-09-27) | GPL-3.0 | ≥3.10 ✔ | Very active: 4 releases in 3 weeks, meaning churn risk, so pin the version | Same Strategy class for backtest, paper and live ("IS_BACKTESTING" toggle; `ALPACA_IS_PAPER`). `sleeptime="1M"` exists in source. Supports Alpaca, IBKR, Tradier and Schwab. `TradingFee(flat_fee, percent_fee)` models costs. Quantities are Decimal (fractional); I found no notional-dollar order type in `order.py`. **Heavy dependencies** (openai, google-adk, ccxt, psycopg2, databento, polygon, etc.) mean a large attack and breakage surface for a once-a-month trade. Defaults to Yahoo data for backtests, which is rate-limited from this container. [GitHub](https://github.com/Lumiwealth/lumibot) |
| **alpaca-py** | 0.44.0 (2026-08-11) | Apache-2.0 | ≥3.10 ✔ | Active official SDK | Notional/fractional orders from $1 ("buy as little as $1 worth"); fractional works in both paper and live; market, limit, stop and stop-limit orders with TIF=Day ([docs](https://docs.alpaca.markets/docs/fractional-trading)). A ~50-line month-end script is simpler and safer than a framework. |
| pylivetrader | 0.7.1 (**2022-04-11**) | Apache 2.0 | n/a | **Abandoned**; do not use | |
| backtrader | 1.9.78.123 (**2023-04-19**) | GPLv3+ | works | Unmaintained | |
| zipline-reloaded | 3.1.1 (2025-07-19) | Apache | ≥3.10 | Slow | Overkill |
| nautilus_trader | 1.231.0 | LGPL | **requires ≥3.12, so not usable on 3.11** | Active | Overkill |

Alpaca account availability outside the US is "contact support" ([alpaca support](https://alpaca.markets/support/countries-alpaca-is-available)), which is a real blocker if the user is non-US.

## (E) Free backtest cross-check tools

- **testfol.io**
  - Free tier works without saved runs. Pro costs $12.50/month billed annually, Pro+ $25 and Max $80 ([pricing](https://testfol.io/pricing)).
  - Simulated tickers:
    - SPYSIM: "Simulated SPY / S&P 500 total return", start 1885, 0% ER.
    - BNDSIM: start 1986, 0.03% ER.
    - CASHX: 3-month T-bill return from 1885.
    - Source: [simulated tickers](https://testfol.io/simulated-tickers/).
  - **The underlying source datasets are not disclosed** on the catalog or help page. The help page only says these are "modeled history" and "research series independently created by Testfolio". The data is most likely Shiller/Cowles-type pre-1926 series, but that is unconfirmed.
  - Tactical signals include SMA and EMA; they are "boolean masks … true or false on the close of any given trading day", with lookbacks expressed in days. A 10-month SMA must be approximated as ~210 trading days, evaluated at month-end via the rebalance schedule. Whether a signal can be based strictly on month-end closes is unclear.
  - The tactical tool shows a "Trading Cost %" field, "applied when the strategy switches allocations". A Turnover & Taxes tab estimates capital-gains tax, excluding wash sales and state taxes.
  - Only US tickers are available because of data licensing.
  - Sources: [help](https://testfol.io/help/), [tactical](https://testfol.io/tactical), [guide](https://testfol.io/guides/tactical-allocation).
  - **It can approximately reproduce the SMA rule with costs.**
- **Portfolio Visualizer**
  - Free: "up to 15 assets with limited history", no month-to-date results.
  - Basic $30/month and Pro $55/month (billed annually) add YTD results and "forward trade signals" ([pricing](https://www.portfoliovisualizer.com/pricing)).
  - The free tier includes the "Moving Averages - Single Asset" timing model, which moves to cash below the MA ([TAA page](https://www.portfoliovisualizer.com/tactical-asset-allocation-model)).
  - I found no transaction-cost field on the TAA page. **It can reproduce the rule without costs, on limited history.**
- **Curvo Backtest**
  - Free; EUR and UCITS; backfills with index data (e.g. IWDA from Jan 1979) "taking into account the costs of the fund".
  - Supports monthly contributions, rebalancing and brokerage costs.
  - No timing or MA rules ([Curvo article, 27 Jul 2026](https://curvo.eu/article/understand-your-portfolio-of-etfs-with-backtest)).
  - **It cannot reproduce the SMA rule.** It is useful for EU buy-and-hold only.
- **Ken French Data Library**
  - Free. Monthly Mkt-RF and RF from 1926, updated through Aug 2026 and now built from CRSP CIZ format ([data library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)).
  - It provides returns, not price levels. An SMA must be computed on a reconstructed total-return index, which differs from Faber's price-based SMA.
  - **It can reproduce the rule only with your own code** (bt or vectorbt), which is exactly the harness's job. It is also the best independent check against testfol's undisclosed SPYSIM.

## Cost arithmetic: annual running cost as % of assets

The table excludes ETF expense ratios, which apply to every option: ~0.03% for US ETFs such as VOO/VTI and ~0.1-0.22% for UCITS world ETFs.

| Rank | Option | $100 | $1k | $10k | Arithmetic |
|---|---|---|---|---|---|
| 1 | $0 broker recurring plan (Fidelity / Vanguard / Robinhood / Schwab MF AIP / IBKR Lite / T212 same-currency / Scalable plan) | 0% | 0% | 0% | $0 platform fee, $0 commission |
| 1= | Custom validation harness (bt/vectorbt) + broker automation, no LLM in the loop | 0% | 0% | 0% | Runs locally, one-off |
| 3 | Custom Alpaca bot on free cron (own PC or GitHub Actions free tier), deterministic | ~0% | ~0% | ~0% | $0 hosting; Alpaca $0 commission plus tiny SEC/FINRA sell fees |
| 3a | Same, plus a monthly Claude Haiku 4.5 sanity check (20k input + 2k output tokens) | 0.36% | 0.036% | 0.0036% | 20k×$1/M + 2k×$5/M = $0.03/month = $0.36/yr |
| 3b | Same, with Opus 5.5 | 1.44% | 0.14% | 0.014% | 20k×$4/M + 2k×$20/M = $0.12/month = $1.44/yr (Batch API halves this) |
| 4 | Composer Starter (US) | n/a (min $50; $2.5k recommended) | ~0% | ~0% | $0 plan plus regulatory fees |
| 5 | Trading 212 buying USD ETF from a GBP/EUR account | 0.15% of each flow | same | same | FX fee on each buy |
| 5 | IBKR Pro Fixed, $100 monthly buys | 1% of each $100 buy | 1% of flow | 1% of flow | $1 min per order, 1% cap. Tiered pricing ($0.35 min) is better |
| 6 | Vanguard Digital Advisor | 0.20% | 0.20% | 0.20% | ≤$20 per $10k |
| 6 | Wealthfront | n/a (min $500) | 0.25% | 0.25% | |
| 6 | Schwab Intelligent Portfolios | n/a | n/a | 0% fee, but cash drag ≈ 6% cash × ~5% equity premium ≈ 0.3%/yr expected opportunity cost (rough estimate) | min $5k |
| 7 | eToro recurring (non-USD depositor) | n/a (min $25) | 0.5% of flow | 0.5% of flow | FX conversion |
| 8 | Nutmeg/JPM fixed | n/a (£500) | 0.62-0.76% | 0.62-0.76% | 0.45% + 0.17-0.31% |
| 8 | growney / Moneyfarm / Scalable Wealth | n/a | ≥0.68% | 0.38-0.91% | per tables above |
| 9 | M1 Finance | $36/$100 = **36%** | $36/$1k = **3.6%** | 0% (waived at ≥$10k) | $3 × 12 |
| 10 | Betterment (no $200/month deposit) | $60/$100 = **60%** | **6%** | $60 = **0.6%** | $5 × 12; 0.25% otherwise |
| 11 | Surmount Core / Composer Advanced | **60% / 120%** | 6% / 12% | 0.6% / 1.2% | $5×12 = $60; $10×12 = $120 |
| 12 | testfol.io Pro for email signal alerts | 150% | 15% | 1.5% | $12.5 × 12 = $150 |
| 13 | QuantConnect live | 408%-1,008% | 40.8%-100.8% | 4.1%-10.1% | ($10 or $60 + $24) × 12 = $408-$1,008 |
| 14 | TradingView Premium + TradersPost Starter | 1,219% | 122% | 12.2% | ($59.95 + $41.65) × 12 = $1,219 |

**Plausible profit benchmark.** Long-run equity returns of about 5-7% a year are not guaranteed, and the expected excess of the trend filter over buy-and-hold is about 0. That gives:
- plausible annual profit of about $5-7 at $100, $50-70 at $1k and $500-700 at $10k;
- plausible **extra** profit from the trend overlay of roughly $0 at every capital level.

So any fixed fee paid *for the overlay* is a pure loss in expectation, and it has to be justified by drawdown reduction rather than return.

## Verdict on the three options

**Option 1: an existing tool with no custom code.**
- A $0 recurring plan (US: Fidelity, Vanguard, Robinhood, Schwab AIP, IBKR Lite; UK: Trading 212, ideally a GBP-denominated ETF to avoid 0.15% FX; EU: Scalable savings plan or Trading 212; elsewhere: IBKR, with Tiered pricing to avoid the 1% minimum on small orders) **meets running cost < profit at $1, $100, $1k, $10k and $100k**, because the cost is 0% plus the ETF expense ratio.
- It cannot automate the trend filter. For US users with ≥$2.5k, Composer Starter can, at $0; it fails the $1 test and carries post-SoFi pricing risk.
- Robos, M1 and Betterment fail below about $10k because of flat fees. Above $10k they cost 0.2-0.9% a year for no added value on a one-fund strategy.

**Option 2: custom code only for backtesting and validation, with broker-native automation for execution.** This is the recommended option.
- **It meets running cost < plausible profit at every capital level**, because runtime cost is $0: backtests are one-off and there is no LLM in the loop.
- Build with bt (MIT, `RunMonthly` + `SelectWhere` + `CapitalFlow` + commissions) and vectorbt (sweeps and sensitivity; note the Commons Clause).
- Validate against Ken French monthly data (1926+) and cross-check against testfol.io's free SPYSIM/CASHX tactical backtest and Portfolio Visualizer's free MA timing model.
- If the overlay is wanted, a free local or cron script can compute the month-end signal and notify the human, who makes two trades per switch. That costs $0, or ~$0.36/yr if Haiku writes a summary, which is unnecessary.

**Option 3: a full custom execution bot.**
- It **technically meets the cost test at $1k and above** (about $0-1.44 a year), and at $100 if no LLM or only Haiku is used. At $1 of capital any LLM usage fails: $0.36/yr on $1 is 36%.
- It adds engineering and bug risk (wrong-side orders, missed month-end, API or auth changes, Lumibot churn) for an expected excess return of about 0.
- Broker availability is also an issue: Alpaca is US-first and "contact support" elsewhere; IBKR's API is heavier; Trading 212's API is beta and its pies endpoints are deprecated.
- It is justified only as a paper-trading demonstration (Alpaca paper is free and supports fractional) or if the user is US-based, insists on full automation of the SMA switch, and is not eligible for Composer.
- If built, use plain alpaca-py (Apache-2.0) with a ~50-line deterministic month-end script, not Lumibot's heavy stack.

**Scaling assurance.** For a liquid broad-index ETF bought monthly, the tools above have no capacity constraint anywhere near $100k, and $0 fees scale as 0%. What changes with scale is tax (the trend switch realizes gains in taxable accounts; testfol's Turnover & Taxes tab gives an estimate) and region-specific wrappers (ISA, Roth IRA, etc.). None of these are software problems.

## CLAIMS

- **[c1] (high)** None of the broker-native recurring investment or pie features reviewed (Fidelity, Vanguard, Schwab, Robinhood, M1, Trading 212, Scalable, eToro, IBKR) supports conditional rules such as a moving-average trend filter; they execute fixed-amount or target-weight purchases only.
  - evidence: Official feature descriptions cover schedules, dollar amounts, target percentages and self-balancing only; Robinhood's page describes only dollar-based recurring orders; T212 AutoInvest offers 'Self-Balancing' or 'By Targets' distribution.
  - sources: https://helpcentre.trading212.com/hc/en-us/articles/30661163244317-Pies-AutoInvest-Introduction, https://robinhood.com/us/en/support/articles/recurring-investments/, https://www.etoro.com/investing/recurring/, https://m1.com/pricing/
- **[c2] (high)** M1 charges a $3/month platform fee unless the user holds at least $10,000 in M1 assets for one day of the 30-day cycle or has an active M1 Personal Loan, which is 36%/yr of a $100 account and 3.6% of a $1,000 account.
  - evidence: M1 disclosure (updated May 2026): 'A $3 monthly fee applied to users who do not meet the waiver requirements.' $3×12=$36.
  - sources: https://m1.com/legal/disclosures/platform-fee-disclosure/, https://help.m1.com/en/articles/9331969-how-much-does-it-cost-to-use-m1
- **[c3] (high)** Betterment Digital charges 0.25%/yr but $5/month for balances under $24,000 unless the client has a $200+ monthly recurring deposit.
  - evidence: Betterment pricing page quoted '$5/month' for balances under $24,000; the fee is avoided with a '$200+ monthly recurring deposit' or a '$24K - $1M balance'.
  - sources: https://www.betterment.com/pricing
- **[c4] (high)** Composer's Starter plan is $0 and automates one strategy with unlimited backtests; Advanced costs $10/month and Pro $32/month. It is US-only, executes via Alpaca and Apex, requires $50 per symphony and recommends $2,500. Its backtests default to 1 bp slippage plus regulatory fees and exclude taxes and the subscription cost.
  - evidence: Composer pricing page and help articles 67 (backtest basics) and 74 (minimum to invest, updated Jun 27 2025).
  - sources: https://www.composer.trade/pricing, https://help.composer.trade/article/67-backtest-basics, https://help.composer.trade/article/74-minimum-to-invest
- **[c5] (high)** SoFi acquired Composer Securities in Q2 2026 (announced June 23, 2026) and rebranded it 'Composer by SoFi'; pricing after the acquisition is not disclosed and access may shift toward SoFi Plus.
  - evidence: SoFi investor-relations press release dated June 23 2026; the Composer homepage header reads 'Composer by SoFi'.
  - sources: https://investors.sofi.com/news/news-details/2026/Introducing-Composer-by-SoFi-AI-Powered-Investing-From-Idea-to-Execution/default.aspx, https://www.composer.trade/
- **[c6] (medium)** testfol.io's free tier offers SPYSIM (simulated S&P 500 total return from 1885, 0% ER), CASHX (3-month T-bills from 1885) and BNDSIM (from 1986) plus SMA/EMA tactical signals with a 'Trading Cost %' input, but it does not disclose the underlying source datasets for these simulations; paid tiers are $12.50, $25 and $80 per month billed annually.
  - evidence: Simulated tickers catalog and help page; the help says only 'modeled history' and 'research series independently created by Testfolio'; the pricing page lists Pro $12.5/mo, Pro+ $25/mo and Max $80/mo.
  - sources: https://testfol.io/simulated-tickers/, https://testfol.io/help/, https://testfol.io/pricing, https://testfol.io/tactical
- **[c7] (high)** Portfolio Visualizer's free tier includes tactical allocation models, including a single-asset moving-average model that moves to cash, but is limited to 15 assets with limited history; paid plans are $30 and $55 per month billed annually.
  - evidence: PV pricing page and tactical asset allocation model page.
  - sources: https://www.portfoliovisualizer.com/pricing, https://www.portfoliovisualizer.com/tactical-asset-allocation-model
- **[c8] (high)** bt 1.2.3 (MIT, released 2026-09-12) provides RunMonthly, SelectWhere, WeighTarget, CapitalFlow (contributions) and commission/cost-model support, which is sufficient to backtest monthly contributions plus a 10-month SMA switch with costs on Python 3.11.
  - evidence: PyPI JSON (version, date, license) and bt/algos.py and bt/backtest.py source on GitHub master.
  - sources: https://pypi.org/pypi/bt/json, https://raw.githubusercontent.com/pmorissette/bt/master/bt/algos.py
- **[c9] (high)** vectorbt 1.1.1 (released 2026-09-26) is licensed Apache 2.0 with the Commons Clause, which forbids selling a product or service whose value derives substantially from it; it requires Python 3.11 to 3.14.
  - evidence: LICENSE.md on GitHub and PyPI metadata (requires_python <3.15,>=3.11).
  - sources: https://raw.githubusercontent.com/polakowo/vectorbt/master/LICENSE.md, https://pypi.org/pypi/vectorbt/json
- **[c10] (high)** Lumibot 4.6.2 (GPL-3.0, released 2026-09-27) runs the same Strategy class in backtest, paper and live modes across Alpaca, IBKR, Tradier and Schwab and models fees via TradingFee. It has a very heavy dependency list (openai, google-adk, ccxt, psycopg2, databento, etc.) and shipped 4 releases in 3 weeks.
  - evidence: GitHub README, lumibot/entities/trading_fee.py, and PyPI requires_dist and release timestamps (4.5.91 on 09-06, 4.6.0 on 09-24, 4.6.1 on 09-26, 4.6.2 on 09-27).
  - sources: https://github.com/Lumiwealth/lumibot, https://pypi.org/pypi/lumibot/json
- **[c11] (high)** Alpaca supports fractional/notional orders from $1 in both paper and live environments (market, limit, stop and stop-limit orders, TIF=Day), and alpaca-py 0.44.0 (Apache-2.0, 2026-08-11) is the maintained SDK; pylivetrader has not been released since 2022-04-11.
  - evidence: Alpaca fractional trading docs and PyPI JSON for alpaca-py and pylivetrader.
  - sources: https://docs.alpaca.markets/docs/fractional-trading, https://pypi.org/pypi/alpaca-py/json, https://pypi.org/pypi/pylivetrader/json
- **[c12] (high)** Scalable Capital's FREE broker charges €0/month and €0 for savings-plan executions from €1, but €0.99 for manual trades under €250. Trading 212 AutoInvest is commission-free from €1/£1 but charges a 0.15% FX fee on cross-currency orders, including within pies.
  - evidence: Scalable trading-costs page; T212 help centre FX-fee article and pies introduction.
  - sources: https://de.scalable.capital/en/trading-costs, https://helpcentre.trading212.com/hc/en-us/articles/360018769897-Is-there-an-FX-Conversion-Fee-for-AutoInvest
- **[c13] (medium)** Automating the trend filter through a TradingView webhook bridge costs about $101.60/month: TradingView Premium at $59.95/month for webhooks plus TradersPost Starter at $41.65/month. That is about $1,219/yr, or 12.2% of a $10k account.
  - evidence: The TradingView pricing comparison shows webhooks only on Premium and above; the TradersPost pricing page lists Starter at $41.65/mo and confines free-tier automation to paper accounts.
  - sources: https://www.tradingview.com/pricing/, https://traderspost.io/pricing
- **[c14] (medium)** Vanguard Digital Advisor charges no more than $20 per $10,000 (≤0.20%) with a $100 minimum, for US residents only. Schwab Intelligent Portfolios charges 0% but requires $5,000 and holds 6%-22.5% in cash.
  - evidence: Vanguard Digital Advisor page; NerdWallet review (updated Dec 17 2025) for Schwab, because schwab.com blocked fetches.
  - sources: https://investor.vanguard.com/advice/digital-advisor, https://www.nerdwallet.com/blog/investing/schwab-intelligent-advisory-review/

## RECOMMENDATIONS

- Adopt Option 2 as the primary architecture: $0-fee broker recurring purchases for execution, with custom code limited to a backtest and validation harness built on bt (MIT) and optionally vectorbt (note the Commons Clause). Do not build a full execution bot as the default.
- Choose the execution venue by region. US: Fidelity, Vanguard (Vanguard ETFs), Robinhood, IBKR Lite, or a Schwab mutual-fund AIP. UK: Trading 212 AutoInvest with a GBP-denominated ETF to avoid the 0.15% FX fee. EU: Scalable Capital FREE savings plan (€0 from €1) or Trading 212. Elsewhere: IBKR on Tiered pricing, not Fixed, whose $1 minimum up to a 1% cap costs up to 1% on a $100 buy.
- Exclude M1, Betterment, Surmount, Composer Advanced/Pro, QuantConnect live, TradingView plus bridge, and testfol.io Pro from the runtime path below $10k. Their fixed fees range from 3.6% to more than 100% of assets a year at $1k, against an expected overlay excess return of about 0.
- Cross-validate the harness against three independent sources: Ken French monthly Mkt-RF+RF (1926 to Aug 2026, requires own SMA on a total-return index), testfol.io free tactical backtest (SPYSIM/CASHX with a ~210-trading-day SMA and the Trading Cost % field), and Portfolio Visualizer's free MA timing model. Require agreement within a stated tolerance before trusting any result.
- If the trend overlay is adopted, implement it as a free deterministic month-end signal that notifies the human to make the switch manually. Keep any LLM out of the monthly loop, or at most use one Haiku 4.5 call (~$0.03/month); never use Fable or Opus at runtime.
- If a paper-trading proof is required, use Alpaca paper (free, fractional supported) with plain alpaca-py (Apache-2.0) and a ~50-line script rather than Lumibot, whose heavy dependency tree and 4 releases in 3 weeks add breakage risk. If Lumibot is used anyway, pin the exact version.
- For US users with at least $2,500 who insist on full automation of the SMA switch without code, Composer Starter ($0, one automated strategy) is the only free no-code option; flag the post-SoFi-acquisition pricing risk and the $50 per symphony minimum.

## OPEN QUESTIONS

- What is the user's country of residence? It decides between US brokers and Composer, Trading 212 or Scalable, or IBKR, and whether Alpaca live accounts are available at all.
- Composer pricing and availability after the SoFi acquisition: will the $0 Starter plan survive, and will non-SoFi-members keep access?
- What exact datasets and splice methodology underlie testfol.io's SPYSIM and CASHX? They are undisclosed, and one source says testfol's simulation introduces systematic biases, especially for bonds.
- Can testfol.io's tactical tool evaluate a signal only on month-end closes (a true 10-month SMA), or only daily SMAs in trading days? This needs hands-on testing.
- QuantConnect's current official tier and live-node prices: secondary sources conflict ($10 vs $60/month for Researcher, plus $24/month per node), and the official pricing page did not render the numbers.
- Schwab ETF recurring and fractional eligibility: StockBrokers.com (Jun 2026) says Stock Slices exclude ETFs, while other secondary sources claim fractional ETF recurring buys; schwab.com blocked verification.
- IBKR Recurring Investments commission on small fractional orders under Pro Fixed vs Tiered, and IBKR Lite availability outside the US; the IBKR pages returned 403.
- Does the Vanguard brokerage account carry an annual account service fee without e-delivery in 2026? Not verified here.
- Tax treatment of trend-filter switches in taxable accounts in the user's jurisdiction, which could exceed any plausible overlay benefit.

## VERIFIER VERDICTS

- **[c1] NEEDS_QUALIFICATION** None of the broker-native recurring investment or pie features reviewed supports conditional rules such as a moving-average trend filter; they execute fixed-amount or target-weight purchases only.
  - reasoning: The sources I could check support the narrow claim. T212's Pies page lists only Self-Balancing or By Targets, plus a UK-only 'Use my cash first' funding condition. Robinhood says 'We only support dollar-based orders on recurring investments'. eToro is monthly only, $25 minimum. Fidelity's page describes plain recurring fractional buys. The claim is weaker than stated in three ways. (1) The Schwab, IBKR and Vanguard pages were 403 or secondary, so for those it rests on absence of evidence. (2) The summary goes further and says Composer is 'the only no-code tool that can run the SMA switch automatically for free'. That ignores non-recurring broker order tools. From memory, and not verified here because the thinkorswim docs returned 404 and search budget was exhausted: Schwab thinkorswim offers study-based conditional orders (e.g. close vs SMA) and IBKR TWS has conditional orders. These are one-shot, need re-arming and are not fractional, but they are $0 broker-native partial automation. (3) The T212 page also lists entities in Cyprus, Bulgaria and Australia and says the service is 'not directed at residents of the United States and Canada'. So 'UK Ltd, EU GmbH (not US)' understates its geographic reach.
  - corrected: None of the recurring or pie auto-invest features checked (T212, Robinhood, eToro, Fidelity; Schwab, IBKR and Vanguard via secondary sources only) supports an SMA condition. Some broker order tools may offer one-shot study- or price-conditional orders (e.g. thinkorswim, IBKR TWS; unverified here) that could partially automate a switch at $0. Composer is therefore not proven to be the only free automated route.
- **[c2] CONFIRMED** M1 $3/month platform fee unless >=$10k for one day of the 30-day cycle or active M1 Personal Loan; 36%/yr of $100, 3.6% of $1k.
  - reasoning: The disclosure says verbatim: 'A $3 monthly fee applied to users who do not meet the waiver requirements'. The waivers are '$10,000 or more in total M1 assets ... for at least one day during your 30-day billing cycle' or 'an active M1 Personal Loan'. It is marked 'Updated May 2026'. Arithmetic: $3 x 12 = $36, which is 36% of $100 and 3.6% of $1k. The disclosure lists other fees the research omitted: a $3/month IRA fee (never charged together with the platform fee) and a minimum-balance fee on accounts under $50 after 90+ days of inactivity. The $50 fee matters directly for a '$1 test' at M1. The $100 opening minimum was not verified.
- **[c3] CONFIRMED** Betterment Digital 0.25%/yr; $5/month under $24k unless $200+ monthly recurring deposit.
  - reasoning: The pricing page confirms 0.25% for $24K+ or '$200+ monthly recurring deposit', and '$5 Monthly' otherwise, with no Digital minimum. One caveat for the cost table: a user who contributes $200/month pays 0.25%, not $60/yr. So 'Betterment fails below ~$10k' applies only to users who contribute less than $200/month.
- **[c4] NEEDS_QUALIFICATION** Composer Starter $0 (1 automated strategy, unlimited backtests), Advanced $10/mo, Pro $32/mo; US only; Alpaca+Apex; $50/symphony min, $2,500 recommended; backtests 1bp slippage + reg fees, exclude taxes and subscription.
  - reasoning: Most of this checks out. Pricing: Starter $0 'Automate your first strategy', Advanced '$10/mo.' for up to 5 strategies, Pro '$32/mo.' or '$384/yr' for up to 500. Help article 74 (updated June 27 2025): '$50 in each symphony', '$2,500 across your portfolio'. Help article 67: daily adjusted closes, 1 bp default slippage, regulatory fees, subscription excluded by default with an optional '$40 monthly' estimate. The homepage names Alpaca Securities and Apex Clearing as carriers, says 'No commissions on trades', and says it is not an offer where Composer is not registered. Caveats: (a) 'Other fees may apply, see full fee schedule' was not reviewed. (b) The $2,500 recommendation exists because non-fractionable assets would otherwise leave cash uninvested. For a two-asset SPY/T-bill-ETF symphony whose assets are fractionable, $50 may suffice, so 'requires $2.5k' overstates the barrier. It still fails a $1 test. (c) Backtests execute at the daily close while live trades run intraday before the close, which is an unmodelled gap (help 67). (d) Post-SoFi pricing is unconfirmed, so these prices may be stale.
  - corrected: As of 2026-09 the Composer pricing page shows Starter $0 (1 automated strategy), Advanced $10/mo and Pro $32/mo ($384/yr). It is US only, carried by Alpaca and Apex, and needs a $50 minimum per symphony. The $2,500 recommendation matters mainly for non-fractionable assets. Backtests use daily adjusted closes, 1 bp slippage and regulatory fees, and exclude tax and subscription. Live fills occur intraday, not at the backtest close.
- **[c5] NEEDS_QUALIFICATION** SoFi acquired Composer Securities in Q2 2026 (announced June 23, 2026), rebranded 'Composer by SoFi'; post-acquisition pricing undisclosed; may shift toward SoFi Plus.
  - reasoning: The IR release dated June 23 2026 says SoFi is launching Composer 'following its acquisition of Composer Securities LLC'. The homepage reads 'Composer by SoFi'. The release does not give a closing date, so 'in Q2 2026' is an inference. It says 'Over time, members will be able to ... access advanced systematic investing tools' via SoFi Plus. It is silent on pricing and on existing customers. So the SoFi Plus shift is a stated direction, not a speculation.
  - corrected: On June 23 2026 SoFi announced 'Composer by SoFi' following its acquisition of Composer Securities LLC; the closing date is unstated. The release says members will over time access systematic tools via SoFi Plus. Future pricing and the fate of the $0 Starter plan are undisclosed.
- **[c6] NEEDS_QUALIFICATION** testfol.io free tier: SPYSIM (1885, 0% ER), CASHX (3m T-bill, 1885), BNDSIM (1986), SMA/EMA tactical signals with 'Trading Cost %'; undisclosed source datasets; paid $12.50/$25/$80 per month billed annually.
  - reasoning: Confirmed: the catalog lists SPYSIM as 'Simulated SPY / S&P 500 total return' 1885 0%, CASHX as '3-month Treasury bill cash return' 1885, and BNDSIM as 1986 0.03%. The tactical page has a 'Trading Cost' % field and an 'Include Turnover & Taxes report' checkbox. Help: 'research series independently created by Testfolio'; signals are 'boolean masks ... true or false on the close of any given trading day'. Pricing: Pro $12.50, Pro+ $25, Max $80, billed annually and labelled 'Early member rate', so likely to rise. The free tier includes the Tactical Allocation Backtester and simulated tickers but excludes email alerts, saved runs, downloads and Tactical Grid Search. Qualifications: (a) The catalog does say backfills are 'constructed from indexes, mutual funds, rates, or portfolio recipes', so a generic method is disclosed but not the specific datasets. 'Undisclosed' should read 'not specifically cited'. (b) Help did not document same-day vs next-day execution after a signal. If the switch executes at the same close that generates the signal, there is look-ahead bias. (c) The 'US tickers only because of data licensing' claim was not confirmed on the pages I fetched.
  - corrected: testfol.io's free tier includes the tactical backtester with SPYSIM (1885), CASHX (1885), BNDSIM (1986) and a Trading Cost % field. Backfills are described only generically ('indexes, mutual funds, rates, or portfolio recipes'), with no dataset citations. Signal-to-trade timing (same close vs next) is undocumented. Paid tiers are $12.50/$25/$80 per month billed annually at 'early member' rates.
- **[c7] CONFIRMED** Portfolio Visualizer free tier includes tactical models including single-asset MA to cash; limited to 15 assets with limited history; paid $30/$55 per month billed annually.
  - reasoning: Pricing: Free 'up to 15 assets with limited history', no MTD/YTD; Basic '$30 / month' and Pro '$55 / month' billed annually. Forward trade signals come only with paid plans. The TAA page lists 'Moving Averages - Single Asset' with lookbacks in months (1-36 or custom) and moves to cash or a chosen out-of-market asset. The research omitted a useful point: PV offers 'Trade at end of month price' or 'Trade at next close price', which lets you test look-ahead sensitivity. No transaction-cost input was found. The free tier's 'limited history' was not quantified, and it may be too short to cover 1929, 1973-74 or 2000-02, which weakens PV as a cross-check.
- **[c8] NEEDS_QUALIFICATION** bt 1.2.3 (MIT, 2026-09-12) provides RunMonthly, SelectWhere, WeighTarget, CapitalFlow and commission support, sufficient for monthly contributions + 10-month SMA switch with costs on Py3.11.
  - reasoning: PyPI: bt 1.2.3, uploaded 2026-09-12T00:45, MIT, requires_python >=3.9. Earlier releases: 1.2.0 on 2026-04-25, and 1.2.1/1.2.2 on 2026-09-11. algos.py on master contains RunMonthly (line 232), SelectWhere (721), WeighTarget (1119), CapitalFlow (1719) and Rebalance. backtest.py accepts a commissions or cost_model. Caveats a quant would insist on: (1) CapitalFlow 'will affect the capital ... without affecting returns' and the capital 'will remain in the strategy until a re-allocation'. Reported returns are therefore time-weighted, not the investor's money-weighted return on contributions, and new cash sits uninvested until the next Rebalance. (2) RunMonthly defaults to the first day of the new month unless run_on_end_of_period=True. SelectWhere on an SMA frame computed from the same bar's close executes at that close, which is look-ahead. The signal must be shifted one bar. (3) bt takes prices you supply. With adjusted closes the SMA is on total return, not Faber's price SMA. 'Sufficient' is true only with these handled correctly.
  - corrected: bt 1.2.3 (MIT, 2026-09-12, Py>=3.9) has the needed building blocks, but correctness depends on details. The signal must be lagged to avoid same-close look-ahead. Choose run_on_end_of_period deliberately. CapitalFlow reports time-weighted returns and leaves cash idle until the next rebalance, so money-weighted P&L must be computed separately.
- **[c9] CONFIRMED** vectorbt 1.1.1 (2026-09-26) Apache 2.0 + Commons Clause forbidding selling a product/service deriving substantially from it; requires Python 3.11-3.14.
  - reasoning: PyPI: 1.1.1, uploaded 2026-09-26T06:17, requires_python '<3.15,>=3.11'. The PyPI license field is empty, but LICENSE.md on master reads 'Commons Clause License Condition v1.0 ... does not grant to you, the right to Sell the Software', and defines Sell as providing 'a product or service whose value derives, entirely or substantially, from the functionality of the Software'. That is irrelevant for personal use; it matters only if the system is ever sold or offered as a service.
- **[c10] CONFIRMED** Lumibot 4.6.2 (GPL-3.0, 2026-09-27), same Strategy for backtest/paper/live across Alpaca, IBKR, Tradier, Schwab, TradingFee; very heavy deps; 4 releases in 3 weeks.
  - reasoning: PyPI: 4.6.2 uploaded 2026-09-27T20:19, GPL-3.0, >=3.10. Releases on PyPI: 4.5.88 (09-01), 4.5.90 (09-04), 4.5.91 (09-06), 4.6.0 (09-24), 4.6.1 (09-26), 4.6.2 (09-27). That is at least 6 releases in September, so churn is understated. trading_fee.py defines TradingFee(flat_fee, percent_fee, maker, taker). requires_dist confirms openai, google-adk, google-genai, litellm, mcp, ccxt, psycopg2-binary, databento, polygon, boto3 and schwab-py. It also includes stealth-browser and proxy tooling (patchright, camoufox, free-proxy) and a Polymarket client (py-clob-client-v2). That makes the supply-chain and attack-surface point stronger than stated. The README recommends Polygon.io via an affiliate link, so the maintainer has a commercial interest. GPL-3.0 applies only on distribution and does not bind personal use.
- **[c11] CONFIRMED** Alpaca fractional/notional from $1 in paper and live; market/limit/stop/stop-limit TIF=Day; alpaca-py 0.44.0 Apache-2.0 2026-08-11; pylivetrader last release 2022-04-11.
  - reasoning: The docs say 'can buy as little as $1 worth of shares'; fractional is supported for 'market, limit, stop & stop limit orders with a time in force=Day'; and 'all Alpaca accounts are allowed to trade fractional shares in both live and paper environments'. Not all assets are fractionable: check fractionable=true. Fractional sells are marked long only. Fractional day trades count toward day-trade limits. PyPI confirms alpaca-py 0.44.0 (2026-08-11, Apache-2.0, >=3.10) and pylivetrader 0.7.1 (2022-04-11). Alpaca's country page gives no country list, only 'contact support', so non-US availability remains unconfirmed.
- **[c12] NEEDS_QUALIFICATION** Scalable FREE Broker EUR0/month, savings plans EUR0 from EUR1, EUR0.99 manual trades under EUR250; T212 AutoInvest commission-free from EUR1/GBP1 with 0.15% FX fee incl. pies.
  - reasoning: Scalable is confirmed verbatim: '€0.00 / month', savings plan '€0', 'from €1 savings amount', '€0.99' under €250, PRIME+ '€4.99 / month'. The page is Germany-focused and does not list other countries. T212 only partly checks out. The FX help article confirms an FX fee applies to 'all orders involving securities traded in currencies different from your account's main currency ... applicable to orders placed within Pies', but it states no percentage. The fee page (trading212.com/terms/fees) returned 403, so 0.15% is unverified here. It matches T212's historical rate but could have changed. The €1/£1 AutoInvest minimum also did not appear on the Pies intro page. Other omissions: spreads and execution quality are not zero cost; savings plans cover only eligible ETFs and stocks; and UCITS ETFs typically carry ~0.1-0.2% TER plus about 15% withholding-tax leakage on US dividends, versus 0.03% for VOO.
  - corrected: Scalable FREE: €0/month, savings plans €0 from €1, €0.99 for manual trades under €250 (verified). Trading 212 charges an FX fee on cross-currency orders, including in Pies (verified). The 0.15% rate and the €1/£1 minimum were not verifiable from primary sources on 2026-09-29.
- **[c13] NEEDS_QUALIFICATION** TradingView webhook bridge costs ~$101.60/month: TV Premium $59.95 for webhooks + TradersPost Starter $41.65/mo; ~$1,219/yr, 12.2% of $10k.
  - reasoning: TradersPost is confirmed, but as 'Starter $41.65 per month, billed yearly', i.e. a $499.80 up-front annual commitment. Its free tier is a 7-day trial with automated submission on paper accounts only. TradingView's pricing page shows Premium at $59.95/mo. The fetch did NOT confirm that webhooks require Premium: the tool could not read the comparison checkmarks. The webhook help page mentions only a 2FA requirement. From memory, TradingView webhooks have historically been available on any paid plan (Essential at $12.95/mo and above), not only Premium; this is unverified. If so, the bridge floor is about $12.95 + $41.65 = $54.60/mo, or $655/yr, which is 6.6% of $10k. The conclusion (absurd for a monthly SMA switch) stands either way. The arithmetic ($59.95 + $41.65 = $101.60; x12 = $1,219.20) is correct given its inputs.
  - corrected: A TradingView-plus-TradersPost bridge costs roughly $55-$102/month: TradersPost Starter at $41.65/mo billed yearly, plus a TradingView paid plan that must support webhooks, where the required tier was unverified (possibly Essential at $12.95). That is about $655-$1,219/yr, or 6.6-12.2% of a $10k account, and uneconomic for this strategy in any case.
- **[c14] CONFIRMED** Vanguard Digital Advisor <=$20 per $10k, $100 minimum, US residents only; Schwab Intelligent Portfolios 0%, $5k minimum, 6%-22.5% cash.
  - reasoning: Vanguard verbatim: 'no more than $20 per $10,000 annually', '$15 - $16 ... per year for every $10K in an all-index portfolio', '$100 in assets is required', and 'United States resident, or ... APO/FPO/DPO'. NerdWallet (updated Dec 17 2025): '0% management fee', $5,000 minimum, cash from 6% to nearly 22.5% (average 6-10%), and Premium 'was discontinued in 2026'. The Schwab facts come from a secondary source; schwab.com was not checked. The research's 0.3%/yr cash-drag figure is a rough expected-return opportunity cost, not a fee, and depends on the assumed equity premium.
- **[c15_unlisted_growney] REFUTED** (From the summary table) growney: 0.68% at EUR5k, 0.38% at EUR10k, 0.25% at EUR100k; source 'extraETF growney test 09/2026'.
  - reasoning: The cited extraETF page says costs are €34 at €5,000, €68 at €10,000 and €380 at €100,000. That is 0.68% at €5k, 0.68% at €10k (not 0.38%), and 0.38% at €100k (not 0.25%). The overall range is 0.25-0.68%. The page is dated 'updated March 26, 2025', not 09/2026. The rows in the research's cost table that use 0.38% at $10k for growney are therefore wrong.
  - corrected: Per extraETF (updated 2025-03-26), growney charges €34/yr at €5k (0.68%), €68/yr at €10k (0.68%) and €380/yr at €100k (0.38%), with an overall range of 0.25-0.68%. Minimums are €500 one-off or €25/month.
- **[c16_unlisted_robos_uk] NEEDS_QUALIFICATION** (From the summary) JPM Personal Investing fixed allocation 0.45% up to GBP100k (managed 0.75%), GBP500 min; Moneyfarm 0.45% + 0.25% platform + funds up to 0.21% = ~0.91% at GBP20k.
  - reasoning: The JPM schedule (effective 17 June 2025) confirms fixed allocation at 0.45% for the first £100k and 0.25% above, and managed styles at 0.75% then 0.35%. It does not state the £500 minimum, which remains secondary. The Moneyfarm page confirms 0.45% (£7.50/mo) + 0.25% (£4.17/mo) + 'up to 0.21%' = 'up to 0.91%' at £20k.
  - corrected: JPM PI: 0.45% fixed / 0.75% managed on the first £100k (verified); the £500 minimum is unverified. Moneyfarm: up to 0.91% all-in at £20k (verified).
- **[c17_unlisted_quantconnect_surmount] NEEDS_QUALIFICATION** (From the summary) QuantConnect live ~$34-84/mo; free tier no live trading. Surmount Free/Core $5/Plus $10/Pro $30.
  - reasoning: QuantConnect's tier-features doc confirms the Free tier has 'No live trading access' and Quant Researcher has 'up to 2 live trading nodes'. Neither the official pricing page nor the docs show dollar prices; the pricing page is now a configurator. The $34-84 range rests on conflicting secondary sources and should be marked unverified. Surmount prices are confirmed ($5/$10/$30). The fetch also indicates the Free plan does not enable automated live investing, which the research did not state explicitly and which reinforces its exclusion. Surmount's footer references Quantbase advisory accounts via Alpaca.
  - corrected: QuantConnect requires a paid tier for live trading; current dollar prices are unverified from primary sources. Surmount's Free plan does not automate live trading; paid tiers are $5, $10 and $30/month.
- **[c18_unlisted_data_tools] NEEDS_QUALIFICATION** (From the summary) Ken French monthly Mkt-RF and RF from 1926, updated through Aug 2026, CRSP CIZ; Curvo free, IWDA backfilled from Jan 1979 including fund costs, contributions and brokerage costs, no MA rules; nautilus_trader requires >=3.12; zipline-reloaded 3.1.1 2025-07-19; backtrader last 2023-04-19.
  - reasoning: All of these are confirmed: Ken French data is current through August 2026 and uses the CIZ format from the January 2025 release. Curvo's article is dated 27 July 2026, is free, backfills IWDA from Jan 1979 using index data including fund costs, and supports contributions and brokerage costs. PyPI confirms nautilus_trader 1.231.0 needs '<3.15,>=3.12', zipline-reloaded 3.1.1 dates from 2025-07-19, and backtrader 1.9.78.123 from 2023-04-19. The needed qualification is about what Ken French's data measures. Mkt is the 'value-weight return of all CRSP firms incorporated in the US and listed on the NYSE, AMEX, or NASDAQ', which is not the S&P 500 (SPYSIM). Cross-check tolerances must allow for index differences, as well as the price-SMA vs total-return-SMA difference the research already noted. nautilus_trader also now has 2.0.0 release candidates, so its API is about to change.
- **[c19_unlisted_cost_arithmetic] NEEDS_QUALIFICATION** (From the cost table) Haiku 20k in + 2k out per month = $0.03/mo = $0.36/yr; Opus 5.5 = $0.12/mo = $1.44/yr; IBKR Pro Fixed $1 min capped at 1% => $1 on $100; M1 36%/3.6%; Betterment 60%/6%/0.6%; TV+TP $1,219/yr.
  - reasoning: The LLM arithmetic checks out. Haiku: 20,000 x $1/1e6 = $0.02 plus 2,000 x $5/1e6 = $0.01, so $0.03/mo and $0.36/yr. Opus: $0.08 + $0.04 = $0.12/mo, $1.44/yr. The Batch API halves these. M1 and Betterment arithmetic is correct. IBKR is right for a $100 buy: $1 minimum, 1% cap = $1. However, the cap also means a $10 buy costs $0.10, not $1, so the 1% ceiling applies at every size; the IBKR pages were not re-verified (403). Omitted from the table: (a) Fidelity/Alpaca sell-side regulatory fees ($0.01-0.03 per $1,000 at Fidelity); (b) the ETF bid-ask spread on each switch; (c) taxes on switches, which are likely the largest real cost of the trend overlay at scale; (d) the human-time cost of a manual monthly check. GitHub Actions 'free cron' is also not free of risk. From memory, not verified here: scheduled workflows in public repos are disabled after 60 days of repo inactivity, and cron start times can be delayed. For a once-a-month trade a silently disabled job is a real failure mode.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- Adopting Option 2 as primary is sound for cost, but the research quietly redefines the user's goal. The user asked for a system that 'makes profit'. Option 2 is buy-and-hold beta. Its 'profit' is market return that anyone gets by buying the ETF, and the research itself estimates the system's own excess over buy-and-hold at about 0. A careful consumer-protection lawyer would require the report to state plainly: 'the software adds no expected return; the expected profit comes from equity-market exposure, which can be negative for 10+ years (e.g. US equities 2000-2012 in nominal terms were roughly flat to negative).'
- The cost test '$0 running cost therefore passes at $1, $100, $1k, $10k' compares cost with the equity return, not with the system's incremental return. Properly framed, any running cost > $0 for the overlay or bot is a loss against the null of just buying the ETF. The research says so for fees but still presents Options 1-3 as 'meeting the test'.
- The '$1 real-money test' cannot provide statistical proof of profit. $1 at 5-7%/yr is $0.05-0.07/yr, well below noise and rounding. At most it proves the order plumbing works. Paper trading over months also has no statistical power to distinguish a trend overlay from buy-and-hold (Sharpe differences of about 0.1-0.2 need decades of data). The recommendations should say explicitly that 'proof' comes only from long out-of-sample backtests with costs, and that live or paper runs validate execution only.
- 'Scaling assurance: no capacity constraint ... none of these are software problems' is overconfident as consumer advice. Scaling does not threaten liquidity, but it scales drawdowns in absolute terms: a 50% drawdown is $50k on $100k. Taxes on trend switches, US wash-sale rules, the German Vorabpauschale, UK CGT outside an ISA, and behavioural abandonment after whipsaws can each erase the claimed benefit. The user explicitly asked for assurance that scaling won't stop profits. The honest answer is that no tool can give that assurance.
- Region-specific venue recommendations omit a major regulatory barrier. EU/UK retail investors generally cannot buy US-domiciled ETFs such as VOO or SPY because of PRIIPs KID rules. The 'Elsewhere: IBKR' and US-ticker-based cross-checks (testfol SPYSIM, Portfolio Visualizer, Ken French) therefore do not match the UCITS instrument a European would actually hold. UCITS proxies differ in TER (0.1-0.22%), in index (e.g. MSCI World vs S&P 500) and in dividend withholding. Validation must be done on the instrument actually traded.
- 'UK: Trading 212 ... EU: Scalable/Trading 212 ... Elsewhere: IBKR' is a product recommendation to an inexperienced person without a stated country, suitability check or tax wrapper analysis. A lawyer would insist it be framed as examples, with the ISA/SIPP/Roth/IRA/Depot tax wrapper decided first, because the wrapper dominates the cost table at every capital level.
- Recommending Composer Starter as the 'only free no-code option' for the SMA switch overstates both the $2,500 barrier (it is a recommendation driven by non-fractionable assets; the hard minimum is $50) and exclusivity. Broker conditional-order tools (e.g. thinkorswim study-based conditional orders, unverified here) may provide $0 partial automation. It also understates platform risk: SoFi's release signals migration toward SoFi Plus, and the backtests fill at the daily close while live trades fill intraday.
- Cross-validating against testfol.io and free Portfolio Visualizer as 'independent sources' is weaker than presented. testfol's SPYSIM backfill datasets are not cited and its signal-to-execution timing is undocumented. PV's free tier has 'limited history' (unquantified, possibly too short for meaningful stress periods) and no cost field. Ken French Mkt is total US market, not the S&P 500. 'Agreement within tolerance' across these sources mostly confirms the arithmetic, not that the strategy has an edge. The harness should also run PV's 'Trade at next close' option to test look-ahead sensitivity.
- The bt harness recommendation omits known pitfalls. Same-bar SMA signals executing at that close create look-ahead unless the signal is lagged. CapitalFlow reports time-weighted returns and leaves contributions uninvested until the next rebalance, so contribution P&L needs separate money-weighted computation. Adjusted-close SMAs differ from Faber's price SMA. Without these, the 'validation harness' can produce flattering but wrong numbers.
- 'Free deterministic month-end signal via GitHub Actions free cron' has operational failure modes the research does not address. Scheduled workflows can be delayed and, in public repos, auto-disabled after inactivity (from memory, unverified). Broker API keys stored in CI secrets are also a security concern. For a once-a-month action, a calendar reminder plus a local script may be more reliable.
- Using Lumibot is correctly discouraged, but the reason is understated. Its dependency tree includes LLM SDKs, stealth-browser automation (patchright, camoufox), a free-proxy scraper and a Polymarket client, which is a significant supply-chain surface for a tool that would hold brokerage credentials. 'Pin the exact version' is insufficient mitigation; avoid it entirely for live keys.
- The 'plausible profit 5-7%/yr' benchmark is ambiguous: real vs nominal, and US vs global. Forward-looking estimates from valuation-based models are often lower than historical returns. Profit-vs-cost ratios should be shown under a low-return scenario (e.g. 2-3% real) and a negative-decade scenario, not only 5-7%.
- Recommending Robinhood and eToro to a novice without noting payment for order flow (Robinhood), eToro's CFD-heavy platform, and its standard FX conversion (0.5% claimed but not re-verified; the waiver lapsed March 31 2026) is a consumer-protection gap. eToro's $25 minimum also fails the '$1 test'.
- Betterment and M1 are dismissed as 'failing below $10k', but Betterment's fee is 0.25% (not $60/yr) for anyone depositing $200+/month. The blanket exclusion is overstated for a user contributing that much, although a single-ETF $0 plan still dominates.

## VERIFIER OVERALL

This research is reliable and I verified most of it. Every PyPI fact checked out exactly (bt 1.2.3, vectorbt 1.1.1 with the Commons Clause, Lumibot 4.6.2 GPL, alpaca-py 0.44.0, pylivetrader and backtrader abandoned, nautilus_trader needing Python 3.12 or later). So did the primary-source pricing for M1, Betterment, Composer (plans, $50 minimum, $2,500 recommendation, 1 bp slippage, stale '$40' estimate), testfol.io, Portfolio Visualizer, Scalable, Alpaca fractional trading, TradersPost, Vanguard Digital Advisor, Moneyfarm and J.P. Morgan Personal Investing. The LLM-cost arithmetic is also correct: Haiku at $0.36/yr, Opus at $1.44/yr.

Errors and overstatements the orchestrator should weight down or fix:

1. **growney fees are wrong.** At €10k the fee is 0.68% (€68), not 0.38%. At €100k it is 0.38%, not 0.25%. The source is dated March 2025, not 09/2026.
2. **Two numbers are unverified from primary sources.**
   - Trading 212's 0.15% FX rate: the help article confirms an FX fee but gives no percentage, and the fees page returned 403.
   - TradingView's 'Premium required for webhooks': not verified, and webhooks may be available on cheaper paid plans. The bridge cost could therefore be about $55/month, not $102. The conclusion that it is uneconomic is unchanged.
3. **QuantConnect prices** come from conflicting secondary sources. The official pages show no dollar figures.
4. **'Composer is the only free way to automate the SMA switch' is overstated.** The $2,500 figure is a recommendation, not a requirement. Broker conditional-order tools may also provide free partial automation (unverified).
5. **Missing omissions:**
   - EU/UK retail investors are generally barred from US-domiciled ETFs (PRIIPs). This breaks the US-ticker cross-check plan for non-US users.
   - bt has look-ahead and cash-flow pitfalls: same-bar signals, and CapitalFlow reports time-weighted returns with contributions left idle until the next rebalance.
   - Ken French data measures the whole US market, not the S&P 500.
   - GitHub Actions scheduled jobs may be delayed or disabled (from memory, unverified).
   - Tax is likely the dominant cost of the trend overlay.

The core architectural conclusion is well supported and can be kept: $0 broker recurring plan, custom code limited to a validation harness, no LLM in the monthly loop, no Lumibot. The framing is what needs correcting. The system adds no expected return. Profit is equity beta and can be negative for a decade. $1 or paper trading proves only that orders execute, not that the strategy has an edge. Nothing guarantees that scaling preserves profit, because drawdowns, taxes and behaviour scale with capital. Present the venue recommendations as region-dependent examples, subject to the tax wrapper and the user's country, not as advice.
