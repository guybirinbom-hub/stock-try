# stocktry

A zero-token, deterministic harness for testing whether simple, published, low-turnover ETF strategies beat
buying and holding an index fund after costs. The decision behind it is in
[`docs/research-report.md`](docs/research-report.md); how every number is produced is in
[`docs/methodology.md`](docs/methodology.md). No language model is called at runtime.

All results are **hypothetical backtests**. Past performance does not indicate future results.

## Outcome, in two sentences

Every candidate strategy tested here (three SPY trend filters and two diversified trend allocations) was
**rejected** by the pre-registered acceptance gates, so buying and holding a broad index fund (SPY) remains the
benchmark to beat, and nothing in this repository has beaten it. The system spends **zero LLM tokens at runtime**:
the backtests, reports and paper-trading runner are deterministic Python.

## Documents

| document | what it is |
|---|---|
| [`docs/research-report.md`](docs/research-report.md) | the research, the decision and the pre-registered gates (start here) |
| [`docs/methodology.md`](docs/methodology.md) | how every number in `results/` is produced |
| [`docs/runbook-paper-trading.md`](docs/runbook-paper-trading.md) | step-by-step paper trading: simulator, Alpaca paper account, scheduling, kill switches |
| [`results/summary.md`](results/summary.md) | headline results next to SPY buy-and-hold and 60/40, and the Gate A scorecard |

## Quickstart

```bash
# Python 3.11; from the repository root
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e . --no-deps

.venv/bin/python -m pytest -q                 # offline unit tests (no network)
.venv/bin/python scripts/fetch_data.py        # fill data/cache (Yahoo, FRED DTB3, Ken French); prints ranges and splice checks
.venv/bin/python scripts/run_backtests.py     # all backtests, validation and cross-checks -> results/ (about 3 minutes)
```

`run_backtests.py` fetches data first if the cache is empty. Use `scripts/fetch_data.py --refresh` to update prices.
Vendor data lives in `data/` (gitignored) and is never committed. CI installs every dependency, transitive ones
included, from the hash-locked `requirements.lock` (`pip install --require-hashes -r requirements.lock`).

## Commands

```bash
# the whole offline test suite (a socket guard blocks network access)
.venv/bin/python -m pytest -q

# every backtest, validation test and cross-check; rewrites results/ (about 3 minutes)
.venv/bin/python scripts/run_backtests.py

# paper-trading runner on the local simulator: prints the plan, sends nothing (no keys, no network)
.venv/bin/python scripts/paper_rebalance.py --broker sim --targets-json tests/fixtures/sample_targets.json \
  --capital 100 --dry-run

# Alpaca PAPER account, dry run (prints the plan, sends nothing). Export the paper keys in your shell only,
# never in a file in this repository; prices come from Alpaca's own market data (IEX feed).
export APCA_API_KEY_ID='PK...' APCA_API_SECRET_KEY='...'
.venv/bin/python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold --dry-run
```

Read the runbook before adding `--no-dry-run`; live trading needs three separate switches and is not recommended.

## What is in `results/`

| file | contents |
|---|---|
| `summary.md` | disclosure, samples, headline metrics vs SPY and 60/40, annual returns, regime slices, 2006 split, tranching, Gate A scorecard |
| `scaling.md` | each strategy at $1 / $100 / $1k / $10k / $100k with Alpaca fees, fractional vs whole shares, skipped sub-$1 orders |
| `plateau.md` | parameter sweeps (lookback 3..18), plateau statistic, GTAA lookback x rebalance-day heatmap |
| `walkforward.md` | expanding-window walk-forward vs the published defaults |
| `bootstrap.md` | stationary block bootstrap percentiles |
| `dsr_pbo.md` | deflated Sharpe ratio with the trial-ledger N, probability of backtest overfitting |
| `leakage.md` | identity and foresight tests on real and synthetic data, one-bar shift |
| `crosscheck.md` | bt 1.2.3 and Ken French cross-checks, with failures diagnosed |
| `trial_ledger.json` | every variant ever run (the N for multiple-testing corrections) |

## Layout

```
src/stocktry/data/        fetch + cache + manifest, quality gates, universe/splices, aligned price panels
src/stocktry/backtest/    engine (signal at month-end close, fill next open), costs (Alpaca fee model), metrics, samples
src/stocktry/strategies/  buy-and-hold, 60/40, SPY trend filters, GTAA; registry.STRATEGIES
src/stocktry/validation/  walk-forward, plateau, bootstrap, ledger + DSR, PBO, leakage tests, cross-checks
src/stocktry/report/      templated markdown / CSV / PNG writers and the end-to-end pipeline
src/stocktry/execution/   paper-trading runner (see docs/runbook-paper-trading.md)
```
