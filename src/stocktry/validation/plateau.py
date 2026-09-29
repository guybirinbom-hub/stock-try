"""Parameter-plateau analysis.

A robust rule should not sit on a sharp peak. For a numeric parameter with
chosen value c, the *neighbourhood* is every grid value p with
|p - c| <= 25 % of c (for c = 10 months: 8..12). The plateau statistic is

    min over the neighbourhood of Sharpe(p) / Sharpe(c)

(worst-case fraction of the Sharpe ratio retained under a +-25 % perturbation;
Gate A.5 requires >= 0.70). The mean retained fraction is reported too. If
Sharpe(c) <= 0 the statistic is undefined (NaN).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def plateau_statistic(sharpe_by_param: pd.Series, center: float, rel: float = 0.25) -> dict:
    s = sharpe_by_param.dropna().sort_index()
    if center not in s.index:
        raise KeyError(f"center {center} not in grid")
    base = float(s.loc[center])
    nb = s[(np.abs(s.index.to_numpy(dtype=float) - center) <= rel * center + 1e-12)]
    if base <= 0:
        return {"center": center, "center_sharpe": base, "neighbors": list(nb.index), "min_retained": float("nan"),
                "mean_retained": float("nan")}
    ratios = nb / base
    return {"center": center, "center_sharpe": base, "neighbors": [int(x) if float(x).is_integer() else x
                                                                   for x in nb.index],
            "min_retained": float(ratios.min()), "mean_retained": float(ratios.mean()),
            "worst_neighbor": nb.idxmin()}


def sweep_frame(rows: list[dict], index: str, columns: str | None = None, value: str = "sharpe") -> pd.DataFrame:
    """Pivot sweep results (list of dicts) into a table (1-D if ``columns`` is None)."""
    df = pd.DataFrame(rows)
    if columns is None:
        return df.set_index(index)[[value]].sort_index()
    return df.pivot_table(index=index, columns=columns, values=value, aggfunc="first").sort_index()
