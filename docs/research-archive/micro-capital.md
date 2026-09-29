# micro-capital

## SUMMARY

## Bottom line

1. **A $1 to $100 account cannot make meaningful profit, even with a real edge.** At $1, a heroic 15%/yr excess return is **$0.15/yr**. At Alpaca, the pass-through regulatory fees alone are about **$0.03 to $0.04 per round trip at any size**, because each fee type is rounded **up** to the nearest cent per day. That is **4% of a $1 position per round trip**. Any daily LLM call costs more than the $1 can earn.
2. **The $1 live account is useful only as a smoke test of the plumbing:** auth, order submission, fractional fills, fee posting and reconciliation. The evidence has to come from:
   - backtests with costs;
   - paper trading at realistic notional ($10k to $100k), run in parallel on the same signals.
3. **Scaling is not the risk for liquid-ETF strategies.** SPY and QQQ each trade about $30B+ a day. Market impact stays below 1 bp until orders reach millions of dollars.
4. **The real scaling risks are elsewhere:**
   - (a) the edge was never real (overfitting);
   - (b) the live fills differ from the backtest's assumed prices. Fractional orders are DAY-only, so they cannot use closing-auction (MOC) orders;
   - (c) whole-share rounding and cash drag when moving off fractional shares;
   - (d) fixed LLM, data and hosting costs that are negligible at $100k but fatal at $100.

---

## 1. Fractional shares via API

