# gap: Residency-conditional broker, instrument, tax and funding matrix

## SUMMARY

## Method and caveats
I checked primary sources directly with curl and text extraction: broker fee PDFs, OpenAPI specs, help-centre APIs, government and tax-authority pages. WebFetch's summariser made up numbers when it summarised Alpaca's fee PDF (it reported a $15 international outbound wire and a 0.25% FX fee). The raw PDF says **$35** and **1.5% (max $40)**. So every number below comes from raw text unless it is flagged. The WebSearch budget ran out partway through. Items marked **[UNVERIFIED]** come from memory or secondary sources and must be checked before any build choice relies on them.

## Broker facts shared by all countries (primary sources)

**Alpaca**
- Canada is excluded: "residents of Canada are not currently eligible". UK and Portugal residents are given as examples of eligible applicants. For any other country the answer is "contact support" (support page dated Feb 2026). Non-US residents can fund with as little as $1 and must sign a W-8BEN. Sources: https://alpaca.markets/learn/live-trading-account-non-us, https://alpaca.markets/support/countries-alpaca-is-available
- Paper trading is free for all users, starts at $100k and can be reset. Fractional orders go down to $1, by quantity or notional. Sources: https://docs.alpaca.markets/docs/paper-trading, https://docs.alpaca.markets/docs/fractional-trading
- Fee schedule (revised 2026-09-17), https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf:
  - ACH return fee $25.
  - Domestic outbound wire $15; international outbound wire $35.
  - Local-currency transfers: 1.5% conversion fee, max $40.
  - No commission on retail order flow.
  - SEC fee $0.0000206 × value on sales; FINRA TAF $0.000195/share on sales; CAT $0.000003/share on buys and sells.
  - Each fee type is rounded **up to $0.01 per day**, so a $1 round trip costs about $0.03–0.04 (3–4%).
  - No inactivity fee is listed.
- International users can fund only in USD (the Rapyd note dates from Nov 2022). SIPC covers customers with no residency requirement: https://www.sipc.org/for-investors/what-sipc-protects

