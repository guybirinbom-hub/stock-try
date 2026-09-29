# tooling

## SUMMARY

## Bottom line (skeptical read)
For a daily or monthly-rebalanced ETF strategy, the lowest-risk stack on Python 3.11 is:
- a small custom pandas backtester, cross-checked against `bt` or `vectorbt`
- adjusted daily bars from Tiingo (free) or Alpaca (free, SIP history), with yfinance only as a fallback
- the FRED keyless CSV for the risk-free rate
- Alpaca paper trading driven by a once-a-day cron job
- Alpaca live with fractional/notional orders for the "$1" stage

**The key finding: a $1 live account cannot show a profit on Alpaca, whatever the strategy.** Alpaca's own fee schedule (revised 2026-09-17) passes through per-share regulatory fees. Each fee type is summed per account per day and then rounded **up to the nearest cent**. So one small sell costs about $0.03 (SEC + TAF + CAT, each rounded up to $0.01), and each buy day costs $0.01 (CAT). That is 3-4% of a $1 position per round trip. A $1 account proves the plumbing works. It does not prove profit. Profit has to be judged in backtest and paper, with the fee model scaled to the intended capital.

The LLM must not sit in a daily loop at tiny capital either. A single Haiku 4.5 call of about 3k tokens in and 500 out costs about $0.0055. Over 252 trading days that is about $1.39/yr, which is 139% of $1 of capital.

---
## 1. Backtesting libraries (versions checked against the PyPI JSON API on 2026-09-29; install checked with `pip install --dry-run` on Python 3.11.15)

| Library | Latest / date | Py 3.11 | Style | Costs/slippage | Notes |
|---|---|---|---|---|---|
| vectorbt (open source) | 1.1.1, 2026-09-26 | yes (>=3.11,<3.15) | vectorized (numba) | fees, fixed_fees, slippage in Portfolio.from_signals/from_orders | Requires **pandas>=3.0.3, numpy>=2.4.6**. Licence is Apache-2.0 **with Commons Clause** ("fair-code"). PRO is a paid membership ($25/mo, $240/yr, $500 lifetime) that adds limit orders, leverage, parallelisation and more. https://pypi.org/project/vectorbt/ , https://vectorbt.pro/ |
| backtrader | 1.9.78.123, **2023-04-19** | installs, but unmaintained | event-driven | commission schemes, slippage | No release in about 3.5 years. Snyk rates it "Inactive". Matplotlib plotting breaks with newer versions. Avoid for new work. https://pypi.org/project/backtrader/ , https://snyk.io/advisor/python/backtrader |
| backtesting.py | 0.6.6, 2026-07-22 | yes (>=3.9) | event-style, **single instrument** | commission (float, (fixed, relative) or callable), spread | **AGPL-3.0**. Fills at next open by default. Has a `FractionalBacktest` class. Cannot do multi-asset portfolio rebalancing, so it is a poor fit for ETF rotation. https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html |
| zipline-reloaded | 3.1.1, 2025-07-19 | yes (3.10-3.13) | event-driven, Pipeline API | slippage and commission models | Requires pandas<3.0, so it **conflicts with vectorbt 1.x** in the same environment. Needs data-bundle ingestion. Heavy dependencies (bcolz, tables, h5py, alembic). Steep learning curve. https://pypi.org/project/zipline-reloaded/ |
| QuantConnect LEAN | lean CLI 1.0.229, 2026-08-28 | CLI yes | event-driven C# engine with Python algorithms | full brokerage fee and slippage models, corporate-action handling | The free cloud tier gives unlimited backtests but **no live trading**. The Researcher tier is about $60/mo, and live nodes start at about $24/mo (secondary source). Local LEAN needs Docker plus your own or purchased data. https://www.quantconnect.com/pricing/ , https://newyorkcityservers.com/blog/quantconnect-review |
| nautilus_trader | 1.231.0, 2026-08-02 (2.0 RCs) | **no: now >=3.12**. The last cp311 wheel is 1.221.0 (2025-10-26), and pip falls back to it | event-driven, Rust core | detailed fill, fee and latency models | Built for professional, often intraday, work. Overkill here, and stuck on an old version under 3.11. https://pypi.org/project/nautilus_trader/ |
| bt | 1.2.3, 2026-09-12 | yes | tree of Algos (RunMonthly, SelectAll, WeighEqually/WeighInvVol, Rebalance) | `commissions=` callable on Backtest | MIT licence. Designed for exactly this use case (periodic multi-asset rebalancing). Assumes you feed it adjusted prices. https://pmorissette.github.io/bt/ |

**When is a custom pandas backtester the better choice?** For daily or monthly rebalancing across fewer than 20 ETFs, a vectorized loop of about 200-400 lines is sufficient. It needs to:
1. take adjusted closes
2. compute a signal at the close of day t
3. trade at the open or close of day t+1 (strictly shifted to avoid look-ahead)
4. apply turnover × (spread + slippage) plus a *per-order fixed fee* that mimics Alpaca's cent rounding, and at the $1 stage a CAT/TAF/SEC rounding model
5. deduct cash yield from FRED

