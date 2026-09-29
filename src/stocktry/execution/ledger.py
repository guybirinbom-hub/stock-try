"""Append-only JSONL shadow ledger and local run lock.

Every run appends records (one JSON object per line, fsync'd): run start,
the plan with its inputs hash, a write-ahead ``submit_intent`` before each
order, each submission result, and a run summary with fills, *modelled*
Alpaca fees, *modelled* dividends and a reconciliation against broker
activities. Alpaca paper does not charge regulatory fees or credit dividends,
so the modelled values here are the P&L of record for paper trading.

The ledger is an audit trail, not the idempotency mechanism: the broker's
order list (looked up by deterministic client_order_id) is the source of truth,
so a crash between submission and the ledger write loses nothing.

De-duplication rules for consumers: modelled fees are per ET day (the last
record for a day wins, because fees are aggregated per day across runs);
modelled dividends are per rebalance id (the last record for an id wins).
"""

from __future__ import annotations

import dataclasses
import errno
import fcntl
import hashlib
import json
import os
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import IO, Any, Iterable, Mapping, Sequence

from .fees import AlpacaFeeSchedule, DEFAULT_SCHEDULE, FeeFill, daily_fees
from .guards import ConcurrentRunError

__all__ = [
    "Ledger",
    "RunLock",
    "default_ledger_path",
    "inputs_hash",
    "to_jsonable",
    "model_dividends",
    "model_fees",
]

SCHEMA_VERSION = 1


def default_ledger_path(strategy: str) -> Path:
    """``<repo root>/data/ledger/<strategy>.jsonl`` (data/ is git-ignored)."""
    return Path(__file__).resolve().parents[3] / "data" / "ledger" / f"{strategy}.jsonl"


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: to_jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, Mapping):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, tuple) and hasattr(obj, "_asdict"):
        return {k: to_jsonable(v) for k, v in obj._asdict().items()}
    if isinstance(obj, (list, tuple, set, frozenset)):
        items = sorted(obj, key=str) if isinstance(obj, (set, frozenset)) else obj
        return [to_jsonable(v) for v in items]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, float) and (obj != obj or obj in (float("inf"), float("-inf"))):
        return str(obj)
    return obj


def inputs_hash(payload: Any) -> str:
    """SHA-256 of the canonical JSON of the run inputs."""
    blob = json.dumps(to_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


class Ledger:
    """Append-only JSONL file. Never rewrites or truncates existing lines."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def append(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rec = {"schema": SCHEMA_VERSION, "ts": datetime.now(timezone.utc).isoformat(), **record}
        line = json.dumps(to_jsonable(rec), sort_keys=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def records_for(self, rebalance_id: str) -> list[dict]:
        return [r for r in self.read() if r.get("rebalance_id") == rebalance_id]


class RunLock:
    """Exclusive, non-blocking local lock (fcntl.flock) next to the ledger."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._fh: IO[str] | None = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            fh.close()
            if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                raise ConcurrentRunError("concurrent_run", "another run holds the local lock") from None
            raise
        self._fh = fh
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fh is not None:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            self._fh.close()
            self._fh = None


def model_fees(fills: Iterable[FeeFill], schedule: AlpacaFeeSchedule = DEFAULT_SCHEDULE) -> dict:
    """Alpaca fee model per ET day: ``{day: {sec, taf, cat, total}}`` dollars."""
    return {d.isoformat(): v for d, v in daily_fees(fills, schedule).items()}


def model_dividends(
    qty_held: Mapping[str, Decimal],
    dividends: Mapping[str, Sequence[tuple[date, float]]],
    start: date,
    end: date,
) -> dict:
    """Cash dividends on holdings with ex-date in ``[start, end)``.

    ``qty_held`` is shares held through the window (for a monthly strategy the
    pre-trade holdings of this rebalance were held since the previous one);
    ``dividends[symbol]`` is (ex_date, dollars per share). Each payment is
    rounded to the nearest cent as Alpaca does for fractional positions, so a
    $1 position typically receives $0.00. Payment dates are not modelled.
    """
    payments = []
    total = Decimal(0)
    for sym, qty in sorted(qty_held.items()):
        if qty <= 0:
            continue
        for ex_date, per_share in dividends.get(sym, ()):
            if start <= ex_date < end and per_share and per_share > 0:
                amount = (qty * Decimal(repr(float(per_share)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                payments.append(
                    {"symbol": sym, "ex_date": ex_date, "per_share": per_share, "qty": qty, "amount": amount}
                )
                total += amount
    return {"window_start": start, "window_end_exclusive": end, "payments": payments, "total": total}
