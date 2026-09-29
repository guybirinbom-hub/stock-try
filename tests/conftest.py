"""Shared fixtures: synthetic bars and panels, and a guard that blocks outbound network.

Unit tests must never touch the network. The guard below makes any socket
connection to a non-local address fail loudly; localhost stays allowed so
tests can run local fake servers.
"""
from __future__ import annotations

import socket

import numpy as np
import pandas as pd
import pytest

_LOCAL = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
_real_connect = socket.socket.connect


def _guarded_connect(self, address):  # type: ignore[no-untyped-def]
    host = address[0] if isinstance(address, tuple) else None
    if host is not None and host not in _LOCAL:
        raise RuntimeError(f"network access disabled in unit tests (tried {host})")
    return _real_connect(self, address)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket.socket, "connect", _guarded_connect)


def make_bars(close, dates=None, open_=None, dividend=None, close_raw=None, start: str = "2000-01-03",
              volume: int = 1000) -> pd.DataFrame:
    """Bars in the package schema from arrays (adjusted close; as-traded close defaults to it)."""
    close = np.asarray(close, dtype=float)
    idx = pd.DatetimeIndex(dates) if dates is not None else pd.bdate_range(start, periods=len(close))
    op = np.asarray(open_, dtype=float) if open_ is not None else close.copy()
    raw = np.asarray(close_raw, dtype=float) if close_raw is not None else close.copy()
    div = np.asarray(dividend, dtype=float) if dividend is not None else np.zeros(len(close))
    df = pd.DataFrame({"open": op, "high": np.maximum(op, close), "low": np.minimum(op, close), "close": close,
                       "volume": volume, "close_raw": raw, "dividend": div}, index=idx)
    df.index.name = "date"
    return df


def gbm_close(n: int, mu: float = 0.07, sigma: float = 0.16, seed: int = 1, start: float = 100.0) -> np.ndarray:
    """Daily geometric Brownian motion (annual mu/sigma), deterministic."""
    rng = np.random.default_rng(seed)
    lr = rng.normal((mu - 0.5 * sigma**2) / 252, sigma / np.sqrt(252), n)
    return start * np.exp(np.cumsum(lr))


@pytest.fixture
def bars_factory():
    return make_bars


@pytest.fixture
def gbm():
    return gbm_close


@pytest.fixture
def dividend_payer_bars() -> pd.DataFrame:
    """Ten years of a quarterly dividend payer with a consistent adjusted/as-traded pair."""
    n = 252 * 10
    idx = pd.bdate_range("2005-01-03", periods=n)
    raw = gbm_close(n, seed=3)
    div = np.zeros(n)
    qe = pd.Series(np.arange(n), index=idx).groupby(idx.to_period("Q")).nth(40).to_numpy()
    div[qe] = raw[qe - 1] * 0.005  # 0.5 % per quarter, ~2 %/yr
    # Backward (Yahoo-style) adjustment: factor_t = prod over later ex-dates of (1 - d / prev raw close)
    f = np.ones(n)
    for k in qe[::-1]:
        f[:k] *= 1 - div[k] / raw[k - 1]
    adj = raw * f
    return make_bars(adj, dates=idx, open_=adj, dividend=div, close_raw=raw)
