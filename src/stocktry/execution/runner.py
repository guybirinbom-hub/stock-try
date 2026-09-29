"""Idempotent monthly rebalance runner. Deterministic; never calls an LLM.

``rebalance_once`` is the only entry point that can place orders. Order of
operations for one run:

1. Validate config and the submission mode (dry-run default; live needs three
   independent conditions). Check the file/env kill switches.
2. Broker clock: refuse a stale or skewed clock; work out today's session, the
   last completed session and the *due* rebalance (first session of the month).
   The ``rebalance_id`` passed in must be the due one: older missed rebalances
   are never replayed, and a newer one always wins.
3. Preflight the account (margin 1, no shorting, options 0, not blocked,
   broker-side ``suspend_trade`` off, empty crypto whitelist).
4. Market-hours gate: only between open+30 min and close-30 min of a session.
   Otherwise a non-dry run exits 0 with a log line and no action (orders are
   never queued for the next open). Execution-window gate: a rebalance is only
   traded within its first ``EXECUTION_WINDOW_SESSIONS`` sessions; later in the
   month the run is a heartbeat and does nothing.
5. Refuse to trade while any open order at the broker is not this
   rebalance's own (a manual dashboard order would land on top of the plan).
   Read existing orders for this rebalance (by client_order_id prefix): legs
   already filled are done, open orders are waited on, partially filled legs
   may get one more attempt (``a2``), nothing is ever resubmitted under an id
   that exists at the broker. New legs (attempt ``a1``) may only be opened on
   the rebalance's scheduled session (session 1 of its execution window), and
   not after a run recorded it as evaluated (``run_end`` completed,
   already_done or nothing_to_do in the local ledger, when there is one). The
   rule for later sessions depends only on the broker calendar and the broker's
   order list, not on the ledger (which an ephemeral CI runner does not keep):
   on sessions 2..N a trigger only finishes legs that already have an order
   (waits, or one ``a2`` residual) and never starts new trades on drifted
   prices, even when the first session placed no order at all. The one
   exception is ``RunConfig.late_start``, an operator's explicit confirmation
   (``--late-start``) that no run evaluated the scheduled session; it opens
   legs on a later session of the window only while no order of the rebalance
   exists at the broker and the ledger shows no evaluated run. The override
   fails closed: when the local ledger cannot be read, a ``late_start`` run is
   refused (status ``blocked``, alert ``late_start_ledger_unreadable``, exit as
   a guard violation) rather than skipping that cross-check.
6. Validate inputs (weights, whitelist, dated fresh prices, live prices,
   equity), plan, and apply plan-level hard guards. Log the full plan.
7. Dry run: stop here. Otherwise sells first; wait for terminal states (cancel
   after the poll timeout); then size buys from min(cash,
   non_marginable_buying_power) and submit. Before every order: kill-switch
   re-check, units cross-check, lookup by client_order_id and by listing, and
   (immediately before sending) a fresh broker clock: nothing is sent after
   close-30min or after the run's own deadline (``deadline_s``), however long
   waiting on fills took.
8. Reconcile against broker activities, write the ledger, alert or ping.

Every hard block raises ``GuardViolation`` after alerting and writing a ledger
record. Timing: decisions use the close of the session before the rebalance
date (the caller computes targets); sizing uses the broker's latest trade
price; freshness guards require closes dated the last completed session.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable, Mapping, Sequence

from . import planning
from .alerts import Alerter
from .broker import Broker, CalendarDay, Clock, DuplicateClientOrderId, LatestPrice, Order
from .fees import FeeFill
from .guards import (
    CASH_LIKE_SYMBOLS,
    MIN_ORDER_NOTIONAL,
    GuardViolation,
    Limits,
    check_equity,
    check_exposure_drop,
    check_initial_deployment,
    check_live_prices,
    check_market_window,
    check_min_notional_feasible,
    check_order_request,
    check_plan_caps,
    check_positions_whitelist,
    check_price_quotes,
    check_weights,
    validate_limits,
)
from .killswitch import check_kill_switches, check_submission_mode, default_kill_switch_path
from .ledger import Ledger, RunLock, default_ledger_path, inputs_hash, model_dividends, model_fees
from .planning import OrderRequest, PlannedOrder, PriceQuote, SkippedLeg, coerce_quotes, format_plan
from .preflight import run_preflight
from .sessions import (
    ET,
    EXECUTION_WINDOW_SESSIONS,
    due_rebalance_date,
    first_session_of_month,
    last_completed_session,
    make_client_order_id,
    make_rebalance_id,
    previous_session,
    rebalance_prefix,
    session_number,
    session_on,
    validate_strategy_name,
    validate_symbol,
)

__all__ = ["RunConfig", "RunResult", "DueRebalance", "compute_due_rebalance", "rebalance_once"]

log = logging.getLogger("stocktry.execution.runner")

ACTIVITY_KINDS = ("FILL", "FEE", "PTC", "DIV", "DIVNRA", "DIVFT", "DIVTXEX", "DIVCGL", "DIVCGS", "DIVROC")
MAX_ATTEMPTS_HARD = 2


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RunConfig:
    """Run configuration. Defaults are the safe ones (dry run, tight limits).

    ``universe``: the strategy's risky symbols (the order whitelist, together
    with ``cash_symbol``). ``allow_exit_to_cash``: the strategy's declaration
    that a large drop in risky exposure (e.g. a trend filter moving to cash) is
    intended. ``initial_deployment``: operator carve-out that lifts the daily
    notional and turnover caps for one run from an all-cash account.
    ``late_start``: operator confirmation that the rebalance was not evaluated
    on its scheduled session (scheduler outage, a guard block fixed since);
    lets a later session of the execution window open its legs while no order
    of the rebalance exists yet, and is refused when the local ledger cannot be
    read (its evaluated-run cross-check). Never set it in an unattended scheduler.
    ``poll_interval_s`` seconds between order-status polls, ``poll_max`` polls
    per wait before cancelling. ``cash_buffer_*``: dollars kept back for fees.
    """

    strategy: str
    universe: tuple[str, ...]
    cash_symbol: str | None = None
    dry_run: bool = True
    live: bool = False
    i_understand_live: bool = False
    allow_exit_to_cash: bool = False
    initial_deployment: bool = False
    late_start: bool = False
    corporate_action_symbols: frozenset[str] = frozenset()
    limits: Limits = field(default_factory=Limits)
    limits_ack: str = ""
    ledger_path: Path | None = None
    kill_switch_path: Path | None = None
    max_attempts: int = MAX_ATTEMPTS_HARD
    poll_interval_s: float = 2.0
    poll_max: int = 30
    cash_buffer_min: Decimal = Decimal("0.10")
    cash_buffer_frac: Decimal = Decimal("0.001")
    local_now: Callable[[], datetime] = _utc_now
    sleep: Callable[[float], None] = time.sleep
    env: Mapping[str, str] | None = None
    alerter: Alerter | None = None
    #: No order is sent later than this many seconds after the run started (keep it well below the
    #: scheduler's job timeout, so a run is never killed between a submit and its cancel).
    deadline_s: float = 480.0
    #: Where the prices came from ("alpaca", "cache", "file", ...) and the Alpaca feed; recorded in the ledger.
    price_source: str = ""
    data_feed: str | None = None


@dataclass
class RunResult:
    status: str  # dry_run | completed | nothing_to_do | already_done | skipped | incomplete | blocked
    rebalance_id: str
    dry_run: bool
    reason: str = ""
    planned: list[tuple[PlannedOrder, str]] = field(default_factory=list)
    skipped: list[SkippedLeg] = field(default_factory=list)
    submitted: list[Order] = field(default_factory=list)
    existing: list[Order] = field(default_factory=list)
    final_orders: list[Order] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    modelled_fees: dict = field(default_factory=dict)
    modelled_dividends: dict | None = None
    reconciliation: dict = field(default_factory=dict)
    plan_text: str = ""

    @property
    def exit_code(self) -> int:
        """0 ok, 1 incomplete, 2 blocked (a guard refusal returned rather than raised; nothing was sent)."""
        return {"incomplete": 1, "blocked": 2}.get(self.status, 0)


@dataclass(frozen=True)
class DueRebalance:
    rebalance_id: str
    rebalance_date: date
    decision_date: date  # session before the rebalance date: the signal's as-of close
    last_completed_session: date  # sizing prices must be dated this session
    clock: Clock
    calendar: list[CalendarDay]


def _calendar_window(broker: Broker, now: datetime) -> list[CalendarDay]:
    today = now.astimezone(ET).date()
    return broker.get_calendar(today - timedelta(days=70), today + timedelta(days=10))


def compute_due_rebalance(broker: Broker, strategy: str) -> DueRebalance:
    """Latest due rebalance per the broker calendar (catch-up rule: latest only)."""
    clock = broker.get_clock()
    cal = _calendar_window(broker, clock.now)
    reb = due_rebalance_date(cal, clock.now)
    return DueRebalance(
        rebalance_id=make_rebalance_id(strategy, reb),
        rebalance_date=reb,
        decision_date=previous_session(cal, reb),
        last_completed_session=last_completed_session(cal, clock.now),
        clock=clock,
        calendar=cal,
    )


@dataclass
class _LegState:
    attempts: int = 0
    side: str | None = None
    filled: bool = False
    open: bool = False


class _Run:
    """One run's mutable working state (never shared between runs)."""

    def __init__(self, broker: Broker, cfg: RunConfig, rebalance_id: str, ledger: Ledger, alerter: Alerter,
                 env: Mapping[str, str]) -> None:
        self.broker = broker
        self.cfg = cfg
        self.rebalance_id = rebalance_id
        self.prefix = rebalance_prefix(rebalance_id)
        self.ledger = ledger
        self.alerter = alerter
        self.env = env
        self.kill_path = cfg.kill_switch_path or default_kill_switch_path(env)
        self.result = RunResult(status="started", rebalance_id=rebalance_id, dry_run=cfg.dry_run)
        self.context = rebalance_id
        self.submitted_count = 0
        self.failed_symbols: set[str] = set()
        self.incomplete_reasons: list[str] = []
        self.rebalance_start: datetime | None = None
        self.today_start: datetime | None = None
        self.symbols_all = tuple(cfg.universe) + ((cfg.cash_symbol,) if cfg.cash_symbol else ())
        self.started = cfg.local_now()
        self.new_legs_allowed = True
        self.new_legs_block = ""  # skip reason for legs without an order when new legs are not allowed
        self.calendar: Sequence[CalendarDay] = ()
        self.halted: str | None = None  # why submissions stopped mid-run (market window / deadline)

    # ------------------------------------------------------------- submission gate
    def past_deadline(self, grace_s: float = 0.0) -> bool:
        return (self.cfg.local_now() - self.started).total_seconds() > self.cfg.deadline_s + grace_s

    def submission_block(self) -> str | None:
        """Reason no order may be sent *now* (fresh broker clock), else None."""
        if self.past_deadline():
            return f"run deadline of {self.cfg.deadline_s:.0f}s reached"
        clock = self.broker.get_clock()
        session = session_on(self.calendar, clock.now.astimezone(ET).date())
        window = check_market_window(clock, session, self.cfg.local_now())
        return f"market window closed ({window})" if window else None

    def halt(self, reason: str) -> None:
        if self.halted is None:
            self.halted = reason
            self.note_incomplete(f"submissions stopped: {reason}")
            self.alert("submissions_stopped", f"{reason}; remaining legs not sent (never queued for the next open)")

    # ------------------------------------------------------------- helpers
    def alert(self, code: str, detail: str) -> None:
        self.result.alerts.append(code)
        self.alerter.alert(code, detail, context=self.context)

    def ours(self, orders: Sequence[Order]) -> list[Order]:
        return [o for o in orders if o.client_order_id.startswith(self.prefix)]

    def is_exempt_order(self, o: Order) -> bool:
        if not self.cfg.allow_exit_to_cash or not o.client_order_id.startswith(self.prefix):
            return False
        return (o.side == "sell" and o.qty is not None) or (o.side == "buy" and o.symbol == self.cfg.cash_symbol)

    def leg_states(self, ours: Sequence[Order]) -> dict[str, _LegState]:
        states: dict[str, _LegState] = {}
        for o in ours:
            rest = o.client_order_id[len(self.prefix):]
            try:
                sym, side, att = rest.rsplit("-", 2)
                n = int(att[1:])
            except ValueError:
                continue
            st = states.setdefault(sym, _LegState())
            st.attempts = max(st.attempts, n)
            st.side = st.side or side
            if o.status == "filled":
                st.filled = True
            if not o.is_terminal:
                st.open = True
        return states

    def order_dollars(self, o: Order, ref: Mapping[str, Decimal]) -> Decimal:
        if o.status == "rejected":
            return Decimal(0)
        if o.is_terminal:
            return o.filled_notional
        if o.notional is not None:
            return o.notional
        if o.qty is not None:
            return o.qty * ref.get(o.symbol, o.filled_avg_price or Decimal(0))
        return Decimal(0)

    def already_today(self, orders: Sequence[Order], ref: Mapping[str, Decimal]) -> Decimal:
        assert self.today_start is not None
        return sum(
            (self.order_dollars(o, ref) for o in orders
             if o.submitted_at >= self.today_start and not self.is_exempt_order(o)),
            Decimal(0),
        )

    def note_incomplete(self, reason: str) -> None:
        if reason not in self.incomplete_reasons:
            self.incomplete_reasons.append(reason)

    def eligible(self, legs: Sequence[PlannedOrder], states: Mapping[str, _LegState],
                 skipped: list[SkippedLeg], record: bool = True) -> list[tuple[PlannedOrder, int]]:
        """Legs that may be submitted now, with their attempt numbers.

        ``record`` False (planning/display only) does not mark the run
        incomplete or alert; the execution phases do.
        """
        out = []
        for leg in legs:
            st = states.get(leg.symbol)
            if leg.symbol in self.failed_symbols:
                skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, "submit_failed_this_run"))
                continue
            if st is None:
                if not self.new_legs_allowed:
                    skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, self.new_legs_block))
                    continue
                out.append((leg, 1))
                continue
            if st.filled:
                skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, "leg_done_this_rebalance"))
                continue
            if st.open:
                skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, "order_still_open"))
                if record:
                    self.note_incomplete(f"{leg.symbol}: order still open")
                continue
            if st.side != leg.side:
                skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, "side_flip_within_rebalance"))
                if record:
                    self.alert("side_flip", f"{leg.symbol}: earlier attempt was a {st.side}, now {leg.side}")
                continue
            if st.attempts >= self.cfg.max_attempts:
                skipped.append(SkippedLeg(leg.symbol, leg.side, leg.est_notional, "max_attempts_reached"))
                if record:
                    self.note_incomplete(f"{leg.symbol}: residual ${leg.est_notional:.2f} after {st.attempts} attempts")
                continue
            out.append((leg, st.attempts + 1))
        return out

    def lookup(self, cid: str, tries: int = 1) -> Order | None:
        for i in range(tries):
            try:
                found = self.broker.get_order_by_client_id(cid)
            except Exception as exc:  # noqa: BLE001
                log.warning("lookup of %s failed: %s", cid, type(exc).__name__)
                found = None
            if found is not None:
                return found
            if i + 1 < tries:
                self.cfg.sleep(self.cfg.poll_interval_s)
        return None

    def submit_idempotent(self, req: OrderRequest) -> Order | None:
        """Submit once. Never resubmits an id that exists at the broker.

        Returns the broker's order for this id (ours or found), or None if no
        order exists (the leg is then marked failed for this run).
        """
        cid = req.client_order_id
        try:
            existing = self.broker.get_order_by_client_id(cid)
            listed = [o for o in self.broker.list_orders("all", after=self.rebalance_start)
                      if o.client_order_id == cid]
        except Exception as exc:  # noqa: BLE001 - cannot verify idempotency -> do not submit
            self.failed_symbols.add(req.symbol)
            self.alert("pre_submit_lookup_failed", f"{cid}: {type(exc).__name__}; order not sent")
            return None
        if existing is not None or listed:
            prior: Order = existing or listed[0]
            self.alert("order_already_exists", f"{cid} already at broker (status {prior.status}); not resubmitted")
            self.result.existing.append(prior)
            return prior
        try:
            block = self.submission_block()  # a fresh clock right before sending (lookups can be slow)
        except GuardViolation:
            raise
        except Exception as exc:  # noqa: BLE001 - cannot verify the window -> do not send
            block = f"broker clock unavailable ({type(exc).__name__})"
        if block:
            self.halt(block)
            return None
        self.ledger.append({"event": "submit_intent", "rebalance_id": self.rebalance_id, "request": req})
        try:
            order = self.broker.submit_order(
                req.symbol, req.side, notional=req.notional, qty=req.qty, client_order_id=cid,
                time_in_force=req.time_in_force, order_type=req.order_type,
            )
        except DuplicateClientOrderId:
            found = self.lookup(cid, tries=3)
            self.alert("duplicate_client_order_id", f"{cid}: broker says the id exists; reconciled, not resubmitted")
            if found is not None:
                self.result.existing.append(found)
            else:
                self.failed_symbols.add(req.symbol)
            return found
        except Exception as exc:  # noqa: BLE001 - ANY error: look the id up before deciding
            found = self.lookup(cid, tries=3)
            if found is not None:
                self.alert("submit_error_but_order_landed",
                           f"{cid}: {type(exc).__name__} on submit, order found at broker; not resubmitted")
                order = found
            else:
                self.failed_symbols.add(req.symbol)
                self.alert("submit_failed", f"{cid}: {type(exc).__name__}: {exc}")
                return None
        self.submitted_count += 1
        self.result.submitted.append(order)
        self.ledger.append({"event": "submitted", "rebalance_id": self.rebalance_id, "order": order})
        return order

    def wait_terminal(self, cids: Sequence[str]) -> dict[str, Order]:
        """Poll until terminal; cancel what is still open after ``poll_max`` polls."""
        final: dict[str, Order] = {}
        pending = list(dict.fromkeys(cids))

        def poll_round() -> None:
            for cid in list(pending):
                o = self.lookup(cid)
                if o is not None and o.is_terminal:
                    final[cid] = o
                    pending.remove(cid)

        for _ in range(self.cfg.poll_max):
            poll_round()
            if not pending:
                return final
            if self.past_deadline():
                break  # cancel now rather than let a job timeout kill the run with orders open
            self.cfg.sleep(self.cfg.poll_interval_s)
        for cid in list(pending):
            o = self.lookup(cid)
            if o is not None and not o.is_terminal:
                try:
                    self.broker.cancel_order(o.id)
                except Exception as exc:  # noqa: BLE001
                    log.warning("cancel of %s failed: %s", cid, type(exc).__name__)
        for _ in range(self.cfg.poll_max):
            poll_round()
            if not pending or self.past_deadline(grace_s=120.0):
                break
            self.cfg.sleep(self.cfg.poll_interval_s)
        for cid in pending:
            self.note_incomplete(f"{cid}: not terminal after cancel")
            self.alert("order_not_terminal", f"{cid} is still open after cancel")
        return final


