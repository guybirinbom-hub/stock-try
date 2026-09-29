"""Trading-session helpers: rebalance scheduling, ids, and a simulator calendar.

Timing conventions
------------------
* A *session* is one regular NYSE trading day (09:30-16:00 ET, 13:00 on early
  closes). The Alpaca adapter uses the broker's own calendar endpoint; the
  hard-coded calendar below exists only for ``LocalSimBroker``.
* The *scheduled rebalance date* of a month is its first session.
* The *due* rebalance at a moment ``now`` is the latest scheduled rebalance date
  on or before today's (ET) date. Older missed rebalances are never replayed.
* The *decision date* is the session before the rebalance date: the strategy
  decides on that close and trades on the rebalance date or later (t+1), which
  matches the backtest's next-bar execution.
* The *last completed session* at ``now`` is the latest session whose close is
  at or before ``now``. Sizing prices must be dated exactly that session.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from .broker import CalendarDay

__all__ = [
    "ET",
    "sim_nyse_calendar",
    "session_on",
    "first_session_of_month",
    "last_completed_session",
    "previous_session",
    "due_rebalance_date",
    "make_rebalance_id",
    "make_client_order_id",
    "rebalance_prefix",
    "validate_strategy_name",
    "validate_symbol",
    "MAX_CLIENT_ORDER_ID_LEN",
]

ET = ZoneInfo("America/New_York")
MAX_CLIENT_ORDER_ID_LEN = 128

_STRATEGY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")

# NYSE full-day holidays and early closes (13:00 ET). Simulator only.
_HOLIDAYS: dict[int, set[date]] = {
    2024: {date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29), date(2024, 5, 27),
           date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2), date(2024, 11, 28), date(2024, 12, 25)},
    2025: {date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18),
           date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 27),
           date(2025, 12, 25)},
    2026: {date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
           date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25)},
    2027: {date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
           date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24)},
}
_EARLY_CLOSES: set[date] = {
    date(2024, 7, 3), date(2024, 11, 29), date(2024, 12, 24),
    date(2025, 7, 3), date(2025, 11, 28), date(2025, 12, 24),
    date(2026, 11, 27), date(2026, 12, 24),
    date(2027, 11, 26),
}


def sim_nyse_calendar(start: date, end: date) -> list[CalendarDay]:
    """Approximate NYSE regular sessions between ``start`` and ``end`` inclusive.

    For the simulator only (2024-2027). Raises ``ValueError`` outside that
    range rather than silently producing a wrong calendar.
    """
    if start.year < 2024 or end.year > 2027:
        raise ValueError("sim calendar covers 2024-2027 only; use the broker calendar")
    out: list[CalendarDay] = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d not in _HOLIDAYS[d.year]:
            close_t = time(13, 0) if d in _EARLY_CLOSES else time(16, 0)
            out.append(
                CalendarDay(d, datetime.combine(d, time(9, 30), ET), datetime.combine(d, close_t, ET))
            )
        d += timedelta(days=1)
    return out


def session_on(calendar: Sequence[CalendarDay], d: date) -> CalendarDay | None:
    """The session on date ``d`` or None (weekend/holiday)."""
    for s in calendar:
        if s.date == d:
            return s
    return None


def first_session_of_month(calendar: Sequence[CalendarDay], year: int, month: int) -> date | None:
    days = [s.date for s in calendar if s.date.year == year and s.date.month == month]
    return min(days) if days else None


def last_completed_session(calendar: Sequence[CalendarDay], now: datetime) -> date:
    """Latest session whose close is at or before ``now`` (tz-aware)."""
    done = [s.date for s in calendar if s.close <= now]
    if not done:
        raise ValueError("calendar has no completed session before now; widen the calendar window")
    return max(done)


def previous_session(calendar: Sequence[CalendarDay], d: date) -> date:
    """The session strictly before date ``d``."""
    prior = [s.date for s in calendar if s.date < d]
    if not prior:
        raise ValueError("calendar has no session before the requested date")
    return max(prior)


def due_rebalance_date(calendar: Sequence[CalendarDay], now: datetime) -> date:
    """Latest scheduled rebalance date (first session of a month) <= today (ET).

    Never returns an older month when a newer one has arrived, so missed months
    are skipped rather than replayed.
    """
    today = now.astimezone(ET).date()
    this_month = first_session_of_month(calendar, today.year, today.month)
    if this_month is not None and this_month <= today:
        return this_month
    prev_year, prev_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    prev = first_session_of_month(calendar, prev_year, prev_month)
    if prev is None:
        raise ValueError("calendar window too narrow to find the due rebalance date")
    return prev


def validate_strategy_name(strategy: str) -> str:
    if not _STRATEGY_RE.match(strategy):
        raise ValueError(f"invalid strategy name {strategy!r}: use [A-Za-z0-9_.-], max 64 chars")
    return strategy


def validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not _SYMBOL_RE.match(symbol):
        raise ValueError(f"invalid symbol {symbol!r}")
    return symbol


def make_rebalance_id(strategy: str, rebalance_date: date) -> str:
    """``<strategy>-<YYYY-MM-DD>``: strategy name plus the scheduled rebalance date."""
    return f"{validate_strategy_name(strategy)}-{rebalance_date.isoformat()}"


def rebalance_prefix(rebalance_id: str) -> str:
    """Prefix shared by every client_order_id of one rebalance."""
    return f"{rebalance_id}-"


def make_client_order_id(rebalance_id: str, symbol: str, side: str, attempt: int) -> str:
    """``<strategy>-<rebalance date>-<symbol>-<side>-a<attempt>`` (<= 128 chars).

    The rebalance id already starts with the strategy name, so the strategy is
    not repeated. Deterministic: the same leg of the same rebalance always maps
    to the same id, which is what makes retries and duplicate triggers safe.
    """
    if side not in ("buy", "sell"):
        raise ValueError(f"invalid side {side!r}")
    if attempt < 1:
        raise ValueError("attempt numbers start at 1")
    cid = f"{rebalance_id}-{validate_symbol(symbol)}-{side}-a{attempt}"
    if len(cid) > MAX_CLIENT_ORDER_ID_LEN:
        raise ValueError("client_order_id longer than 128 characters")
    return cid
