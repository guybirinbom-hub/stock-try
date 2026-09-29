#!/usr/bin/env python
"""Run one paper-trading rebalance cycle. Dry run by default. Zero LLM calls.

Examples
--------
Simulated broker, sample targets, $100, print the plan only::

    python scripts/paper_rebalance.py --broker sim \\
        --targets-json tests/fixtures/sample_targets.json --capital 100 --dry-run

Alpaca paper, registry strategy, plan only (needs APCA_API_KEY_ID/SECRET)::

    python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold

Alpaca paper, actually submit paper orders::

    python scripts/paper_rebalance.py --broker alpaca --strategy spy_buy_hold --no-dry-run

Live (never from CI): ``LIVE_TRADING=yes-live`` in the environment AND
``--live --i-understand-live --no-dry-run``.

Exit codes: 0 ok (including "market closed, nothing done"), 1 incomplete
rebalance, 2 guard violation, 3 kill switch / live not authorized,
4 configuration, credential or data error, 5 unexpected error during a run
(already alerted and written to the ledger).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
try:  # works without `pip install -e .`
    import stocktry  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(REPO / "src"))

from stocktry.execution.broker import BrokerError  # noqa: E402
from stocktry.execution.guards import LIMITS_OVERRIDE_ACK, GuardViolation, KillSwitchEngaged, Limits  # noqa: E402
from stocktry.execution.ledger import Ledger, default_ledger_path  # noqa: E402
from stocktry.execution.logsafe import configure_logging  # noqa: E402
from stocktry.execution.planning import PriceQuote  # noqa: E402
from stocktry.execution.runner import RunConfig, compute_due_rebalance, rebalance_once  # noqa: E402
from stocktry.execution.sessions import ET, sim_nyse_calendar  # noqa: E402
from stocktry.execution.strategy_io import (  # noqa: E402
    CoreUnavailable,
    StrategyInputs,
    inputs_from_registry,
    load_targets_file,
)

log = logging.getLogger("paper_rebalance")

EXIT_OK, EXIT_INCOMPLETE, EXIT_GUARD, EXIT_KILL, EXIT_CONFIG, EXIT_ERROR = 0, 1, 2, 3, 4, 5


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group()
    src.add_argument("--strategy", help="name in stocktry.strategies.registry.STRATEGIES")
    src.add_argument("--targets-json", type=Path, help="JSON file with targets (and optionally dated prices)")
    p.add_argument("--broker", choices=("sim", "alpaca"), default="sim")
    p.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True,
                   help="print the plan and submit nothing (default). --no-dry-run submits.")
    p.add_argument("--live", action="store_true", help="request a LIVE broker (also needs env and the flag below)")
    p.add_argument("--i-understand-live", action="store_true", help="acknowledge real-money orders")
    p.add_argument("--capital", type=float, default=100.0, help="sim only: starting account value in dollars")
    p.add_argument("--rebalance-date", type=date.fromisoformat,
                   help="sim only: simulate a run at 11:00 ET on this date (tests/demos)")
    p.add_argument("--sim-now", type=datetime.fromisoformat, help="sim only: simulated tz-aware time")
    p.add_argument("--ledger", type=Path, help="ledger JSONL path (default data/ledger/<strategy>.jsonl)")
    p.add_argument("--refresh-data", action=argparse.BooleanOptionalAction, default=None,
                   help="refetch prices (default: yes for alpaca, no for sim)")
    p.add_argument("--initial-deployment", action="store_true",
                   help="carve-out: lift daily-notional and turnover caps for one run from an all-cash account")
    p.add_argument("--corporate-action", action="append", default=[], metavar="SYMBOL",
                   help="allow a >30%% price move for SYMBOL (real split or distribution)")
    p.add_argument("--max-order-notional", type=Decimal, help="override per-order dollar cap (needs --limits-ack)")
    p.add_argument("--max-order-frac", type=Decimal, help="override per-order cap as fraction of equity")
    p.add_argument("--max-daily-notional-frac", type=Decimal, help="override daily gross cap (fraction)")
    p.add_argument("--limits-ack", default="", help=f"must equal: {LIMITS_OVERRIDE_ACK!r}")
    admin = p.add_mutually_exclusive_group()
    admin.add_argument("--harden-account", action="store_true", help="apply broker safety settings, then exit")
    admin.add_argument("--engage-kill-switch", action="store_true", help="set broker suspend_trade=true, exit")
    admin.add_argument("--release-kill-switch", metavar="CONFIRM", help="clear suspend_trade (needs the phrase)")
    admin.add_argument("--show-ledger", type=int, metavar="N", help="print the last N ledger records and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def _sim_now(args: argparse.Namespace, inputs: StrategyInputs | None) -> datetime:
    if args.sim_now is not None:
        if args.sim_now.tzinfo is None:
            raise ValueError("--sim-now must include a UTC offset, e.g. 2026-10-01T11:00:00-04:00")
        return args.sim_now
    if args.rebalance_date is not None:
        return datetime.combine(args.rebalance_date, time(11, 0), ET)
    sessions = {q.session for q in (inputs.quotes or {}).values()} if inputs and inputs.quotes else set()
    if sessions and None not in sessions:
        last = max(sessions)
        cal = sim_nyse_calendar(last, last + timedelta(days=10))
        nxt = [c.date for c in cal if c.date > last]
        return datetime.combine(nxt[0], time(11, 0), ET)
    return datetime.now(timezone.utc)


def make_sim_broker(args: argparse.Namespace, inputs: StrategyInputs):
    from stocktry.execution.simbroker import LocalSimBroker

    if not inputs.quotes:
        raise ValueError("the simulator needs prices (in the targets file, or via --strategy and the data layer)")
    prices = {s: q.close for s, q in inputs.quotes.items()}
    capital = Decimal(str(args.capital))
    positions = {}
    invested = Decimal(0)
    for sym, w in inputs.sim_initial_weights.items():
        value = (capital * Decimal(str(w))).quantize(Decimal("0.01"))
        positions[sym] = (value / Decimal(str(prices[sym]))).quantize(Decimal("0.000000001"))
        invested += positions[sym] * Decimal(str(prices[sym]))
    return LocalSimBroker(cash=capital - invested, prices=prices, positions=positions, now=_sim_now(args, inputs))


def make_alpaca_broker(args: argparse.Namespace):
    from stocktry.execution.alpaca_broker import AlpacaBroker

    return AlpacaBroker(live=args.live)


def build_limits(args: argparse.Namespace) -> Limits:
    kw = {}
    if args.max_order_notional is not None:
        kw["max_order_notional_abs"] = args.max_order_notional
    if args.max_order_frac is not None:
        kw["max_order_notional_frac"] = args.max_order_frac
    if args.max_daily_notional_frac is not None:
        kw["max_daily_notional_frac"] = args.max_daily_notional_frac
    return Limits(**kw)


def admin_action(args: argparse.Namespace) -> int:
    from stocktry.execution.killswitch import engage_broker_kill_switch, release_broker_kill_switch
    from stocktry.execution.preflight import harden_account

    if args.broker != "alpaca":
        print("admin actions need --broker alpaca")
        return EXIT_CONFIG
    broker = make_alpaca_broker(args)
    if args.harden_account:
        report = harden_account(broker)
        for k, v in report.items():
            print(f"{k:<28} {v}")
        return EXIT_OK
    if args.engage_kill_switch:
        engage_broker_kill_switch(broker)
        print("broker-side kill switch ENGAGED (suspend_trade=true); new orders are refused by Alpaca")
        return EXIT_OK
    cfg = release_broker_kill_switch(broker, args.release_kill_switch)
    print(f"broker-side kill switch released: suspend_trade={cfg.suspend_trade}")
    return EXIT_OK


def show_ledger(args: argparse.Namespace) -> int:
    name = args.strategy
    if name is None and args.targets_json is not None:
        name = json.loads(args.targets_json.read_text())["strategy"]
    path = args.ledger or (default_ledger_path(name) if name else None)
    if path is None:
        print("pass --ledger PATH or --strategy/--targets-json")
        return EXIT_CONFIG
    for rec in Ledger(path).read()[-args.show_ledger:]:
        keys = ("ts", "event", "rebalance_id", "status", "reason", "code")
        print(" ".join(f"{k}={rec[k]}" for k in keys if k in rec))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO, stream=sys.stdout, wrap_std_streams=True)
    if args.show_ledger is not None:
        return show_ledger(args)
    if args.harden_account or args.engage_kill_switch or args.release_kill_switch:
        try:
            return admin_action(args)
        except GuardViolation as gv:
            print(f"FAILED: {gv}")
            return EXIT_GUARD
        except BrokerError as exc:
            print(f"broker error: {exc}")
            return EXIT_CONFIG
    if args.strategy is None and args.targets_json is None:
        print("one of --strategy or --targets-json is required")
        return EXIT_CONFIG
    if args.broker != "sim" and (args.rebalance_date or args.sim_now):
        print("--rebalance-date/--sim-now are simulator-only; the broker calendar decides the due rebalance")
        return EXIT_CONFIG
    if args.live and args.broker != "alpaca":
        print("--live needs --broker alpaca")
        return EXIT_CONFIG
    refresh = args.refresh_data if args.refresh_data is not None else args.broker == "alpaca"

    try:
        file_inputs = load_targets_file(args.targets_json) if args.targets_json else None
        if args.broker == "sim":
            if file_inputs is None:
                # Registry strategy on the simulator: evaluate on real data first, then simulate.
                probe = _registry_inputs_for_sim(args, refresh)
                broker = make_sim_broker(args, probe)
            else:
                broker = make_sim_broker(args, file_inputs)
        else:
            broker = make_alpaca_broker(args)
        name = file_inputs.strategy if file_inputs else args.strategy
        due = compute_due_rebalance(broker, name)
        if args.rebalance_date is not None and due.rebalance_date != args.rebalance_date:
            print(f"note: {args.rebalance_date} is not a scheduled rebalance date; due rebalance is "
                  f"{due.rebalance_date} (latest first session of a month on or before it)")
        if file_inputs is not None:
            inputs = file_inputs
            if inputs.quotes is None:
                reg = inputs_from_registry_prices(inputs, due.last_completed_session, refresh)
                inputs = reg
        else:
            inputs = inputs_from_registry(args.strategy, decision_date=due.decision_date,
                                          last_session=due.last_completed_session, refresh=refresh)
    except (CoreUnavailable, KeyError, ValueError, NotImplementedError, RuntimeError, BrokerError) as exc:
        print(f"configuration/data error: {exc}")
        return EXIT_CONFIG

    print(f"strategy={inputs.strategy} broker={broker.name} dry_run={args.dry_run} "
          f"rebalance_id={due.rebalance_id} decision_date={due.decision_date} "
          f"prices_session={due.last_completed_session}")
    if inputs.note:
        print(f"note: {inputs.note}")
    if inputs.targets is None:
        print("not a rebalance month for this strategy: nothing to do")
        return EXIT_OK
    print("targets: " + (", ".join(f"{s}={w:.4f}" for s, w in sorted(inputs.targets.items())) or "(all cash)"))

    cfg = RunConfig(
        strategy=inputs.strategy,
        universe=tuple(inputs.universe),
        cash_symbol=inputs.cash_symbol,
        dry_run=args.dry_run,
        live=args.live,
        i_understand_live=args.i_understand_live,
        allow_exit_to_cash=inputs.allows_exit_to_cash,
        initial_deployment=args.initial_deployment,
        corporate_action_symbols=frozenset(args.corporate_action),
        limits=build_limits(args),
        limits_ack=args.limits_ack,
        ledger_path=args.ledger,
        local_now=(lambda: broker.now) if args.broker == "sim" else (lambda: datetime.now(timezone.utc)),
        sleep=(lambda s: None) if args.broker == "sim" else __import__("time").sleep,
    )
    try:
        result = rebalance_once(inputs.targets, broker, cfg, prices=inputs.quotes or {},
                                rebalance_id=due.rebalance_id, dividends=inputs.dividends)
    except KillSwitchEngaged as ks:
        print(f"ABORTED by kill switch: {ks}")
        return EXIT_KILL
    except GuardViolation as gv:
        print(f"BLOCKED by guard: {gv}")
        return EXIT_GUARD
    except Exception as exc:  # noqa: BLE001 - already alerted and ledgered by the runner
        print(f"ERROR during run ({type(exc).__name__}); see the log and the ledger")
        return EXIT_ERROR

    print(f"status={result.status} {result.reason}".rstrip())  # the plan itself is logged by the runner
    if result.modelled_fees:
        total = sum((Decimal(v["total"]) for v in result.modelled_fees.values()), Decimal(0))
        label = "estimated" if result.dry_run else "modelled"
        print(f"{label} Alpaca regulatory fees: ${total:.2f}")
    if result.submitted:
        print(f"submitted {len(result.submitted)} order(s)")
    if result.alerts:
        print(f"alerts: {', '.join(result.alerts)}")
    return result.exit_code


def _registry_inputs_for_sim(args: argparse.Namespace, refresh: bool) -> StrategyInputs:
    """For --strategy with the simulator: pick a simulated date, then evaluate."""
    from stocktry.execution.simbroker import LocalSimBroker
    from stocktry.execution.strategy_io import load_registry_spec

    spec = load_registry_spec(args.strategy)
    symbols = list(spec.universe) + ([spec.cash_symbol] if spec.cash_symbol else [])
    probe = LocalSimBroker(cash=1, prices={s: 1.0 for s in symbols}, now=_sim_now(args, None))
    due = compute_due_rebalance(probe, spec.name)
    return inputs_from_registry(args.strategy, decision_date=due.decision_date,
                                last_session=due.last_completed_session, refresh=refresh)


def inputs_from_registry_prices(inputs: StrategyInputs, session: date, refresh: bool) -> StrategyInputs:
    """Targets file without prices: fetch dated closes for its symbols from the data layer."""
    from dataclasses import replace

    from stocktry.execution.planning import quotes_from_frame
    from stocktry.execution.strategy_io import fetch_closes_and_dividends

    symbols = list(inputs.universe) + ([inputs.cash_symbol] if inputs.cash_symbol else [])
    frame, divs = fetch_closes_and_dividends(symbols, refresh=refresh)
    quotes: dict[str, PriceQuote] = quotes_from_frame(frame, session)
    return replace(inputs, quotes=quotes, dividends=inputs.dividends or divs)


if __name__ == "__main__":
    sys.exit(main())