def _positions(broker: Broker) -> dict[str, Decimal]:
    return {p.symbol: p.qty for p in broker.get_positions() if p.qty != 0}


def _live_prices(broker: Broker, symbols: Sequence[str]) -> dict[str, LatestPrice]:
    return {s: broker.get_latest_price(s) for s in sorted(set(symbols))}


def rebalance_once(
    targets: Mapping[str, float],
    broker: Broker,
    cfg: RunConfig,
    *,
    prices: Mapping[str, PriceQuote | float | Mapping],
    rebalance_id: str,
    dividends: Mapping[str, Sequence[tuple[date, float]]] | None = None,
    ledger: Ledger | None = None,
) -> RunResult:
    """Run one idempotent rebalance toward ``targets`` (risky weights, remainder cash).

    ``prices``: last-completed-session closes as ``PriceQuote`` (close, session,
    prev_close) per symbol; undated floats are refused. ``dividends``: optional
    ``{symbol: [(ex_date, $/share)]}`` for the modelled-dividend ledger entry.
    Raises ``GuardViolation`` (after alerting and ledgering) on any hard block.
    """
    env = os.environ if cfg.env is None else cfg.env
    alerter = cfg.alerter or Alerter.from_env(env)
    validate_strategy_name(cfg.strategy)
    ledger = ledger or Ledger(cfg.ledger_path or default_ledger_path(cfg.strategy))
    run = _Run(broker, cfg, rebalance_id, ledger, alerter, env)
    try:
        with RunLock(ledger.path.with_suffix(".lock")):
            return _rebalance(run, targets, prices, dividends)
    except GuardViolation as gv:
        run.alert(gv.code, gv.detail)
        _safe_append(ledger, {"event": "guard_violation", "rebalance_id": rebalance_id, "code": gv.code,
                              "detail": gv.detail, "submitted": run.result.submitted})
        raise
    except Exception as exc:
        run.alert("unexpected_error", f"{type(exc).__name__}: {exc}")
        _safe_append(ledger, {"event": "error", "rebalance_id": rebalance_id, "error": type(exc).__name__,
                              "submitted": run.result.submitted})
        raise


