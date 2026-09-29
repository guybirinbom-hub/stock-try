"""Universe table, return-based splicing and panel construction."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocktry.data import universe as U
from stocktry.data.panel import build_panel, load_series, panel_from_bars

from conftest import gbm_close, make_bars


def test_spread_table_matches_spec():
    expect = {"SPY": 0.5, "VTI": 1.0, "IEF": 1.0, "AGG": 1.5, "BND": 1.5, "VNQ": 1.5, "GLD": 1.5, "EFA": 1.5,
              "DBC": 3.0, "BIL": 0.5, "SHV": 0.5, "VFINX": 0.0, "VTSMX": 0.0, "VFITX": 0.0, "VBMFX": 0.0,
              "VGSIX": 0.0, "VGTSX": 0.0}
    for s, bp in expect.items():
        assert U.UNIVERSE[s].half_spread_bp == bp
    for s in ("VFINX", "VTSMX", "VFITX", "VBMFX", "VGSIX", "VGTSX"):
        assert U.UNIVERSE[s].is_proxy


def test_international_and_commodity_never_spliced():
    assert not U.SPLICES["EFA"].enabled and not U.SPLICES["DBC"].enabled
    assert U.SPLICES["IEF"].min_corr == 0.95 and U.SPLICES["VNQ"].min_corr == 0.995


def _pair(n_proxy=2520, overlap_start=1260, noise=0.0005, seed=5):
    """Proxy from day 0, target from day ``overlap_start``; target = proxy returns + small noise."""
    idx = pd.bdate_range("2000-01-03", periods=n_proxy)
    p = gbm_close(n_proxy, seed=seed)
    rng = np.random.default_rng(seed + 1)
    r = np.diff(p) / p[:-1] + rng.normal(0, noise, n_proxy - 1)
    t = 50.0 * np.cumprod(np.r_[1.0, 1.0 + r[overlap_start:]])  # prices on days overlap_start .. n-1
    proxy = make_bars(p, dates=idx)
    target = make_bars(t, dates=idx[overlap_start:])
    return target, proxy


def test_splice_accepted_returns_and_boundary():
    target, proxy = _pair()
    rule = U.SpliceRule("SPY", "VFINX", True, 0.995)
    out, info = U.splice_bars(target, proxy, rule)
    assert info.accepted and info.overlap_months >= 36 and info.correlation >= 0.995
    b = pd.Timestamp(info.boundary)
    first = target.index[0]
    assert b.month == first.month and b.year == first.year and b == target.index[
        (target.index.year == first.year) & (target.index.month == first.month)][-1]
    # After the boundary: exactly the target's returns; level equals the target from the boundary on.
    np.testing.assert_allclose(out.loc[b:, "close"].to_numpy(), target.loc[b:, "close"].to_numpy())
    # Up to the boundary: proxy returns + (ER_proxy - ER_target)/252 per day.
    adj = (U.UNIVERSE["VFINX"].expense_ratio - U.UNIVERSE["SPY"].expense_ratio) / 252
    seg = out.loc[:b, "close"]
    pr = proxy.loc[:b, "close"].pct_change().iloc[1:]
    np.testing.assert_allclose(seg.pct_change().iloc[1:].to_numpy(), (pr + adj).to_numpy(), rtol=1e-9, atol=1e-12)
    assert out.loc[:b].iloc[:-1]["close_raw"].isna().all()
    assert out.index[0] == proxy.index[0]


def test_splice_rejected_low_correlation():
    target, proxy = _pair(noise=0.02)
    with pytest.raises(U.SpliceRejected):
        U.splice_bars(target, proxy, U.SpliceRule("SPY", "VFINX", True, 0.995))


def test_splice_rejected_short_overlap():
    target, proxy = _pair(n_proxy=1400, overlap_start=1000)  # ~19 months of overlap
    with pytest.raises(U.SpliceRejected):
        U.splice_bars(target, proxy, U.SpliceRule("SPY", "VFINX", True, 0.9))


def test_splice_disabled_rule_rejected():
    target, proxy = _pair()
    with pytest.raises(U.SpliceRejected):
        U.splice_bars(target, proxy, U.SPLICES["EFA"])


def _loader(frames):
    return lambda s: (frames[s], {"splits": []})


def test_panel_proxy_mode_substitutes_efa_and_respects_valid_from():
    idx = pd.bdate_range("1985-01-02", periods=252 * 12)
    frames = {
        "EFA": make_bars(gbm_close(len(idx), seed=1), dates=idx),
        "VGTSX": make_bars(gbm_close(len(idx), seed=2), dates=idx),
        "SPY": make_bars(gbm_close(252 * 4, seed=4), dates=idx[-252 * 4:]),
        "VFINX": make_bars(gbm_close(len(idx), seed=4), dates=idx),
    }
    p = build_panel(["EFA"], "proxy", loader=_loader(frames), dtb3_pct=pd.Series(dtype=float), run_quality=False)
    np.testing.assert_allclose(p.closes["EFA"].to_numpy(), frames["VGTSX"]["close"].to_numpy())
    assert p.meta["EFA"].symbol == "VGTSX"
    # VFINX rows before valid_from (1987-01-01) are dropped when it is used as a proxy.
    df, _, _, _ = load_series("VFINX", "etf", _loader(frames), run_quality=False)
    assert df.index[0] >= pd.Timestamp("1987-01-01")


def test_panel_alignment_ffill_and_no_backfill():
    a = make_bars(np.linspace(10, 11, 30), start="2020-01-01")
    b = make_bars(np.linspace(20, 21, 20), dates=a.index[10:])
    b = b.drop(b.index[5])  # a missing day after inception is forward-filled
    p = panel_from_bars({"A": a, "B": b}, None)
    assert p.closes["B"].iloc[:10].isna().all()
    assert p.closes["B"].iloc[15] == p.closes["B"].iloc[14]
    assert p.opens["B"].iloc[15] == p.closes["B"].iloc[14]
