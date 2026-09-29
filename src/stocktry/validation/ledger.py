"""Trial ledger: every backtest variant ever run, for multiple-testing corrections.

The ledger is one JSON file (committed under ``results/trial_ledger.json``).
Each *trial* is identified by ``(strategy family, parameters, sample)``;
recording a trial adds or refreshes a per-configuration run record (cost tier,
capital, share mode, fill). A run record is rewritten (with a new
``timestamp_utc``) only when its statistics change, so re-running unchanged
code on unchanged data leaves the file byte-identical. Trials are never
removed, so the trial count N can only grow.

Per-trial statistics used by the deflated Sharpe ratio (Sharpe per period,
T, skew, non-excess kurtosis) come from the trial's *headline* run
(``HEADLINE_RUN_KEY``) when present, else from its first recorded run.
Leaky results (``same_bar_fill``) are refused: every caller must state
``leaky=`` explicitly.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

HEADLINE_RUN_KEY = "gate|10000|fractional|next_open"
SCHEMA_VERSION = 1


def _jsonable(x: Any) -> Any:
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def trial_key(family: str, params: dict[str, Any], sample: str) -> str:
    blob = json.dumps({"family": family, "params": _jsonable(params), "sample": sample}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def run_key(cost_tier: str, capital: float, whole_shares: bool, fill: str) -> str:
    return f"{cost_tier}|{capital:g}|{'whole' if whole_shares else 'fractional'}|{fill}"


#: Per-trial fields written by earlier versions that changed on every re-run (git churn); dropped on load.
_VOLATILE_TRIAL_FIELDS = ("last_seen_utc", "run_count")


@dataclass
class TrialLedger:
    path: Path
    _data: dict | None = field(default=None, init=False, repr=False, compare=False)

    def load(self) -> dict:
        if self._data is None:
            if not Path(self.path).exists():
                data = {"schema_version": SCHEMA_VERSION,
                        "description": "Every backtest variant run by stocktry; N for DSR/PBO comes from here.",
                        "trials": {}}
            else:
                data = json.loads(Path(self.path).read_text())
            for tr in data.get("trials", {}).values():
                for k in _VOLATILE_TRIAL_FIELDS:
                    tr.pop(k, None)
            self._data = data
        return self._data

    def _save(self, data: dict) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".ledger", suffix=".json")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=1, sort_keys=True)
        os.replace(tmp, p)

    def record(self, *, strategy: str, family: str, params: dict[str, Any], sample: str, cost_tier: str,
               capital: float, whole_shares: bool, fill: str, t: int, sharpe_per_period: float, skew: float,
               kurtosis: float, cagr: float, max_dd: float, first_month: str, last_month: str,
               leaky: bool, purpose: str = "backtest") -> str:
        """Add/refresh one run; returns the trial key.

        ``leaky`` is required (no default) so no caller can forget it; a leaky
        (same-bar-fill) result is refused. Nothing is written when the trial and
        run already exist with identical statistics.
        """
        if leaky:
            raise ValueError("refusing to record a leaky (same-bar-fill) result in the trial ledger")
        data = self.load()
        key = trial_key(family, params, sample)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stats = _jsonable({
            "t": t, "sharpe_per_period": sharpe_per_period, "skew": skew, "kurtosis": kurtosis, "cagr": cagr,
            "max_dd": max_dd, "first_month": first_month, "last_month": last_month,
        })
        rk = run_key(cost_tier, capital, whole_shares, fill)
        tr = data["trials"].get(key)
        if tr is not None:
            old = tr["runs"].get(rk)
            if old is not None and {k: v for k, v in old.items() if k != "timestamp_utc"} == stats:
                return key  # unchanged: no write, no timestamp churn
        if tr is None:
            tr = {"strategy": strategy, "family": family, "params": _jsonable(params), "sample": sample,
                  "purpose": purpose, "first_seen_utc": now, "runs": {}}
            data["trials"][key] = tr
        tr["runs"][rk] = {**stats, "timestamp_utc": now}
        self._save(data)
        return key

    def trials(self, sample: str | None = None, families: tuple[str, ...] | None = None) -> pd.DataFrame:
        """One row per trial with the statistics of its headline run."""
        rows = []
        for key, tr in self.load()["trials"].items():
            if sample is not None and tr["sample"] != sample:
                continue
            if families is not None and tr["family"] not in families:
                continue
            runs = tr["runs"]
            r = runs.get(HEADLINE_RUN_KEY) or next(iter(runs.values()))
            rows.append({"key": key, "strategy": tr["strategy"], "family": tr["family"], "sample": tr["sample"],
                         "purpose": tr.get("purpose", ""), "params": json.dumps(tr["params"], sort_keys=True),
                         **{k: r.get(k) for k in ("t", "sharpe_per_period", "skew", "kurtosis", "cagr", "max_dd")}})
        return pd.DataFrame(rows)

    def n_trials(self, sample: str | None = None, families: tuple[str, ...] | None = None) -> int:
        return len(self.trials(sample, families))

    def sharpe_variance(self, sample: str | None = None, families: tuple[str, ...] | None = None) -> float:
        """Cross-trial variance (ddof=1) of per-period Sharpe ratios."""
        df = self.trials(sample, families)
        x = pd.to_numeric(df.get("sharpe_per_period", pd.Series(dtype=float)), errors="coerce").dropna()
        return float(x.var(ddof=1)) if len(x) > 1 else float("nan")