def _safe_append(ledger: Ledger, rec: dict) -> None:
    try:
        ledger.append(rec)
    except Exception as exc:  # noqa: BLE001 - never mask the original failure
        log.error("ledger write failed: %s", type(exc).__name__)


def _rebalance(
    run: _Run,
    targets: Mapping[str, float],
    prices_in: Mapping[str, PriceQuote | float | Mapping],
    dividends: Mapping[str, Sequence[tuple[date, float]]] | None,
) -> RunResult:
    cfg, broker, res = run.cfg, run.broker, run.result
    # 1. configuration and mode ------------------------------------------------
    for s in run.symbols_all:
        validate_symbol(s)
    if cfg.cash_symbol and cfg.cash_symbol not in CASH_LIKE_SYMBOLS:
        raise GuardViolation("cash_symbol_not_cash_like",
                             f"cash_symbol {cfg.cash_symbol} is not one of {sorted(CASH_LIKE_SYMBOLS)}")
    if not 1 <= cfg.max_attempts <= MAX_ATTEMPTS_HARD:
        raise GuardViolation("max_attempts_invalid", "max_attempts must be 1 or 2")
    validate_limits(cfg.limits, cfg.limits_ack)
    check_submission_mode(broker_is_live=broker.is_live, dry_run=cfg.dry_run, live=cfg.live,
                          i_understand_live=cfg.i_understand_live, env=run.env)
    check_kill_switches(run.env, run.kill_path)
    run.ledger.append({"event": "run_start", "rebalance_id": run.rebalance_id, "strategy": cfg.strategy,
                       "broker": broker.name, "dry_run": cfg.dry_run, "live": broker.is_live,
                       "price_source": cfg.price_source or "caller", "data_feed": cfg.data_feed})

    # 2. clock, calendar, due rebalance ----------------------------------------
    clock = broker.get_clock()
    cal = _calendar_window(broker, clock.now)
    run.calendar = cal
    today = clock.now.astimezone(ET).date()
    session = session_on(cal, today)
    window = check_market_window(clock, session, cfg.local_now())
    due = due_rebalance_date(cal, clock.now)
    n_session = session_number(cal, due, today)
    exec_window = (None if n_session <= EXECUTION_WINDOW_SESSIONS else
                   f"execution_window_closed (the {due.isoformat()} rebalance may only be traded in its first "
                   f"{EXECUTION_WINDOW_SESSIONS} sessions; today is session {n_session}; waiting for next month)")
    expected = make_rebalance_id(cfg.strategy, due)
    if run.rebalance_id != expected:
        raise GuardViolation("rebalance_id_not_due",
                             f"requested {run.rebalance_id} but the due rebalance is {expected}")
    run.context = f"{cfg.strategy} {due.isoformat()}"
    run.rebalance_start = datetime.combine(due, dtime(0, 0), ET)
    run.today_start = datetime.combine(today, dtime(0, 0), ET)

    # 3. account preflight -------------------------------------------------------
    pre = run_preflight(broker)

    # 4. market-hours gate, then the execution window ------------------------------------
    if window is not None and not cfg.dry_run:
        log.info("no action: %s (orders are never queued for the next open)", window)
        res.status, res.reason = "skipped", window
        run.ledger.append({"event": "skipped", "rebalance_id": run.rebalance_id, "reason": window})
        if session is None:
            # weekend/holiday: the scheduler fired at a valid time on a closed day; the run is alive. A run on a
            # session day but outside the window pings nothing, so a mistimed scheduler trips the dead-man check.
            run.alerter.ping_success()
        return res
    if exec_window is not None and not cfg.dry_run:
        log.info("no action: %s", exec_window)
        res.status, res.reason = "skipped", exec_window
        run.ledger.append({"event": "skipped", "rebalance_id": run.rebalance_id, "reason": exec_window})
        run.alerter.ping_success()  # a normal mid-month heartbeat run
        return res

    last_session = last_completed_session(cal, clock.now)

    # 5. foreign open orders, then existing orders for this rebalance -------------------
    foreign_open = [o for o in broker.list_orders("open") if not o.client_order_id.startswith(run.prefix)
                    and not o.is_terminal]
    if foreign_open:
        raise GuardViolation(
            "foreign_open_orders",
            f"{len(foreign_open)} open order(s) at the broker were not placed by this rebalance "
            f"({', '.join(sorted({o.symbol for o in foreign_open}))}); cancel them or use a dedicated account")
    orders_since = broker.list_orders("all", after=run.rebalance_start)
    ours_start = run.ours(orders_since)
    res.existing.extend(ours_start)
    refusal = _new_leg_gate(run, ours_start, n_session, today, due)
    if refusal is not None:
        # an operator override whose cross-check cannot be performed: refuse the whole run, before any wait or
        # order, with an alert and a guard-violation ledger record (exit 2, like a raised guard; no success ping)
        code, detail = refusal
        run.alert(code, detail)
        res.status, res.reason = "blocked", f"{code}: {detail}"
        _safe_append(run.ledger, {"event": "guard_violation", "rebalance_id": run.rebalance_id, "code": code,
                                  "detail": detail, "submitted": []})
        return res
    open_ours = [o.client_order_id for o in ours_start if not o.is_terminal]
    if open_ours and not cfg.dry_run:
        log.info("waiting for %d open order(s) from an earlier run", len(open_ours))
        run.wait_terminal(open_ours)
        orders_since = broker.list_orders("all", after=run.rebalance_start)
        ours_start = run.ours(orders_since)

    # 6. inputs, plan, plan-level guards ------------------------------------------------
    positions = _positions(broker)
    pre_trade_positions = dict(positions)
    check_positions_whitelist(positions, cfg.universe, cfg.cash_symbol)
    check_weights(targets, cfg.universe, cfg.limits.max_weight, cfg.cash_symbol)
    tgt_full = planning.full_targets(targets, cfg.cash_symbol)
    needed = sorted({s for s, w in tgt_full.items() if w > 0} | set(positions))
    quotes = coerce_quotes(prices_in)
    check_price_quotes(quotes, needed, last_session, cfg.corporate_action_symbols, cfg.limits.max_price_move)
    live = _live_prices(broker, needed)
    check_live_prices(live, quotes, clock.now, cfg.corporate_action_symbols, cfg.limits.max_price_move)
    ref = {s: lp.price for s, lp in live.items()}
    account = broker.get_account()
    equity = account.cash + sum((q * ref[s] for s, q in positions.items()), Decimal(0))
    check_equity(equity, account.equity)
    if cfg.initial_deployment:
        check_initial_deployment(sum((q * ref[s] for s, q in positions.items()), Decimal(0)) / equity)
    cash_buffer = max(cfg.cash_buffer_min, cfg.cash_buffer_frac * equity)
    cash_available = min(account.cash, account.non_marginable_buying_power)
    plan = planning.plan_rebalance(
        targets=targets, positions=positions, prices=ref, equity=equity, cash_available=cash_available,
        cash_buffer=cash_buffer, min_notional=MIN_ORDER_NOTIONAL, cash_symbol=cfg.cash_symbol,
        allow_exit_to_cash=cfg.allow_exit_to_cash,
    )
    states = run.leg_states(ours_start)
    skipped = list(plan.skipped)
    eligible = run.eligible(plan.legs, states, skipped, record=False)
    planned = [(leg, make_client_order_id(run.rebalance_id, leg.symbol, leg.side, att)) for leg, att in eligible]
    res.planned, res.skipped = planned, skipped
    header = (f"order plan {run.rebalance_id} ({'DRY RUN' if cfg.dry_run else broker.name}); equity "
              f"${equity:,.2f}; prices as of {last_session}; decision uses caller's targets")
    res.plan_text = format_plan(planned, skipped, header=header)
    log.info("\n%s", res.plan_text)

    check_exposure_drop(plan, cfg.allow_exit_to_cash, cfg.limits.max_exposure_drop)
    check_min_notional_feasible(plan)
    legs = [leg for leg, _ in planned]
    for leg in legs:
        asset = broker.get_asset(leg.symbol)
        if not asset.tradable:
            raise GuardViolation("asset_not_tradable", f"{leg.symbol} is not tradable")
        if not leg.close_position and not asset.fractionable:
            raise GuardViolation("asset_not_fractionable", f"{leg.symbol} is not fractionable (notional orders)")
    check_plan_caps(legs, equity=equity, limits=cfg.limits, already_today=run.already_today(orders_since, ref),
                    initial_deployment=cfg.initial_deployment, n_symbols=len(run.symbols_all))
    for leg, cid in planned:
        check_order_request(planning.build_order_request(leg, cid), leg, positions.get(leg.symbol, Decimal(0)))

    payload = {"strategy": cfg.strategy, "rebalance_id": run.rebalance_id, "targets": dict(targets),
               "quotes": quotes, "universe": list(cfg.universe), "cash_symbol": cfg.cash_symbol}
    run.ledger.append({
        "event": "plan", "rebalance_id": run.rebalance_id, "inputs_hash": inputs_hash(payload),
        "targets": dict(targets), "quotes": quotes, "live_prices": live, "equity": equity, "cash": account.cash,
        "positions": positions, "planned": [{"client_order_id": c, "leg": l} for l, c in planned],
        "skipped": skipped, "preflight": pre, "market_window": window or "open", "dry_run": cfg.dry_run,
    })

    first_run_for_rebalance = not ours_start
    if dividends is not None and first_run_for_rebalance:
        prev_reb = _previous_rebalance_date(cal, due)
        res.modelled_dividends = model_dividends(pre_trade_positions, dividends, prev_reb, due) if prev_reb else None

    # 7a. dry run ----------------------------------------------------------------------
    if cfg.dry_run:
        res.status = "dry_run"
        gate = window or exec_window
        res.reason = f"market gate would skip: {gate}" if gate else "market gate open"
        res.modelled_fees = model_fees(FeeFill(today, leg.side, leg.qty_est, leg.ref_price) for leg in legs)
        run.ledger.append({"event": "run_end", "rebalance_id": run.rebalance_id, "status": res.status,
                           "reason": res.reason, "modelled_fees_estimate": res.modelled_fees,
                           "modelled_dividends": res.modelled_dividends})
        run.alerter.ping_success()
        return res

    if not planned:
        if ours_start:
            res.status = "already_done"
        elif any(sk.reason == FIRST_SESSION_PASSED for sk in skipped):
            res.status, res.reason = "skipped", (
                f"{FIRST_SESSION_PASSED}: legs of the {due.isoformat()} rebalance may only be opened on its "
                f"scheduled session; today is session {n_session}, so drift waits for next month (an operator "
                f"who knows no run evaluated {due.isoformat()} may rerun with --late-start)")
            log.info("no action: %s", res.reason)
        else:
            res.status = "nothing_to_do"
    else:
        # 7b. sells, wait, then buys ------------------------------------------------------
        sells_ok = _execute_phase(run, "sell", targets, needed, quotes, clock)
        if sells_ok:
            _execute_phase(run, "buy", targets, needed, quotes, clock)
        elif not run.halted:
            run.note_incomplete("sells not terminal; buys not sent")

    # 8. reconcile, ledger, alert/ping --------------------------------------------------------
    _finish(run, cal, due, today)
    return res