**Alpaca (official docs):**
- Buy "as little as $1 worth of shares". Fractional orders support "market, limit, stop & stop limit orders with a time_in_force=Day". Extended hours (pre, post and overnight) are also supported.
- Only assets with `fractionable = true` are eligible. There is no fractional short selling: "All fractional sell orders are marked long."
- "Fractional share transactions are executed either on a principal or riskless principal basis." In other words, Alpaca or its counterparty takes the other side of the fractional piece.
- `notional` and `qty` accept up to 9 decimal places. You can sell fractional quantities. [docs.alpaca.markets/docs/fractional-trading](https://docs.alpaca.markets/docs/fractional-trading)
- The orders doc confirms that fractional and notional orders accept **only `day`**. GTC, IOC, FOK, **OPG and CLS are rejected**. "Notional orders ... cannot be replaced": you must cancel and resubmit. [docs.alpaca.markets/docs/orders-at-alpaca](https://docs.alpaca.markets/docs/orders-at-alpaca)
- **Consequence:** a fractional account cannot trade in the opening or closing auction. A backtest that assumes fills at the close cannot be replicated exactly with fractional orders. You must measure the gap.

**Interactive Brokers (IBKR Pro):**
- Fractional trading covers eligible US, Canadian and European stocks and some ETFs. It is enabled via a trading permission, and the API can place any order type TWS supports. [IBKR fractional](https://www.interactivebrokers.com/en/trading/fractional-trading.php)
- Commission, from the IBKR pricing page fetched 2026-09-29: "For each fractional share trade, you will be charged the greater of 1% of the trade value or USD 0.01". Example given: a $5.00 trade costs $0.05 commission.
- IBKR Pro Fixed is $0.005/share, minimum $1.00, maximum 1% of trade value. Tiered is $0.0035/share, minimum $0.35.
- **IBKR Lite ($0 commission) is "US Residents Only".** [IBKR stock commissions](https://www.interactivebrokers.com/en/pricing/commissions-stocks.php)
- So at $1 to $100, IBKR Pro costs about **1% per side, 2% per round trip**. That is fatal for anything but buy-and-hold.

**Other brokers:**
- **Public.com** has an individual API with notional `amount` orders. I could not confirm a minimum or residency rules. [Public API docs](https://public.com/api/docs/resources/order-placement/place-order)
- **Schwab:** fractional shares exist in the app from $1, but I could not confirm Trader API support. [Schwab](https://www.schwab.com/fractional-shares-stock-slices)

## 2. Cost drag at tiny size

### Regulatory fees (primary sources)

- **SEC Section 31 fee:**
  - $27.80 per $1M through 2025-05-13.
  - **$0.00** from 2025-05-14 through 2026-04-03.
  - **$20.60 per $1M from 2026-04-04**, until 60 days after the FY2027 appropriation. [SEC FY2025](https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2), [SEC FY2026](https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2)
- **FINRA TAF (sells only):**
  - $0.000166/share with an $8.30 cap in 2024-25.
  - **$0.000195/share with a $9.79 cap from 2026-01-01.** [Robinhood fee page quoting FINRA](https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood/), [Alpaca fee schedule](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf)
  - **FINRA paused TAF at $0.00 for trades from 2026-10-01 to 2026-12-31** (SR-FINRA-2026-021, filed for immediate effectiveness). It resumes 2027-01-01. [Federal Register](https://www.federalregister.gov/documents/2026/09/23/2026-19392/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-and), [SEC exhibit 5](https://www.sec.gov/files/rules/sro/finra/2026/34-106409-ex5.pdf). It is unverified whether Alpaca passes the pause through.
- **CAT fee:** $0.000003 per share, charged on buys and sells.

### Alpaca's fee schedule (updated 2026-09-17)

- No commission.
- SEC fee: $0.0000206 × trade value, on sells.
- TAF: $0.000195/share, on sells.
- CAT: $0.000003/share, on buys and sells.
- **Critically:** "Fees are calculated on the exact executed quantity, including fractional shares ... Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is **rounded up to the nearest cent**." [Alpaca BrokFeeSched.pdf](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf)
- So any day with a sell costs at least $0.01 SEC + $0.01 TAF + $0.01 CAT = **$0.03**. A buy-only day costs **$0.01** (CAT).
- Other Alpaca fees: 1.5% local-currency transfer fee (max $40), $35 outbound international wire, $25 ACH return.

### Payment for order flow and price improvement

- Alpaca's Q2 2026 Rule 606 report: market makers (Virtu, Citadel, Jane Street, GTS) pay Alpaca for marketable orders at "12% of the spread per share, capped at 5 cents per share". Non-marketable orders earn 20 mils/share.
- In April 2026, S&P 500 market-order payments were about 72 to 95 cents per 100 shares.
- The report itself notes the conflict: PFOF and price improvement come from the same pool of market-maker profit. [Alpaca 606 2026Q2](https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2026Q2.pdf)
- IBKR Pro does not charge a PFOF-funded $0; Lite is US-only.

### Spreads (issuer 30-day median NBBO spreads as of 2026-09-28, plus one-tick arithmetic)

| ETF | Price | Spread | Spread (bp) | Dollar volume/day |
|---|---|---|---|---|
| SPY | 765.61 | 0.00% median, i.e. 1 tick | ~0.13 | 42.7M sh ≈ $32.7B |
| QQQ | 736.53 | 1 tick assumed | ~0.14 | 41.8M ≈ $30.8B |
| IWM | 280.02 | 0.00% median | ~0.36 | 23.1M (30d avg) ≈ $6.5B |
| TLT | 79.32 | 0.01% median | ~1.26 | 38.3M (30d avg) ≈ $3.0B |
| GLD | 377.91 | 0.01% median | ~1.0 | 14.8M ≈ $5.6B |
| VTI | 375.84 | 1 tick assumed | ~0.27 | 3.9M ≈ $1.5B |
| BND | 70.28 | 1 tick assumed | ~1.42 | 11.0M ≈ $0.78B |

- Spread sources: [SSGA SPY](https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy), [iShares IWM](https://www.ishares.com/us/products/239710/ishares-russell-2000-etf), [iShares TLT](https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf), [SSGA GLD](https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld).
- Volumes are one-day volumes for 2026-09-28 from stockanalysis.com ([SPY](https://stockanalysis.com/etf/spy/), [QQQ](https://stockanalysis.com/etf/qqq/), [GLD](https://stockanalysis.com/etf/gld/), [VTI](https://stockanalysis.com/etf/vti/), [BND](https://stockanalysis.com/etf/bnd/)), except the IWM and TLT 30-day averages from iShares.
- Typical large-cap stocks: Nasdaq research puts index-weighted S&P 500 spread cost at "just over 4.5 bp per trade", with the largest names such as AAPL and MSFT around 1 bp. [Nasdaq](https://www.nasdaq.com/articles/sampling-sp-500-minimize-spreads) (secondary snippet; I could not open the page).
- Half-penny ticks for tick-constrained names (amended Rule 612) take effect 2026-11-02, which may narrow the SPY and QQQ spreads further. [SEC 2024-137](https://www.sec.gov/newsroom/press-releases/2024-137)

### All-in round-trip cost, SPY at Alpaca vs IBKR Pro Fixed

My arithmetic: one buy day and one sell day, fees rounded up per day, plus a full 1-tick spread.

| Notional | Alpaca fees (TAF on) | + spread | Alpaca total | During TAF pause | IBKR Pro Fixed commission |
|---|---|---|---|---|---|
| $1 | $0.04 | 0.00013¢ | **4.00%** | 3.0% | $0.02 = 2.0% |
| $10 | $0.04 | ~0 | **0.40%** | 0.30% | $0.20 = 2.0% |
| $100 | $0.04 | $0.0013 | **0.041%** | 0.031% | $2.00 = 2.0% |
| $1,000 | $0.06 | $0.013 | **0.0073%** | 0.0063% | $2.00 = 0.2% |
| $10,000 | $0.24 | $0.13 | **0.0037%** | ~0.0036% | $2.00 = 0.02% |
| $100,000 | $2.11 | $1.31 | **0.0034%** | ~0.0034% | $2.00 = 0.002% |

- For BND (widest of the 7 at ~1.4 bp) at $10k: 0.0168%.
- **Frequency multiplies this.** A $1 account rebalanced **daily** pays about $0.03 × 252 ≈ **$7.56/yr, or 756% of capital**.
- **Monthly** rebalancing costs 12 × $0.03 ≈ $0.36/yr: **36% of $1, 3.6% of $10, 0.36% of $100, 0.036% of $1,000**.
- Takeaway: below about $1,000, the fixed-cent floor dominates. Above about $1,000, the proportional SEC fee plus spread dominates, and it is tiny.

## 3. US regulatory constraints

- **Pattern day trader rule: obsolete.** The SEC approved FINRA's amendments to Rule 4210 on 2026-04-14, effective **2026-06-04**. They "replace in their entirety" the PDT day-trade count and the $25,000 minimum with real-time intraday margin standards. Brokers may phase in until 2027-10-20. [FINRA RN 26-10](https://www.finra.org/rules-guidance/notices/26-10), [FINRA investor insight](https://www.finra.org/investors/insights/intraday-margin-requirements)
  - $2,000 is still the minimum equity for leveraged margin trading.
  - Alpaca says it implemented the new framework on 2026-06-04. [Alpaca blog](https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/)
  - For a sub-$2,000 account this means no leverage but no day-trade counting.
- **Settlement:** T+1 since 2024-05-28. [Investor.gov T+1 bulletin](https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins/new-t1-settlement-cycle-what-investors-need-know-investor-bulletin)
- **Cash accounts (Regulation T):**
  - Buying and then selling before paying for the purchase is "freeriding" and can trigger a **90-day freeze**. [Investor.gov freeriding](https://www.investor.gov/introduction-investing/investing-basics/glossary/freeriding)
  - Good-faith violations (selling a purchase made with unsettled proceeds before those proceeds settle) are a broker-policy form of the same rule.
  - Irrelevant for a daily or monthly ETF strategy that buys with settled cash, but the code should track settled cash.
- **Alpaca "user protection" rejects potential self-wash-trade orders.** [Alpaca docs](https://docs.alpaca.markets/docs/user-protection)
- **Taxes for US persons:**
  - Short-term gains (held one year or less) are taxed as ordinary income. [IRS TC409](https://www.irs.gov/taxtopics/tc409)
  - Wash sale: a loss is disallowed if substantially identical securities are bought within 30 days before or after the sale, and the loss is added to the new basis. [IRS Pub 550](https://www.irs.gov/publications/p550)
  - Frequent-rebalancing strategies turn buy-and-hold's deferred, long-term gains into short-term ones. That is a real after-tax drag of several percent of gains per year for US taxpayers.
- **Non-US residents at a US broker:**
  - US-source capital gains are generally **not** US-taxed unless the person is present in the US for 183+ days or the gains are effectively connected with a US business. [IRS NRA capital gains](https://www.irs.gov/individuals/international-taxpayers/the-taxation-of-capital-gains-of-nonresident-alien-students-scholars-and-employees-of-foreign-governments)
  - Dividends are withheld at 30%, or the treaty rate via W-8BEN [IRS NRA withholding](https://www.irs.gov/individuals/international-taxpayers/nra-withholding): 15% for UK and most EU portfolio holdings, **25% for Israel**. [IRS treaty tables](https://www.irs.gov/individuals/international-taxpayers/tax-treaty-tables)
  - Home-country tax still applies. For example, Israel taxes real capital gains and dividends at 25%. [PwC Israel](https://taxsummaries.pwc.com/israel/individual/income-determination)
  - The FINRA and Reg T rules above apply because they bind the US broker, not the customer's nationality.
  - Alpaca accepts non-US individuals from about $1 and generates the W-8BEN (Canada excluded; the country list is via support). [Alpaca non-US](https://alpaca.markets/learn/live-trading-account-non-us)
  - Funding cost matters: a 1.5% FX fee, or bank wire fees of often $15 to $50, would exceed a $1 or even $100 test.
- **EU/UK residents and US ETFs:** EU retail clients generally **cannot buy US-domiciled ETFs** (SPY, QQQ, BND...) because they have no PRIIPs KID. Individual US stocks are unaffected, and UCITS equivalents (e.g. Irish-domiciled S&P 500 ETFs) are used instead. [justETF (2018)](https://www.justetf.com/en/news/etf/us-domiciled-etfs.html)
  - The UK is moving from PRIIPs to the Consumer Composite Investments regime (in force 2026-04-06, transition to 2027-06-08). Whether this reopens US ETFs to UK retail is unresolved. [FCA PS25/20](https://www.fca.org.uk/publications/policy-statements/ps25-20-supporting-informed-decision-making-final-rules-consumer-composite-investments)
  - Most EU, UK and Israeli local brokers have no public retail trading API; IBKR is the main API option.

## 4. Profit arithmetic vs running cost

Expected annual profit = capital × return:

| Capital | 3% excess | 8% excess | 15% excess | 10% absolute |
|---|---|---|---|---|
| $1 | $0.03 | $0.08 | $0.15 | $0.10 |
| $10 | $0.30 | $0.80 | $1.50 | $1.00 |
| $100 | $3 | $8 | $15 | $10 |
| $1,000 | $30 | $80 | $150 | $100 |
| $10,000 | $300 | $800 | $1,500 | $1,000 |
| $100,000 | $3,000 | $8,000 | $15,000 | $10,000 |

Annual cost of a daily job (252 trading days), and the capital needed just to break even (= annual cost ÷ excess return):

| Job cost | Per year | Break-even at 3% | at 8% | at 15% |
|---|---|---|---|---|
| $0.01/day | $2.52 | $84 | $32 | $17 |
| $0.10/day | $25.20 | $840 | $315 | $168 |
| $1.00/day | $252 | $8,400 | $3,150 | $1,680 |

- For a 365-day cron, multiply by 1.45.

**What real jobs cost, at the supplied prices:**
- Haiku 4.5 with 5k input and 0.5k output tokens: 5,000×$1/1M + 500×$5/1M = **$0.0075/day ≈ $1.89/yr**, or $0.95 with the Batch API.
- The same prompt on Opus 5.5: $0.03/day ≈ $7.56/yr.
- An agentic Opus run with 100k input and 5k output: $0.40 + $0.10 = **$0.50/day ≈ $126/yr**. That needs about $4,200 of capital at 3% excess return just to break even.

**Why "excess" is the right column:** the benchmark (buy-and-hold VTI or SPY) earns the absolute return with near-zero running cost. The LLM system has to pay for itself out of **excess** return. The base rate for excess return is poor: 79% of active US large-cap funds underperformed the S&P 500 in 2025 (SPIVA via [InvestmentNews](https://www.investmentnews.com/equities/active-managers-stumble-again-in-2025-as-large-caps-dominate/265541)). So 8 to 15% sustained excess returns are fantasy-tier assumptions. 0 to 3% is a more honest planning range, and 0% or negative is the modal outcome.

## 5. Scalability and a test design that transfers from $1 to $10k+

**Market impact.** The square-root law says impact ≈ Y·σ_daily·√(Q/V), with Y ≈ 1. [Donier/Bouchaud slides](https://www.imperial.ac.uk/media/imperial-college/research-centres-and-groups/cfm-imperial-institute-of-quantitative-finance/events/imperial-eth-2016/Jonathan-Donier-.pdf), [Bouchaud](https://bouchaud.substack.com/p/the-square-root-law-of-market-impact)

Taking SPY at σ = 1%/day and V = $32.7B:

| Order size | Share of ADV | Impact |
|---|---|---|
| $10k | 0.00003% | ~0.06 bp |
| $100k | 0.0003% | 0.18 bp |
| $1M | 0.003% | 0.55 bp |
| $10M | 0.03% | 1.7 bp |

- BND ($0.78B ADV, σ ≈ 0.4%/day): $100k ≈ 0.45 bp; $10M ≈ 4.5 bp, at 1.3% of ADV.
- For retail sizes, orders this small mostly just pay the spread; the law is really for large metaorders.
- Real institutional costs measured on $1.7T of executions were "an order of magnitude smaller" than earlier academic estimates. [Frazzini, Israel, Moskowitz 2018](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719)
- Conclusion: for monthly or daily liquid-ETF strategies, capacity is not a constraint below about $10M. The edge, if any, does **not** decay from impact at this person's scale. Small-cap stocks, options or illiquid names would differ.

**Fractional to whole-share transition.**
- Whole shares cause rounding error of up to half a share price per holding. At a 60/40 SPY/BND split on $10k, SPY's $6,000 target becomes 7 shares ($5,359) or 8 ($6,125). The error is up to about $383, or **3.8% of the portfolio**. At $100k it is 0.38%. At $1M, 0.04%.
- Whole-share accounts regain OPG/CLS auction orders, so they can match a close-price backtest. Fractional accounts cannot.
- Therefore the $1 account's fills are *systematically different* from the $10k account's fills. That difference has to be measured, not assumed away.

**Recommended verification design (parallel shadow):**
- (1) One signal engine produces target weights once per rebalance, and those weights are logged and hashed.
- (2) The same weights drive three books:
  - (a) the backtest's simulated fill at its assumed price, e.g. the close plus assumed cost;
  - (b) an Alpaca **paper** account reset to $10k to $100k (the paper default is $100k and can be reset);
  - (c) a live account at $1 to $100.
- (3) Per trade, record the NBBO bid/ask/mid at order submission (arrival), the fill price, and the fees actually charged. Compute implementation shortfall in bp against arrival mid and against the backtest's assumed price.
- (4) **Alpaca paper trading does not simulate** market impact, latency slippage, queue position, price improvement, **regulatory fees or dividends**. Its fills are against the NBBO, with random partial fills 10% of the time. [Alpaca paper trading](https://docs.alpaca.markets/docs/paper-trading) The accounting layer must add fees (using the per-day round-up formula) and dividends (net of withholding for non-US residents) to paper P&L.
- (5) Scale-up gate, all four required:
  - live-fill shortfall at $1 to $100 matches paper shortfall within a tolerance, e.g. ±1 bp for SPY-class ETFs;
  - paper-account shortfall stays below the cost assumed in the backtest;
  - signals are identical across books;
  - the fee-inclusive paper P&L beats the benchmark after LLM and infrastructure costs, pro-rated to the target capital.
- (6) Scale in steps: $100 → $1k → $10k. Re-check the shortfall at each step.

**Statistical honesty about "proof."** A backtest or live track record can only reject "no edge" slowly. The t-stat of excess return ≈ IR × √years, where IR = excess return ÷ tracking error. [Lo 2002, FAJ](https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios) For t = 2, years needed ≈ (2/IR)²:

| Information ratio | Example | Years needed |
|---|---|---|
| 0.2 | 3% excess at 15% tracking error | 100 |
| 0.5 | | 16 |
| 1.0 | | 4 |

Months of paper trading **verify implementation fidelity and cost assumptions. They do not verify the edge.** Edge evidence must come from long out-of-sample backtests with costs, walk-forward testing and multiple-testing corrections, and those are still weak.

## 6. Plain answer: can $1 make meaningful profit?

**No.** $1 at an optimistic 10%/yr earns $0.10, and the fee floor at Alpaca is $0.03 to $0.04 per round trip. A single Haiku call a day (about $0.0075) costs roughly 19× the daily expected profit of $1 even at 15%/yr ($0.15/252 ≈ $0.0006/day).
- Even $100 cannot pay for a $0.10/day LLM job unless excess return is about 25% or more.
- The honest use of $1 to $100 real money is a **smoke test** of the live pipeline: order routing, fractional fills, fee posting, reconciliation, error handling and kill switch. The rest of the proof comes from backtests and paper trading at realistic notional.
- **Running economics only work if:**
  - the LLM is used rarely: monthly or quarterly decisions, or only for research and code generation during design, with a deterministic rules engine in production;
  - Batch or Haiku is used for any recurring call;
  - capital is large enough that annual LLM, data and hosting cost is well under 10 to 20% of the *realistic* expected excess profit, which realistically means thousands of dollars of capital, not tens.

## CLAIMS

- **[C1] (high)** Alpaca fractional/notional orders can be as small as $1, support market/limit/stop/stop-limit only with time_in_force=day (OPG/CLS/GTC/IOC/FOK rejected), cannot be replaced, cannot be short, and are executed on a principal or riskless-principal basis.
  - evidence: Alpaca fractional trading doc: 'as little as $1 worth of shares'; 'market, limit, stop & stop limit orders with a time_in_force=Day'; 'All fractional sell orders are marked long'; 'executed either on a principal or riskless principal basis'. Orders doc: only DAY supported for fractional; 'Notional orders ... cannot be replaced.'
  - sources: https://docs.alpaca.markets/docs/fractional-trading, https://docs.alpaca.markets/docs/orders-at-alpaca
- **[C2] (high)** Alpaca passes through the SEC fee ($0.0000206 x value, sells), FINRA TAF ($0.000195/share, sells, max $9.79) and CAT ($0.000003/share, buys and sells), computed on exact fractional quantities, aggregated per fee type per day per account and rounded UP to the nearest cent, creating a ~$0.03 floor on any day with a sell and $0.01 on a buy-only day.
  - evidence: Alpaca Brokerage Fee Schedule (updated 2026-09-17), 'How fees are charged': 'Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent ($0.01).' Arithmetic: $1 round trip = $0.01 (buy CAT) + $0.01 SEC + $0.01 TAF + $0.01 CAT = $0.04 = 4%.
  - sources: https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf, https://docs.alpaca.markets/docs/regulatory-fees
- **[C3] (high)** The SEC Section 31 fee rate was $0.00 per $1M from 2025-05-14 to 2026-04-03 and is $20.60 per $1M from 2026-04-04 (previously $27.80 through 2025-05-13).
  - evidence: SEC fee rate advisories FY2025 and FY2026 quoted verbatim.
  - sources: https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2, https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- **[C4] (high)** FINRA TAF for equity sells is $0.000195/share (max $9.79/trade) from 2026-01-01, but FINRA paused TAF at $0.00 for transactions 2026-10-01 to 2026-12-31 (SR-FINRA-2026-021, immediately effective), resuming 2027-01-01.
  - evidence: Robinhood and Alpaca fee pages list $0.000195/$9.79; FINRA Exhibit 5A text sets TAF to $0.00 from Oct 1 to Dec 31 2026 and Exhibit 5B restores $0.000195 from Jan 1 2027; Federal Register notice of filing and immediate effectiveness dated 2026-09-23.
  - sources: https://www.sec.gov/files/rules/sro/finra/2026/34-106409-ex5.pdf, https://www.federalregister.gov/documents/2026/09/23/2026-19392/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-and, https://robinhood.com/us/en/support/articles/trading-fees-on-robinhood/
- **[C5] (high)** IBKR charges fractional share trades the greater of 1% of trade value or $0.01 (effectively ~2% round trip at $1-$100), IBKR Pro Fixed is $0.005/share min $1 max 1% of value, and IBKR Lite ($0 commission) is available to US residents only.
  - evidence: IBKR commissions page (fetched 2026-09-29): 'For each fractional share trade, you will be charged the greater of 1% of the trade value or USD 0.01'; table 'IB SmartRouting Eligibility: All / All / US Residents Only'; 'IBKR Lite is available to US residents'.
  - sources: https://www.interactivebrokers.com/en/pricing/commissions-stocks.php
- **[C6] (high)** Major ETFs trade at about one tick: 30-day median NBBO spread 0.00% for SPY and IWM, 0.01% for TLT and GLD as of 2026-09-28; at current prices 1 cent = 0.13 bp (SPY), 0.36 bp (IWM), 1.26 bp (TLT), 1.42 bp (BND).
  - evidence: SSGA SPY page: median bid-ask 0.00% (Sep 28 2026), close $765.61; iShares IWM 0.00%, $280.02; iShares TLT 0.01%, $79.32; SSGA GLD 0.01%, $377.91; BND $70.28 from stockanalysis. Arithmetic 0.01/765.61*1e4=0.13bp.
  - sources: https://www.ssga.com/us/en/intermediary/etfs/spdr-sp-500-etf-trust-spy, https://www.ishares.com/us/products/239710/ishares-russell-2000-etf, https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf, https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld, https://stockanalysis.com/etf/bnd/
- **[C7] (high)** Alpaca receives payment for order flow from Virtu, Citadel, Jane Street and GTS: marketable core-session orders earn 12% of the spread per share (capped at 5c/share); S&P 500 market orders paid roughly 72-95 cents per 100 shares in April 2026.
  - evidence: Alpaca Rule 606 report Q2 2026, April 2026 S&P 500 section: Virtu 95.16, Citadel 84.52, Jane Street 72.57, GTS 84.70 cents per hundred shares for market orders; material aspects text '12% of the spread per share, capped at 5 cents per share'.
  - sources: https://files.alpaca.markets/disclosures/library/SEC+606a1+-+2026Q2.pdf
- **[C8] (high)** The FINRA pattern-day-trader rule and $25,000 minimum were replaced by intraday margin standards effective 2026-06-04 (broker phase-in until 2027-10-20); $2,000 remains the minimum equity for margin; Alpaca says it implemented the change on 2026-06-04.
  - evidence: FINRA Regulatory Notice 26-10: new standards 'replace in their entirety' PDT day-trade counts and the $25,000 requirement; effective June 4, 2026; phase-in to October 20, 2027. FINRA investor insight: '$2,000 is the minimum equity required to engage in leveraged trading'.
  - sources: https://www.finra.org/rules-guidance/notices/26-10, https://www.finra.org/investors/insights/intraday-margin-requirements, https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/
- **[C9] (high)** Alpaca paper trading fills against the NBBO and does not simulate market impact, latency slippage, queue position, price improvement, regulatory fees or dividends; default balance $100k, resettable.
  - evidence: Alpaca paper trading doc quoted verbatim list of what is not accounted for; random partial fills 10% of the time.
  - sources: https://docs.alpaca.markets/docs/paper-trading
- **[C10] (medium)** Non-US-resident individuals are generally not subject to US tax on US-source capital gains unless present in the US 183+ days (or effectively connected income), but US dividends are subject to 30% withholding reduced by treaty via W-8BEN (e.g., 15% UK portfolio dividends, 25% Israel portfolio dividends).
  - evidence: IRS page on NRA capital gains (183-day rule, 30% or treaty rate); IRS NRA withholding page (30% statutory, W-8BEN); IRS treaty table 1 rates as summarized in search results.
  - sources: https://www.irs.gov/individuals/international-taxpayers/the-taxation-of-capital-gains-of-nonresident-alien-students-scholars-and-employees-of-foreign-governments, https://www.irs.gov/individuals/international-taxpayers/nra-withholding, https://www.irs.gov/individuals/international-taxpayers/tax-treaty-tables
- **[C11] (medium)** EU (and, at least historically, UK) retail investors generally cannot buy US-domiciled ETFs like SPY/QQQ/BND because they lack a PRIIPs KID; individual US stocks are unaffected.
  - evidence: justETF (2018): US-domiciled ETFs did not produce KIDs when PRIIPs took effect in 2018. UK CCI regime in force 2026-04-06 with transition to 2027-06-08 (effect on US ETF access unresolved).
  - sources: https://www.justetf.com/en/news/etf/us-domiciled-etfs.html, https://www.fca.org.uk/publications/policy-statements/ps25-20-supporting-informed-decision-making-final-rules-consumer-composite-investments
- **[C12] (medium)** SPY and QQQ each trade roughly $30B+ per day, so a retail order up to $100k is <0.001% of ADV and square-root-law impact is ~0.2 bp or less; capacity is not the binding constraint for liquid-ETF strategies at this person's scale.
  - evidence: Volumes 2026-09-28: SPY 42.69M sh x $765.61 = $32.7B; QQQ 41.78M x $736.53 = $30.8B. Impact = 1 x 1% x sqrt(1e5/3.27e10) = 0.175 bp. Square-root law I = Y sigma sqrt(Q/V), Y~1; AQR found real costs an order of magnitude smaller than earlier estimates.
  - sources: https://stockanalysis.com/etf/spy/, https://stockanalysis.com/etf/qqq/, https://www.imperial.ac.uk/media/imperial-college/research-centres-and-groups/cfm-imperial-institute-of-quantitative-finance/events/imperial-eth-2016/Jonathan-Donier-.pdf, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3229719
- **[C13] (high)** Alpaca allows non-US individuals (except e.g. Canada) to fund with as little as $1 and handles W-8BEN at onboarding, but charges a 1.5% local-currency transfer fee (max $40) and $35 for outbound international wires.
  - evidence: Alpaca non-US article (updated 2026-03-11): 'fund their accounts with as little as $1'; Canada not eligible. Fee schedule: 'Local Currency Transfers 1.5% conversion fee, Max of $40'; 'International Wire Transfers (Outbound) $35'.
  - sources: https://alpaca.markets/learn/live-trading-account-non-us, https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf
- **[C14] (high)** Short-term US capital gains (holding <=1 year) are taxed as ordinary income and wash-sale losses (repurchase within 30 days) are disallowed and added to basis, which penalizes frequent-rebalancing strategies for US taxpayers.
  - evidence: IRS Topic 409 and Publication 550 quoted.
  - sources: https://www.irs.gov/taxtopics/tc409, https://www.irs.gov/publications/p550

## RECOMMENDATIONS

- Treat any live account of $1-$100 strictly as a pipeline smoke test (auth, fractional fill, fee posting, reconciliation, kill switch), budgeted as a cost of about $0.03-$0.04 per round trip at Alpaca. Do not report its P&L as evidence of an edge.
- Prove or disprove the strategy with (a) long out-of-sample, walk-forward backtests that include the per-day round-up fee formula, 1-tick spreads and a slippage buffer, and (b) an Alpaca paper account reset to the target capital ($10k-$100k), fed by exactly the same signal engine.
- Build an accounting layer that adds what Alpaca paper omits: regulatory fees using SEC $20.60/M, TAF $0.000195/share with the Oct-Dec 2026 $0.00 pause, CAT $0.000003/share, each rounded up per day; plus dividends net of withholding for the person's country.
- Log arrival NBBO (bid/ask/mid) at every order and compute implementation shortfall in bp versus arrival mid and versus the backtest's assumed fill price, separately for live-fractional, paper and backtest. Gate scale-up on live shortfall matching paper within about ±1 bp for SPY-class ETFs.
- Because fractional orders are DAY-only (no MOC/OPG), either design the backtest to fill at a realistic intraday time (e.g. the next-day open plus spread, or a fixed-time snapshot), or plan to use whole-share MOC orders once capital allows. Never assume close-price fills for a fractional account.
- Restrict the universe to the most liquid US ETFs (SPY/QQQ/IWM/VTI/TLT/GLD/BND class) and to monthly or slower rebalancing. At $1k capital, monthly rebalancing costs about $0.36/yr in fee floors (0.036%), whereas daily rebalancing at $1 costs about 756% of capital per year.
- Keep the LLM out of the per-trade loop. Use it for research and code during design, and at most for low-frequency (monthly) decisions via Haiku 4.5 or the Batch API (about $0.001-$0.01 per call). Require that annual LLM + data + hosting cost be under ~10-20% of realistic expected excess profit. With a 3% excess assumption, a $0.10/day job needs ~$840 of capital just to break even and ~$4-8k to be worth it.
- Use Alpaca, not IBKR Pro, for tiny-notional tests (IBKR fractional costs about 1% per side). Reconsider IBKR for larger whole-share accounts, or if the person is outside Alpaca's supported countries.
- Before any live funding, confirm the person's country: Alpaca eligibility, the funding path (a 1.5% FX fee or a bank wire fee can exceed a $1-$100 test), the dividend treaty rate, home-country capital gains tax, and, for EU/UK residents, whether US-domiciled ETFs are purchasable at all (UCITS substitutes otherwise).
- Set expectations with the statistics: a 3% excess return at 15% tracking error needs about 100 years of data for t=2, and an information ratio of 1.0 needs about 4 years. Months of paper trading verify execution and costs, not the existence of an edge. The default comparison is buy-and-hold of a low-cost index ETF with zero running cost.

## OPEN QUESTIONS

- Whether Alpaca passes the FINRA TAF pause (Oct 1 - Dec 31 2026) through to customers, and whether its 'rounded up per fee type per day' rule means a $0.01 CAT minimum even on pure buy days in practice (worth confirming on the $1 live test by reading account activities/fees).
- Alpaca's supported country list is only available via support; residency of the person is unknown, so eligibility and funding cost for a $1-$100 deposit are unresolved.
- Actual price improvement statistics for Alpaca fractional (principal) fills vs NBBO; the Rule 606 report gives PFOF, not execution quality (would need Rule 605 data or own measurements).
- Whether the UK Consumer Composite Investments regime (from 2026-04-06) re-opens US-domiciled ETFs to UK retail investors in practice, and which UK/EU/Israeli brokers offer a usable retail API besides IBKR.
- Whether the Schwab Trader API and Public.com API support fractional/notional orders with a $1 minimum, and their residency requirements (not confirmed from primary docs).
- The effect of the amended Rule 612 half-penny tick (compliance 2026-11-02) on SPY/QQQ spreads and on PFOF/price improvement economics.
- The Nasdaq ~4.5 bp index-weighted S&P 500 spread figure was taken from a search snippet; the article itself could not be opened to confirm the date and whether it is a full or half spread.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** Alpaca fractional/notional orders can be as small as $1, support market/limit/stop/stop-limit only with time_in_force=day (OPG/CLS/GTC/IOC/FOK rejected), cannot be replaced, cannot be short, and are executed on a principal or riskless-principal basis.
  - reasoning: I downloaded both Alpaca docs pages and read their text. The fractional page says: 'buy as little as $1 worth of shares for over 2,000 US equities', 'market, limit, stop & stop limit orders with a time in force=Day', 'All fractional sell orders are marked long', 'executed either on a principal or riskless principal basis', and '9 decimal point values'. The orders page has a 'Fractional orders (USD)' TIF table: DAY is Yes for all four order types; GTC, IOC, FOK, OPG and CLS are No for all. It also says 'Notional orders ... cannot be replaced ... will be rejected.' Caveat the research leaves out: the restriction applies to each ORDER, not to a type of account. In the same Alpaca account, whole-share qty orders may use OPG and CLS. So an account holding $1k or more can buy whole shares at the closing auction (MOC) and put only the fractional remainder on a DAY order. The fractional page also says fractional orders work in pre-market, post-market and overnight sessions, and the orders page restricts extended hours to limit orders. The summary's plain 'extended hours supported' should therefore say 'limit orders only'.
- **[C2] CONFIRMED** Alpaca passes through the SEC fee ($0.0000206 x value, sells), FINRA TAF ($0.000195/share, sells, max $9.79) and CAT ($0.000003/share, buys and sells), computed on exact fractional quantities, aggregated per fee type per day per account and rounded UP to the nearest cent, creating a ~$0.03 floor on any day with a sell and $0.01 on a buy-only day.
  - reasoning: I extracted the PDF text myself. It reads 'Revised on September 17, 2026'. The equities rates are: SEC Transaction Fee 'When sells only $0.0000206 * Trade Value'; TAF 'When sells only $0.000195 per share *Max of $9.79 per trade (capped at 50,205 shares or more)'; CAT 'When buys and sells $0.000003 per executed equivalent share'. Under 'How fees are charged': 'Fees are calculated on the exact executed quantity, including fractional shares, with no rounding of share quantity. Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent $0.01.' The regulatory-fees doc agrees ('0.00083 ... rounded up to 0.01'). I rechecked the arithmetic. A $1 SPY round trip on separate days is $0.01 (buy-day CAT) + $0.01 + $0.01 + $0.01 = $0.04. The $1k, $10k and $100k rows reproduce: $0.06, $0.24 and $2.11 in fees. Caveats: (a) this is documented policy, and the real posting of a $0.01 CAT charge on a buy-only day still has to be seen in account activities; (b) the schedule reserves the right to charge commissions if 'order flow [is] determined to be non-retail in nature'; (c) the rates are 'subject to change without notice'.
- **[C3] CONFIRMED** The SEC Section 31 fee rate was $0.00 per $1M from 2025-05-14 to 2026-04-03 and is $20.60 per $1M from 2026-04-04 (previously $27.80 through 2025-05-13).
  - reasoning: The FY2025 advisory says '$0.00 per million dollars' effective May 14, 2025, and '$27.80 per million for covered sales ... through May 13, 2025'. The FY2026 advisory says '$20.60 per million dollars' 'starting on April 4, 2026', with $0.00 through April 3, 2026, and that it runs 'until 60 calendar days after legislation is enacted that sets the amount of the Commission's fiscal year 2027 appropriation'. The rate can therefore change mid-2027, so the code should make it a dated, configurable parameter.
- **[C4] CONFIRMED** FINRA TAF for equity sells is $0.000195/share (max $9.79/trade) from 2026-01-01, but FINRA paused TAF at $0.00 for transactions 2026-10-01 to 2026-12-31 (SR-FINRA-2026-021, immediately effective), resuming 2027-01-01.
  - reasoning: The FINRA fee adjustment schedule (SR-FINRA-2024-019) lists 2026 as '$0.000195 per share (up to $9.79 max per trade)'. I extracted the SEC Exhibit 5 text. Exhibit 5A covers 'October 1, 2026 through December 31, 2026' and sets '$[0.000195]0.00 per share for each sale of a covered equity security, with a maximum charge of $[9.79]0.00'. Exhibit 5B, 'from January 1, 2027 through December 31, 2028', restores $0.000195 and $9.79. The filing is dated September 15, 2026, is immediately effective, and its stated rationale is revenue running above projections. One conflict needs attention. FINRA's own fee adjustment schedule page still lists 2027 at '$0.000232 per share (up to $11.61 max per trade)', 2028 at $0.000240 and 2029 at $0.000249. The Exhibit 5B text, by contrast, shows $0.000195 for 2027 and 2028. So the 2027 rate is ambiguous. Alpaca's schedule, revised 2026-09-17 after the filing, still lists $0.000195 and says nothing about the pause, so pass-through remains unverified. The fee is levied on member firms, and brokers are not obliged to pass the pause through.
- **[C5] NEEDS_QUALIFICATION** IBKR charges fractional share trades the greater of 1% of the trade value or $0.01 (effectively ~2% round trip at $1-$100), IBKR Pro Fixed is $0.005/share min $1 max 1% of value, and IBKR Lite ($0 commission) is available to US residents only.
  - reasoning: WebFetch returned 403 today, so I checked a copy of the commissions page saved earlier in this session. The quotes match. Pro Fixed is USD 0.005, 'Minimum per order USD 1.00', 'Maximum per order 1% of Trade Value'. Tiered is USD 0.0035 with a USD 0.35 minimum. The table's eligibility row reads 'All / All / US Residents Only', and the page says 'IBKR Lite is available to US residents'. The fractional footnote reads: 'Fractional share trades are subject to the same commission rates as whole share trades, with a minimum commission of USD 0.01. For each fractional share trade, you will be charged the greater of 1% of the trade value or USD 0.01', with examples ($5.00 trade gives $0.05; $0.75 trade gives $0.01). Qualifications: (1) the footnote contradicts itself ('same commission rates as whole share trades' versus 'greater of 1%'), and the examples support 1%; the rate should be confirmed with a live or paper order before any model relies on it. (2) The 2% round-trip figure is commission only. IBKR also passes through SEC, TAF and CAT fees, and on Tiered it adds exchange and clearing fees. (3) The IBKR column in the cost table stops being fractional at $1k and above, which is fine but inconsistent with the other rows. (4) The summary's phrase 'IBKR Pro does not charge a PFOF-funded $0' is garbled.
- **[C6] NEEDS_QUALIFICATION** Major ETFs trade at about one tick: 30-day median NBBO spread 0.00% for SPY and IWM, 0.01% for TLT and GLD as of 2026-09-28; at current prices 1 cent = 0.13 bp (SPY), 0.36 bp (IWM), 1.26 bp (TLT), 1.42 bp (BND).
  - reasoning: Confirmed: SSGA shows SPY closing at $765.61 with a 30-day median spread of 0.00% as of Sep 28, 2026. iShares shows IWM at 0.00% and TLT at 0.01% with a close of $79.32. The arithmetic checks out: 0.01/765.61 = 0.13 bp; 0.01/280.02 = 0.36 bp; 0.01/79.32 = 1.26 bp; 0.01/70.28 = 1.42 bp. Problems: (1) GLD is NOT about one tick. A 0.01% median on $377.91 is roughly 1.9 to 5.7 cents after rounding, centred near 4 ticks (a 1-tick spread would be 0.26 bp and would display as 0.00%). The research's table uses about 1 bp for GLD, which contradicts the 'one tick' headline. (2) QQQ, VTI and BND are one-tick ASSUMPTIONS, not measurements. (3) These are published NBBO medians. They do not show what an Alpaca principal fractional fill or an IEX-only quote actually delivers. (4) The iShares TLT page shows daily volume of 62.6M, against the 38.3M 30-day average the research used. Different measures, but ADV figures should say which one they are.
- **[C7] CONFIRMED** Alpaca receives payment for order flow from Virtu, Citadel, Jane Street and GTS: marketable core-session orders earn 12% of the spread per share (capped at 5c/share); S&P 500 market orders paid roughly 72-95 cents per 100 shares in April 2026.
  - reasoning: I extracted the Q2 2026 Rule 606 PDF, generated Jul 16, 2026. For April 2026 S&P 500 stocks, net payment for market orders in cents per hundred shares is: Virtu 95.1577, Citadel 84.5192, Jane Street 72.5700, GTS 84.6962. The material-aspects text reads: 'Marketable orders filled during the core session will receive 12% of the spread per share, capped at 5 cents per share', and non-marketable orders receive '20 mils per share'. It also states the PFOF versus price-improvement conflict. Caveat: Rule 606's 'S&P 500 Stocks' category covers the index constituents. ETFs such as SPY are reported under 'Non-S&P 500', so these per-100-share figures are not SPY-specific. A 12% share of a 1-cent SPY spread is only about 0.12 cent per share. Rule 606 says nothing about execution quality; that would need Rule 605 data or the person's own measurements.
- **[C8] CONFIRMED** The FINRA pattern-day-trader rule and $25,000 minimum were replaced by intraday margin standards effective 2026-06-04 (broker phase-in until 2027-10-20); $2,000 remains the minimum equity for margin; Alpaca says it implemented the change on 2026-06-04.
  - reasoning: FINRA RN 26-10 gives SEC approval as April 14, 2026, effective 'June 4, 2026', with a phase-in to 'October 20, 2027'. It removes the day-trade counts and 'The $25,000 pattern day trader minimum equity requirement'. The FINRA investor insight reads: '$2,000 is the minimum equity required to engage in leveraged trading ... You can trade in a margin account with less than $2,000 in equity, but you cannot use leverage.' The Alpaca blog says PDT was 'officially lifted' in production on June 4, 2026. Caveat: the new rule covers margin accounts. Cash accounts are still bound by Reg T settled-cash rules (freeriding and good-faith violations), which the research does note. Other brokers may still be phasing in until October 2027.
- **[C9] NEEDS_QUALIFICATION** Alpaca paper trading fills against the NBBO and does not simulate market impact, latency slippage, queue position, price improvement, regulatory fees or dividends; default balance $100k, resettable.
  - reasoning: The list of what paper trading omits is quoted correctly: market impact, information leakage, latency slippage, queue position, price improvement, regulatory fees and dividends. Partial fills occur 'for a random size 10% of the time'. The default balance is $100k. Corrections: (1) 'Resettable' is outdated. The doc now says 'We've updated the dashboard to allow you to create and delete paper accounts, rather than resetting them', and 'You cannot change the account balance after it is created'. To run at $10k, you create a new paper account at $10k. (2) The doc also says order quantity is not checked against real liquidity, so paper fills can exceed what the market would actually give. (3) Paper-only accounts receive IEX market data only. On the free Basic plan, real-time quotes are IEX-only rather than the SIP NBBO. That matters for the research's arrival-NBBO logging.
- **[C10] NEEDS_QUALIFICATION** Non-US-resident individuals are generally not subject to US tax on US-source capital gains unless present in the US 183+ days (or effectively connected income), but US dividends are subject to 30% withholding reduced by treaty via W-8BEN (e.g., 15% UK portfolio dividends, 25% Israel portfolio dividends).
  - reasoning: The substance is correct (IRC 871(a)(2) and the 30%/W-8BEN regime). But the cited IRS page is specifically about 'Foreign students, scholars and employees of foreign governments'; the general statement belongs in IRS Pub 519. The treaty rates came from search snippets. The IRS Table 1 PDF (Rev. May 2023) exists, but I could not parse its row layout. From knowledge of the treaties, the US-Israel general dividend rate is 25% and the US-UK portfolio rate is 15%, which is consistent. Missing caveats that matter at scale: (a) US estate tax applies to non-resident aliens' US-situs assets above $60,000, and US stocks and US-domiciled ETFs are US-situs. That is a real scale-up risk. (b) Home-country tax applies on each realized rebalance gain; Israel adds surtaxes on capital income above a threshold. (c) Home-country foreign-account reporting duties.
  - corrected: Under IRC 871(a)(2) (see IRS Pub 519), non-resident aliens are generally not US-taxed on US-source capital gains from portfolio trading unless present 183+ days or the gains are effectively connected with a US business. US dividends are withheld at 30%, reduced via W-8BEN to the treaty rate (e.g., 15% UK, 25% Israel). US estate tax applies to US-situs holdings over $60k, and home-country tax and reporting apply.
- **[C11] NEEDS_QUALIFICATION** EU (and, at least historically, UK) retail investors generally cannot buy US-domiciled ETFs like SPY/QQQ/BND because they lack a PRIIPs KID; individual US stocks are unaffected.
  - reasoning: The justETF source is dated 28 March 2018. It is still broadly accurate: current secondary sources from 2025-26 say EU/UK-regulated brokers block retail purchases of US ETFs that lack a KID. FCA PS25/20 confirms the CCI regime began 6 April 2026 with full effect 8 June 2027, and commentators say it will not automatically open access to US ETFs. Qualifications: (1) the block is enforced by EU/UK-regulated brokers, including IBKR's EU and UK entities. Owning a US ETF is not illegal. Whether a US broker onboarding a UK or EU resident across borders (e.g., Alpaca, which lists the UK and Portugal as eligible countries) lets them buy SPY is unverified, so do not assume either way. (2) The justETF article mentions an exception for 'sophisticated' or professional investors, often with very large portfolio thresholds (it cites over £500k). (3) The primary source is 8 years old.
  - corrected: EU/UK-regulated brokers generally do not sell US-domiciled ETFs without a KID to retail clients (the UK CCI regime, in transition 2026-04-06 to 2027-06-08, does not clearly change this). Individual US stocks and UCITS equivalents are available. Whether a cross-border US broker such as Alpaca restricts EU/UK residents from US ETFs must be confirmed directly.
- **[C12] CONFIRMED** SPY and QQQ each trade roughly $30B+ per day, so a retail order up to $100k is <0.001% of ADV and square-root-law impact is ~0.2 bp or less; capacity is not the binding constraint for liquid-ETF strategies at this person's scale.
  - reasoning: stockanalysis shows 2026-09-28 volumes of 42,694,470 shares for SPY at $765.61 (= $32.7B) and 41,775,024 for QQQ at $736.53 (= $30.8B). My arithmetic: 1e5/3.27e10 = 3.06e-6; sqrt = 1.75e-3; times 1% = 0.175 bp. $10M gives 1.75 bp, and BND at $10M gives about 4.5 bp. All reproduce. AQR's Frazzini, Israel and Moskowitz report '$1.7 trillion' of live executions with costs 'an order of magnitude smaller than previous studies suggest'. That is an AQR working paper from a sophisticated institutional executor, so it does not show retail fills will match. Caveats: the volumes are single-day figures, not ADV. The square-root law is fitted to metaorders and says little about orders of a few hundred dollars, which the research acknowledges. The conclusion holds: capacity is not the binding constraint. But 'scaling is not the risk' is only true for market impact. See pushback.
- **[C13] CONFIRMED** Alpaca allows non-US individuals (except e.g. Canada) to fund with as little as $1 and handles W-8BEN at onboarding, but charges a 1.5% local-currency transfer fee (max $40) and $35 for outbound international wires.
  - reasoning: The non-US article (last updated March 11th, 2026) reads: 'as little as $1', 'Canadian residents are not currently supported', '195+ countries', and W-8BEN for non-US tax residents. The fee schedule PDF reads: 'Local Currency Transfers Inbound and Outbound) 1.5% conversion fee *Max of $40 USD per transaction' and 'International Wire Transfers Outbound) $35 / transaction'. Caveats: the article says funding methods vary by country and does not list them. The person's own bank will charge its outgoing international-wire and FX fees on top, often $15 to $50 or more. Eligibility is confirmed per country only through support.
- **[C14] CONFIRMED** Short-term US capital gains (holding <=1 year) are taxed as ordinary income and wash-sale losses (repurchase within 30 days) are disallowed and added to basis, which penalizes frequent-rebalancing strategies for US taxpayers.
  - reasoning: This is standard, well-established IRS doctrine (Topic 409 and Pub 550). I did not re-fetch these pages because the rules are long-standing and unchanged. Note: the summary's 'several percent of gains per year' tax drag has no source. It depends on bracket, turnover and state tax, and should be modelled rather than asserted. Wash-sale rules also reach purchases in IRAs and a spouse's accounts, which a bot running several accounts could trigger.
- **[S1-uncited-in-claims] REFUTED** Half-penny ticks for tick-constrained names (amended Rule 612) take effect 2026-11-02, which may narrow SPY/QQQ spreads further (cited to SEC press release 2024-137).
  - reasoning: This claim is outdated. The SEC first extended compliance to the first business day of November 2026 (release 2025-130). Then, on June 11, 2026, Chairman Atkins' statement and an exemptive order (Federal Register 2026-06-15) extended it again to 'the first business day of November 2027'. The same holds for Rule 610(c) access fee caps. The cited 2024-137 release shows the original 2025 date and does not support 2026-11-02 in any case.
  - corrected: The Rule 612 half-penny tick and the Rule 610(c) access-fee caps are deferred to the first business day of November 2027 (SEC exemptive relief, June 2026). Nothing changes in November 2026.
- **[S2-arithmetic] REFUTED** A single Haiku call a day (~$0.0075) costs roughly 19x the daily expected profit of $1 even at 15%/yr ($0.15/252 ≈ $0.0006/day).
  - reasoning: At 15%: 0.15/252 = $0.000595 per day, and 0.0075/0.000595 = 12.6x, not 19x. The 19x figure corresponds to 10%/yr (0.10/252 = 0.000397; 0.0075/0.000397 = 18.9x). The qualitative point is unaffected. All the other arithmetic I checked reproduces exactly: the break-even table ($84/$32/$17; $840/$315/$168), the Haiku, Opus and agentic costs ($1.89/yr, $7.56/yr, $126/yr, $4,200 break-even), the fee rows, the square-root impacts, the whole-share rounding ($6,000/765.61 = 7.84 shares; half a share = $383 = 3.8% of $10k), and the t-stat table ((2/0.2)^2 = 100, (2/0.5)^2 = 16, (2/1)^2 = 4).
  - corrected: A $0.0075/day Haiku call is about 12.6x the daily expected profit of $1 at 15%/yr, or about 19x at 10%/yr.
- **[S3-base-rate] NEEDS_QUALIFICATION** 79% of active US large-cap funds underperformed the S&P 500 in 2025 (SPIVA), so 0-3% excess is an honest planning range.
  - reasoning: InvestmentNews confirms '79% of all active large-cap U.S. equity funds underperformed the S&P 500' in 2025 (SPIVA U.S.), which it calls the fourth-worst year in 25. That is a one-year figure, and SPIVA's long-horizon numbers (10 to 20 years) are the right base rate: underperformance over those horizons is roughly 85 to 90% or more. Mutual-fund results after fees are also not a direct prior for a retail LLM-driven system. The retail-trader literature is harsher. Calling 0 to 3% 'honest' still leans optimistic; the planning prior should be at most 0 after costs.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- LOG ARRIVAL NBBO AT EVERY ORDER: the research never says what this costs. Alpaca's free Basic plan gives IEX-only real-time quotes, not the SIP NBBO. Real-time SIP needs Algo Trader Plus at $99/month ($1,188/yr), which at 3% excess return needs about $39,600 of capital just to break even (1188/0.03). That would break the person's hard cost constraint. Fix: record submission timestamps and pull historical SIP quotes for free once the 15-minute delay has passed ('Historical data limitation: latest 15 minutes' on Basic). Rebuild arrival NBBO after the fact. Never use an IEX quote as the NBBO.
- SCALE-UP GATE '±1 bp live vs paper shortfall': statistically ill-posed. At $1 to $100 the live orders are fractional fills that Alpaca executes as principal or riskless principal. Paper orders fill against the NBBO with random partial fills. Monthly rebalancing of a handful of ETFs gives only about 50 to 100 fills a year, and noise from arrival to fill is several bp per fill. The gate needs a confidence interval from enough fills, not a fixed ±1 bp. Fees (4% of $1) must be excluded from the bp comparison.
- SCALE-UP GATE 'fee-inclusive paper P&L beats benchmark after LLM/infra costs': contradicts the research's own statistics section, which says months of paper trading cannot verify the edge (t≈IR·√years). A gate built on short-horizon P&L will pass or fail on luck. The P&L condition should be dropped, or replaced by a pre-registered backtest/walk-forward result plus a check that paper matches the backtest on the same days.
- 'SCALING IS NOT THE RISK': true only for market impact. For this person, the scaling risks that matter are: an edge that was never real; decay or regime change; LLM non-determinism and model deprecation changing signals over time; tax drag growing with realized gains; drawdowns in absolute dollars; and, for non-US persons, US estate-tax exposure on US-situs assets above $60k. A consumer-protection lawyer would object to any wording that tells a novice scaling is safe.
- FRACTIONAL VS WHOLE-SHARE 'ACCOUNTS': at Alpaca the DAY-only restriction applies to each order, not to a kind of account. The same account can place whole-share CLS/OPG orders and send only the fractional remainder as a DAY order. The design should use whole-share MOC orders plus a fractional remainder once a holding reaches one share, instead of treating the two as separate account regimes.
- HARD-CODED FEE PARAMETERS in the accounting layer (SEC $20.60/M, TAF $0.000195 with the Q4-2026 pause): the rates are dated and in flux. SEC changes 60 days after the FY2027 appropriation. The 2027 TAF is ambiguous: FINRA's fee-adjustment page says $0.000232 and cap $11.61, while the SR-FINRA-2026-021 Exhibit 5B says $0.000195. Alpaca may or may not pass the pause through. Use dated, configurable fee tables and reconcile each day against the fees actually posted in Alpaca account activities.
- RULE 612 HALF-PENNY TICK (Nov 2026): wrong date, now November 2027. No design or cost assumption should rely on it.
- ALPACA OVER IBKR FOR TINY TESTS: the commission reasoning is fine, but the recommendation skips gating questions a lawyer would put first. Is Alpaca permitted to onboard residents of the person's country? What protection applies (SIPC up to $500k at a US broker, but no home-country compensation scheme or dispute forum)? Can non-US persons buy US ETFs there? What does funding cost? For a non-US person, one inbound international wire ($15 to $50 at the bank, or 1.5% FX, up to $40, via Alpaca) can cost 15x to 50x the $1 'test'. The live smoke test should run only if funding costs a few dollars at most; otherwise do the end-to-end test in paper and skip live money entirely.
- LIVE $1 SMOKE TEST SAFETY: the research omits account-configuration risk. Alpaca accounts may have margin enabled; with more than $2,000 of equity that means leverage. Require a cash-only or no-margin configuration, options and shorting disabled, a hard notional cap in code, a kill switch, and keys held outside the LLM's context. Never give an LLM agent unrestricted order-placement tools.
- LLM FOR 'LOW-FREQUENCY (MONTHLY) DECISIONS': no evidence was offered that an LLM adds excess return to an ETF allocation. The cheapest honest default is no LLM in the production loop at all: a deterministic rules engine, with Claude used only in design and research. Any LLM-in-the-loop variant has to beat that no-LLM version out of sample, net of its token cost.
- PLANNING RANGE '0-3% EXCESS': still optimistic for a novice's LLM-assisted system. The base rate should use SPIVA's long horizons (roughly 85 to 90%+ of funds underperform over 10 to 20 years), not one year. The orchestrator should put the likely conclusion to the user plainly: the benchmark (buy-and-hold of a low-cost index ETF/UCITS ETF) is the null. The most probable correct answer may be not to run an active system at all.
- TAX STATEMENTS: 'several percent of gains per year' after-tax drag has no source. The analysis also leaves out the home-country tax on every realized rebalance for non-US persons (e.g., Israel's 25% on real gains plus surtaxes), wash-sale interaction across IRA and spouse accounts for US persons, and PFIC issues if a US person uses UCITS substitutes. Tax treatment should be a per-country modelled input, not a single sentence.
- PAPER ACCOUNT 'RESET TO $10k-$100k': the reset feature was replaced by creating and deleting paper accounts, and paper-only accounts get IEX data only. Minor, but the runbook must say 'create a new paper account at X'.

## VERIFIER OVERALL

This research is reliable on primary-source facts and on arithmetic. I independently extracted the Alpaca fee schedule (revised 2026-09-17), the Alpaca Q2 2026 Rule 606 PDF and FINRA's SR-FINRA-2026-021 Exhibit 5, and read the Alpaca order/fractional/paper docs. The quoted fee mechanics are exact: per-fee-type daily aggregation, rounded up to the cent. So are the SEC and TAF rates, the TAF pause, the PDT replacement, the PFOF terms and the order-type limits. Nearly every table reproduces when I redo the arithmetic.

Errors and outdated items the orchestrator should weight down or correct:
(1) The Rule 612 half-penny tick date is REFUTED: SEC relief in June 2026 moved it to November 2027.
(2) The '19x' Haiku-vs-profit ratio is 12.6x at 15%; 19x corresponds to 10%.
(3) GLD does not trade at one tick. QQQ, VTI and BND spreads are assumptions, not measurements.
(4) Alpaca paper 'reset' is outdated (now create/delete), and paper-only accounts get IEX data only.
(5) The 2027 TAF rate is ambiguous ($0.000195 per Exhibit 5B versus $0.000232 per FINRA's fee schedule), and Alpaca pass-through of the Q4-2026 pause is unverified.
(6) The IBKR fractional footnote contradicts itself.
(7) The EU/UK US-ETF restriction rests on a 2018 blog post and is broker-dependent. It binds EU/UK-regulated brokers, but whether cross-border Alpaca applies it is unknown.
(8) The NRA capital-gains citation is a page for students and scholars, and the US estate-tax exposure above $60k is omitted.

The biggest substantive gap is cost. The recommended arrival-NBBO measurement quietly assumes SIP data, and real-time SIP at Alpaca costs $99/month, which would break the person's running-cost constraint. It is workable for free only by querying historical SIP quotes after the 15-minute delay.

The scale-up gate is the weakest part of the design. A fixed ±1 bp tolerance on a handful of fractional principal fills is statistically meaningless. A short-horizon 'paper P&L beats benchmark' condition contradicts the research's own (correct) t-stat section. 'Scaling is not the risk' is true only for market impact; a consumer-protection reader would object to a novice hearing it as reassurance.

The core conclusions are sound and should be kept:
- $1 to $100 cannot generate meaningful profit.
- The live $1 account is at most a plumbing smoke test, and should be skipped if funding fees exceed a few dollars.
- The evidence has to come from cost-inclusive walk-forward backtests plus paper trading at realistic notional.
- LLM calls must stay out of the per-trade loop.
- The default comparator is buy-and-hold of a low-cost index fund.