It is better than any library in these cases:
- you need to model per-day fixed fees accurately (no library models Alpaca's per-day, round-up-to-a-cent aggregation)
- you want fully auditable code the LLM can review
- you want zero dependency risk (backtrader-style abandonment, the pandas 2 vs 3 split)

Validate it by reproducing one strategy in `bt` or `vectorbt` and requiring the equity curves to match within a small tolerance.

## 2. Free historical daily data

| Source | Free limits | Adjusted? | Notes |
|---|---|---|---|
| yfinance 1.7.0 (2026-08-26) | no key. Yahoo throttles by IP | auto_adjust | The PyPI disclaimer says it is "not affiliated... intended for research and educational purposes" and the Yahoo API is "intended for personal use only". Repeated `YFRateLimitError` issues through 2025 (#2289, #2411, #2480, #2567), including at 4-5 requests/day. **This container got HTTP 429.** Not reliable enough for an unattended cron job. https://pypi.org/project/yfinance/ , https://github.com/ranaroussi/yfinance/issues/2411 |
| Alpaca Market Data (Basic, free) | 200 calls/min. Real-time is IEX only. SIP historical allowed if `end` is at least 15 min old | `adjustment=raw/split/dividend/spin-off/all` | Feed default is `sip`. About 7+ years of history (from ~2016-2019; exact start not stated in the docs). Too short to cover 2000-02 or 2008. https://docs.alpaca.markets/docs/about-market-data-api , https://docs.alpaca.markets/reference/stockbars , https://docs.alpaca.markets/us/docs/market-data-faq |
| Tiingo Starter (free) | 50 req/hr, 1,000/day, 500 unique symbols/mo, 1 GB | yes (adjClose, divCash, splitFactor) | 30+ years of history. "Internal Use Only" (personal). Power plan is $30/mo. Container probe: reachable, returns "Please supply a token". https://www.tiingo.com/about/pricing |
| Massive (formerly Polygon.io) Basic | 5 calls/min, **2 years** history, end-of-day | adjusted flag | History is too short for backtesting. Renamed 2025-10-30. https://massive.com/pricing , https://massive.com/blog/polygon-is-now-massive |
| Alpha Vantage free | 25 req/day, 5/min (secondary sources; the official page returned 503/timeouts from here) | DAILY_ADJUSTED exists; historically premium-gated | Too few calls for a universe. https://www.alphavantage.co/premium/ , https://apicostcalc.com/alpha-vantage.html |
| EODHD free | 20 calls/day | adjusted_close included (verified with the demo key) | History depth on the free tier is unclear: the vendor page says 30+ yrs; older info says 1 yr. The demo key only covers sample tickers (AAPL). https://eodhd.com/pricing |
| Stooq | no key | adjusted | The connection is flaky from this container (one 200, then resets). Useful only as a manual cross-check. |
| Nasdaq Data Link | the free WIKI equity prices ended in 2018 | — | Returned 403 from here. Not recommended. |
| FRED | keyless CSV `fredgraph.csv?id=DGS3MO` works from the container (latest 2026-09-25 = 4.24%). The API needs a free key | n/a | Risk-free rate source. https://fred.stlouisfed.org/docs/api/fred/ |

**Survivorship bias for ETF-only strategies.** Classic delisting bias is small if you trade a handful of large, liquid ETFs. The bigger problems are:
- **selection/hindsight bias**: picking today the ETFs you know survived and did well
- **short histories**: inception dates cut backtests short. Tiingo also covers mutual funds, which can serve as longer proxies.

Use total-return (dividend-adjusted) prices, or strategy returns will be understated by about the dividend yield (roughly 1.2-2%/yr for equity ETFs).

## 3. Paper trading
**Alpaca paper** is the only option here that is fully cron-drivable and free:
- "Free and available to all Alpaca users"
- **separate paper keys** and endpoint (paper-api.alpaca.markets)
- "Anyone globally can create an Alpaca Paper Only Account" with an email
- default balance is $100k (configurable at creation); accounts can be deleted and recreated instead of reset
- fractional orders work

Realism caveats, quoted from the docs:
- fills are matched against the NBBO
- random partial fills 10% of the time
- it "does NOT account for" slippage from latency or market impact
- it "does NOT simulate dividends"
- regulatory fees are not modelled

So the paper P&L needs a shadow ledger that adds modelled fees and dividends. https://docs.alpaca.markets/docs/paper-trading

**IBKR paper** is realistic, but it needs a funded live account and TWS or IB Gateway running. Gateway sessions need a manual 2FA re-authentication **every Sunday 01:00 ET**; community tools (IBC, ibeam, ibg-controller) automate around this. That makes it poor for unattended cron use. https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm

Other options:
- **Trading 212** has a public API (beta) with a demo environment (demo.trading212.com/api/v0), for Invest and ISA accounts only. Order-type limits in live mode are unclear. https://docs.trading212.com/api
- **eToro** has a public API with a demo endpoint. https://api-portal.etoro.com/
- **DEGIRO** has no official public API.

## 4. Live execution with tiny capital
**Alpaca stocks/ETFs**
- **Commission**: $0 for retail order flow.
- **Pass-through fees** (fee schedule rev. 2026-09-17):
  - SEC fee is $0.0000206 × value (sells only)
  - FINRA TAF is $0.000195/share (sells only, max $9.79)
  - CAT fee is $0.000003/share (buys and sells)
  - "Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent."
  - Source: https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf
- **Arithmetic at $1**: sell day = SEC $0.01 + TAF $0.01 + CAT $0.01 = $0.03. Buy day = CAT $0.01. A monthly rebalance that includes sells costs about $0.03-0.04 × 12 = $0.36-0.48/yr, which is 36-48% of $1. At $1,000 the same fees are 0.04-0.05%/yr, which is negligible. **The fees are a fixed dollar amount per trading day, so the drag shrinks as capital grows.** This scaling works in the person's favour; market impact is irrelevant below roughly $1M in liquid ETFs.
- The SEC rate went from $0.00/M (through 2026-04-03) to $20.60/M from 2026-04-04. https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- **Fractional orders**: market, limit, stop and stop-limit, **time-in-force DAY only**. Extended/overnight hours are supported. Not every asset is fractionable (check `fractionable=true`). Minimum is **$1 notional for buys**. https://docs.alpaca.markets/docs/fractional-trading , https://alpaca.markets/support/can-we-submit-orders-smaller-than-1-usd-in-notional-value
- **Countries**: Alpaca says it serves many countries. **Canada is excluded**, and the list is otherwise "contact support". Non-US users can fund from $1 (the $30k minimum was lifted). Funding is USD only via wire or Rapyd. Local-currency transfers cost 1.5% (max $40), and outbound international wires cost $35. A bank's own outgoing international wire fee (often $15-50) would wipe out a $1-$100 experiment. https://alpaca.markets/support/is-alpaca-available-outside-the-us , https://alpaca.markets/support/international-use-fund-account
- **API rate limit**: 200 requests/min on the free tier.

**IBKR**
- Pro Fixed costs $0.005/share, **minimum $1.00 per order**, max 1% of trade value. That is up to 1% of a small order: $0.01 on a $1 order, but $1 on $100.
- IBKR Lite is $0, but only for **US and India** residents.
- Fractional shares from about $1 in US stocks. API support for fractional equity orders is disputed (cashQty exists; community reports say fractional equities are not supported via the TWS API).
- Heavy operational burden (Gateway, weekly 2FA).
- https://www.interactivebrokers.com/en/pricing/commissions-stocks.php , https://www.ibkrguides.com/orgportal/trade-in-fractions.htm

**Crypto** (an alternative if the stock broker is unavailable in the person's country; it trades 24/7 and its fee drag is larger)
- **Alpaca crypto**: 0.15% maker / 0.25% taker at the lowest tier. TIF gtc/ioc. Per-pair `min_order_size`. Available in select jurisdictions. https://docs.alpaca.markets/docs/crypto-fees
- **Coinbase Advanced**: the live API reports BTC-USD `quote_min_size = $1`. Base-tier fees are high: US 0.50%/0.90% after a 2026-09-16 cut per secondary sources; historically 0.60%/1.20%.
- **Kraken**: live API reports XBTUSD `ordermin 0.00005 BTC` (about $4.20 at $84k) and `costmin $0.5`. Base tier 0.25%/0.40%. **So $1 of BTC is not possible on Kraken.**
- **Binance spot testnet** returned **HTTP 451** from this (US-based) container, which means it is geo-blocked.

## 5. Scheduling
**GitHub Actions**
- Free for public repos. Private repos on the Free plan get 2,000 min/mo. Linux 1-core runners cost $0.002/min. https://docs.github.com/en/billing/concepts/product-billing/github-actions
- The docs warn that cron "can be delayed during periods of high loads... including the start of every hour". Public-repo schedules are **disabled after 60 days without repo activity**. https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows
- 2026 community reports describe 8-14 h delays and dropped days. https://github.com/orgs/community/discussions/201738

Mitigations:
- schedule at an odd minute (for example :23)
- make the job idempotent, so that any run between the close and the next open submits DAY orders for the next session
- add a watchdog, or an external trigger (workflow_dispatch from a free cron service)
- keep API keys in GitHub Secrets. On a public repo, never log positions or keys.

**Alternatives**:
- Oracle Cloud Always Free Ampere VM ($0; its page returned 403, so this is not verified here; idle-reclaim policy applies)
- a $4-6/mo VPS
- a Raspberry Pi (about $0.5-1/mo in electricity)

A once-daily job running under 1 minute is effectively $0 on GitHub Actions.

## 6. LLM layer
- Package: `anthropic` 1.9.0 (2026-09-28, Python >=3.10). Batches are available via `client.messages.batches.create`. https://pypi.org/project/anthropic/
- **Batch API**: 50% off. Most batches finish within 1 h; the hard limit is 24 h. https://platform.claude.com/docs/en/build-with-claude/batch-processing
- **Prompt caching**:
  - minimum cacheable prefix is 4,096 tokens on Haiku 4.5 and 512 on Sonnet 5.5 / Opus 5.5
  - 5-minute TTL writes cost 1.25×; 1-hour TTL writes cost 2×; reads cost 0.1× (0.05× on Opus 5.5)
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - **A once-per-day single call gets no benefit from caching.** Neither TTL survives 24 h, so every day pays for a cache write. (The docs' own worked example claiming a "1h cache daily hit" is wrong on this point.) Caching only helps when several calls in the same run share a prefix.

Per-call cost at 3,000 input + 500 output tokens:
- Haiku 4.5: 3,000×$1/M + 500×$5/M = $0.0055. ×252 days = $1.39/yr; about $0.69/yr batched
- Sonnet 5.5: $0.011/call → $2.77/yr
- Opus 5.5: $0.022/call → $5.54/yr

Breakeven comparison: at $1,000 capital with an optimistic 3%/yr edge over buy-and-hold ($30), a daily Haiku call (1.4/30 ≈ 5% of the edge) is tolerable. At $100 it eats about 46% of the edge. At $1 it cannot pay for itself.

**Recommended design**: the trading rule is deterministic Python. The LLM is used in development, and at most for a weekly or monthly batched sanity-review of the signals and orders (about $0.07/yr on Haiku).

## Recommended minimal stack
**(i) Backtesting**
- Packages: `pandas`, `numpy`, `requests`, `tiingo` or plain REST, `alpaca-py` 0.44.0, `pandas_market_calendars` 5.4.0 or `exchange_calendars`, `matplotlib`. Optionally `bt` 1.2.3 as an independent cross-check.
- Use a custom backtester with a strict t+1 execution shift, a spread/slippage assumption (for example 2-5 bps per side for large ETFs), and Alpaca's per-day, round-up-to-a-cent fee model.
- Data: Tiingo adjClose (30+ yrs) as the primary source, Alpaca SIP daily bars with `adjustment=all` as the cross-check, and FRED DGS3MO keyless as the risk-free rate.
- Put vectorbt (pandas 3) and zipline (pandas<3) in separate environments if both are ever used.

**(ii) Paper trading**
- An Alpaca paper account (email only, works globally) with paper API keys.
- A GitHub Actions cron job at an odd minute after the US close, placing notional DAY market orders for the next open.
- A shadow ledger that adds modelled fees and dividends. Compare against the backtest's expected fills to measure tracking error.

**(iii) $1 live**
- An Alpaca live brokerage account (KYC; availability depends on country; not available in Canada), funded with USD.
- Run the exact same code with live keys and notional orders of at least $1.
- **Treat $1 live as a plumbing and reconciliation test only.** Expect about $0.03-0.04 of fees per rebalance with sells.
- The first capital level where fees stop dominating is about $100-$500: $0.04 × 12 rebalances = $0.48/yr, which is 0.1-0.5%.
- Keep the LLM out of the daily loop.

**Sign-ups needed**:
- Alpaca (paper keys now; live account after KYC)
- Tiingo (free token)
- GitHub (repo plus Secrets)
- Anthropic API key (only if the monthly LLM review is used)
- FRED API key is optional (the keyless CSV works)

## CLAIMS

- **[C1] (high)** Alpaca passes through SEC ($0.0000206 x value, sells), FINRA TAF ($0.000195/share, sells, max $9.79) and CAT ($0.000003/share, buys and sells) fees. Each fee type is aggregated per account per day and then rounded up to the nearest $0.01, so a tiny sell day costs about $0.03 and a tiny buy day about $0.01.
  - evidence: Text extracted from Alpaca's Brokerage Fee Schedule PDF, 'Revised on September 17, 2026': 'Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent ($0.01).' Arithmetic: a $1 sell gives SEC $0.00002, TAF about $0.0000003 and CAT about $0.000000005, and each is rounded up to $0.01.
  - sources: https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf, https://docs.alpaca.markets/us/docs/regulatory-fees
- **[C2] (high)** Alpaca paper trading is free, uses separate API keys, is open to anyone globally with an email, fills against the NBBO with random partial fills 10% of the time, and does NOT simulate slippage, market impact, dividends or regulatory fees.
  - evidence: Alpaca paper-trading docs, quoted verbatim via WebFetch.
  - sources: https://docs.alpaca.markets/docs/paper-trading
- **[C3] (high)** Alpaca fractional orders support market, limit, stop and stop-limit orders with time_in_force=DAY only; not all assets are fractionable; buy orders need a minimum notional of $1.
  - evidence: Fractional trading docs quote; support article titled 'can we submit orders smaller than 1 USD in notional value'.
  - sources: https://docs.alpaca.markets/docs/fractional-trading, https://alpaca.markets/support/can-we-submit-orders-smaller-than-1-usd-in-notional-value
- **[C4] (high)** Alpaca's free market-data plan gives real-time data from IEX only and 200 API calls/min; SIP historical bars can be queried if the end time is at least 15 minutes old; bars accept adjustment=raw/split/dividend/spin-off/all; Algo Trader Plus costs $99/mo.
  - evidence: About Market Data API comparison table, market-data FAQ, and stockbars reference.
  - sources: https://docs.alpaca.markets/docs/about-market-data-api, https://docs.alpaca.markets/us/docs/market-data-faq, https://docs.alpaca.markets/reference/stockbars
- **[C5] (high)** backtrader's last PyPI release was 1.9.78.123 on 2023-04-19 (unmaintained). nautilus_trader now requires Python >=3.12 (the last cp311 wheel is 1.221.0 from 2025-10-26). vectorbt 1.1.1 (2026-09-26) requires pandas>=3, while zipline-reloaded 3.1.1 requires pandas<3.
  - evidence: PyPI JSON API queried 2026-09-29, plus `pip install --dry-run` on Python 3.11.15, which resolved nautilus_trader-1.221.0, pandas-3.0.6 for vectorbt and pandas-2.3.3 for zipline-reloaded.
  - sources: https://pypi.org/pypi/backtrader/json, https://pypi.org/pypi/nautilus_trader/json, https://pypi.org/pypi/vectorbt/json, https://pypi.org/pypi/zipline-reloaded/json
- **[C6] (high)** backtesting.py is AGPL-3.0 and single-instrument only, so it cannot backtest multi-ETF portfolio rebalancing. bt (MIT, 1.2.3, 2026-09-12) is built for periodic multi-asset rebalancing via Algo stacks.
  - evidence: backtesting.py API docs show a single-instrument Backtest(data, strategy, commission, spread...); PyPI licence metadata; bt docs show RunMonthly/SelectAll/WeighEqually/Rebalance.
  - sources: https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html, https://pmorissette.github.io/bt/, https://pypi.org/pypi/backtesting/json
- **[C7] (high)** The Tiingo free Starter tier allows 50 requests/hour, 1,000/day and 500 unique symbols/month, with 30+ years of EOD history, for internal/personal use only. The Massive (ex-Polygon) free tier offers only 2 years of history at 5 calls/min.
  - evidence: Tiingo pricing page and Massive pricing page, quoted via WebFetch.
  - sources: https://www.tiingo.com/about/pricing, https://massive.com/pricing, https://massive.com/blog/polygon-is-now-massive
- **[C8] (high)** yfinance is unofficial, meant for research and personal use, and has been repeatedly rate-limited (YFRateLimitError) through 2025, sometimes at 4-5 requests/day. The Yahoo chart endpoint returned HTTP 429 from this container, so it is unsuitable as the primary source for an unattended job.
  - evidence: PyPI disclaimer; multiple GitHub issues; container curl returned 429.
  - sources: https://pypi.org/project/yfinance/, https://github.com/ranaroussi/yfinance/issues/2411, https://github.com/ranaroussi/yfinance/issues/2289
- **[C9] (high)** GitHub Actions is free for public repos on standard runners (2,000 min/mo on private repos with GitHub Free). Scheduled workflows can be delayed at high load, especially at the top of the hour, and are auto-disabled in public repos after 60 days without activity. Community reports in 2026 describe multi-hour delays and dropped runs.
  - evidence: GitHub billing and events docs quoted; community discussion #201738.
  - sources: https://docs.github.com/en/billing/concepts/product-billing/github-actions, https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows, https://github.com/orgs/community/discussions/201738
- **[C10] (medium)** IBKR Pro Fixed charges $0.005/share with a $1.00 minimum per order (capped at 1% of trade value); IBKR Lite is available only to US and India residents; IB Gateway requires manual re-authentication every Sunday at 01:00 ET, which makes unattended automation harder than with Alpaca.
  - evidence: IBKR commission page (via search summary; direct fetch returned 403) and the IBKR auto-restart documentation quote.
  - sources: https://www.interactivebrokers.com/en/pricing/commissions-stocks.php, https://www.interactivebrokers.com/en/trading/why-ibkr-lite.php, https://www.ibkrguides.com/traderworkstation/auto-restart-considerations.htm
- **[C11] (medium)** Non-US residents can open Alpaca accounts and fund them from $1, but Canada is not supported and deposits must be in USD. Local-currency transfers cost 1.5% (max $40) and outbound international wires cost $35, so funding costs can exceed a tiny test balance.
  - evidence: Alpaca support pages (Oct 2025) and the fee schedule PDF (Local Currency Transfers 1.5%, max $40; International Wire outbound $35).
  - sources: https://alpaca.markets/support/is-alpaca-available-outside-the-us, https://alpaca.markets/support/international-use-fund-account, https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf
- **[C12] (high)** The prompt-caching minimum prefix is 4,096 tokens on Haiku 4.5 and 512 on Sonnet 5.5 / Opus 5.5. Cache writes cost 1.25x (5 min) or 2x (1 h) and reads 0.1x. Since neither TTL survives 24 h, a once-daily single call gets no caching benefit. The Batch API gives 50% off, with most batches done within 1 h and a 24 h limit.
  - evidence: Anthropic prompt-caching and batch-processing docs; TTL arithmetic.
  - sources: https://platform.claude.com/docs/en/build-with-claude/prompt-caching, https://platform.claude.com/docs/en/build-with-claude/batch-processing
- **[C13] (high)** The minimum crypto order on Kraken XBTUSD is 0.00005 BTC (about $4.20 at $84k; costmin $0.5), so a $1 BTC order is impossible there. Coinbase BTC-USD has quote_min_size $1. The Binance spot testnet returned HTTP 451 (geo-blocked) from this US-based container.
  - evidence: Live public API calls from the container: api.kraken.com AssetPairs, api.coinbase.com products/BTC-USD, testnet.binance.vision/api/v3/time.
  - sources: https://api.kraken.com/0/public/AssetPairs?pair=XBTUSD, https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD, https://testnet.binance.vision/api/v3/time
- **[C14] (high)** The SEC Section 31 fee rate is $20.60 per million from 2026-04-04 (after $0.00/M through 2026-04-03).
  - evidence: SEC fee rate advisory and FINRA information notice, matching Alpaca's $0.0000206 x trade value.
  - sources: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2, https://www.finra.org/rules-guidance/notices/information-notice-20260317

## RECOMMENDATIONS

- Build a custom pandas/numpy daily backtester (about 300 lines). It should use strict t+1 execution, dividend-adjusted closes, a per-side spread/slippage assumption, and an explicit Alpaca fee model: per-day, per-fee-type totals rounded up to the nearest cent. Parameterise it by starting capital so the fee drag at $1, $100, $1,000 and $10,000 is visible. Cross-validate one strategy against bt 1.2.3.
- Use Tiingo's free token (30+ yrs adjClose) as the primary backtest data source and Alpaca SIP daily bars with adjustment=all (end at least 15 min old) as the independent cross-check and the live-signal source. Get the risk-free rate from FRED's keyless fredgraph.csv (DGS3MO). Use yfinance only as a manual fallback and cache everything to local parquet/CSV.
- Do not use backtrader (unmaintained since 2023-04), backtesting.py (single-asset, AGPL), nautilus_trader (needs Python 3.12+), zipline-reloaded (heavy, pandas<3) or QuantConnect live (about $60+/mo) for this project.
- Paper-trade on Alpaca: sign up with email (works globally), generate paper keys, and run a GitHub Actions cron at an odd minute (for example 21:23 UTC) that places notional DAY orders for the next open. Make the job idempotent and alert on a missed day. Keep a shadow ledger that adds the dividends and regulatory fees Alpaca paper does not simulate.
- Treat the $1 live stage purely as an execution and reconciliation test. Expect about $0.03 per sell day and $0.01 per buy day in regulatory fees (3-4% of $1 per round trip). Judge profitability only from backtest plus paper results with fees modelled at the target capital. Fixed per-day fees fall as a percentage as capital grows, so scaling from $100 to $10k improves the net result for liquid ETFs.
- Before opening a live account, the person must confirm their country is supported by Alpaca (Canada is not) and price the cost of sending USD from their bank: an international wire can cost $15-50 plus Alpaca's 1.5% local-currency conversion fee (max $40). If Alpaca is unavailable, evaluate IBKR (a $1 minimum per order makes sub-$100 trades uneconomic) or the Trading 212 / eToro public APIs with their demo modes.
- Keep the LLM out of the daily trading loop. Encode the strategy as deterministic Python. At most, run one batched Haiku 4.5 review per week or month (about $0.003 per call with batching). Budget LLM running cost at under 10% of the expected annual edge in dollars. Do not rely on prompt caching for a once-daily call.
- Pin exact versions in requirements.txt (pandas, numpy, alpaca-py==0.44.0, anthropic==1.9.0, pandas_market_calendars==5.4.0, bt==1.2.3), keep all keys in GitHub Secrets, use a private repo (2,000 free minutes/mo is ample) or a public repo with no position logging.

## OPEN QUESTIONS

- What is the person's country of residence? It decides whether Alpaca live (or Alpaca crypto) is available at all, and what it costs to fund a USD account.
- How far back does Alpaca's free SIP daily history go (2016 vs 2019)? The docs do not state a start date; confirm with a keyed request.
- How deep is EODHD's free-tier history (the vendor page says 30+ years; other sources say 1 year)? Also, the exact Alpha Vantage free limits and whether TIME_SERIES_DAILY_ADJUSTED is premium: the official pages returned 503 or timed out from this container.
- Does the IBKR TWS API accept fractional equity orders via cashQty for retail accounts in 2026? Sources conflict and IBKR pages returned 403.
- Trading 212 public API: which order types and fractional/value orders work in live (not demo) mode, and what are the rate limits? The docs pages did not render.
- What is the Alpaca crypto per-pair minimum order size for BTC/USD (the docs example shows 0.0001) and which non-US jurisdictions can trade crypto? This needs a keyed /v2/assets query.
- Are the current Coinbase Advanced base-tier fees (reported 0.50%/0.90% US after 2026-09-16) confirmed by a primary source? The Coinbase blog returned 403.
- How reliable is GitHub Actions cron for this specific repo? Measure actual trigger delay over the first 2-4 weeks of paper trading before depending on it.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** Alpaca passes through SEC ($0.0000206 x value, sells), TAF ($0.000195/share, sells, max $9.79), CAT ($0.000003/share, buys+sells); each fee type aggregated per account per day then rounded up to $0.01, so a tiny sell day costs ~$0.03 and a tiny buy day ~$0.01.
  - reasoning: I downloaded the PDF (HTTP 200) and extracted its text. It says 'Revised on September 17, 2026'. It lists 'SEC Transaction Fee When sells only $0.0000206 * Trade Value', 'TAF When sells only $0.000195 per share * Max of $9.79 per trade' and 'CAT When buys and sells $0.000003 per executed equivalent share'. It also says: 'Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent $0.01.' The arithmetic holds: a sell day costs 3 x $0.01 = $0.03, a buy-only day costs $0.01 (CAT), and a round trip on $1 costs about 4%. Caveat: the older docs page docs.alpaca.markets/us/docs/regulatory-fees says 'We round up total fees... If the total fee is calculated as 0.00083, it will be rounded up to 0.01'. That wording is ambiguous: rounding the combined total would make a sell day $0.01, not $0.03. The PDF is newer and explicit, so it governs, but the $1 live test should confirm this from the account's FEE activity entries. Minor overstatement in the summary: 'the fees are a fixed dollar amount per trading day' is only true at tiny size. The SEC fee is ad valorem and TAF is per share, so at $10k of sells the SEC fee is about $0.21.
- **[C2] CONFIRMED** Alpaca paper is free, separate keys, open globally with email, NBBO fills, random partial fills 10% of the time, does not simulate slippage/impact/dividends/regulatory fees.
  - reasoning: The docs quote: 'Anyone globally can create an Alpaca Paper Only Account! All you need to do is sign up with your email address.' Default balance is $100k, fills match 'against... NBBO', and orders 'receive partial fills for a random size 10% of the time'. The docs list what is not simulated: market impact, information leakage, slippage from latency, queue position, price improvement, regulatory fees and dividends. Two limitations the research omitted: 'Order quantities aren't validated against actual available liquidity', and the balance cannot be changed after creation without resetting. The research should explicitly recommend creating the paper account at the intended real capital (for example $100-$1,000), not $100k, so the $1 minimum notional and rounding effects show up.
- **[C3] CONFIRMED** Fractional orders: market, limit, stop, stop-limit, TIF=DAY only; not all assets fractionable; $1 minimum notional for buys.
  - reasoning: The docs say 'Market, limit, stop & stop limit orders with a time in force=Day', require checking fractionable=true, and support extended and overnight sessions. The support article (April 2026) says 'we enforce a minimum 1 USD notional amount for Buy entry orders.' The research omitted two consequences. (a) Because only DAY is allowed, fractional orders cannot use opg/cls (auction) TIF, so the fill will not be the official open or close print a backtest usually assumes. (b) The docs say fractional dividends are paid pro rata 'rounded to the nearest penny'. A $1 SPY position earns roughly $0.003 per quarter, which rounds to $0.00, so the live $1 account gets no dividends at all.
- **[C4] CONFIRMED** Free Alpaca data: IEX real-time, 200 calls/min, SIP historical if end >=15 min old, adjustment=raw/split/dividend/spin-off/all, Algo Trader Plus $99/mo.
  - reasoning: The comparison table shows Basic is 'Free' with '200 / min' and IEX real-time, and Algo Trader Plus is '$99 / month'. The FAQ says: 'the end parameter must be at least 15 minutes old to query SIP data without a subscription.' The stockbars reference lists the adjustment values raw/split/dividend/spin-off/all (comma-combinable) and feed default 'sip'. Correction to the summary: the About Market Data page states historical coverage 'Since 2016' for both plans, so the summary's 'exact start not stated... ~2016-2019' is wrong. The conclusion is unchanged: the history is too short for 2000-02 or 2008.
- **[C5] CONFIRMED** backtrader last release 1.9.78.123 on 2023-04-19; nautilus_trader requires >=3.12, last cp311 wheel 1.221.0 (2025-10-26); vectorbt 1.1.1 requires pandas>=3; zipline-reloaded 3.1.1 requires pandas<3.
  - reasoning: PyPI JSON queried today gives: backtrader 1.9.78.123, uploaded 2023-04-19. nautilus_trader 1.231.0 has requires_python '<3.15,>=3.12', and its last release with a cp311 wheel is 1.221.0 (2025-10-26). vectorbt 1.1.1 (2026-09-26) requires 'numpy>=2.4.6', 'pandas<4.0,>=3.0.3' and python >=3.11. zipline-reloaded 3.1.1 (2025-07-19) requires 'pandas<3.0'. The vectorbt LICENSE on GitHub is 'Apache 2.0 with Commons Clause', as the summary says. A pip dry-run on Python 3.11.15 resolves bt 1.2.3 together with vectorbt 1.1.1 on pandas 3.0.6, so bt and vectorbt can share an environment. Note that bt pulls in ffn, which pulls in yfinance.
- **[C6] CONFIRMED** backtesting.py is AGPL-3.0 and single-instrument only; bt (MIT, 1.2.3, 2026-09-12) is built for periodic multi-asset rebalancing.
  - reasoning: PyPI licence metadata: backtesting 0.6.6 is AGPL-3.0, and bt 1.2.3 (2026-09-12) is MIT. The backtesting.py Backtest defaults are commission=0, spread=0 and trade_on_close=False, which means next-bar open fills. Nuance: backtesting.lib now has MultiBacktest ('Run supplied Strategy on several instruments, in parallel'). That runs the strategy separately on each instrument; it is not a shared-cash portfolio, so the claim that it cannot do portfolio rebalancing still holds. bt's Algo stack (RunMonthly/SelectAll/Weigh*/Rebalance) is designed for exactly this case.
- **[C7] CONFIRMED** Tiingo free: 50 req/hr, 1,000/day, 500 symbols/mo, 30+ yrs, internal use only; Massive free: 2 yrs history, 5 calls/min.
  - reasoning: The Tiingo pricing page quotes '50', '1000', '500', '1 GB', '30+ Years' and 'Internal Use Only', with Power at '$30/month'. The Massive page quotes '5 API Calls / Minute', '2 Years Historical Data' and 'End of Day Data'. Its cheapest paid plan is Stocks Starter at $29/mo with 5 years of history. The rename post is dated October 30, 2025, and it says api.polygon.io keys and endpoints keep working. Tiingo's actual adjustment methodology was not checked against Alpaca's adjustment=all. Expect small differences in the dividend-adjustment factor, so any cross-check needs a tolerance.
- **[C8] NEEDS_QUALIFICATION** yfinance is unofficial, for research/personal use, repeatedly rate-limited through 2025 sometimes at 4-5 requests/day; container got 429; unsuitable as primary unattended source.
  - reasoning: The PyPI disclaimer is quoted correctly. Issue #2411 exists, but it contains no report of limits at '4-5 requests/day'. That figure may come from another issue, but it was not verified here. A 429 from a datacenter container does not show how yfinance behaves from a home IP. The recommendation still stands, especially because GitHub-hosted runners are also datacenter IPs.
  - corrected: yfinance is unofficial. PyPI says it is 'not affiliated, endorsed, or vetted by Yahoo... intended for research and educational purposes' and that 'the Yahoo! finance API is intended for personal use only'. YFRateLimitError issues were widespread in 2025, for example #2411 (opened 2025-04-23, closed as not planned). Throttling is IP-dependent, and datacenter or cloud IPs (this container, GitHub Actions runners) are hit much harder than residential IPs. It is a poor primary source for an unattended cloud cron job.
- **[C9] NEEDS_QUALIFICATION** GitHub Actions free for public repos, 2,000 min/mo private on Free; schedule delays at high load especially top of hour; public-repo schedules disabled after 60 days inactivity; 2026 community reports of multi-hour delays and dropped runs.
  - reasoning: The docs and billing pages match the claim. The community thread contradicts the odd-minute mitigation that the research recommends. With delays of up to 14 h, a job at 21:23 UTC can land around 11:23 UTC the next day. That is still before the US open, but only just, and a dropped day means a missed rebalance. Idempotency is essential so that a late or duplicate run cannot double-submit orders.
  - corrected: Confirmed: standard runners are free on public repos; GitHub Free includes 2,000 private-repo minutes per month; Linux 1-core costs $0.002/min; public-repo schedules are disabled after 60 days without activity; and the docs say 'The schedule event can be delayed during periods of high loads' and that queued jobs may be dropped. However, the research's own cited 2026 report (discussion #201738, July 13, 2026) says that moving the cron from :00 to :07 'produced no measurable improvement'. Runs stayed clustered 8-14 h late, and there were whole missing days. So scheduling at an odd minute is not a reliable mitigation. External triggering (workflow_dispatch from another scheduler) or a VPS/Pi cron is the actual fix.
- **[C10] NEEDS_QUALIFICATION** IBKR Pro Fixed $0.005/share, $1 min, 1% max; IBKR Lite only US and India; IB Gateway needs manual re-auth every Sunday 01:00 ET.
  - reasoning: The IBKR commission pages returned 403 to me as well, so the per-share and minimum figures rest on secondary sources and long-standing knowledge. The Lite country list is contested. The cited re-auth page covers TWS only.
  - corrected: IBKR Pro Fixed is $0.005/share, with a $1.00 minimum and a cap of 1% of trade value. IBKR Pro Tiered, which the research omits, has a $0.35 minimum plus pass-through fees. On any order under about $100, the 1% cap binds on both plans, so the effective commission is about 1% per side, not a flat $1. IBKR Lite eligibility conflicts across sources: the research says US and India; a search summary says US and Singapore, and IBKR's Singapore site hosts a why-ibkr-lite page; a secondary blog says US only. Treat Lite as mainly US-only and verify for the person's country. The weekly re-authentication text ('This security process occurs each Sunday at 1:00 am ET', 'manual authentication once a week') comes from a TWS auto-restart page that does not explicitly mention IB Gateway. Community practice says Gateway behaves the same way, but the cited source does not say so.
- **[C11] NEEDS_QUALIFICATION** Non-US residents can open Alpaca accounts funded from $1, Canada excluded, USD-only deposits; local-currency transfers 1.5% (max $40), outbound international wires $35, so funding can exceed a tiny balance.
  - reasoning: The fee PDF lines are verified verbatim. The research presents the outbound wire fee as a funding cost and adds the conversion fee on top of a wire in recommendation 6, which misreads the schedule. The country list is not published officially.
  - corrected: The support article (October 2025) says Alpaca lifted the $30k minimum for non-US users ('fund their accounts with as little as $1'). The official 'Countries Alpaca is available' page (February 2026) now lists no countries and just says 'contact support'. Canada's exclusion appears in Alpaca search snippets and forum threads, but not on that page. Deposits must be in USD, by wire or via Rapyd (funding article dated November 2022). The fee PDF's '$35 International Wire Transfers (Outbound)' is a WITHDRAWAL fee. The 1.5% (max $40) applies to Local Currency Transfers in and out, which is an alternative to a USD wire and is not charged on top of one. The correct framing: funding a small test costs the sender bank's wire fee OR about 1.5% FX, and getting money back costs $35 by international wire (or 1.5% local-currency). So a $1-$100 live test is effectively unrecoverable for non-US users.
- **[C12] NEEDS_QUALIFICATION** Caching minimum 4,096 tokens Haiku 4.5 / 512 Sonnet 5.5 & Opus 5.5; writes 1.25x/2x, reads 0.1x; daily single call gets no caching benefit (docs' '1h cache daily hit' example wrong); Batch 50% off, most <1h, 24h limit.
  - reasoning: I downloaded prompt-caching.md (159 KB) and grepped for daily/every day/each day. The only hits are about RAG context that 'changes daily'. There is no worked example claiming daily cache hits. All other numbers check out. Arithmetic: batched Haiku call = 3,000 x $0.50/M + 500 x $2.50/M = $0.00275; x 252 = $0.69/yr; x 52 = $0.14/yr; x 12 = $0.033/yr.
  - corrected: Minimums: 4,096 tokens for Haiku 4.5 and 512 for Sonnet 5.5 and Opus 5.5. Writes cost 1.25x (5 min) or 2x (1 h). Reads cost 0.1x, except Opus 5.5 at 0.05x and Fable 5.1 at 0.025x. Haiku 4.5 cache hits are $0.10/MTok. Batch: 'most batches completing within 1 hour', and requests expire after 24 h. Batch prices are Haiku 4.5 $0.50/$2.50, Sonnet 5.5 $1/$5 and Opus 5.5 $2/$10, and cache discounts stack with batch discounts on a best-effort basis. A once-daily call cannot benefit from caching. It also cannot be cached at all on Haiku: the 3,000-token prompt is below the 4,096 minimum. The raw prompt-caching markdown contains no '1h cache daily hit' worked example. That parenthetical is almost certainly a WebFetch-summarizer hallucination (my own WebFetch summary invented a similar 'daily use patterns' line), so the research's claim that the docs are wrong is unsupported.
- **[C13] CONFIRMED** Kraken XBTUSD ordermin 0.00005 BTC (~$4.20 at $84k), costmin $0.5; Coinbase BTC-USD quote_min_size $1; Binance spot testnet HTTP 451.
  - reasoning: I re-ran the calls today. Kraken XXBTZUSD returns ordermin 0.00005 and costmin 0.5, with last price 84182.4, so the minimum is 0.00005 x 84182 = $4.21. Coinbase BTC-USD returns quote_min_size '1' at price 84184.66. testnet.binance.vision returns HTTP 451. Not verified: the Coinbase base-tier fee cut to 0.50%/0.90% on 2026-09-16 (secondary sources only) and the Kraken 0.25%/0.40% base tier; the public AssetPairs response returned empty fee arrays.
- **[C14] CONFIRMED** SEC Section 31 fee $20.60 per million from 2026-04-04, after $0.00/M through 2026-04-03.
  - reasoning: The SEC advisory quotes: 'the fee rates applicable to most securities transactions will be set at $20.60 per million dollars' starting April 4, 2026, and 'a rate of $0.00 per million for covered sales occurring on charge dates through April 3, 2026'. This matches Alpaca's $0.0000206 x value. Caveat: Section 31 rates are reset at least annually, typically with the fiscal-year or mid-year adjustment, so the fee model should read the rate as a parameter, not hard-code it.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- Rec 1 (custom ~300-line pandas backtester as primary): a careful quant would reverse the roles. Hand-rolled backtesters, especially LLM-written ones, are exactly where look-ahead, off-by-one shift and adjusted-price bugs hide. Calling it 'fully auditable' is an assertion, not proof. Use bt (MIT, maintained, and co-installable with vectorbt on pandas 3, as verified by dry-run) as the reference engine, and apply the custom code only as a fee/rounding overlay. Require agreement across several strategies and a buy-and-hold benchmark, not a single cross-check, and add unit tests with synthetic data where the correct P&L is known by hand.
- Rec 1/5 (fill assumptions): fractional orders are DAY-only, so there are no opg/cls auction orders. Live fills will not equal the official open or close print the backtest assumes. The backtest needs an explicit open-vs-fill slippage term calibrated from paper and live fills, and 2-5 bps per side is an unvalidated guess.
- Rec 5 ('scaling from $100 to $10k improves the net result'): this answers only the fee-drag half of the person's scaling concern. Fees are also not fixed at larger size: the SEC fee is ad valorem and TAF is per share. The person's real worry, whether an edge survives scaling and time, is about the edge persisting out of sample (overfitting, regime change, crowding), not about fees. Saying market impact is 'irrelevant below ~$1M' holds only for mega-liquid ETFs like SPY/QQQ/IEF, not for thin sector or country ETFs. Paper fills also do not validate liquidity; the Alpaca docs say quantities are not checked against available liquidity.
- The LLM breakeven math assumes an 'optimistic 3%/yr edge over buy-and-hold'. There is no evidence for that number. The honest prior for a retail rules-based ETF strategy is roughly zero or negative excess return after costs and taxes. Framed that way, any recurring LLM cost is unjustified until paper and out-of-sample results show an edge, and the realistic benchmark to beat is a $0-cost buy-and-hold of a broad index ETF.
- Rec 4 (GitHub Actions cron at an odd minute): the thread the research itself cites (#201738, July 2026) reports that moving the cron off :00 did nothing and that runs were 8-14 h late with dropped days. Use an external scheduler (a VPS, Pi, or a free external cron firing workflow_dispatch), make runs idempotent by checking open orders and positions before submitting, alert on any missed run, and use a private repo. Putting live trading keys in a public repo's CI invites leakage through logs.
- Rec 4 (shadow ledger adding dividends): at the $1 live stage, fractional dividends are rounded to the nearest penny, so a $1 position gets about $0.00. Dividend-adjusted backtests will therefore overstate the $1-stage results as well as the fee drag. The paper account should also be created at the intended real capital, not the $100k default.
- Rec 6 (funding costs): it misreads Alpaca's schedule. The $35 international wire is an OUTBOUND (withdrawal) fee, and the 1.5% (max $40) applies to local-currency transfers as an alternative to a USD wire, not on top of one. A consumer-protection lawyer would add that for a non-US resident the $1-$100 test money is effectively unrecoverable, since withdrawal costs $35. The person should be told this plainly before depositing anything.
- Rec 6 / crypto fallback: suggesting crypto (24/7, higher volatility, 0.25-1.2% fee tiers, weaker investor protection) to a novice as a fallback when stock brokers are unavailable is something a consumer-protection lawyer would object to. It changes the risk profile the person asked for, and Alpaca Crypto's non-US availability was not verified.
- Rec 6 (Trading 212 / eToro APIs): neither was verified for live order types, fractional/value orders, rate limits or ToS on automated trading (the docs did not render). They should not be offered as equivalent alternatives without that verification. IBKR's small-order cost should be stated as about 1% per side (the 1% cap binds under about $100), not as 'a $1 minimum', and the Tiered plan ($0.35 minimum) should be mentioned.
- Non-US residency, legal and tax issues omitted across all recommendations: US withholding on dividends (30% default, reduced only by treaty via W-8BEN); home-country capital-gains reporting even on tiny accounts; which investor-protection scheme applies (SIPC covers the US broker, not home-country schemes); and whether the person's local regulator restricts use of a foreign broker. Residency is still unknown, so no live-account recommendation should be final.
- Rec 2 (Alpaca SIP daily bars as the live-signal source): free users must keep end at least 15 minutes old, so the job must run after about 16:15 ET. Adjusted history (adjustment=all) changes retroactively after each dividend, so signals recomputed later will not match what was traded. Snapshot the exact inputs used for each decision so the paper record can be audited.
- Rec 7/8 (Haiku batch review, pinned versions): fine, but the monthly LLM 'sanity review' has no stated decision authority or acceptance test. An LLM review that can veto or modify orders becomes an untested discretionary overlay. It should be advisory only and logged, or backtested itself (which is impossible for LLM judgement without look-ahead contamination from the model's training data).

## VERIFIER OVERALL

Reliability is fairly high for the hard facts. The high-stakes claims hold: the Alpaca fee schedule (per-type, per-day round-up; SEC $20.60/M), the paper-trading limits, the fractional DAY-only rule and $1 minimum, all PyPI versions and dependency conflicts, the Tiingo and Massive limits, the Kraken/Coinbase/Binance probes, and the Claude price arithmetic. I re-verified each against primary sources or live endpoints today. The headline conclusion stands: a $1 Alpaca account cannot demonstrate profit, and the LLM should stay out of the daily loop.

Weight down the following:
1. The prompt-caching 'docs example is wrong' aside is unsupported and probably a summarizer hallucination. The raw docs contain no such example. Separately, a 3k-token Haiku prompt is below the 4,096-token cache minimum anyway.
2. The funding-cost framing misreads the fee schedule. The $35 wire is a withdrawal fee, and the 1.5% applies instead of a wire, not on top of one. Alpaca's official country page is now 'contact support', not a list.
3. The GitHub Actions odd-minute mitigation is contradicted by the thread the research cites.
4. The IBKR details are secondary: Lite eligibility conflicts (US+India, US+Singapore, or US only), the 1% cap binds on small orders, and the re-auth source is TWS-only.
5. Two yfinance points: the '4-5 requests/day' figure was not found in the cited issue, and a 429 from a datacenter IP says nothing about residential use.
6. 'Alpaca history ~2016-2019, not stated' should be 'Since 2016' per the docs.
7. The optimistic 3%/yr edge in the breakeven math has no source and should not anchor any decision.
8. Unverified items: QuantConnect prices (the page shows none), vectorbt PRO's feature list, Alpha Vantage and EODHD limits, and Coinbase fees.

Missing from the research: fractional dividends round to $0 at $1; there are no auction TIFs for fractional orders; and non-US tax and legal issues. The orchestrator should treat the tooling stack (bt plus a fee-overlay backtester, Tiingo plus Alpaca data, Alpaca paper) as sound. Treat the scaling and profitability framing as unproven: fee drag shrinking with capital is not evidence that an edge exists or survives scaling.