#: Statuses of a ``run_end`` record that mean the rebalance was evaluated (its new legs are closed).
EVALUATED_STATUSES = ("completed", "already_done", "nothing_to_do")
FIRST_SESSION_PASSED = "first_session_passed"
LATE_START_LEDGER_UNREADABLE = "late_start_ledger_unreadable"


def _new_leg_gate(run: _Run, ours_start: Sequence[Order], n_session: int, today: date,
                  due: date) -> tuple[str, str] | None:
    """Decide whether this run may open new legs (attempt ``a1``); see the module docstring, step 5.

    Broker state and the calendar decide; the local ledger can only close the gate further. Returns
    ``(code, detail)`` when the run must be refused outright: a ``late_start`` override whose ledger
    cross-check cannot be performed. Unattended runs never get a refusal from here.
    """
    try:
        records = run.ledger.read()
    except (OSError, ValueError) as exc:  # e.g. a line cut short by a crash
        if run.cfg.late_start:  # the operator override fails closed: its cross-check needs the ledger
            run.new_legs_allowed, run.new_legs_block = False, LATE_START_LEDGER_UNREADABLE
            return LATE_START_LEDGER_UNREADABLE, (
                f"--late-start must confirm from the local ledger that no run evaluated the {due.isoformat()} "
                f"rebalance, but {run.ledger.path} cannot be read ({type(exc).__name__}); nothing was sent. "
                f"Repair the ledger (runbook section 9) and rerun, or leave the drift to next month")
        # unattended: the broker rule and the calendar still apply
        log.warning("ledger unreadable (%s); deciding new legs from broker state and the calendar only",
                    type(exc).__name__)
        records = []
    evaluated = any(r.get("event") == "run_end" and r.get("rebalance_id") == run.rebalance_id
                    and r.get("status") in EVALUATED_STATUSES for r in records)
    if ours_start:
        first_day = min(o.submitted_at for o in ours_start).astimezone(ET).date()
        if first_day != today:
            run.new_legs_allowed, run.new_legs_block = False, "rebalance_already_executed"
        elif evaluated:
            run.new_legs_allowed, run.new_legs_block = False, "rebalance_already_evaluated"
        return None
    if evaluated:
        run.new_legs_allowed, run.new_legs_block = False, "rebalance_already_evaluated"
        if run.cfg.late_start:
            log.warning("--late-start ignored: the ledger shows the %s rebalance was already evaluated",
                        due.isoformat())
        return None
    if n_session > 1 and not run.cfg.late_start:
        run.new_legs_allowed, run.new_legs_block = False, FIRST_SESSION_PASSED
        return None
    if n_session > 1:
        log.warning("late start (operator confirmed): opening legs of the %s rebalance on session %d (%s)",
                    due.isoformat(), n_session, today.isoformat())
        run.ledger.append({"event": "late_start", "rebalance_id": run.rebalance_id, "session": n_session,
                           "dry_run": run.cfg.dry_run})
    return None


