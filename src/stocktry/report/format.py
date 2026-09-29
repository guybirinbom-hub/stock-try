"""Markdown/CSV formatting helpers (templated text only; no language model anywhere)."""
from __future__ import annotations

import math
from typing import Any, Callable

import pandas as pd


def pct(x: Any, d: int = 1) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "n/a" if not math.isfinite(v) else f"{v * 100:.{d}f}%"


def num(x: Any, d: int = 2) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "n/a" if not math.isfinite(v) else f"{v:.{d}f}"


def bp(x: Any, d: int = 1) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "n/a" if not math.isfinite(v) else f"{v:.{d}f} bp"


def money(x: Any, d: int = 2) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "n/a" if not math.isfinite(v) else f"${v:,.{d}f}"


def integer(x: Any) -> str:
    try:
        return f"{int(round(float(x)))}"
    except (TypeError, ValueError):
        return str(x)


def yesno(x: Any) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return "PASS" if bool(x) else "FAIL"


def md_table(df: pd.DataFrame, formats: dict[str, Callable[[Any], str]] | None = None, index: bool = True,
             index_label: str | None = None) -> str:
    """Render a DataFrame as a GitHub markdown table with per-column formatters."""
    formats = formats or {}
    cols = list(df.columns)
    head = ([index_label or (df.index.name or "")] if index else []) + [str(c) for c in cols]
    lines = ["| " + " | ".join(head) + " |", "|" + "|".join(["---"] * len(head)) + "|"]
    for idx, row in df.iterrows():
        cells = [" / ".join(str(x) for x in idx) if isinstance(idx, tuple) else str(idx)] if index else []
        for c in cols:
            v = row[c]
            f = formats.get(c)
            cells.append(f(v) if f else ("" if v is None else (num(v) if isinstance(v, float) else str(v))))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
