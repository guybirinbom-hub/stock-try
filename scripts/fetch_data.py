#!/usr/bin/env python
"""Fetch or refresh the price universe, T-bill yields and Fama-French factors into data/cache.

Usage (from the repository root):
    .venv/bin/python scripts/fetch_data.py            # fill missing cache entries only
    .venv/bin/python scripts/fetch_data.py --refresh  # re-download everything

Prints each series' date range, source and quality result, then the splice
validation table. Vendor data stays in data/ (gitignored) and is never committed.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from stocktry.data import fetch  # noqa: E402
from stocktry.data.universe import SPLICES, UNIVERSE, SpliceRejected, splice_bars, validate_splice  # noqa: E402


def cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("symbols", nargs="*", help="subset of symbols (default: whole universe)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    syms = [s.upper() for s in args.symbols] or list(UNIVERSE)
    print(f"{'symbol':7} {'source':10} {'first':10} {'last':10} {'rows':>6} {'divs':>5}  splits / notes")
    failures = 0
    bars = {}
    for s in syms:
        try:
            df, man = fetch.get_bars_with_manifest(s, refresh=args.refresh)
            bars[s] = df
            src = man.get("source", "?") + ("(stale)" if man.get("stale") else "")
            note = ",".join(man.get("splits", [])) or ""
            vf = UNIVERSE[s].valid_from if s in UNIVERSE else None
            if vf:
                note += f" rows before {vf} excluded (see universe.py)"
            print(f"{s:7} {src:10} {man['first_date']:10} {man['last_date']:10} {man['rows']:6d} "
                  f"{man['dividend_events']:5d}  {note}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"{s:7} FAILED: {type(e).__name__}: {e}")
    try:
        y = fetch.get_tbill_yield(refresh=args.refresh)
        print(f"{'DTB3':7} {'FRED':10} {y.index[0].date()!s:10} {y.index[-1].date()!s:10} {len(y):6d}   last {y.iloc[-1]:.2f}%")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"DTB3    FAILED: {e}")
    try:
        ff = fetch.get_ff_factors(refresh=args.refresh)
        print(f"{'FF3':7} {'French':10} {ff.index[0].date()!s:10} {ff.index[-1].date()!s:10} {len(ff):6d}   monthly")
    except Exception as e:  # noqa: BLE001
        failures += 1
        print(f"FF3     FAILED: {e}")
    print("\nSplice validation (monthly returns over the full overlap):")
    print(f"{'target':7} {'proxy':6} {'enabled':8} {'overlap':>7} {'corr':>7} {'min':>6}  result")
    for t, r in SPLICES.items():
        if r.proxy is None:
            print(f"{t:7} {'-':6} {'no':8} {'':>7} {'':>7} {'':>6}  {r.reason}")
            continue
        if t not in bars or r.proxy not in bars:
            continue
        n, c = validate_splice(bars[t]["close"], bars[r.proxy]["close"], r)
        if r.enabled:
            try:
                _, info = splice_bars(bars[t], bars[r.proxy], r)
                res = f"accepted, boundary {info.boundary}"
            except SpliceRejected as e:
                res = f"REJECTED: {e}"
        else:
            res = r.reason
        print(f"{t:7} {r.proxy:6} {'yes' if r.enabled else 'no':8} {n:7d} {c:7.4f} {r.min_corr:6.3f}  {res}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(cli())