def _previous_rebalance_date(cal: Sequence[CalendarDay], due: date) -> date | None:
    y, m = (due.year - 1, 12) if due.month == 1 else (due.year, due.month - 1)
    return first_session_of_month(cal, y, m)


def _execute_phase(
    run: _Run,
    side: str,
    targets: Mapping[str, float],
    needed: Sequence[str],
    quotes: Mapping[str, PriceQuote],
    clock: Clock,
) -> bool:
    """Submit ``side`` legs (up to ``max_attempts`` rounds); True if all terminal."""
    cfg, broker = run.cfg, run.broker
    all_terminal = True
    for _round in range(cfg.max_attempts + 1):  # last round only detects residuals left at max attempts
        orders_since = broker.list_orders("all", after=run.rebalance_start)
        foreign_open = [o for o in orders_since if not o.client_order_id.startswith(run.prefix) and not o.is_terminal]
        if foreign_open:
            raise GuardViolation("foreign_open_orders",
                                 f"an order not placed by this rebalance appeared mid-run ({foreign_open[0].symbol})")
        states = run.leg_states(run.ours(orders_since))
        positions = _positions(broker)
        check_positions_whitelist(positions, cfg.universe, cfg.cash_symbol)
        syms = sorted(set(needed) | set(positions))
        live = _live_prices(broker, syms)
        check_live_prices(live, quotes, broker.get_clock().now, cfg.corporate_action_symbols,
                          cfg.limits.max_price_move)
        ref = {s: lp.price for s, lp in live.items()}
        account = broker.get_account()
        equity = account.cash + sum((q * ref[s] for s, q in positions.items()), Decimal(0))
        check_equity(equity, account.equity)
        cash_buffer = max(cfg.cash_buffer_min, cfg.cash_buffer_frac * equity)
        plan = planning.plan_rebalance(
            targets=targets, positions=positions, prices=ref, equity=equity,
            cash_available=min(account.cash, account.non_marginable_buying_power), cash_buffer=cash_buffer,
            min_notional=MIN_ORDER_NOTIONAL, cash_symbol=cfg.cash_symbol,
            allow_exit_to_cash=cfg.allow_exit_to_cash, sides=(side,),
        )
        scratch: list[SkippedLeg] = []
        eligible = run.eligible(plan.legs, states, scratch)
        if not eligible:
            break
        legs = [leg for leg, _ in eligible]
        check_plan_caps(legs, equity=equity, limits=cfg.limits, already_today=run.already_today(orders_since, ref),
                        initial_deployment=cfg.initial_deployment, n_symbols=len(run.symbols_all),
                        orders_so_far=run.submitted_count)
        cids = []
        for leg, attempt in eligible:
            if run.halted:
                break
            cid = make_client_order_id(run.rebalance_id, leg.symbol, leg.side, attempt)
            req = planning.build_order_request(leg, cid)
            check_order_request(req, leg, positions.get(leg.symbol, Decimal(0)))
            check_kill_switches(run.env, run.kill_path)
            if run.submitted_count + 1 > cfg.limits.max_orders_per_symbol * len(run.symbols_all):
                raise GuardViolation("max_orders_per_run", "order count cap reached")
            order = run.submit_idempotent(req)
            if order is not None:
                cids.append(order.client_order_id)
        final = run.wait_terminal(cids)
        if len(final) < len(cids) or run.halted:
            all_terminal = False
            break
    return all_terminal


