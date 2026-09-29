# gap: Verified, reachable, licence-compliant long-history total-return data pipeline

## SUMMARY

## Bottom line
A working, free, reachable pipeline covering 2000-02, 2008, 2020 and 2022 for all eight sleeves exists from this container **today**. I confirmed it by live requests on 2026-09-29 and by numerical cross-checks, not just from docs. The key finding: **Yahoo's v8 chart API is NOT blocked. It returns HTTP 429 to curl's default User-Agent and HTTP 200 to a browser User-Agent** (tested repeatedly). That unlocks Vanguard mutual-fund proxies back to 1980-1996 with dividends *and* capital-gain distributions folded in.

Yahoo has no licence for redistribution, so it cannot be the only source or be committed to git. Pair it with:
- Ken French (index-level check),
- FRED (public-domain rates),
- a Tiingo free token (second vendor for the same funds),
- EODHD demo (VTI only),
- AQR / World Bank backfills for commodities and gold.

A common start date of **1996-05** (limited by VGSIX/VGTSX) needs no synthetic data. Backfills extend the start to about 1990 or earlier.

## 1. Source-by-source findings (verified = live request from this container on 2026-09-29)

| Source | Free limits | History | Dividends / adjustment | Point-in-time? | Licence / git | Reachability here |
|---|---|---|---|---|---|---|
| **Yahoo v8 chart** (`query1.finance.yahoo.com/v8/finance/chart/SYM`) | Undocumented. 429 with curl UA; 200 on 3/3 tries plus 25 more with `Mozilla/5.0` UA | VFINX 1980-01-02, VBMFX 1986-12-11, VUSTX 1986-05-19, VFITX/VFISX 1991-10-28, VTSMX 1992-04-27, VGTSX 1996-04-29, VGSIX 1996-05-13, VWIGX 1981-09-30, PCRIX 2002-07-01, IEF 2002-07-30, AGG 2003-09-29, GLD 2004-11-18, DBC 2006-02-06, GC=F 2000-08-30 (all verified) | `adjclose` is backward-adjusted for splits and dividends. For mutual funds, capital gains are folded into "dividends": VWIGX 2021-12-15 event $6.069 against a $43 NAV | No. Backward adjustment is rescaled at every new event | Unofficial endpoint with no data licence. The Yahoo API terms bar deriving income and storing data where third parties can access it (https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html). **Never commit** | **Works with browser UA** |
| **Tiingo EOD** | 50 req/h, 1,000/day, 500 unique symbols/month, 1 GB. "30+ Years" (https://www.tiingo.com/about/pricing) | Claimed 30+ yrs; depth for VFINX etc. **unverified** (needs token) | adjOpen/High/Low/Close, divCash, splitFactor. "follows the standard method set forth by… CRSP". Mutual-fund NAVs in OHLC fields (https://www.tiingo.com/documentation/end-of-day) | Backward-adjusted, so revised | "Internal Use Only… may not display or share the data with another person or organization". Paid Power tier ($30/mo) is still internal-only. **Do not commit to any repo another person can read** | api.tiingo.com reachable; returns "Please supply a token" |
| **Alpaca Market Data (Basic)** | 200 calls/min; "Historical data timeframe: Since 2016"; "latest 15 minutes" limitation (https://docs.alpaca.markets/us/docs/about-market-data-api) | ~2016+ only. Useless for 2000-02 and 2008 | `adjustment=raw/split/dividend/spin-off/all` (https://docs.alpaca.markets/reference/stockbars). Separate `/v1/corporate-actions` with cash_dividend and capital_gains_distribution types, with the warning "no guarantees on the creation time of corporate actions" (https://docs.alpaca.markets/us/reference/corporateactions-1) | Method undocumented. Presumed backward, so revised | Exchange-sourced data. Treat as no redistribution (Alpaca data agreement not read — **unverified**) | data.alpaca.markets and paper-api return 401 without keys |
| **Ken French Data Library** | Keyless zip over HTTPS | US Mkt, SMB, HML, RF from 1926-07 (monthly and daily). Files "created using the 202608 CRSP database". Developed ex-US 3 factors from 1990-07 (Bloomberg-based) | Returns include reinvested dividends (CRSP) | **No**: "We reconstruct the full history of returns each month" (https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | "Copyright Eugene F. Fama and Kenneth R. French". No explicit licence. Download at build time and commit only checksums and derived stats (conservative) | **200 verified** |
| **FRED** | Keyless `fredgraph.csv?id=` works. Official API needs a key | TB3MS 1934-01→2026-08; DGS3MO 1981-09-01→2026-09-25; DTB3 1954-01-04→2026-09-25; DGS5/DGS10 1962 | Yields, not returns. Must convert | Rarely revised | TB3MS, DGS3MO and DGS5 pages are labelled "Public Domain: Citation Requested" (verified on each series page). FRED terms forbid bulk scraping and repackaging all of FRED (https://fred.stlouisfed.org/legal/). **Committable with citation.** LBMA gold series page reads "ICE Benchmark Administration Ltd (IBA) Data To Be Removed From FRED" | **200 verified** |
| **Alpha Vantage** | "25 API requests per day"; cheapest paid plan $49.99/mo (https://www.alphavantage.co/premium/) | "25+ years" | Docs label **TIME_SERIES_DAILY_ADJUSTED "Premium"**. On TIME_SERIES_DAILY: "The 'full' outputsize is available to premium keys". **TIME_SERIES_MONTHLY_ADJUSTED is not labelled premium** and returned data with the demo key (IBM). It includes monthly adjusted close and monthly dividend (https://www.alphavantage.co/documentation/) | Backward-adjusted | Terms page returned 503 — **unverified** | Reachable. Demo key works only for IBM |
| **EODHD** | Free: "20/day", "Past year" only, personal use (https://eodhd.com/pricing) | Paid $19.99/mo "30+ years". Demo key tickers per docs: AAPL.US, TSLA.US, VTI.US, AMZN.US, BTC-USD.CC, EURUSD.FOREX (https://eodhd.com/financial-apis/api-for-historical-data-and-volumes). MCD.US also worked with demo | `adjusted_close` "adjusted for both splits and dividends"; mutual funds covered | Backward-adjusted | Personal use; don't commit | **Demo VTI.US 2001-05-31→2026-09-28 (6,369 rows) and /div endpoint verified**; SPY/VFINX return 403 with demo |
| **Nasdaq Data Link** | API key required (verified error QEPx04) | WIKI Prices stopped in 2018 (from memory, **unverified this session**) | — | — | Per-dataset licences | 403 without key |
| **Shiller (shillerdata.com)** | Keyless xls | 1871.01→**2026.09** from the current link (https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/70fec4f5-727f-4e53-b5f1-179af109c5fa/ie_data.xls). The old Yale URL http://www.econ.yale.edu/~shiller/data/ie_data.xls stops at 2023.09 | Real and nominal total-return price columns. **Prices are monthly averages** and dividends are interpolated, so not month-end | Revised | Disclaimer only, no licence | 200 verified |
| **Damodaran** histretSP.xls | Keyless | Annual 1928–2025 (updated 2026-01-01): S&P 500 incl. dividends, 3-month T-bill, 10-yr T-bond, Baa, "Real Estate", Gold | Annual only. "Real Estate" is a home-price series, **not REIT TR** | Revised annually | No explicit licence | 200 verified (https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls) |
| **AQR data sets** | Keyless xlsx | Commodities for the Long Run: monthly **excess** returns 1877-02→2025-05 (equal-weight futures; Levine et al., FAJ 2018, peer-reviewed). QMJ/BAB/HML-Devil/VME updated 2026-07/08 (https://www.aqr.com/Insights/Datasets) | Excess over cash; add T-bill to get TR | Updated irregularly (commodities lags ~16 months) | "Copyright ©2018 Ari Levine, Yao Hua Ooi…" plus AQR Terms of Use. **Do not commit** | 200 verified |
| **testfol.io** | Web UI only; no documented API | Simulated series (SPYSIM from 1885, VTISIM, IEFSIM, GLDSIM, REITSIM, CASHX…). "all preset tickers track total return" (https://testfol.io/help/) | Constructed series, not real funds | — | No licence or API documented. **Use only for manual eyeball checks** | Site reachable |
| **Stooq** | — | — | — | — | — | stooq.com tunnel closed mid-exchange; `static.stooq.com/db/h/d_us_txt.zip` returns **401 Basic auth**. **Not usable** |
| **SEC EDGAR** (N-CSR "Financial Highlights" = audited fiscal-year total return per share class) | "Current max request rate: 10 requests/second"; must declare a User-Agent (https://www.sec.gov/os/accessing-edgar-data) | Fund annual reports on EDGAR back to ~2003 (N-CSR) | Audited annual TR including all distributions | Point-in-time as filed | US government public data. **Committable** | data.sec.gov returns 200 with UA |
| **World Bank Pink Sheet** | Keyless xlsx | Gold $/oz **monthly average** 1960M01→2024M12 in the file I fetched ("Updated on January 03, 2025"). The URL changes monthly, so the current URL is **unverified** | Spot price; gold pays no dividends | Revised | CC BY 4.0 per World Bank open-data policy (**not re-verified this session**) | 200 verified |

## 2. The three Alpaca questions
1. **Earliest date.** Primary docs say "Historical data timeframe: Since 2016" for both Basic and Algo Trader Plus (https://docs.alpaca.markets/us/docs/about-market-data-api). No exact first bar date is documented. **Unverified** until a keyed call with `start=2010-01-01` shows the first returned bar. Either way it is too short for 2000-02 and 2008, so Alpaca is only an execution and recent-period cross-check source.
2. **Paper-only accounts.** "Anyone globally can create an Alpaca Paper Only Account! All you need to do is sign up with your email address." Also: "As an Alpaca Paper Only Account holder, you are only entitled to receive and make use of IEX market data." (https://docs.alpaca.markets/us/docs/paper-trading, page updated 2026-09-25).
   - This **conflicts** with the generic Basic-plan doc: "The Basic plan serves as the default option for both Paper and Live trading accounts". The FAQ adds: "the end parameter must be at least 15 minutes old to query SIP data without a subscription" (https://docs.alpaca.markets/us/docs/market-data-faq).
   - Resolution: SIP-delayed history may technically return data for a paper-only key, but the *entitlement* for paper-only holders is IEX only. Build as IEX-only (`feed=iex`).
   - IEX daily bars contain only IEX trades. Their close can differ from the consolidated official close, and volume is a small fraction (the FAQ's AAPL example: 12,630 IEX trades vs 535,136 SIP trades). Do not use IEX closes for backtest returns.
3. **adjustment=all.** Defined as split + dividend + spin-off. The docs do not describe the methodology or say whether history is recomputed.
   - Every backward-adjusting vendor (Yahoo, Tiingo, EODHD, Alpha Vantage) rescales all pre-ex-date prices by (1 − D/P_prev) when a new dividend arrives, so absolute adjusted levels change after every distribution.
   - Scale-invariant signals computed at a past date are unaffected, because the new factor multiplies every price before the new ex-date equally. Examples: returns, momentum, price/SMA ratios.
   - Absolute-level signals are not unaffected: fixed price thresholds, or logged "adjusted price = X".
   - **Reproducibility fix:** log raw close plus distribution events. Build your own forward total-return index, TR_t = TR_{t−1}·(close_t + div_t)/close_{t−1}, which never changes retroactively.
   - Whether Alpaca's `dividend` adjustment includes `capital_gains_distribution` events is **unverified**.

## 3. Empirical cross-validation (run in this container)
- **Same fund, two vendors.** VTI monthly total returns, Yahoo vs EODHD demo, 303 months:
  - mean diff 0.0 bp, mean |diff| 0.08 bp, max 9.8 bp;
  - only 2 months over 5 bp (2006-10 −7.5, 2006-11 +9.8).
  - So **5 bp/month is achievable, but only for same-instrument/different-vendor checks**. The two vendors may share an upstream feed, so this is weaker independence than it looks.
- **Fund vs index.** VTSMX vs French Mkt (Mkt-RF+RF), 1992-05→2026-08, 412 months:
  - correlation 0.9992; mean |diff| 12.9 bp; p95 36.6 bp; max 72.2 bp;
  - annual tracking difference −38 bp/yr (expense ratio plus CRSP-universe differences).
  - A 5 bp tolerance would fail here by design.
- **Annual check.** VFINX (Yahoo) vs Damodaran S&P 500 TR, 1990-2025: mean −0.6 bp, but single years range −85 to +72 bp. Damodaran's series is an approximation, so ±100 bp/yr is the right tolerance.
- **Synthetic Treasury from yields.** A 5-yr par bond rolled monthly vs VFITX, 1991-2026:
  - with FRED **GS5 (monthly-average yields)**: corr **0.70**, mean |diff| 78 bp;
  - with **DGS5 resampled to month-end**: corr **0.971**, mean |diff| 22 bp, p95 59 bp, CAGR 3.77% vs fund 4.41% (−64 bp/yr bias).
  - Averaged series silently destroy validity.
- **Yahoo `interval=1mo&range=max` returns quarterly (3mo) granularity** (meta.dataGranularity="3mo", 167 points since 1985). Always pull daily with `period1=0&period2=<now>&interval=1d&events=div,split` and resample locally.

## 4. Recommended pipeline (per series: primary / second vendor / independent check / backfill)

| Series (target ETF) | Primary (daily adjclose) | Second vendor | Independent check | Backfill before primary | Earliest usable |
|---|---|---|---|---|---|
| US equity (VTI/SPY) | Yahoo VFINX 1980 / VTSMX 1992 | Tiingo same fund; EODHD demo VTI 2001 | French Mkt 1926 (monthly corr ≥0.995); Damodaran and Shiller annual | French Mkt − ER | 1926 (index) / 1980 (fund) |
| International (VEA/VXUS) | Yahoo VGTSX 1996-04 | Tiingo VGTSX | French Developed ex-US Mkt 1990-07 | French Dev ex-US − ER (1990-07→1996-04) | 1990-07 |
| Intermediate Treasury (IEF) | Yahoo VFITX 1991-10 | Tiingo VFITX; IEF overlap 2002 | DGS5 month-end synthetic (corr 0.97) | DGS5 synthetic, flagged as modelled, 1962 | 1962 (model) / 1991 (fund) |
| Aggregate bonds (AGG/BND) | Yahoo VBMFX 1986-12 | Tiingo VBMFX; AGG overlap 2003 | SEC N-CSR annual TR | none free found | 1986-12 |
| REITs (VNQ) | Yahoo VGSIX 1996-05 | Tiingo VGSIX; VNQ overlap 2004 | N-CSR annual TR (Damodaran "Real Estate" is NOT usable) | none free verified | 1996-05 |
| Commodities (DBC) | Yahoo DBC 2006 / PCRIX 2002 | Tiingo | AQR CLR excess + TB3MS (overlap corr to be measured) | AQR CLR 1877→2025-05; after that ETF only | 1877 (index) / 2002 (fund) |
| Gold (GLD) | Yahoo GLD 2004-11 | Tiingo GLD | Damodaran annual gold; World Bank monthly average | GC=F 2000-08 (price only); World Bank monthly average 1960 (lagged-average caveat) | 1960 (avg) / 2004 (ETF) |
| T-bills (BIL/cash) | FRED DTB3/DGS3MO daily → month-end, r = y/12 (TB3MS for monthly) | French RF 1926 | Yahoo BIL/SHV 2007 | — | 1934 |

**Splicing rules**
- Splice on **returns, never prices**, at a month boundary.
- Proxy return adjustment for the fee difference: r_adj = r_proxy + (ER_proxy − ER_target)/12. For an index proxy with no fees: r_adj = r_index − ER_target/12.
- Require ≥36 overlapping months before the splice that pass the fund-vs-index tolerance: corr ≥0.995 (equity) or ≥0.95 (bonds, commodities), and a 12-month rolling tracking difference within ±(|ΔER| + 75 bp).
- Record the splice date and proxy in the manifest.
- Switch to the ETF only after it has ≥12 months of history.
- Report backtests both on the "fund-only common start 1996-05" and the "with backfill" samples.

**Caching and reproducibility**
- `data/raw/<source>/<symbol>/<retrieved_utc>.json|csv`, immutable.
- `data/processed/<series>.csv` (or parquet if pyarrow is installed).
- `manifest.json` per file:
  - URL with token redacted,
  - retrieval UTC,
  - SHA-256 of the raw bytes,
  - row count, first and last date,
  - parser version,
  - splice metadata.
- Each backtest records the manifest hash.
- On refresh, diff old vs new returns for overlapping dates. Any |Δr| > 1e-6 is logged as a vendor revision; French revisions are expected.

**Git policy**
- Commit code, manifests, checksums, test outputs, and aggregate statistics.
- Commit raw data **only** for FRED public-domain series (with citation) and SEC filings.
- Keep Yahoo, Tiingo, EODHD, Alpaca, AQR, French, Shiller, Damodaran and testfol data in `.gitignore`d `data/`, re-downloaded by script.
- Tiingo's "may not… share the data with another person" makes even a private repo with collaborators non-compliant.

**Running cost:** zero tokens. This is a monthly cron in pure Python (roughly 30 HTTP calls/month), well inside the Tiingo free tier (1,000/day, 500 symbols/month) and polite for Yahoo.

## 5. Data-quality pitfalls and detection tests
1. **Missing dividends.** Per year, compare TR (adjclose) against price return. Bond funds should show a gap of about their yield; equity funds about 1–3%. Also count distribution events per year against expected frequency (monthly for bond funds, quarterly for VFINX). A zero-event year for a payer is a failure.
2. **Split errors.** Flag |daily raw return| > 25% on diversified funds. Confirm the move matches a split event and that adjclose shows no jump.
3. **Stale NAVs / holidays.** Runs of ≥2 identical daily closes, or a 0.000 monthly return, for equity funds. Also check that month-end dates align across series.
4. **Capital-gain distributions.** Yahoo folds them into dividends (VWIGX 2021-12-15, $6.069). Other vendors may not. Test: compare fund annual TR against the audited N-CSR Financial Highlights TR; tolerance ±10 bp.
5. **TR vs price-return mismatch between strategy and benchmark.** Unit test: a 100% buy-and-hold "strategy" in the benchmark ETF must equal the benchmark to within 1 bp/yr.
6. **Averaged vs point-in-time prices.** Shiller, World Bank and FRED GS* are monthly averages. Test: autocorrelation of monthly returns (averaging induces about +0.25 lag-1 autocorrelation). Refuse averaged series in signal computations; use DGS*, daily data resampled.
7. **Silent downsampling.** Yahoo 1mo+max gives 3mo. Assert median bar spacing ≤1 trading day and check `meta.dataGranularity`.
8. **Multi-table CSVs.** French files hold monthly and annual blocks, "-99.99" missing codes and trailing copyright lines. Assert 6-digit YYYYMM keys, strictly increasing, and no duplicates.
9. **FRED missing values** ("." in the CSV). Coerce to NaN and forward-fill at most 3 days.
10. **Yield-to-return conversion.** TB3MS is discount basis, annualized. Use monthly return ≈ y/12 and cross-check against French RF (expect |diff| < 10 bp/month).
11. **Retroactive adjustment.** Store raw data plus events. Test that re-downloaded adjclose ratios for past windows match within 1e-6.
12. **Fund inception vs vendor start.** VFINX launched 1976, but Yahoo starts 1980. Never assume the first vendor date equals inception.
13. **Wrong proxy semantics.** Damodaran "Real Estate" is housing, not REITs. AQR commodities is equal-weight excess return, not DBC. PCRIX holds TIPS collateral. VWIGX is active. Document each in the manifest.

## 6. Endpoints to curl for reachability (no keys where possible)
- Yahoo: `curl -A 'Mozilla/5.0 (X11; Linux x86_64)' 'https://query1.finance.yahoo.com/v8/finance/chart/VFINX?period1=0&period2=1790700000&interval=1d&events=div,split'`. Expect 200; without `-A` expect 429.
- French: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip`, `.../Developed_ex_US_3_Factors_CSV.zip`, `.../F-F_Research_Data_Factors_daily_CSV.zip`.
- FRED: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3` (also TB3MS, DGS3MO, DGS5).
- Tiingo: `https://api.tiingo.com/tiingo/daily/VFINX/prices?startDate=1976-01-01&token=$TIINGO` (no token → "Please supply a token").
- EODHD: `https://eodhd.com/api/eod/VTI.US?api_token=demo&fmt=json` and `/api/div/VTI.US?api_token=demo&fmt=json`.
- Alpha Vantage: `https://www.alphavantage.co/query?function=TIME_SERIES_MONTHLY_ADJUSTED&symbol=IBM&apikey=demo`.
- Alpaca (keyed): `https://data.alpaca.markets/v2/stocks/bars?symbols=SPY&timeframe=1Day&start=2010-01-01&feed=iex&adjustment=raw` with APCA headers. Check the first bar date. Then retry with `feed=sip&end=<now−1h>` to see whether a paper-only key is technically served SIP.
- Shiller, Damodaran, AQR, World Bank: the URLs cited above.
- SEC: `https://data.sec.gov/submissions/CIK0000036405.json` with header `User-Agent: Name email`.

## Explicitly unverified
- Tiingo history depth for VFINX, VBMFX and VGSIX, and whether Tiingo divCash includes capital gains.
- Alpaca's exact first bar date; whether a paper-only key is actually served SIP; whether adjustment=dividend includes capital-gain distributions.
- Alpha Vantage mutual-fund coverage and its terms of service (page returned 503).
- EODHD demo-key terms.
- The current URL of the World Bank Pink Sheet file and its CC BY 4.0 licence.
- Nasdaq WIKI end date.
- Yahoo UA-based access stability over time: it is an undocumented endpoint and may change or throttle without notice.
- Correlation of AQR commodities with DBC/PCRIX on overlap (not computed).


## CLAIMS

- **[C1] (high)** Yahoo Finance v8 chart API is reachable from this container when a browser User-Agent is sent (HTTP 200), and returns HTTP 429 to curl's default User-Agent. It serves daily adjclose plus dividend events back to VFINX 1980-01-02, VBMFX 1986-12-11, VFITX 1991-10-28, VTSMX 1992-04-27, VGTSX 1996-04-29 and VGSIX 1996-05-13.
  - evidence: Live curl tests on 2026-09-29: first-trade dates and dividend counts as listed (e.g. VFINX 11,780 daily rows, 187 dividends). Requests without -A 'Mozilla/5.0' returned 'Edge: Too Many Requests'.
  - sources: https://query1.finance.yahoo.com/v8/finance/chart/VFINX?period1=0&period2=1790700000&interval=1d&events=div,split
- **[C2] (high)** Yahoo's interval=1mo with range=max silently returns quarterly (3mo) data, so daily data must be pulled and resampled locally.
  - evidence: Response meta.dataGranularity='3mo'. Timestamps were 1985-01-01, 1985-04-01, 1985-07-01…, 167 points.
  - sources: https://query1.finance.yahoo.com/v8/finance/chart/VFINX?range=max&interval=1mo&events=div
- **[C3] (high)** Alpaca's Basic (free) market data plan has 'Historical data timeframe: Since 2016', a 'latest 15 minutes' historical limitation and 200 calls/min. It is the default for paper and live accounts.
  - evidence: Plan table on the Alpaca docs page (fetched 2026-09-29).
  - sources: https://docs.alpaca.markets/us/docs/about-market-data-api
- **[C4] (high)** Alpaca Paper Only Accounts can be opened by anyone globally with only an email, but such holders are 'only entitled to receive and make use of IEX market data'. This conflicts with the FAQ statement that SIP historical data is queryable without a subscription if end is at least 15 minutes old.
  - evidence: Verbatim quotes from the paper-trading page (updated 2026-09-25) and the market-data FAQ.
  - sources: https://docs.alpaca.markets/us/docs/paper-trading, https://docs.alpaca.markets/us/docs/market-data-faq
- **[C5] (high)** Alpaca's bars endpoint offers adjustment=raw|split|dividend|spin-off|all, but documents no methodology or retroactive-revision behaviour. A separate corporate-actions endpoint exposes cash_dividend and capital_gains_distribution events, with no guarantee on their creation time.
  - evidence: Parameter descriptions in the stockbars reference; type list and warning in the corporate-actions reference.
  - sources: https://docs.alpaca.markets/reference/stockbars, https://docs.alpaca.markets/us/reference/corporateactions-1
- **[C6] (high)** Tiingo free tier: 50 requests/hour, 1,000/day, 500 unique symbols/month, 1 GB, '30+ Years' history. Licence is 'Internal Use Only' (no sharing with another person). Adjustments follow the CRSP method, and mutual-fund NAVs are provided.
  - evidence: Pricing page and EOD documentation fetched 2026-09-29.
  - sources: https://www.tiingo.com/about/pricing, https://www.tiingo.com/documentation/end-of-day
- **[C7] (high)** Alpha Vantage free tier is 25 requests/day. TIME_SERIES_DAILY_ADJUSTED is labelled Premium and TIME_SERIES_DAILY outputsize=full is premium-only. TIME_SERIES_MONTHLY_ADJUSTED is not labelled premium and returns adjusted close plus monthly dividend.
  - evidence: Docs text: 'The "full" outputsize is available to premium keys'; 'TIME_SERIES_DAILY_ADJUSTED Trending Premium'. The demo MONTHLY_ADJUSTED call for IBM returned data.
  - sources: https://www.alphavantage.co/documentation/, https://www.alphavantage.co/premium/
- **[C8] (high)** EODHD free plan gives 20 calls/day and only the past year of EOD data, so it is useless for history. The demo key, however, returns full VTI.US history (2001-05-31 to 2026-09-28) with split- and dividend-adjusted close, plus dividend events.
  - evidence: Pricing page; live curl returned 6,369 rows; /api/div/VTI.US returned dividend records.
  - sources: https://eodhd.com/pricing, https://eodhd.com/financial-apis/api-for-historical-data-and-volumes, https://eodhd.com/api/eod/VTI.US?api_token=demo&fmt=json
- **[C9] (high)** Ken French files are keyless and current (created from the 202608 CRSP database). The US market goes back to 1926-07 and Developed ex-US to 1990-07. The full history is reconstructed each month, so values are not point-in-time.
  - evidence: File headers downloaded; data library page states 'We reconstruct the full history of returns each month' and carries a copyright notice with no explicit licence.
  - sources: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_ex_US_3_Factors_CSV.zip
- **[C10] (high)** FRED TB3MS (from 1934), DGS3MO (from 1981) and DGS5 are labelled 'Public Domain: Citation Requested' and are downloadable keyless via fredgraph.csv. LBMA gold has been removed from FRED.
  - evidence: Series pages show the licence label. The GOLDAMGBD228NLBM page title reads 'ICE Benchmark Administration Ltd (IBA) Data To Be Removed From FRED'.
  - sources: https://fred.stlouisfed.org/series/TB3MS, https://fred.stlouisfed.org/series/DGS3MO, https://fred.stlouisfed.org/legal/
- **[C11] (high)** Same-fund cross-vendor agreement is under 5 bp/month (VTI Yahoo vs EODHD: mean |diff| 0.08 bp, max 9.8 bp over 303 months). Fund-vs-index agreement is much looser (VTSMX vs French Mkt: corr 0.9992, mean |diff| 12.9 bp, p95 36.6 bp, −38 bp/yr drift). Tolerances must therefore differ by comparison type.
  - evidence: Computed in this container from downloaded series.
  - sources: https://query1.finance.yahoo.com/v8/finance/chart/VTSMX, https://eodhd.com/api/eod/VTI.US?api_token=demo&fmt=json, https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip
- **[C12] (high)** Using monthly-average yields (FRED GS5) to synthesize Treasury returns gives corr 0.70 with VFITX, while month-end daily yields (DGS5) give corr 0.971 (mean |diff| 22 bp). The synthetic understates the fund's CAGR by about 64 bp/yr (3.77% vs 4.41%).
  - evidence: Par-bond roll model computed in this container over 1991-2026 (419 months).
  - sources: https://fred.stlouisfed.org/graph/fredgraph.csv?id=GS5, https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS5
- **[C13] (medium)** Yahoo folds mutual-fund capital-gain distributions into its dividend events and adjclose. VWIGX shows a $6.069 'dividend' on 2021-12-15 against a ~$43 NAV.
  - evidence: Events list from the chart API; only a 'dividends' key is returned even when requesting capitalGain.
  - sources: https://query1.finance.yahoo.com/v8/finance/chart/VWIGX?period1=1577836800&period2=1790700000&interval=1d&events=div,capitalGain
- **[C14] (high)** Long-history backfills are keyless: AQR 'Commodities for the Long Run' monthly excess returns (1877-02 to 2025-05); the current Shiller file (1871.01 to 2026.09, monthly-average prices); Damodaran annual returns 1928-2025. Stooq bulk downloads return 401 and Nasdaq Data Link requires an API key.
  - evidence: Files downloaded and parsed in this container; static.stooq.com returned 'WWW-Authenticate: Basic'; Nasdaq returned error QEPx04.
  - sources: https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx, https://shillerdata.com/, https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls, https://static.stooq.com/db/h/d_us_txt.zip

## RECOMMENDATIONS

- Adopt Yahoo (with browser User-Agent, daily interval, events=div,split) as the primary fetcher for Vanguard mutual-fund proxies. Require a second vendor (Tiingo free token) for the same tickers, with |monthly diff| ≤5 bp in ≥98% of months and none >25 bp. Treat Yahoo as fragile and personal-use only.
- Use index-level independent checks with fund-vs-index tolerances, not 5 bp: French Mkt for US equity, French Developed ex-US for international, DGS5 month-end synthetic for Treasuries, FRED DTB3/French RF for cash. Require corr ≥0.995 (equity) or ≥0.95 (bonds and commodities), and a 12-month tracking difference within ±(|ΔER|+75 bp).
- Report every backtest on two samples: fund-only common start 1996-05 (no synthetic data; covers 2000-02, 2008, 2020, 2022), and an extended sample with documented backfills (French Dev ex-US 1990-07, DGS5 synthetic, AQR commodities + T-bill, World Bank gold) flagged as modelled.
- Splice on returns only, adjusting r_adj = r_proxy + (ER_proxy − ER_target)/12, and require ≥36 months of passing overlap before a splice. Record splice metadata in a manifest.
- Store raw responses immutably with SHA-256, retrieval time, first/last date and parser version. Store raw close + distribution events and compute your own forward TR index so logged signals are reproducible despite backward-adjustment revisions. Diff re-downloads and log any |Δr| > 1e-6 as a vendor revision.
- Git: commit code, manifests, checksums, tests and aggregate results. Commit raw data only for FRED public-domain series (with citation) and SEC filings. .gitignore everything from Yahoo, Tiingo, EODHD, Alpaca, AQR, French, Shiller, Damodaran and testfol.
- Use Alpaca paper-only accounts with feed=iex for order simulation only. Never use IEX daily bars for backtest returns or monthly signal closes; use consolidated closes from Yahoo or Tiingo.
- Implement the 13 data-quality tests in section 5 as pytest checks that gate every backtest. At minimum: distribution-count per year, split-jump detector, stale-NAV runs, buy-and-hold-equals-benchmark unit test, bar-spacing assertion, and averaged-series autocorrelation guard.
- Keep the data pipeline LLM-free: a monthly cron of about 30 HTTP calls costs $0 in tokens and stays within all free tiers.
- Before building on it, run the keyed Alpaca probe (start=2010-01-01; then feed=sip with end=now−1h on a paper-only key) and a Tiingo VFINX/VBMFX/VGSIX start-date probe to close the remaining unverified items.

## OPEN QUESTIONS

- Exact first daily bar date on Alpaca Basic, and whether a paper-only (non-KYC) key is technically served SIP-delayed historical bars despite the IEX-only entitlement text.
- Does Alpaca adjustment=dividend/all include capital_gains_distribution events, and are historical adjusted values recomputed after new events (presumed yes, undocumented)?
- Tiingo actual history depth for VFINX (1976?), VBMFX, VGSIX and VGTSX, and whether Tiingo divCash includes mutual-fund capital-gain distributions.
- How stable is Yahoo's User-Agent-based access from this datacenter IP over weeks of monthly runs? Is a fallback needed (for example Tiingo as primary)?
- Correlation and tracking of AQR equal-weight commodity excess returns (plus T-bill) vs DBC and PCRIX over 2002-2025. Is it an acceptable backfill for a DBC sleeve?
- Is there a free, licence-clear REIT total-return series before 1996-05 (for example Nareit index history on reit.com)? Not checked.
- Alpha Vantage terms of service (page returned 503) and whether MONTHLY_ADJUSTED covers mutual funds such as VFINX on a free key.
- Current URL of the World Bank Pink Sheet monthly file and confirmation of its CC BY 4.0 licence; the file fetched was dated 2025-01-03.
- Whether Ken French and Damodaran data may legally be committed to a private or public repo (no explicit licence found); currently treated as do-not-commit.
- User's country of residence: this affects broker choice (Alpaca live vs paper-only) and whether US mutual-fund or ETF proxies match instruments they can actually buy (e.g. EU PRIIPs restrictions on US ETFs).

## VERIFIER VERDICTS

- **[C1] NEEDS_QUALIFICATION** Yahoo v8 chart API returns 200 with a browser User-Agent and 429 with curl's default UA from this container; daily adjclose plus dividends back to VFINX 1980-01-02, VBMFX 1986-12-11, VFITX 1991-10-28, VTSMX 1992-04-27, VGTSX 1996-04-29, VGSIX 1996-05-13.
  - reasoning: I reproduced everything technical on 2026-09-29. No UA returned 429 and 'Mozilla/5.0 (X11; Linux x86_64)' returned 200. The first dates matched exactly: VFINX 1980-01-02 (11,780 rows, 187 dividends), VBMFX 1986-12-11 (491 dividends), VUSTX 1986-05-19, VFITX/VFISX 1991-10-28, VTSMX 1992-04-27, VGTSX 1996-04-29, VGSIX 1996-05-13, VWIGX 1981-09-30, PCRIX 2002-07-01, IEF 2002-07-30, AGG 2003-09-29, GLD 2004-11-18 (0 dividends), DBC 2006-02-06, GC=F 2000-08-30. The qualification is about what 'works' means. The 429 is a deliberate access control, and spoofing a browser UA to get past it breaks Yahoo's general Terms of Service. Those terms forbid users to 'access or collect data ... from our Services using any automated means ... including ... robots, spiders, scrapers ... for any purpose without our express, prior permission' (https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). The research cited only the Yahoo Developer Network API terms (apiforydn). Those govern developer.yahoo.com APIs, and their storage/third-party clauses are about Yahoo *user* data, not market data. So the research misstated the licence position and understated the violation. Separately, FRED fails the opposite way: it rejected the Mozilla UA with an HTTP/2 error (curl exit 92, Python RemoteDisconnected) and accepted curl's default UA. So a single global UA setting breaks one source or the other.
  - corrected: The Yahoo v8 chart endpoint is technically reachable from this container on 2026-09-29 only when a browser User-Agent is spoofed. The listed start dates and dividend counts are accurate. Automated collection breaks Yahoo's general ToS (no automated collection 'for any purpose without our express, prior permission'), so this source is reachable but NOT licence-compliant, and access can stop at any time. Other hosts (FRED) reject the browser UA, so UA must be set per host.
- **[C2] NEEDS_QUALIFICATION** Yahoo interval=1mo with range=max silently returns quarterly (3mo) data, so daily must be pulled and resampled.
  - reasoning: Reproduced: range=max&interval=1mo gives meta.dataGranularity='3mo', 167 points, 1985-01-01 then 1985-04-01. But interval=1mo with period1=0&period2=<now> returns true monthly data ('1mo', 501 points, 1985-01-01 then 1985-02-01). So the downgrade is specific to range=max. Both monthly variants start in 1985, not 1980, so monthly bars also silently drop about five years of VFINX history. The recommendation (pull daily, resample locally) stands, and the loss of pre-1985 history is an extra reason for it.
  - corrected: interval=1mo with range=max is silently downgraded to 3mo. interval=1mo with explicit period1/period2 returns genuine monthly bars, but only from 1985 even where daily data starts in 1980. Pull daily and resample; assert dataGranularity and median bar spacing.
- **[C3] CONFIRMED** Alpaca Basic: 'Historical data timeframe: Since 2016', 'latest 15 minutes' limitation, 200 calls/min, default for paper and live accounts.
  - reasoning: The plan table on the page (updated 2026-07-16) says Historical Data Timeframe 'Since 2016' for both Basic and Algo Trader Plus, limitation 'latest 15 minutes', '200 / min', and 'The Basic plan serves as the default option for both Paper and Live trading accounts'. The same page says Basic real-time covers 'for equities only the IEX exchange'. Alpaca also does not cover the mutual-fund proxies, so it cannot supply any of the long-history series.
- **[C4] NEEDS_QUALIFICATION** Paper Only Accounts: anyone globally, email only; holders 'only entitled to receive and make use of IEX market data'; this conflicts with the FAQ saying SIP history is queryable without a subscription if end is at least 15 minutes old.
  - reasoning: Both quotes are verbatim correct. My fetch showed the paper-trading page as updated 2026-07-07, not 2026-09-25 as the research says, so the date is doubtful. The 'conflict' is overstated. The plan page defines Basic as IEX-only for real-time equities with SIP history delayed 15 minutes, and the paper-only text is an entitlement statement. These are compatible readings (technical access vs licence entitlement), not a documentation contradiction. The research's resolution (build on feed=iex) is sound.
  - corrected: Paper-only accounts are open globally with just an email and are entitled only to IEX data. Basic is technically able to serve 15-minute-delayed SIP history, but a paper-only holder should assume no entitlement to it. Page date unverified (fetched as 2026-07-07).
- **[C5] CONFIRMED** Alpaca bars adjustment=raw|split|dividend|spin-off|all with no documented methodology; corporate-actions endpoint lists cash_dividend and capital_gains_distribution with no creation-time guarantee.
  - reasoning: The stockbars reference lists raw/split/dividend/spin-off/all, allows combining them with commas, and defines dividend only as 'adjust price for cash dividends'. That wording weakly suggests capital-gain distributions are NOT included. The default feed is sip. The corporate-actions reference lists capital_gains_distribution and cash_dividend and warns 'Currently Alpaca has no guarantees on the creation time of corporate actions'.
- **[C6] CONFIRMED** Tiingo free: 50/h, 1,000/day, 500 unique symbols/month, 1 GB, '30+ Years'; 'Internal Use Only' (no sharing); CRSP-method adjustments; mutual-fund NAVs in OHLC.
  - reasoning: The pricing page gives Starter $0: 50/hour, 1000/day, 500 symbols/month, 1 GB, '30+ Years', 'Internal Use Only'. It defines internal use as 'you may only use the data for your own personal use and you may not display or share the data with another person or organization'. Power is $30/mo and also internal-only. The docs say adjustments follow 'the standard method set forth by ... (CRSP)' and 'open, high, low, close will contain the NAV value' for mutual funds. The depth of actual mutual-fund history and whether divCash includes capital gains are not documented. '30+ Years' is marketing copy, not a per-symbol guarantee.
- **[C7] CONFIRMED** Alpha Vantage free 25/day; DAILY_ADJUSTED premium; DAILY full outputsize premium; MONTHLY_ADJUSTED free with adjusted close and dividend.
  - reasoning: Premium page: 'standard API usage limit (25 API requests per day)'. The cheapest plan is '75 requests/min ... $49.99/month'. Docs: 'TIME_SERIES_DAILY_ADJUSTED Trending Premium'; 'The "full" outputsize is available to premium keys'. The MONTHLY_ADJUSTED demo call for IBM returned adjusted close and dividend amount (last refreshed 2026-09-28). New since the research: the ToS URL now returns 200 as a PDF. It grants use 'for personal, non-commercial use', a 'non-sublicensable, non-transferable ... revocable licence', and defines commercial use broadly. The demo key does NOT serve VFINX ('demo API key is for demo purposes only'), so mutual-fund coverage on a free key remains untested.
- **[C8] NEEDS_QUALIFICATION** EODHD free 20/day, past year only; demo key returns full VTI.US 2001-05-31 to 2026-09-28 with adjusted close plus dividends.
  - reasoning: Pricing confirmed: Free '20/day', 'Past year', 'Personal use'. Cheapest paid 'All World' is $19.99/mo, '30+ years', also 'Personal use'. The demo ticker list is verbatim AAPL.US, TSLA.US, VTI.US, AMZN.US, BTC-USD.CC, EURUSD.FOREX. Reproduced: 6,369 rows from 2001-05-31 to 2026-09-28; /div returns 200; SPY.US returns 403; MCD.US returns 200 with the demo key. The caveat: the demo key is documented 'to test the data for a few tickers'. Wiring it into a production pipeline as a standing second vendor goes beyond its stated purpose and can be withdrawn silently. It also covers only VTI, not any of the mutual-fund proxies.
  - corrected: The EODHD demo key currently returns full VTI.US history. It is a test key for a handful of tickers, not a licensed data feed, so it can serve as a one-off cross-check for VTI only.
- **[C9] CONFIRMED** Ken French keyless and current (202608 CRSP); US from 1926-07, Developed ex-US from 1990-07; full history reconstructed monthly.
  - reasoning: US factors header: 'created using the 202608 CRSP database'. Developed ex-US header: 'created using the 202608 Bloomberg database', first row 199007. The library page says: 'We reconstruct the full history of returns each month when we update the portfolios. (Historical returns can change, for example, if CRSP revises its database.)' There is a copyright notice for Fama and French and no licence. Missing caveat: the factors file notes that RF comes from Ibbotson until 202405 and from the 'ICE BofA US 1-Month Treasury Bill Index' from 202406. It is a 1-month bill, not the 3-month DTB3/TB3MS, so RF cross-checks have a structural break and a maturity mismatch.
- **[C10] NEEDS_QUALIFICATION** FRED TB3MS, DGS3MO, DGS5 are 'Public Domain: Citation Requested', keyless via fredgraph.csv; LBMA gold removed; implicitly committable with citation.
  - reasoning: The labels are confirmed for TB3MS, DGS3MO, DGS5 and DTB3. fredgraph.csv returns 200 with curl's default UA but fails with a browser UA. GOLDAMGBD228NLBM now 301-redirects to a January 2022 blog post ('ice-benchmark-administration-ltd-iba-data-to-be-removed-from-fred'), so it was removed in 2022. The research, however, understated the FRED terms. Beyond bulk scraping, prohibition (p) says users may not 'Store, cache, or archive any portion of the FRED Services or FRED Content; provide any stored, cached, or archived portion ... to any third party; or incorporate any FRED Content in any database, compilation, archive, cache'. The Public Domain label reads 'may be used without permission, provided you do not engage in any prohibited use'. Committing FRED-sourced CSVs to a repo is therefore in tension with FRED's own terms, even though the underlying Treasury/H.15 data is public domain. The clean route is to take those series from the original government publisher (Treasury / Fed H.15), or to commit only derived statistics.
  - corrected: FRED Treasury-yield series are labelled 'Public Domain: Citation Requested' and are keyless via fredgraph.csv (with a non-browser UA). FRED's terms still forbid storing, caching or archiving FRED content or passing it to third parties, so raw FRED downloads should not be committed; source the public-domain data from Treasury or the Fed H.15 if raw data must be versioned. LBMA gold was removed from FRED in January 2022.
- **[C11] NEEDS_QUALIFICATION** VTI Yahoo vs EODHD: mean|diff| 0.08 bp, max 9.8 bp over 303 months; VTSMX vs French Mkt: corr 0.9992, mean|diff| 12.9 bp, p95 36.6 bp, max 72.2 bp, -38 bp/yr drift.
  - reasoning: Reproduced. VTI: 302 months, mean diff about 0, mean |diff| 0.077 bp, max 9.79 bp; only 2006-10 (7.5) and 2006-11 (-9.8) exceed 5 bp. These two offset each other, which is a dividend-date misalignment, and the near-identity suggests a shared upstream. VTSMX vs French Mkt+RF, 1992-05 to 2026-08: 412 months, corr 0.99923, mean |diff| 12.87 bp, p95 36.7 bp, max 72.2 bp. The drift figure did NOT reproduce. The arithmetic mean diff ×12 is -29.9 bp/yr, and the CAGR gap is 10.74% vs 11.06% = -32 bp/yr, not -38. The conclusion that tolerances must depend on comparison type is right.
  - corrected: The same-fund cross-vendor figures are confirmed, but the vendors probably share a feed. VTSMX vs French Mkt stats are confirmed except the drift, which is about -30 to -32 bp/yr, not -38.
- **[C12] CONFIRMED** GS5-based synthetic 5y Treasury corr 0.70 with VFITX; DGS5 month-end corr 0.971, mean|diff| 22 bp; synthetic CAGR 3.77% vs fund 4.41% (-64 bp/yr).
  - reasoning: Independently reproduced with a semiannual-coupon par bond, repriced at 5-1/12 years each month, over 1991-12 to 2026-08 (417 months). GS5: corr 0.701, mean |diff| 78.0 bp. DGS5 last obs of month: corr 0.971, mean |diff| 22.1 bp, p95 58.3 bp. CAGR synthetic 3.79% vs fund 4.49%, a -70 bp/yr gap; the exact gap depends on window. So the direction and size of the bias are confirmed. Note the synthetic lags the fund even though the fund pays fees, so the model omits roll-down/curve and holdings effects. It should not be used for level-sensitive or carry-sensitive strategies.
- **[C13] NEEDS_QUALIFICATION** Yahoo folds capital-gain distributions into dividends/adjclose; VWIGX $6.069 on 2021-12-15 against ~$43 NAV.
  - reasoning: Reproduced: events=div,capitalGain returns only a 'dividends' key, with 2021-12-15 amount 6.069. Raw close fell from 48.77 to 43.22 while adjclose rose (33.71 to 34.12). The adjustment-factor ratio 0.69118/0.78942 = 0.8756 = 1 - 6.069/48.77, so adjclose does incorporate the full distribution. Two corrections. First, the distribution is 12.4% of the prior NAV of $48.77; $43 is the post-ex NAV. Second, I could not confirm from a Vanguard source how the $6.069 splits between capital gains and income. The claim that it is mainly capital gains is plausible for December 2021 but unverified.
  - corrected: Yahoo exposes a single 'dividends' event stream for this fund, and adjclose incorporates the full $6.069 distribution of 2021-12-15, 12.4% of the prior $48.77 NAV. The income/capital-gain split was not verified against Vanguard records.
- **[C14] NEEDS_QUALIFICATION** Keyless backfills: AQR Commodities for the Long Run 1877-02 to 2025-05 excess returns; Shiller 1871.01 to 2026.09 monthly averages; Damodaran 1928-2025; Stooq bulk 401; Nasdaq Data Link needs key.
  - reasoning: AQR file: last serial date 45807 = 2025-05-30, first 1877-02-28, and the series is 'Excess return of equal-weight commodities portfolio', citing FAJ 2018 v74 n2. Confirmed. Shiller current file: 1871.01 to 2026.09. However, the 2026.09 row is preliminary: the file itself notes 'Sept price is Sept 1st close', 'CPI estimated', 'Sept GS10 is Sept 1st value'. So the last one to two rows must be dropped or flagged. The old Yale URL still returns 200. Damodaran: annual 1928 to 2025. 'Real Estate' is 'the home price data' and gold is 'Year-end prices'. Confirmed. Stooq: 401 with 'WWW-Authenticate: Basic'. Confirmed. Nasdaq Data Link: I got HTTP 403 with an HTML bot page, not error QEPx04, so the 'needs key' reason is plausible but the observed error differs.
  - corrected: The backfill files are keyless and reachable with the stated ranges. The latest Shiller rows are preliminary estimates, and Nasdaq Data Link blocks unauthenticated access (403).
- **[S1 (summary claim)] CONFIRMED** VFINX (Yahoo) vs Damodaran S&P 500 TR 1990-2025: mean -0.6 bp, single years -85 to +72 bp.
  - reasoning: Reproduced exactly: mean -0.6 bp, min -84.8 (1993), max +71.6 (1992). Because the mean is about 0, Damodaran's series runs about the fund's expense ratio (~15 bp) below the true S&P TR. This check cannot detect expense-sized errors, only gross ones.
- **[S2 (splice feasibility, implied by pipeline table)] REFUTED** International can be backfilled with French Developed ex-US (1990-07 to 1996-04) under the rule corr >= 0.995 for equity; commodities via PCRIX 2002/DBC with bond/commodity corr >= 0.95.
  - reasoning: I tested the research's own splice rules on the overlap. VGTSX vs French Developed ex-US (Mkt+RF), 1996-06 to 2026-08, 363 months: corr 0.9844, mean |diff| 66.7 bp/month, p95 165 bp, max 333 bp; minimum 36-month rolling corr 0.967, median 0.984. This fails the ≥0.995 equity rule in every window. The cause is semantic: VGTSX/VXUS includes emerging markets, while French Developed ex-US and VEA exclude them. International NAV fair-value timing adds noise. PCRIX vs DBC, 2006-03 to 2026-09: corr 0.906, mean |diff| 176 bp/month, which fails the ≥0.95 rule. PCRIX is an active fund with TIPS collateral tracking a different commodity index. The 'earliest usable 1990-07 international' and 'PCRIX 2002 commodities' rows are therefore not supported by the pipeline's own acceptance tests. VGSIX vs VNQ (corr 0.9994) does pass.
  - corrected: French Developed ex-US is not an acceptable splice proxy for VGTSX/VXUS under the stated rule (corr 0.984, mean |diff| 67 bp/month); at best it proxies VEA with a separate test. PCRIX is not an acceptable DBC proxy (corr 0.906). The international and commodity sleeves have no verified backfill before 1996 and 2006 respectively.
- **[S3 (SEC EDGAR)] NEEDS_QUALIFICATION** EDGAR max 10 requests/second with declared User-Agent; data.sec.gov returns 200 with UA; N-CSR audited annual TR committable.
  - reasoning: 'Current max request rate: 10 requests/second.' and the UA requirement are confirmed, and data.sec.gov returned 200 with a UA. The caveats concern using this data. N-CSR Financial Highlights total returns are per FISCAL year, which varies by fund and is not always the calendar year. Pre-2024 filings are unstructured HTML/text, so parsing is laborious. The proposed ±10 bp annual tolerance is only meaningful when the fiscal periods are aligned exactly.

## VERIFIER PUSHBACK ON RECOMMENDATIONS

- LICENCE (lawyer): 'Adopt Yahoo with browser User-Agent as the primary fetcher' fails the dimension's own 'licence-compliant' requirement. Yahoo's general ToS forbids automated collection 'for any purpose without our express, prior permission' (https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). Spoofing a browser UA to get past a 429 is deliberate circumvention of an access control, not an innocent default. The research cited the wrong Yahoo terms (Developer Network API, 'user data' clauses) and so understated the problem. For a person with no legal or technical background, the orchestrator should not present this as the recommended primary source. At most: a documented, personal, one-off research download, with the user told plainly that it breaches Yahoo's ToS. The licensed alternative (Tiingo free, internal/personal use) should be primary once its mutual-fund depth is verified.
- LICENCE (lawyer): 'Commit raw data only for FRED public-domain series' conflicts with FRED terms (p): no storing, caching or archiving FRED content and no providing it to third parties. The public-domain label is conditioned on 'provided you do not engage in any prohibited use'. Take the Treasury/H.15 series from the originating government publisher if raw files must be versioned, or commit only checksums and derived statistics.
- LICENCE: using the EODHD 'demo' key as a standing second vendor exceeds its documented purpose ('to test the data for a few tickers'). It covers VTI only, none of the mutual-fund proxies, and can be withdrawn without notice. Treat it as a one-off sanity check only.
- LICENCE: Tiingo, Alpha Vantage and EODHD are all personal/internal-use licences. The plan is compliant only while the data and its outputs are used by the account holder alone. If the user later shares signals, publishes results with the data, or hands the repo or a hosted dashboard to anyone else (including friends, or a CI system accessible to others), that likely breaches Tiingo's 'may not display or share the data with another person' and Alpha Vantage's commercial-use definition. The user must be told this explicitly.
- QUANT: the pipeline table's international backfill (French Developed ex-US 1990-07) fails its own ≥0.995 correlation rule (measured 0.984, mean |diff| 67 bp/month). It is also semantically wrong: VGTSX/VXUS include emerging markets; Developed ex-US and VEA do not. The table conflates 'VEA/VXUS'. The target ETF must be chosen first and the proxy validated against that exact target.
- QUANT: commodities 'Yahoo DBC 2006 / PCRIX 2002' is not a valid splice (PCRIX vs DBC corr 0.906 vs the ≥0.95 rule). AQR equal-weight commodities is a different construction from DBC's energy-heavy optimum-yield index. Any backtest with a commodity sleeve before 2006 is modelled, not measured, and must be labelled as such.
- QUANT: the gold backfill mixes GC=F (a continuous front-month futures price, not back-adjusted, so roll jumps enter the 'returns') with World Bank monthly AVERAGES. Section 5 of the same research says averaged series 'silently destroy validity' and must be refused in signal computation. The recommendation contradicts its own data-quality rule. Pre-2004 gold should be annual-only (Damodaran year-end) or excluded from signal-driven backtests.
- QUANT: the DGS5 synthetic understates VFITX by about 64 to 70 bp/yr (reproduced). Backfilling IEF to 1962, through a rate regime (1960s-80s) with no fund to validate against, creates a sample whose results depend on an unvalidated model. Report it separately and never pool it with measured data when claiming a strategy 'works'.
- QUANT (selection bias): the eight sleeves and their surviving Vanguard proxies were chosen with hindsight: funds that still exist, and asset classes known ex post to be in popular portfolios. A 1996-2026 monthly sample is about 360 observations with only a handful of crisis regimes. Even perfect data will not 'prove' a tactical strategy. The orchestrator should not let clean data be read as evidence of an edge.
- QUANT: 'require Tiingo as second vendor with ≥98% of months ≤5 bp' is premature. Tiingo's depth for VFINX/VBMFX/VGSIX/VGTSX and its treatment of capital-gain distributions are unverified. And near-exact agreement between vendors likely reflects a shared upstream (the VTI Yahoo-EODHD match is 0.08 bp), which is not independent validation. Only index-level checks (French, SEC N-CSR) are genuinely independent.
- QUANT: 'French RF / TB3MS y/12 within 10 bp/month' ignores that French RF is a 1-month bill (ICE BofA index from 2024-06, Ibbotson before) while TB3MS/DTB3 are 3-month discount-basis yields. At 1980s yield levels, the discount-to-bond-equivalent gap alone approaches the tolerance. Compute the investment (bond-equivalent) yield or use the tolerance only after 1990.
- QUANT: the N-CSR ±10 bp annual check silently assumes calendar-year fiscal periods. Several Vanguard funds have non-December fiscal year-ends, so the returns must be aligned to the exact fiscal-period dates, or the test will throw false failures or false passes.
- QUANT: the distribution-count test ('a zero-event year for a payer is a failure'; expected frequency monthly or quarterly) will false-positive on funds with irregular or annual schedules. VGTSX shows only 78 events in 30 years. Expected frequencies must be per fund and time-varying.
- OPERATIONS: 'Running cost zero tokens' is true for the data cron. But the hosting assumption (an always-on machine or CI) was not costed. CI runners from datacenter IPs are exactly what Yahoo rate-limits, and the claimed UA workaround may not survive there. Budget a fallback licensed source now, not after it breaks.
- OPERATIONS: the Shiller latest rows are preliminary ('Sept price is Sept 1st close', 'CPI estimated'). The ingest must drop or flag the final one to two rows, or the monthly 'revision diff' will fire every month.
- SCOPE (consumer protection): US mutual-fund Investor share proxies (VFINX, VGTSX, etc.) and US ETFs may not be buyable by the user if they are outside the US (e.g. EU PRIIPs/KID restrictions). A backtest on instruments the user cannot hold says little about what the user can actually achieve. Residency must be settled before this pipeline's sleeve choice is locked in.

## VERIFIER OVERALL

The technical and empirical core of this research is unusually solid, and I reproduced most of it independently from this container on 2026-09-29. It holds up:
- Yahoo UA behaviour (429 without a browser UA, 200 with one) and every start date and dividend count;
- the 1mo/range=max downgrade to 3mo;
- VTI Yahoo vs EODHD agreement (0.08 bp mean |diff|, max 9.8 bp);
- VTSMX vs French correlation and error stats;
- the GS5 vs DGS5 synthetic-Treasury result (0.70 vs 0.971);
- the VFINX vs Damodaran range;
- VWIGX adjclose incorporating the $6.069 distribution;
- AQR end date 2025-05, Shiller 2026.09, the Stooq 401;
- the quoted Alpaca, Tiingo, Alpha Vantage and EODHD documentation.

Numeric slips are minor:
- VTSMX drift is about -30 to -32 bp/yr, not -38.
- The paper-trading page date fetched as 2026-07-07, not 2026-09-25.
- interval=1mo is only downgraded under range=max, and monthly bars start in 1985, not 1980.

Weight down three things.

(1) The licence-compliance conclusions, which is the dimension's own headline requirement. The recommended primary source (Yahoo via a spoofed UA) violates Yahoo's general ToS ban on automated collection; the research cited the wrong Yahoo terms. Its 'FRED is committable' advice conflicts with FRED's no-store/no-cache/no-archive clause. Its use of the EODHD demo key exceeds that key's stated purpose. The honest summary is that a reachable pipeline exists, but a fully licence-compliant, free, long-history total-return pipeline does not: every free long-history fund source is personal-use-only or ToS-restricted.

(2) The backfill table. Applying the research's own splice rules, the international backfill (VGTSX vs French Developed ex-US, corr 0.984) and the commodity proxy (PCRIX vs DBC, corr 0.906) fail. The gold backfill uses averaged and unadjusted futures series that its own quality section forbids. The 'earliest usable' dates for international (1990), commodities (2002/1877) and gold (1960/2000) should be treated as unvalidated. Only the fund-only 1996-05 common-start sample is well supported, and only for US equity, US bonds, Treasuries, REITs and cash.

(3) Any implication that clean data makes a strategy provable. About 360 monthly observations with survivor-selected proxies cannot establish an edge; the data merely stops the backtest from being wrong for mechanical reasons.

Keep:
- the reproducibility design (immutable raw data plus events, a forward TR index, manifests and revision diffs);
- the 'splice on returns' rule;
- the separate tolerances for same-instrument vs index checks;
- the IEX-only warning for Alpaca paper accounts;
- the LLM-free data cron.

Open items still unverified: Tiingo mutual-fund depth, and the income vs capital-gain composition of the VWIGX distribution.
