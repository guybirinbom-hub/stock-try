#!/usr/bin/env python
"""Run every backtest, validation test and cross-check; write results/.

Usage (from the repository root):
    .venv/bin/python scripts/run_backtests.py [--results-dir results] [--ledger results/trial_ledger.json]

Works from the local data cache (data/cache), fetching first if it is empty.
Deterministic, zero LLM calls. There is deliberately no option to enable
same-bar fills: that mode exists only inside the leakage tests.
"""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from stocktry.report.pipeline import main  # noqa: E402


def cli() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results-dir", default=str(REPO / "results"), help="output directory (default: results/)")
    ap.add_argument("--ledger", default=None, help="trial ledger path (default: <results-dir>/trial_ledger.json)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    warnings.filterwarnings("ignore", category=FutureWarning)
    main(Path(args.results_dir), Path(args.ledger) if args.ledger else None)


if __name__ == "__main__":
    cli()