def _finish(run: _Run, cal: Sequence[CalendarDay], due: date, today: date) -> None:
    broker, res = run.broker, run.result
    orders_since = broker.list_orders("all", after=run.rebalance_start)
    ours = run.ours(orders_since)
    res.final_orders = ours
    if res.status == "started":
        res.status = "incomplete" if (run.incomplete_reasons or run.failed_symbols) else "completed"
    todays_fills = [
        FeeFill(o.submitted_at.astimezone(ET).date(), o.side, o.filled_qty, o.filled_avg_price)
        for o in orders_since
        if o.filled_qty > 0 and o.filled_avg_price is not None and run.today_start is not None
        and o.submitted_at >= run.today_start
    ]
    res.modelled_fees = model_fees(todays_fills)
    prev_reb = _previous_rebalance_date(cal, due)
    res.reconciliation = _reconcile(run, ours, prev_reb or due)
    if res.status == "incomplete":
        run.alert("rebalance_incomplete", "; ".join(run.incomplete_reasons) or "legs not fully filled")
    run.ledger.append({
        "event": "run_end", "rebalance_id": run.rebalance_id, "status": res.status,
        "incomplete_reasons": run.incomplete_reasons, "orders": ours,
        "fills": [{"client_order_id": o.client_order_id, "symbol": o.symbol, "side": o.side,
                   "filled_qty": o.filled_qty, "filled_avg_price": o.filled_avg_price, "status": o.status}
                  for o in ours],
        "modelled_fees_by_day": res.modelled_fees, "modelled_dividends": res.modelled_dividends,
        "reconciliation": res.reconciliation, "alerts": res.alerts,
    })
    if res.status in ("completed", "already_done", "nothing_to_do", "skipped"):
        run.alerter.ping_success()


