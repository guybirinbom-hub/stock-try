"""Walk-forward selection and a pre-registered out-of-sample split.

Walk-forward (expanding window): starting after ``min_train_months`` months,
at each step the variant with the highest annualized Sharpe (versus T-bills)
over *all* months so far is chosen and its returns for the next
``step_months`` months are appended to the out-of-sample (OOS) series. Ties go
to the first column (deterministic). Each variant's monthly return already
depends only on data up to the previous month-end (engine lag), so selecting
among pre-computed variant return series is causal.

Approximation (documented): switching variants at a step boundary is treated
as if the new variant had been held all along; the one-off trade that would
move the portfolio from the old variant's position to the new one's is not
charged. With monthly-signal trend rules this is at most one extra switch per
year.

The pre-registered split date is 2006-01-01 (Faber's publication year):
months before it are "pre-publication", months from it on "post-publication".
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest import metrics as M

PREREGISTERED_SPLIT = "2006-01-01"


@dataclass
class WalkForwardResult:
    oos_returns: pd.Series
    oos_rf: pd.Series
    choices: pd.DataFrame  # one row per step

    def summary(self) -> dict:
        r, rf = self.oos_returns, self.oos_rf
        return {"months": len(r), "first_month": str(r.index[0].to_period("M")) if len(r) else None,
                "cagr": M.cagr(r), "sharpe": M.sharpe(r, rf), "max_dd": M.max_drawdown_from_returns(r),
                "vol": M.annualized_vol(r)}


def walk_forward(returns: pd.DataFrame, rf: pd.Series, min_train_months: int = 60, step_months: int = 12
                 ) -> WalkForwardResult:
    """``returns``: months x variants (aligned, no NaN); ``rf``: monthly T-bill returns."""
    df = returns.dropna()
    rfa = rf.reindex(df.index).fillna(0.0)
    n = len(df)
    pieces, rows = [], []
    k = min_train_months
    while k < n:
        train = df.iloc[:k]
        ex = train.sub(rfa.iloc[:k], axis=0)
        sd = ex.std(ddof=1)
        sr = (ex.mean() / sd.replace(0, np.nan)) * np.sqrt(12)
        best = sr.idxmax() if sr.notna().any() else df.columns[0]
        test = df.iloc[k: k + step_months][best]
        pieces.append(test)
        rows.append({"train_start": df.index[0].date(), "train_end": df.index[k - 1].date(),
                     "test_start": test.index[0].date(), "test_end": test.index[-1].date(),
                     "chosen": best, "train_sharpe": float(sr[best])})
        k += step_months
    oos = pd.concat(pieces) if pieces else pd.Series(dtype=float)
    return WalkForwardResult(oos, rfa.reindex(oos.index), pd.DataFrame(rows))


def split_metrics(r: pd.Series, rf: pd.Series, split: str = PREREGISTERED_SPLIT) -> pd.DataFrame:
    """Metrics before and from the split date (rows 'pre', 'post')."""
    cut = pd.Timestamp(split)
    out = {}
    for label, sel in (("pre", r.index < cut), ("post", r.index >= cut)):
        x = r[sel]
        if len(x) < 2:
            continue
        out[label] = {"first_month": str(x.index[0].to_period("M")), "last_month": str(x.index[-1].to_period("M")),
                      "months": len(x), "cagr": M.cagr(x), "sharpe": M.sharpe(x, rf.reindex(x.index)),
                      "max_dd": M.max_drawdown_from_returns(x), "vol": M.annualized_vol(x)}
    return pd.DataFrame(out).T