**Interactive Brokers (IBKR)**
- US stocks (https://www.interactivebrokers.com/en/pricing/commissions-stocks.php):
  - IBKR Lite is $0 but for **US residents only**; it covers Individual, Joint, IRA and some Trust accounts.
  - Pro Fixed: $0.005/share, min $1, max 1% of trade value.
  - Pro Tiered: $0.0035/share, min $0.35, plus exchange and clearing fees.
  - Fractional trades cost the greater of 1% or $0.01.
- European exchanges, including Xetra, Euronext and the Netherlands: Tiered is 0.05%, min €1.25; Fixed min €3 (plus pass-through fees). UK: Tiered min £1, Fixed min £3 (https://www.interactivebrokers.co.uk/en/pricing/commissions-stocks-europe.php).
- Canada Fixed: CAD 0.01/share, min CAD 1.
- FX conversion: 0.20 bp, **min USD 2** (https://www.interactivebrokers.com/en/pricing/commissions-spot-currencies.php).
- Two free withdrawals per month (https://www.interactivebrokers.com/en/pricing/other-fees.php).
- A free trial paper account exists. [UNVERIFIED] whether the trial gives API access.
- For EEA and UK retail clients, IBKR says it "is required to block trading in a PRIIP if a KID is not available", which blocks US ETFs (https://www.interactivebrokers.com/lib/cstools/faq/#/content/1136192471).

**Trading 212**
- Public API, taken from the OpenAPI spec (https://docs.trading212.com/_spec/api.json):
  - It is **beta**. Only **Invest and Stocks ISA** accounts can use it; SIPP is excluded (https://helpcentre.trading212.com/hc/en-us/articles/14584770928157).
  - Environments: demo (https://demo.trading212.com/api/v0) and live.
  - Order types: market, limit, stop and stop-limit.
  - Orders are sized by **quantity only**: "Placing orders by value is not currently supported via the API".
  - Orders execute in the primary account currency only.
  - The market-order endpoint is **"not idempotent"**.
  - The pies endpoints are **deprecated**.
  - There is **no quote or market-data endpoint**.
  - Rate limits include market orders 50/min and account summary 1 per 5 s.
- Entities: Trading 212 UK Ltd (UK), Trading 212 EU GmbH (DE, NL, FR, IE and others; BaFin), Trading 212 Markets Ltd (CY and others), Trading 212 AU. There is **no US, Canada, Israel or India** (https://helpcentre.trading212.com/hc/en-us/articles/12933782261917).
- Fees:
  - Commission 0; custody 0; FX 0.15%.
  - Bank-transfer deposits are free. Card deposits cost 0.7% once cumulative card deposits pass 2,000 GBP/EUR.
  - Withdrawals are free. There is no inactivity fee.
  - Help-centre articles updated 2026-08/09, e.g. https://helpcentre.trading212.com/hc/en-us/articles/360007139838 and /11471996799517.
- Trading 212 EU GmbH **withholds German tax automatically** for German residents (https://helpcentre.trading212.com/hc/en-us/articles/24308101760029).
- Investor protection: FSCS £85k for investments (UK entity); German EdW €20k (EU GmbH).
- [UNVERIFIED] Minimum order value, reported as about £1/€1.

**eToro**
- The public API has demo and real trading endpoints and sizes orders by amount or units. Accounts must be verified before API access: https://api-portal.etoro.com/, https://api-portal.etoro.com/core/guides/market-orders.md
- Fees (https://www.etoro.com/trading/fees/):
  - ETFs 0 commission; stocks $1–2 per open or close.
  - $5 withdrawal fee from a USD account, with a $30 minimum withdrawal. Local-currency (GBP/EUR/AUD/DKK) accounts withdraw free.
  - Inactivity fee listed as "Free".
- [UNVERIFIED] FX fee, minimum trade size, and API availability by country.

**Saxo OpenAPI**
- Retail clients can use it, but **manual logon is required**: no certificate-based auth for retail, and Saxo recommends re-authenticating weekly.
- The SIM account can trade only FX unless it is linked to a *funded* live account, and an unlinked SIM expires after 20 days (https://openapi.help.saxo/hc/en-us/articles/4416637197457, /4416934146449).
- This makes it a poor fit for unattended automation and for tiny accounts.

**US-only brokers**
- Tradier Lite: $0/month, stocks $0.35/trade, API included (https://tradier.com/individuals/pricing).
- Public.com API: open to all members, commission-free, fractional orders, and can trade **IRA** accounts (https://public.com/api). [UNVERIFIED] whether Public offers paper trading.
- Schwab Trader API: the developer page is JS-only [UNVERIFIED].

**India: Zerodha Kite Connect**
- The Personal API is free; the data tier costs ₹500/month (https://kite.trade/).
- The access token expires at 6 AM the next day as a "regulatory requirement", so someone must log in by hand each trading day the bot trades (https://kite.trade/docs/connect/v3/user/).

## Instrument access rules
- **EU (PRIIPs):** retail clients cannot buy US ETFs that lack a KID. Use UCITS funds instead: VWCE, SXR8/CSPX, and XEON as the cash proxy (tickers are illustrative).
- **UK (CCI regime):** rules took effect **2026-04-06**; firms must replace KIDs and KIIDs by 7–8 June 2027 (https://www.fca.org.uk/publications/policy-statements/ps25-20-...). The rules also cover "an overseas distributor of a CCI that distributes a CCI in the UK even if it is not required to be FCA authorised" (K&L Gates, 2026-09-04: https://www.klgates.com/...9-4-2026).
  - In practice US ETFs remain unavailable. The Overseas Funds Regime replaced the "KID wall" with an "OFR wall" (https://edale.co/us-uk-etf-kid-cci-reporting/, blog).
- **Alpaca:** **[UNVERIFIED]** whether it blocks US ETFs for UK/EU residents. It is US-regulated and nothing it publishes mentions a block. UK/EU residents who buy there take on CCI/PRIIPs regulatory risk and offshore-fund tax complexity.
- **US, CA, AU, IL, IN:** no KID rule. US ETFs can be bought. For non-US persons, Irish UCITS funds are still better for estate tax and dividend withholding (sections below).

## Dividend withholding and estate tax
- US treaty rates on portfolio dividends: **15%** for AU, CA, FR, DE, IE, NL, UK; **25%** for IL and IN; **30%** non-treaty. Source: PwC, https://taxsummaries.pwc.com/united-states/corporate/withholding-taxes (secondary but reputable).
- An Irish UCITS fund suffers 15% at fund level (Ireland treaty rate); investors in non-Irish countries pay no further Irish withholding [UNVERIFIED].
- US estate tax: a return is required if a nonresident's **US-situs assets exceed $60,000** (https://www.irs.gov/individuals/international-taxpayers/some-nonresidents-with-us-assets-must-file-estate-tax-returns). US-domiciled ETFs are US-situs; Irish UCITS funds are not.
- Estate-tax treaties with the US (UK, DE, FR, NL, IE, AU, and CA via its income-tax treaty) soften this; IL and IN have none [UNVERIFIED — the IRS treaty page returned 404].

## After-tax drag of the trend overlay vs buy-and-hold
Model assumptions: 7% nominal return, 20 years. Buy-and-hold pays tax once at the end. The trend overlay (about 1.5 switches/yr, roughly 0.75 exits) is approximated as realizing all gains every year. The overlay's lower pre-tax return from time spent in cash is ignored, so this isolates tax drag. Formula: annualized after-tax BH = ((1.07^20 − t·(1.07^20 − 1))^(1/20) − 1); trend = 7%·(1 − t).

| Case | BH after-tax | Trend after-tax | Drag (pp/yr) |
|---|---|---|---|
| US taxable, BH at 15% LTCG vs trend at 24% STCG | 6.37% | 5.32% | **1.05** |
| UK GIA, 24% | 5.96% | 5.32% | 0.64 |
| DE, 26.375% × 70% (Teilfreistellung) = 18.46% | 6.22% | 5.71% | 0.51 |
| FR CTO, 31.4% | 5.59% | 4.80% | 0.79 |
| IE, ETF exit tax 38%; BH deemed disposal every 8 years | 4.67% | 4.34% | 0.33 (plus ETF losses cannot be offset) |
| IL, 25% real gain | 5.91% | 5.25% | 0.66 |
| CA, 50% inclusion × 43.4% = 21.7% | 6.07% | 5.48% | 0.58 |
| AU, BH 16% (50% discount) vs trend 32% (held under 12 months) | 6.33% | 4.76% | **1.57** |
| IN foreign ETF, BH 12.5% (held over 24 months) vs slab rate about 31.2% | 6.48% | 4.82% | **1.66** |
| IN domestic Nifty ETF, 12.5% vs 20% | 6.48% | 5.60% | 0.88 |
| NL Box 3 | 0.36 × 5.88% ≈ 2.1% of net assets above the exemption, the **same for both** | | **0** |
| ISA / Roth IRA / TFSA / PEA | | | **0** |

**Small-account nuance:** allowances wipe out the drag for small accounts.
- UK £3,000 allowance: no CGT until about £43k at 7% (£3,000 / 0.07).
- DE €1,000 Sparer-Pauschbetrag: zero until about €20.4k (€1,000 / (0.7 × 0.07)).
- The US 0% LTCG bracket also helps low earners.
- Ireland's exit tax has no allowance.
- Australia: the discount is replaced by cost-base indexation for gains accruing from **1 July 2027**. This comes from PwC and needs checking against the ATO.

## Per-jurisdiction tables (condensed)
Fee column = commission on a $1 / $100 / $10k order. Only regulatory fees are listed; spreads are not.

**United States**
| Item | Answer |
|---|---|
| API brokers | Alpaca (free paper; $0 / $0 / $0 plus reg fees of about $0.21 on a $10k sale); Public (IRA via API); IBKR Lite ($0); Tradier ($0.35/trade); Schwab [UNVERIFIED] |
| Funding | ACH free (Alpaca); outbound domestic wire $15 |
| Instruments | VTI/VOO; cash proxy BIL/SGOV |
| Tax | STCG at ordinary rates; LTCG 0/15/20% (https://www.irs.gov/taxtopics/tc409); 30-day wash-sale rule |
| Wrappers | Roth/traditional IRA via Public API and IBKR (Lite covers IRA) |
| Reporting | 1099-B imports; about 1 h/yr, $0–50 |
| Protection | SIPC $500k / $250k cash; FINRA arbitration |
| FX | none |

**United Kingdom**
| Item | Answer |
|---|---|
| API brokers | Trading 212 Invest/ISA (demo + live; $0 / $0 / $0; FX 0.15% only on non-GBP lines); IBKR UK (min £1 tiered = 100% of a $1 order, 1% of $100); Alpaca (eligible, but USD wires and $35 outbound wire) |
| Instruments | UCITS funds such as VWRP and VUAG; GBP money-market ETF (CSH2 or ERNS) [ticker availability UNVERIFIED] |
| Tax | CGT 18%/24%, £3,000 allowance (https://www.gov.uk/capital-gains-tax/rates, /allowances); 30-day bed-and-breakfast rule (HMRC CG51560) |
| Wrappers | Stocks & Shares ISA is API-tradable on Trading 212. SIPP is not. |
| Reporting | GIA: Self Assessment and per-trade GBP conversion; accumulating offshore funds also require excess reportable income each year [UNVERIFIED]; about 3–6 h or £150–400. ISA: none. |
| Protection | FSCS £85k; FOS for UK firms |
| FX | none if GBP lines are used |

**Germany**
| Item | Answer |
|---|---|
| API brokers | Trading 212 EU GmbH ($0 commission; German tax withheld automatically); IBKR IE (€1.25 min = 1.25% of $100; €5 on $10k); Alpaca [country UNVERIFIED] |
| Instruments | UCITS only (VWCE, SXR8, XEON) |
| Tax | 25% + Soli (§32d EStG); 30% Teilfreistellung for equity funds (§20 InvStG); Vorabpauschale = start price × 70% × Basiszins (§18 InvStG); €1,000 allowance (§20(9) EStG); no wash-sale rule |
| Wrappers | none with API access |
| Reporting | Trading 212 EU GmbH: ~0 h. A foreign broker needs Anlage KAP plus a self-computed Vorabpauschale: 3–8 h or €150–400 [estimate]. |
| Protection | EdW €20k |
| FX | none if EUR lines are used |

**France**
| Item | Answer |
|---|---|
| API brokers | Trading 212 EU GmbH; IBKR IE; eToro |
| Instruments | UCITS only |
| Tax | PFU **31.4%** = 12.8% income tax + 18.6% social levies (service-public F21618, checked 2026-04-15); no wash-sale rule |
| Wrappers | PEA: income-tax exempt after 5 years, but **no API broker for a PEA is known** [UNVERIFIED] |
| Reporting | Foreign accounts (including the German Trading 212 entity) need a yearly Form 3916 (€1,500 penalty) plus form 2074 [UNVERIFIED]; 3–6 h |
| Protection | EdW or ICCL, depending on the broker |

**Netherlands**
| Item | Answer |
|---|---|
| API brokers | Trading 212 EU GmbH; IBKR IE |
| Instruments | UCITS only |
| Tax | Box 3 deemed return (5.88% in 2025, https://www.rijksoverheid.nl/onderwerpen/inkomstenbelasting/box-3); 36% rate and €57,684 exemption [UNVERIFIED for 2026]; the government is aiming for an actual-return tax from 1 Jan 2028. **Switching has no tax consequence**, which makes this the most trend-friendly country. |
| Reporting | yearly 1 Jan balances; under 1 h |
| Protection | EdW / ICCL |

**Ireland**
| Item | Answer |
|---|---|
| API brokers | Trading 212 EU GmbH; IBKR IE |
| Instruments | UCITS only |
| Tax | ETFs: exit tax **41% through 2025, 38% from 1 Jan 2026** (Revenue TDM 27-01A-02); 8-year deemed disposal; since 2022 US ETFs are no longer automatically treated as shares (TDM 27-01A-03); CGT 33% and €1,270 exemption (revenue.ie) |
| Wrappers | none with API access |
| Reporting | Form 11, self-assessment per disposal; about €200–500 for an accountant [estimate] |
| Protection | ICCL €20k [UNVERIFIED] |
| Verdict | the trend overlay is **tax-hostile**: every exit is taxed at 38% and ETF losses cannot be used |

**Israel**
| Item | Answer |
|---|---|
| API brokers | IBKR ($1 min per US order; $2 min per FX conversion); eToro (Israel appears in its fee country list); Alpaca "contact support"; **no Trading 212**; local brokers with an API [UNVERIFIED] |
| Instruments | US ETFs are allowed, but **Irish UCITS funds (CSPX; IB01 as cash proxy) are preferred**: this avoids 25% US dividend withholding and the $60k estate-tax exposure, since Israel has no estate treaty |
| Tax | 25% on real gain; for foreign-currency assets the exchange rate is the "index", so FX gains are effectively untaxed. 3% surtax plus an extra 2% on capital income above ILS 721,560 (2026). No estate tax. (PwC Israel) |
| Reporting | a foreign broker withholds nothing, so an annual return is needed; accountant ₪1,000–3,000 [estimate] |
| Protection | SIPC via IBKR LLC [entity UNVERIFIED] |

**Canada**
| Item | Answer |
|---|---|
| API brokers | IBKR Canada (CAD 1 min = 1% of a C$100 order); **Alpaca excluded**; no Trading 212; Questrade and Wealthsimple have no retail trading API [UNVERIFIED] |
| Instruments | XEQT/VFV or US ETFs (US ETFs best inside an RRSP) |
| Tax | half of a capital gain is taxable (PwC); superficial-loss rule, 30 days [UNVERIFIED — canada.ca blocked]; no estate tax |
| Wrappers | TFSA/RRSP at IBKR [UNVERIFIED that the API works for them] |
| Reporting | T5008; track ACB yourself; T1135 if foreign cost exceeds C$100k [UNVERIFIED] |
| Protection | CIPF [UNVERIFIED] |

**Australia**
| Item | Answer |
|---|---|
| API brokers | Trading 212 AU (API eligibility of AU accounts [UNVERIFIED]); IBKR AU; eToro |
| Instruments | VAS/IVV; AAA or BILL as cash proxy; US ETFs allowed |
| Tax | 50% CGT discount after 12 months until 30 June 2027, then indexation (PwC); ATO wash-sale ruling TR 2008/1 [UNVERIFIED] |
| Wrappers | super: only an SMSF could automate, at high cost |
| Protection | no compensation scheme; disputes go to AFCA |

**India**
| Item | Answer |
|---|---|
| API brokers | Zerodha Kite Personal (free; manual daily login); IBKR under LRS; Alpaca [UNVERIFIED] |
| Instruments | NIFTYBEES + LIQUIDBEES domestically; foreign ETFs via LRS (US$250k/yr; 20% TCS above ₹10 lakh [UNVERIFIED]) |
| Tax | foreign ETF: 12.5% if held over 24 months, otherwise slab rate; listed domestic ETF: 12.5% above ₹1.25 lakh after 12 months (PwC India), STCG 20% [UNVERIFIED]; no estate treaty |
| Reporting | Schedule FA plus Form 67; CA fee ₹3–10k [estimate] |
| Charges | DP charge about ₹15 per sell [UNVERIFIED], which is 15% of a ₹100 sale |
| Protection | exchange investor protection fund; SEBI SCORES / SMART ODR |

## Cross-country summary: cheapest viable path
| Country | (a) Paper | (b) $1–100 live test | (c) $10k+ |
|---|---|---|---|
| US | Alpaca paper | Alpaca, ACH ($1 round trip ≈ $0.03 in rounding fees) | Alpaca or Public; Roth IRA via Public/IBKR |
| UK | Trading 212 demo API | Trading 212 ISA (free deposit and withdrawal) | Trading 212 ISA up to the £20k limit [UNVERIFIED], IBKR beyond |
| DE / FR / NL / IE | Trading 212 demo | Trading 212 EU GmbH, EUR lines | Trading 212 or IBKR IE (0.05%) |
| IL | Alpaca paper (logic only) | **Not economical: skip live, use paper** ($2 FX min + $1 commission + wire fees) | IBKR with Irish UCITS |
| CA | Alpaca paper (logic only) or IBKR trial | **Skip live** (CAD 1 min per trade) | IBKR Canada, TFSA |
| AU | Trading 212 demo | Trading 212 AU if its API is enabled for AU accounts | IBKR AU or Trading 212 |
| IN | local simulator plus Kite read-only | ₹10k+ in Nifty ETFs via Kite; foreign exposure not economical | Kite (domestic) + IBKR via LRS |

## Recommended broker-adapter interface
- `capabilities()` returns: notional orders supported (Alpaca yes, eToro yes, Trading 212 **no**), fractional, idempotency key supported, has quotes (Trading 212 **no**), account currency, rate limits, paper base URL.
- Market and reference data:
  - `get_clock()` / `is_open(exchange)`
  - `resolve_instrument(symbol)` returns the broker id (Trading 212 `VWCE..._EQ`, eToro `instrumentId`), currency, min qty/value and whether it is fractionable
  - `get_price(symbol)`, with external data as fallback
- Account state: `get_account()` (cash, equity, currency) and `get_positions()`.
- Orders:
  - `submit_market_order(symbol, side, qty=None, notional=None, client_id)`. The adapter converts notional to qty where needed.
  - Idempotency: before any retry, check open and recent orders by `client_id`, because Trading 212 orders are non-idempotent.
  - `get_order(id)`, `list_open_orders()`, `cancel_order(id)`.
- History and tax: `get_fills(since)` exports tax lots to a per-country tax module.
- Per-country config: equity and cash instruments, wash-sale window, long-term holding period, allowance, the fee model (min commission, FX %, withdrawal fee), and a flag for whether live trading is economical below $X.
- Ship a `LocalSimBroker` that implements the same interface, for countries with no paper API (India, Canada).

## CLAIMS

- **[C1] (high)** Alpaca does not accept Canadian residents for live accounts; for other countries its published answer is 'contact support'; non-US residents may fund with as little as $1 and sign a W-8BEN; UK residents are given as eligible.
  - evidence: Alpaca Learn FAQ (updated 2026-03-11): 'residents of Canada are not currently eligible to open an account'; support page dated Feb 2026 says contact support.
  - sources: https://alpaca.markets/learn/live-trading-account-non-us, https://alpaca.markets/support/countries-alpaca-is-available
- **[C2] (high)** Alpaca fee schedule (revised 2026-09-17): international outbound wire $35, domestic outbound wire $15, local-currency transfers 1.5% conversion (max $40), ACH return $25; SEC $0.0000206×value and FINRA TAF $0.000195/share on sales, CAT $0.000003/share; each fee type rounded up to $0.01 per day.
  - evidence: Raw text extracted from the PDF with pypdf. The WebFetch summary misreported these numbers ($15 intl, 0.25% FX).
  - sources: https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf
- **[C3] (high)** Trading 212 Public API is beta, only for Invest and Stocks ISA accounts (not SIPP), has demo and live environments, sizes orders by quantity only (value orders not supported), executes only in the primary account currency, has a non-idempotent market-order endpoint, has deprecated pies endpoints and no market-data/quote endpoint.
  - evidence: OpenAPI spec paths list and descriptions; help-centre article on API keys.
  - sources: https://docs.trading212.com/_spec/api.json, https://helpcentre.trading212.com/hc/en-us/articles/14584770928157-Trading-212-API-key
- **[C4] (high)** Trading 212 serves UK (UK Ltd), DE/NL/FR/IE and others (EU GmbH, BaFin) and Australia (AU Pty), but not US, Canada, Israel or India. Invest/ISA has 0 commission, 0.15% FX fee, free bank deposits, 0.7% card fee after 2,000 GBP/EUR, free withdrawals, no inactivity fee. It auto-withholds German tax for German residents.
  - evidence: Help-centre articles updated Aug–Sep 2026, fetched via the Zendesk API.
  - sources: https://helpcentre.trading212.com/hc/en-us/articles/12933782261917-What-are-the-supported-countries, https://helpcentre.trading212.com/hc/en-us/articles/11471996799517-What-are-the-fees-in-the-Invest-ISAs-and-SIPP, https://helpcentre.trading212.com/hc/en-us/articles/360007139838-What-are-the-fees-for-funding-my-account, https://helpcentre.trading212.com/hc/en-us/articles/24308101760029-How-am-I-taxed
- **[C5] (high)** IBKR Lite ($0 US stocks/ETFs) is for US residents only. IBKR Pro Fixed is $0.005/share, min $1, max 1% of trade value; fractional trades cost the greater of 1% or $0.01. European Tiered is 0.05%, min EUR 1.25 (Fixed min EUR 3). FX conversion is 0.20 bp, min USD 2. Two free withdrawals per month.
  - evidence: IBKR pricing pages (raw HTML text).
  - sources: https://www.interactivebrokers.com/en/pricing/commissions-stocks.php, https://www.interactivebrokers.co.uk/en/pricing/commissions-stocks-europe.php, https://www.interactivebrokers.com/en/pricing/commissions-spot-currencies.php, https://www.interactivebrokers.com/en/pricing/other-fees.php
- **[C6] (medium)** EEA and UK retail clients cannot buy US-listed ETFs lacking a KID (IBKR blocks them). The UK CCI regime took effect 6 April 2026, with a transition to 7–8 June 2027, and applies to overseas distributors even if not FCA-authorised. In practice US ETFs remain unavailable to UK retail.
  - evidence: IBKR PRIIPs FAQ; FCA PS25/20; K&L Gates 2026-09-04 quoting the regime scope; edale.co blog on the 'OFR wall'.
  - sources: https://www.interactivebrokers.com/lib/cstools/faq/#/content/1136192471, https://www.fca.org.uk/publications/policy-statements/ps25-20-supporting-informed-decision-making-final-rules-consumer-composite-investments, https://www.klgates.com/thought-leadership/UK-Retail-Product-Disclosure-Regime-for-Consumer-Composite-Investments-From-UCITS-KIIDs-and-PRIIPs-KIDs-to-CCI-Product-Summaries-9-4-2026, https://edale.co/us-uk-etf-kid-cci-reporting/
- **[C7] (high)** Ireland: the exit-tax rate on investment-undertaking gains for individuals was 41% for 2015–2025 and is 38% on or after 1 January 2026. From 1 January 2022 US-domiciled ETFs are no longer automatically treated as ordinary shares (the 8-year deemed-disposal clock counted from 2022). CGT on ordinary gains is 33% with a EUR 1,270 exemption.
  - evidence: Revenue Tax and Duty Manuals 27-01A-02 (rate table) and 27-01A-03 (last reviewed May 2025); revenue.ie CGT page.
  - sources: https://www.revenue.ie/en/tax-professionals/tdm/income-tax-capital-gains-tax-corporation-tax/part-27/27-01a-02.pdf, https://www.revenue.ie/en/tax-professionals/tdm/income-tax-capital-gains-tax-corporation-tax/part-27/27-01a-03.pdf, https://www.revenue.ie/en/gains-gifts-and-inheritance/transfering-an-asset/how-to-calculate-cgt.aspx
- **[C8] (high)** France's flat tax on securities gains is 31.4% (12.8% income tax + 18.6% social levies). UK CGT is 18%/24% with a £3,000 allowance and a 30-day bed-and-breakfast matching rule.
  - evidence: service-public F21618 (checked 2026-04-15) and F2329 (CSG 10.6% + CRDS 0.5% + 7.5% = 18.6%); gov.uk CGT rates/allowances; HMRC CG51560.
  - sources: https://www.service-public.gouv.fr/particuliers/vosdroits/F21618, https://www.service-public.gouv.fr/particuliers/vosdroits/F2329, https://www.gov.uk/capital-gains-tax/rates, https://www.gov.uk/capital-gains-tax/allowances, https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
- **[C9] (high)** German investment-fund taxation: 25% flat tax (§32d EStG, plus Soli), 30% partial exemption for equity funds (§20 InvStG), Vorabpauschale based on 70% of the Basiszins (§18 InvStG), EUR 1,000 saver allowance (§20(9) EStG).
  - evidence: gesetze-im-internet.de statute text.
  - sources: https://www.gesetze-im-internet.de/estg/__32d.html, https://www.gesetze-im-internet.de/invstg_2018/__20.html, https://www.gesetze-im-internet.de/invstg_2018/__18.html, https://www.gesetze-im-internet.de/estg/__20.html
- **[C10] (medium)** US treaty withholding on portfolio dividends is 15% for residents of AU, CA, FR, DE, IE, NL and UK, 25% for Israel and India, and 30% without a treaty. Nonresident non-citizens must file a US estate-tax return if US-situs assets exceed $60,000.
  - evidence: PwC treaty table (secondary but reputable); IRS page on nonresident estate returns.
  - sources: https://taxsummaries.pwc.com/united-states/corporate/withholding-taxes, https://www.irs.gov/individuals/international-taxpayers/some-nonresidents-with-us-assets-must-file-estate-tax-returns
- **[C11] (medium)** Israel taxes real gains on securities at 25% (30% for 10%+ holders); for foreign-currency assets the exchange rate is deemed the index. A 3% surtax plus an extra 2% applies to capital income above ILS 721,560 (2026). Israel has no estate tax.
  - evidence: PwC Worldwide Tax Summaries, Israel individual pages (secondary; the Israeli Tax Authority page was not reachable).
  - sources: https://taxsummaries.pwc.com/israel/individual/income-determination, https://taxsummaries.pwc.com/israel/individual/taxes-on-personal-income, https://taxsummaries.pwc.com/israel/individual/other-taxes
- **[C12] (medium)** Australia: a 50% CGT discount for assets held 12+ months applies to disposals up to 30 June 2027 and is replaced by cost-base indexation for gains accruing from 1 July 2027. Canada: half of a capital gain is taxable.
  - evidence: PwC Australia and Canada individual income-determination pages (secondary; ATO and canada.ca were blocked). The Australian change is surprising and should be confirmed with the ATO.
  - sources: https://taxsummaries.pwc.com/australia/individual/income-determination, https://taxsummaries.pwc.com/canada/individual/income-determination
- **[C13] (high)** Saxo OpenAPI requires manual logon for retail clients (no certificate-based auth). A SIM account can trade only FX unless linked to a funded live account, and an unlinked SIM expires after 20 days. eToro's public API has demo and real endpoints, needs a verified account, and supports amount-based orders. eToro charges 0 commission on ETFs, $5 per withdrawal from a USD account and a $30 minimum withdrawal.
  - evidence: Saxo OpenAPI help-centre articles; eToro API docs and fees page.
  - sources: https://openapi.help.saxo/hc/en-us/articles/4416637197457-Can-Certificate-Based-Authentication-CBA-be-enabled-for-my-app, https://openapi.help.saxo/hc/en-us/articles/4416934146449-How-do-I-connect-a-Live-account-to-a-SIM-Demo-account, https://api-portal.etoro.com/core/guides/market-orders.md, https://www.etoro.com/trading/fees/
- **[C14] (high)** India's Zerodha Kite Connect Personal API is free (the data tier is ₹500/month), but access tokens expire at 6 AM the next day as a regulatory requirement, so a human login is needed on each trading day. Public.com's API is available to all members, is commission-free and can trade IRA accounts.
  - evidence: kite.trade pricing and docs; public.com/api page.
  - sources: https://kite.trade/, https://kite.trade/docs/connect/v3/user/, https://public.com/api

## RECOMMENDATIONS

- Build the broker layer as an adapter interface now. Minimum operations: capabilities, clock/is_open, resolve_instrument, get_price, get_account, get_positions, submit_market_order (qty or notional, client_id), get_order, list_open_orders, cancel_order, get_fills. Implement AlpacaAdapter, Trading212Adapter and LocalSimBroker first; add IBKR later for CA, IL, IN-via-LRS and $10k+ EU accounts.
- Trading212Adapter must convert notional to quantity using an external price, because the API has no quote endpoint and no value orders. It must also check pending and historical orders before any retry, because market orders are non-idempotent. Do not use the deprecated pies endpoints.
- Add a per-country config file: equity and cash instruments (US: VTI/BIL; UK: GBP-line UCITS in an ISA; EU: VWCE/XEON in EUR; IL: CSPX/IB01 UCITS via IBKR; CA: XEQT/CASH or US ETFs in an RRSP; AU: VAS/AAA; IN: NIFTYBEES/LIQUIDBEES), wash-sale window, long-term holding period, annual allowance, fee model (min commission, FX %, withdrawal fee), and a 'live_min_economic_balance' threshold.
- Default non-US users to Irish-domiciled UCITS funds even where US ETFs are legal (IL, CA outside an RRSP, AU, IN). This avoids 25–30% US dividend withholding and US estate-tax exposure above $60k.
- Gate the trend overlay on tax regime. Enable it by default only in tax-free wrappers (ISA, Roth IRA, TFSA) and the Netherlands (Box 3, no tax on switching). Disable it or show a warning for Ireland (38% exit tax per exit, no ETF loss relief), Australia and India (loss of long-holding concessions; about 1.6 pp/yr modeled drag), and US taxable accounts (about 1 pp/yr). The overlay must beat these drags after tax before it is enabled.
- For the $1–$100 live test, allow only zero-fixed-cost paths: Alpaca via ACH (US), and Trading 212 Invest/ISA with same-currency instruments (UK/EU, AU if API-enabled). For Canada, Israel, and non-US Alpaca users who would need wires, show 'not economical: skip live, use paper'. Alpaca's $35 outbound international wire and IBKR's $2 minimum FX charge exceed any plausible profit on $100.
- Add a tax-lot export (CSV with per-trade local-currency values at trade-date FX), since most non-US paths need self-assessment. Budget reporting time or accountant fees as a running cost in the go/no-go test; in IE, IL and IN an accountant fee alone can exceed profit on accounts under about $5–10k.
- Before shipping country defaults, verify the UNVERIFIED items: Alpaca eligibility for IL/IN/DE/FR/NL/IE and whether it blocks US ETFs for UK/EU residents; Trading 212 minimum order value and AU API eligibility; IBKR trial-account API access; the Australian 1 July 2027 CGT change; Irish treatment of US ETFs post-2022 (TDM 27-04-01); the French Form 3916 obligation for Trading 212 EU GmbH accounts.

## OPEN QUESTIONS

- Does Alpaca block or restrict US-ETF purchases for UK or EU residents, and which of IL, IN, DE, FR, NL, IE are currently accepted? Its public answer is only 'contact support'.
- Is the Trading 212 API enabled for Trading 212 AU Invest accounts, and what is the exact minimum order value (quantity × price) the API accepts for fractional ETF orders?
- Does the IBKR free-trial paper account (no funding) support TWS/Web API access, or does API paper trading require a funded live account?
- Will UK CCI rules from 8 June 2027 make Alpaca (as an overseas distributor) stop offering US ETFs to UK residents?
- Is the Australian replacement of the 50% CGT discount with indexation from 1 July 2027 enacted law? Only PwC reports it; the ATO page was blocked.
- What does Ireland's TDM 27-04-01 say about VOO/VTI? Does it confirm equivalent-offshore-fund treatment (38% exit-tax style and deemed disposal)?
- Which estate-tax treaties give the UK, DE, FR, NL, IE, AU and CA residents relief above the $60k threshold? The IRS treaty list page returned 404.
- Current eToro FX conversion fee and minimum trade size by residency, and which countries can use its public API.
- India: exact current TCS rate and threshold under LRS, the Zerodha DP charge per sell, STT on ETF units, and whether SEBI's retail-algo framework requires registration for a once-a-month API order.

## VERIFIER VERDICTS

- **[C1] CONFIRMED** Alpaca does not accept Canadian residents for live accounts; for other countries its published answer is 'contact support'; non-US residents may fund with as little as $1 and sign a W-8BEN; UK residents are given as eligible.
  - reasoning: Raw page text: 'This blog was last updated on March 11th, 2026' ... 'residents of Canada are not currently eligible to open an account. To check if your country is supported, please contact our team'. It also says 'Non US users can fund their accounts with as little as $1 after approval', gives 'A UK resident who is an Indian citizen may open a live account while residing in the UK' and a Portuguese example, and says 'If you are a non US tax resident, you will complete a W 8BEN form during onboarding.' The support page is dated 'February 2026' and only says to contact support. Extra caveats: the page says 'Funding options may vary depending on your country of residence', and 'the Pattern Day Trader rule applies to accounts at Alpaca, regardless of whether the account holder is a non US resident.' The same page also says '195+ countries' are listed at signup, but appearing in the signup dropdown does not mean live eligibility.
- **[C2] CONFIRMED** Alpaca fee schedule (revised 2026-09-17): international outbound wire $35, domestic outbound wire $15, local-currency transfers 1.5% conversion (max $40), ACH return $25; SEC $0.0000206×value and FINRA TAF $0.000195/share on sales, CAT $0.000003/share; each fee type rounded up to $0.01 per day.
  - reasoning: I extracted the PDF myself with pypdf. It shows 'ACH Return Fee $25', 'Domestic Wire Transfers (Outbound) $15', 'International Wire Transfers (Outbound) $35', 'Local Currency Transfers (Inbound and Outbound) 1.5% conversion fee * Max of $40 USD', SEC $0.0000206 × trade value on sells, TAF $0.000195/share (max $9.79), and CAT $0.000003 per executed equivalent share on buys and sells. It also says 'Each fee type is aggregated separately at the daily, per-account level... rounded up to the nearest cent' and 'Revised on September 17, 2026'. The $1 round-trip arithmetic holds. Same-day: CAT $0.01 + SEC $0.01 + TAF $0.01 = $0.03. Separate days: buy-day CAT $0.01 + sell-day $0.03 = $0.04. So 3–4% of a $1 trade. On a $10k sale the SEC fee is 10,000 × 0.0000206 = $0.206, plus TAF and CAT of about $0.01 each, so about $0.22–0.23. Two things the research left out. (a) The 'Local Currency Transfers (Inbound and Outbound)' line contradicts the summary's statement that international users can fund only in USD, which rests on a 2022 Rapyd note. (b) There are other fees a tiny account could hit: 'Failure to Offboard ... $10 quarterly', ADR pass-through fees of $0.01–0.05/share, and $25 outbound ACATS. No inactivity fee is listed, which is correct.
- **[C3] CONFIRMED** Trading 212 Public API is beta, only for Invest and Stocks ISA accounts (not SIPP), has demo and live environments, sizes orders by quantity only (value orders not supported), executes only in the primary account currency, has a non-idempotent market-order endpoint, has deprecated pies endpoints and no market-data/quote endpoint.
  - reasoning: I downloaded the spec. It says 'This API is currently in **beta**' and 'enabled and usable only for **Invest and Stocks ISA** account types', with servers demo.trading212.com and live.trading212.com. On value orders: 'Placing orders by value is not currently supported via the API'. On currency: 'Orders can be executed only in the **primary account currency**' and 'Multi-currency accounts are not currently supported'. The market, limit and stop endpoints each say 'In this beta version, this endpoint is **not idempotent**'. All six /pies endpoints have deprecated=true. There is no quote endpoint. The help centre (updated 2026-09-23) says 'not currently available for SIPP accounts'. Nuances that matter for the adapter design: (1) the MarketRequest schema has only ticker, quantity and extendedHours. There is **no client-order-id field**, so the recommended client_id idempotency cannot be sent to Trading 212 and can only be approximated by reconciling against orders and history. (2) The positions endpoint returns currentPrice for held instruments, so 'no price at all' is slightly overstated, but nothing gives a price for an instrument you do not hold. (3) Limit and stop orders are limited to 1 request per 2 s, and pending-orders and account summary to 1 per 5 s. (4) Sells use negative quantity.
- **[C4] CONFIRMED** Trading 212 serves UK (UK Ltd), DE/NL/FR/IE and others (EU GmbH, BaFin) and Australia (AU Pty), but not US, Canada, Israel or India. Invest/ISA has 0 commission, 0.15% FX fee, free bank deposits, 0.7% card fee after 2,000 GBP/EUR, free withdrawals, no inactivity fee. It auto-withholds German tax for German residents.
  - reasoning: I fetched the articles through the Zendesk API. The entities article (updated 2026-09-26) lists UK Ltd (UK and others), Markets Ltd (CY, IT, PL, etc.), AU PTY (Australia), and EU GmbH (DE, NL, FR, IE, ES, PT, CH and others). The US, Canada, Israel and India are absent. The fees article (updated 2026-09-26) says 'FX fee: 0.15% Trading commission: Free Custody Fee: Free'. The funding article (updated 2026-09-29) says card and similar methods are fee-free up to 2,000 GBP/EUR cumulative, then 0.7%, bank transfers are free, and 'all withdrawals remain free'. The tax article (2026-09-03) confirms automatic German withholding at 25% + Soli (+ church tax). Caveats: automatic withholding 'applies only to transactions starting from January 5th, 2026' and only for German tax residents under the EU entity. Exchange pass-through fees still apply, such as UK stamp duty 0.5% on LSE shares (not ETFs), SEC and FINRA fees on US sells, and the French FTT. I did not verify the no-inactivity-fee point on these pages, but the fees article says FX is 'the only fee'.
- **[C5] CONFIRMED** IBKR Lite ($0 US stocks/ETFs) is for US residents only. IBKR Pro Fixed is $0.005/share, min $1, max 1% of trade value; fractional trades cost the greater of 1% or $0.01. European Tiered is 0.05%, min EUR 1.25 (Fixed min EUR 3). FX conversion is 0.20 bp, min USD 2. Two free withdrawals per month.
  - reasoning: Raw HTML text confirms each figure: 'Eligibility ... US Residents Only' for Lite; Fixed USD 0.005, min USD 1.00, max 1% of trade value; Tiered USD 0.0035, min 0.35; 'For each fractional share trade, you will be charged the greater of 1% of the trade value or USD 0.01'; Germany and Netherlands Tiered 0.05%, min EUR 1.25 (fractional also EUR 1.25), Fixed smart-routed min EUR 3.00; FX 'Tier I - USD 2.00' minimum and 0.20 bp; 'IBKR allows two free withdrawal requests per calendar month'. The research then misapplies these numbers elsewhere. Because of the 1% cap, and IBKR's rule that 'In the event the calculated maximum per order is less than the minimum per order, the maximum per order will be assessed', a $1 US order costs about $0.01 and a $100 order at most $1. Canada is CAD 0.01/share, min CAD 1, but **max 0.5% of trade value**, so a C$100 order costs C$0.50, not C$1 (1%) as the Canada table says.
- **[C6] NEEDS_QUALIFICATION** EEA and UK retail clients cannot buy US-listed ETFs lacking a KID (IBKR blocks them). The UK CCI regime took effect 6 April 2026, with a transition to 7–8 June 2027, and applies to overseas distributors even if not FCA-authorised. In practice US ETFs remain unavailable to UK retail.
  - reasoning: K&L Gates confirms 'took effect on 6 April 2026', a 'transitional period until 7 June 2027', and the overseas-distributor perimeter quote, but it does not discuss US ETFs. The 'OFR wall' point comes from edale.co. WebFetch identified it as an FCA-regulated financial advisory firm (FRN 812332). It is a practitioner and marketing source, not law. The IBKR FAQ returned HTTP 403 to WebFetch, so I could not re-verify the quote. The EEA part matches widely known IBKR practice, but the UK half of that FAQ may predate the April 2026 revocation of UK PRIIPs. Web search budget was exhausted, so I could not look for UK platforms that re-enabled US ETFs after CCI.
  - corrected: EEA retail clients are blocked from US-domiciled ETFs under PRIIPs (IBKR practice; its FAQ was 403 to me). In the UK the PRIIPs KID rule was replaced by the CCI regime on 6 April 2026, with a transitional period to 7 June 2027 (K&L Gates, 2026-09-04). US ETFs still appear to be generally unavailable to UK retail, but the barrier is now mainly that they are not recognised under the Overseas Funds Regime or s272 and so cannot be promoted. That comes from an FCA-regulated adviser's marketing blog, not a regulator. The UK position is legally in flux. Whether an offshore broker such as Alpaca will sell them to UK residents is unknown.
- **[C7] CONFIRMED** Ireland: exit tax 41% for 2015–2025, 38% from 1 January 2026; from 1 January 2022 US-domiciled ETFs are no longer automatically treated as ordinary shares; CGT 33% with EUR 1,270 exemption.
  - reasoning: TDM 27-01A-02 ('Document last updated January 2026'), Table 1(a): 'Between 1 January 2015 and 31 December 2025 41%' and 'On or after 1 January 2026 38%'. TDM 27-01A-03 ('last reviewed May 2025') says the earlier confirmation about ETFs domiciled in 'the USA, the EEA or in an OECD member state ... does not apply to such investments with effect from 1 January 2022'. Where an ETF is found equivalent to an Irish ETF, the 8-year deemed disposal applies. That wording means case-by-case analysis ('where following an analysis ... it is found to be equivalent'), not automatic reclassification of every US ETF. CGT 33% / €1,270 is standard. I did not re-fetch the revenue.ie CGT page.
- **[C8] CONFIRMED** France's flat tax on securities gains is 31.4% (12.8% income tax + 18.6% social levies). UK CGT is 18%/24% with a £3,000 allowance and a 30-day bed-and-breakfast matching rule.
  - reasoning: service-public F21618 raw text: 'prélèvement forfaitaire unique au taux de 31,4 % ( 12,8 % d'impôt sur le revenu et 18,6 % de prélèvements sociaux )', 'Vérifié le 15 avril 2026'. The UK figures (18%/24% from 30 Oct 2024, £3,000 AEA, and the 30-day rule in CG51560) are standard. I did not re-fetch the gov.uk pages.
- **[C9] CONFIRMED** German investment-fund taxation: 25% flat tax plus Soli, 30% partial exemption for equity funds, Vorabpauschale on 70% of Basiszins, EUR 1,000 saver allowance.
  - reasoning: §18 InvStG: 'Multiplikation des Rücknahmepreises des Investmentanteils zu Beginn des Kalenderjahres mit 70 Prozent des Basiszinses'. §20(9) EStG: 'ein Betrag von 1 000 Euro abzuziehen (Sparer-Pauschbetrag)'. The 30% Teilfreistellung (§20(1) InvStG) and the 25% §32d rate are well established. Trading 212's tax page also states 25% + 5.5% Soli. Nuance: a money-market or cash-proxy fund such as XEON gets 0% partial exemption, so the trend overlay's cash leg is taxed at the full 26.375%.
- **[C10] CONFIRMED** US treaty portfolio dividend withholding 15% for AU, CA, FR, DE, IE, NL, UK; 25% for IL and IN; 30% non-treaty. Nonresidents must file estate return if US-situs assets exceed $60,000.
  - reasoning: The PwC page was last reviewed 04 Sep 2026. It states the 30% non-treaty rate, and its direct-dividend column (5 for most, 12.5 IL, 15 IN) matches the known treaty structure, whose portfolio rates are 15/25/25. I could not machine-extract the portfolio column itself. IRS: 'must file an estate tax return, Form 706-NA ... if the fair market value at death of the decedent's U.S.-situated assets exceeds $60,000'. Caveat: the $60k figure is a filing threshold, and tax is due above the roughly $13,000 unified credit equivalent. Treaty relief varies a lot. The UK treaty largely exempts US securities of UK domiciliaries, while older treaties such as IE and AU may give little relief. Their 'soften this' is too vague.
- **[C11] CONFIRMED** Israel taxes real gains on securities at 25% (30% for 10%+ holders); foreign-currency assets use exchange rate as index; 3% surtax plus extra 2% on capital income above ILS 721,560 (2026); no estate tax.
  - reasoning: PwC Israel (last reviewed 29 June 2026) says 'taxed at a rate of 25% for individuals. This rate is increased to 30% where the seller was a 10% or more shareholder'. It also says 'the currency exchange rate shall be deemed the index rate' and '3% surtax applies on annual taxable income exceeding ILS 721,560', plus an additional 2% on capital income above ILS 721,560 in 2026. PwC is secondary and I did not check the Israeli Tax Authority. 'No estate tax' was not on the pages fetched but is well known. The 'FX gains effectively untaxed' framing is roughly right for USD appreciation against ILS, but the gain is then measured in USD, so an ILS-denominated loss can still produce taxable real gain.
- **[C12] NEEDS_QUALIFICATION** Australia: 50% CGT discount to 30 June 2027, replaced by cost-base indexation for gains accruing from 1 July 2027. Canada: half of a capital gain is taxable.
  - reasoning: The research omitted the minimum 30% rate. That matters: its after-tax table taxes Australian buy-and-hold at 16% for 20 years, which contradicts its own statement that the discount ends in 2027. For gains accruing after July 2027, buy-and-hold is taxed at 30% or more on real (indexed) gains, so the modelled 1.57 pp/yr trend-overlay drag in Australia is badly overstated for any new investor. Status: PwC calls it law, but I could not confirm enactment against the ATO or legislation.
  - corrected: PwC Australia (last reviewed 30 June 2026) says that 'under recent law changes' the 50% discount is replaced by cost-base indexation for individuals and trusts from 1 July 2027. Post-1 July 2027 accrued gains are also 'subject to a minimum 30% tax rate'. Assets held on 30 June 2027 are deemed disposed of and reacquired at market value, with the gain deferred. Canada: one-half inclusion (PwC, 12 June 2026). ATO primary confirmation is still missing (ato.gov.au returned 403).
- **[C13] NEEDS_QUALIFICATION** Saxo OpenAPI requires manual logon for retail (no CBA); a SIM account can trade only FX unless linked to a funded live account; unlinked SIM expires after 20 days. eToro API has demo and real endpoints, needs verified account, supports amount orders; eToro 0 commission on ETFs, $5 withdrawal from USD account, $30 minimum.
  - reasoning: Saxo article bodies were fetched through the Zendesk API: CBA updated 2022-05-23, SIM linking updated 2026-09-07. eToro API portal: 'To access the API, your eToro account must be verified'. The market-orders guide confirms you can specify exactly one of 'amount', 'units' or 'contracts'. eToro orders also carry a leverage field, so the adapter must force leverage=1 to avoid CFD exposure. The eToro fees page matches the $5/$30 USD-account withdrawal figures and 'We charge zero commission for ETF trades'.
  - corrected: Saxo gives Certificate-Based Auth only to institutional partners, so retail must log on manually. After that, access and refresh tokens 'can be used to keep the session active for as long as the client app requires', and Saxo recommends re-authenticating weekly (article dated 2022). An unlinked SIM can only fetch prices for Saxo's own instruments such as simple FX crosses. The restriction is on market data, not a stated FX-only trading limit. A SIM 'cannot expire while linked', and near expiry it can be manually extended. The 20-day figure is not in the cited article. Linking requires a funded live account. The eToro points are confirmed, but stock trades cost '$1 or $2 ... when opening and closing ... depending on your country', and conversion fees 'vary depending on location, payment method, and Club level'.
- **[C14] CONFIRMED** Zerodha Kite Connect Personal API free (data tier ₹500/month); access tokens expire 6 AM next day as regulatory requirement. Public.com API available to all members, commission-free, can trade IRA accounts.
  - reasoning: kite.trade: 'Personal (Free) Full fledged order, GTT...' and 'Connect ... for ₹ 500 / month'. Kite docs: 'it'll expire at 6 AM on the next day (regulatory requirement)'. public.com/api: 'Our API is now available to all Public members—no approval required' and 'Trade through cash, margin, IRA, or business accounts'. Caveats: Public says 'There are certain restrictions placed on international accounts', so it is effectively a US option. SEBI's retail-algo framework (static-IP whitelisting and algo tagging for API orders) may further constrain running Kite orders from a cloud container. I did not verify that this session.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- The whole 10-country matrix and three-adapter build is premature. The user has not given their residency. Building and maintaining configs for 10 countries spends build and test tokens and adds surface for bugs, but only one country will be used. Ask residency first, then build one adapter and a LocalSim. That fits the user's rule that running and maintenance cost must stay below plausible profit.
- Idempotency via client_id cannot work on Trading 212. Its MarketRequest schema accepts only ticker, quantity and extendedHours, with no client-order-id field, and every order endpoint is documented as 'not idempotent'. Reconciliation by ticker, quantity and time window is heuristic and can double-fill. Only an Invest/ISA cash account avoids margin, and even there a double order can overspend and leave the portfolio unintentionally all-in. The adapter needs hard position caps, a pre-trade cash check, a daily order-count kill switch and a no-retry-on-timeout policy (query history first, alert a human if the result is ambiguous).
- Trading212Adapter depends on an external price feed, since there is no quote endpoint and no value orders. From this container Yahoo returned 429 and stooq was cut off. A stale external price can size orders wrongly, and the API is beta and can change without notice. A careful quant would require a verified, working price source and a slippage check against the fill before relying on this path.
- Defaulting non-US users to Irish UCITS is over-generalised, and the rationale overstates the benefit. Irish UCITS still suffer 15% US withholding at fund level. For treaty countries already at 15% (CA, AU, UK, EU) there is no withholding saving, and the saving is roughly 10–15 pp of about a 1.3% dividend yield, around 0.13–0.2%/yr, only for IL, IN and non-treaty residents. (1) For Canadians it is usually worse. US-listed ETFs in an RRSP are exempt from US withholding under the treaty, and in taxable accounts the direct 15% is creditable. Irish-fund withholding is not creditable, and offshore-fund property rules (s.94.1) and T1135 reporting add complexity. (2) For Australians, ASX-domiciled funds are the normal low-friction choice, and an AU–US estate-tax treaty exists. (3) For Israelis, US withholding of 25% on dividends is largely creditable against Israel's 25% dividend tax, so the main benefit is estate tax and deferral, not withholding. The recommendation should apply to IL and IN mainly, justified by estate tax, and should leave CA and AU on domestic funds.
- The trend-overlay tax-drag numbers are upper bounds, and the Australian row is outdated. The model realises all gains every year and taxes all US gains as short-term. With about 0.75 exits a year, many holding periods exceed 12 months (long-term), and whipsaw losses offset gains, so the US drag of about 1.05 pp is overstated. The Australian 1.57 pp assumes a 16% buy-and-hold rate for 20 years. PwC says the discount ends 1 July 2027 and a minimum 30% rate applies to post-2027 accrued gains, so for any new investor the buy-and-hold advantage largely disappears. More fundamentally, gating the overlay on tax is secondary. It should be enabled in any wrapper only if out-of-sample, after-cost evidence shows it beats buy-and-hold on a risk-adjusted basis. Tax-free wrappers remove a cost; they do not create an edge.
- The $1–$100 live test proves plumbing, not profitability. On Alpaca, per-day rounding of regulatory fees makes a $1 round trip cost 3–4%, so a $1 test will show a loss regardless of strategy quality. Nothing at $1–$100 is statistically informative about profit or about scaling (the user's explicit worry). The recommendation should say the live micro-test validates order routing, fills and fee accounting only. Profit evidence must come from long out-of-sample backtests with costs, plus multi-month paper trading, and scaling risk from capacity and slippage analysis.
- The Israel and Canada 'not economical, skip live' conclusions use wrong IBKR arithmetic. Pro Fixed US commissions are capped at 1% of trade value, and 'the maximum per order will be assessed' when below the minimum. So a $1 fractional order costs about $0.01 and $100 costs at most $1. IBKR Canada caps commission at 0.5% of trade value, so a C$100 order costs C$0.50, not C$1 (1%). The $2 minimum FX charge can be avoided by wiring USD from a USD-denominated bank account, which is common in Israel. The conclusion may still hold once inbound bank wire fees are included, but the reasoning should be redone with the caps.
- Tradier is presented as a $0.35/trade option without its '$50/year' inactivity fee for accounts with 'less than 2 trades per year' (Tradier pricing page). A low-turnover monthly or trend strategy can trigger it, and $0.35 on a $1–$100 order is 0.35–35%.
- The research says international Alpaca users can fund only in USD, citing a 2022 Rapyd note. The 2026-09-17 fee schedule lists 'Local Currency Transfers (Inbound and Outbound) 1.5% conversion fee, max $40'. The funding matrix for non-US Alpaca users should use the current schedule, noting 1.5% FX on the way in and out (3% round trip), which is material.
- Consumer-protection issues with recommending Alpaca to UK/EU residents: (1) UK residents buying US-domiciled ETFs that lack UK reporting-fund status may have gains taxed as offshore income gains at income-tax rates of up to 45%, not CGT. That is a serious trap, not mere 'complexity', and the research does not flag it. (2) No FSCS or FOS access; disputes go to US FINRA arbitration, and SIPC covers broker failure, not investment losses. (3) The W-8BEN must be renewed about every three years or withholding rises to 30%. (4) The PDT rule applies. (5) The CCI and PRIIPs perimeter may change after June 2027. Default UK/EU users to a locally regulated broker, such as a Trading 212 ISA/Invest account with UCITS funds, and treat Alpaca as a paper-trading sandbox only.
- India: the recommendation treats Kite as an automation path, but the daily 6 AM token expiry forces a daily manual login. SEBI's 2025–26 retail-algo framework (API order tagging and static-IP registration) is not verified, and running from an ephemeral cloud IP may be non-compliant or simply blocked. It needs verification before any build. The ₹15 DP charge per sell (15% of a ₹100 sale) also makes micro-tests uneconomic, which the research partly notes.
- Accountant and reporting costs should be compared with incremental profit over a passive ETF, not gross profit. At ₪1,000–3,000 (about $270–810) a year, the system must add at least that much alpha over buy-and-hold. At a plausible 0–1%/yr excess return, that needs roughly $27k–$81k or more, far above the research's '$5–10k' break-even, which implicitly uses the full 7% gross return.
- Saxo was dismissed partly because of the 'SIM can trade only FX' claim, which misreads the source (the restriction is on price data). The conclusion that Saxo is a poor fit for tiny unattended accounts probably still stands, because live linking needs funding and there is weekly re-auth, but the reason should be corrected.
- Legal and suitability point: an inexperienced person running an LLM-driven automated account should be told explicitly that brokers' API terms (e.g., Trading 212's mandatory API risk warning, 'no official partnerships with any third-party apps') place all liability for software errors on the account holder. API keys should be IP-restricted and read-only until live trading is justified, and the orchestrator should not frame any of these paths as validated profit engines.

## VERIFIER OVERALL

This research is above average in reliability on raw facts. Almost every broker fee, API limit, and French, Irish and German tax number I re-checked against primary sources (Alpaca fee PDF, Trading 212 OpenAPI spec and help-centre API, IBKR pricing HTML, Revenue TDMs, service-public, gesetze-im-internet) matched exactly. The researcher also correctly caught WebFetch hallucinations in the Alpaca PDF, and its UNVERIFIED flags are honest.

Weaknesses sit in the derived conclusions and recommendations, not in the quoted facts:
(1) It ignored IBKR's 1% (US) and 0.5% (Canada) commission caps, so the IL and CA small-order economics are wrong. The Canada table's 1% should be 0.5%.
(2) The Australian tax-drag row contradicts its own finding that the CGT discount ends in July 2027, and it omits the minimum 30% rate PwC reports.
(3) The Irish-UCITS-by-default recommendation overstates the withholding benefit and is wrong for Canada and questionable for Australia.
(4) The Saxo SIM claim misreads the source.
(5) 'Alpaca funds USD only' is contradicted by the current fee schedule.
(6) The trend tax-drag model is an upper bound. It assumes full annual realisation and all-short-term gains in the US.
(7) The UK status of US ETFs rests partly on an adviser's marketing blog and is legally in flux. The UK offshore-reporting-fund tax trap for Alpaca users is missing.
(8) Tradier's $50/yr inactivity fee is omitted.

The orchestrator should:
- Trust the fee and API-limit facts in C1–C5, C7–C9, C11 and C14.
- Weight down the Australian and US drag magnitudes, the Irish UCITS default, and the IL/CA 'skip live' arithmetic.
- Treat the adapter design's client_id idempotency as infeasible on Trading 212.
- Above all, not build a 10-country matrix before learning the user's residency.

The $1 live test should be framed only as a plumbing check. It cannot evidence profitability or scaling safety.

Limitations of this check: my web-search budget was exhausted, so I could not search for contrary evidence on UK CCI practice, Australian enactment, or SEBI algo rules. The ATO (403) and the IBKR FAQ (403) could not be accessed.