def _reconcile(run: _Run, ours: Sequence[Order], since: date) -> dict:
    broker, cfg = run.broker, run.cfg
    strategy_prefix = f"{cfg.strategy}-"
    out: dict = {"since": since, "broker": broker.name}
    try:
        acts = broker.get_activities(ACTIVITY_KINDS, after=since)
        orders_window = broker.list_orders("all", after=datetime.combine(since, dtime(0, 0), ET))
    except Exception as exc:  # noqa: BLE001 - reconciliation is best effort; never fails the run
        out["error"] = type(exc).__name__
        return out
    our_ids = {o.id for o in ours}
    foreign = [o for o in orders_window if not o.client_order_id.startswith(strategy_prefix)]
    fills = [a for a in acts if a.kind == "FILL"]
    out["broker_fill_count_this_rebalance"] = sum(1 for a in fills if a.order_id in our_ids)
    out["runner_filled_orders_this_rebalance"] = sum(1 for o in ours if o.filled_qty > 0)
    out["broker_fees"] = sum((-a.amount for a in acts if a.kind in ("FEE", "PTC")), Decimal(0))
    out["broker_dividends"] = sum((a.amount for a in acts if a.kind.startswith("DIV")), Decimal(0))
    out["foreign_order_count"] = len(foreign)
    out["note"] = ("Alpaca paper does not charge regulatory fees or credit dividends; the modelled "
                   "values in this ledger are the P&L of record for paper trading.")
    if foreign:
        run.alert("foreign_orders", f"{len(foreign)} order(s) since {since} were not placed by {cfg.strategy}")
    return out
