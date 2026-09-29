"""Adjusted-price derivation, cache/manifest round trip, source chain and parsers (offline)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocktry.data import fetch


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("STOCKTRY_DATA_DIR", str(tmp_path))
    return tmp_path / "cache"


def _raw(n=30):
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="America/New_York")
    close = np.linspace(100, 110, n)
    adj = close * np.linspace(0.9, 1.0, n)
    return pd.DataFrame({"open": close - 1, "high": close + 1, "low": close - 2, "close_raw": close,
                         "adj_close": adj, "volume": np.arange(n, dtype=float), "dividend": 0.0}, index=idx)


def test_adjusted_ohlc_derivation():
    raw = _raw()
    out = fetch.normalize_bars(raw)
    f = raw["adj_close"].to_numpy() / raw["close_raw"].to_numpy()
    np.testing.assert_allclose(out["open"], (raw["open"] * f).to_numpy())
    np.testing.assert_allclose(out["high"], (raw["high"] * f).to_numpy())
    np.testing.assert_allclose(out["low"], (raw["low"] * f).to_numpy())
    np.testing.assert_allclose(out["close"], raw["adj_close"].to_numpy())
    np.testing.assert_allclose(out["close_raw"], raw["close_raw"].to_numpy())
    assert out.index.tz is None and out.index.name == "date"
    assert list(out.columns) == ["open", "high", "low", "close", "volume", "close_raw", "dividend"]
    assert out["volume"].dtype == np.int64


def test_normalize_drops_duplicates_and_fills_missing_open():
    raw = _raw()
    raw.iloc[3, raw.columns.get_loc("open")] = np.nan
    raw = pd.concat([raw, raw.iloc[[5]]]).sort_index()
    out = fetch.normalize_bars(raw)
    assert out.index.is_unique and len(out) == 30
    assert out["open"].iloc[3] == out["close"].iloc[3]


def test_cache_manifest_round_trip(cache, bars_factory):
    df = bars_factory(np.linspace(10, 20, 40), dividend=np.r_[np.zeros(39), 0.25])
    man = fetch.write_bars_cache("TEST", df, "yfinance", splits=[df.index[10]], cdir=cache)
    back, man2 = fetch.read_bars_cache("TEST", cdir=cache)
    pd.testing.assert_frame_equal(back, df, check_freq=False, rtol=1e-9)
    assert man2 == man
    assert man["rows"] == 40 and man["first_date"] == str(df.index[0].date())
    assert man["last_date"] == str(df.index[-1].date()) and man["dividend_events"] == 1
    assert man["splits"] == [str(df.index[10].date())] and len(man["sha256"]) == 64


def test_cache_tamper_detected(cache, bars_factory):
    fetch.write_bars_cache("TEST", bars_factory(np.linspace(10, 20, 40)), "yfinance", cdir=cache)
    p = cache / "TEST.csv"
    p.write_text(p.read_text().replace("10,", "11,", 1))
    with pytest.raises(fetch.CacheIntegrityError):
        fetch.read_bars_cache("TEST", cdir=cache)


def test_get_bars_uses_cache_without_network(cache, bars_factory, monkeypatch):
    df = bars_factory(np.linspace(10, 20, 40))
    fetch.write_bars_cache("TEST", df, "yfinance", cdir=cache)

    def boom(*a, **k):
        raise AssertionError("network source called although cache exists")

    monkeypatch.setattr(fetch, "SOURCES", {"yfinance": boom, "yahoo_raw": boom})
    out = fetch.get_bars("TEST")
    assert len(out) == 40


def test_source_chain_falls_back_to_yahoo_raw(cache, bars_factory, monkeypatch):
    good = bars_factory(np.linspace(10, 20, 300), start="2015-01-02")

    def fail(sym):
        raise fetch.FetchError("yfinance down")

    monkeypatch.setattr(fetch, "SOURCES", {"yfinance": fail, "yahoo_raw": lambda s: (good, [])})
    out, man = fetch.get_bars_with_manifest("SPYX", refresh=True)
    assert man["source"] == "yahoo_raw" and len(out) == 300


def test_stale_cache_when_network_fails(cache, bars_factory, monkeypatch):
    fetch.write_bars_cache("TEST", bars_factory(np.linspace(10, 20, 40)), "yfinance", cdir=cache)

    def fail(sym):
        raise fetch.FetchError("down")

    monkeypatch.setattr(fetch, "SOURCES", {"yfinance": fail, "yahoo_raw": fail})
    out, man = fetch.get_bars_with_manifest("TEST", refresh=True)
    assert man.get("stale") is True and len(out) == 40


def test_no_cache_and_no_network_raises(cache, monkeypatch):
    def fail(sym):
        raise fetch.FetchError("down")

    monkeypatch.setattr(fetch, "SOURCES", {"yfinance": fail, "yahoo_raw": fail})
    with pytest.raises(fetch.FetchError):
        fetch.get_bars("NOPE", refresh=True)


def test_quality_failure_rejects_source(cache, bars_factory, monkeypatch):
    bad = bars_factory(np.r_[np.linspace(10, 20, 30), [100.0], np.linspace(20, 21, 30)])  # +400 % jump
    good = bars_factory(np.linspace(10, 20, 300))
    monkeypatch.setattr(fetch, "SOURCES", {"yfinance": lambda s: (bad, []), "yahoo_raw": lambda s: (good, [])})
    _, man = fetch.get_bars_with_manifest("SPYX", refresh=True)
    assert man["source"] == "yahoo_raw"


@pytest.mark.parametrize("header", ["observation_date", "DATE"])
def test_parse_fred_csv(header):
    text = f"{header},DTB3\n2020-01-02,1.52\n2020-01-03,.\n2020-01-06,1.50\n"
    s = fetch.parse_fred_csv(text, "DTB3")
    assert list(s.index.strftime("%Y-%m-%d")) == ["2020-01-02", "2020-01-06"]
    assert s.iloc[-1] == 1.50


def test_parse_ff_factors():
    text = ("This file was created ...\n\n,Mkt-RF,SMB,HML,RF\n192607,   2.89,  -2.42,  -2.75,   0.22\n"
            "192608,   2.64,  -1.44,   4.13,   0.25\n\n Annual Factors: January-December \n,Mkt-RF,SMB,HML,RF\n"
            "  1927,  29.47,  -2.04,  -3.54,   3.12\n")
    ff = fetch.parse_ff_factors_csv(text)
    assert len(ff) == 2
    assert ff.index[0] == pd.Timestamp("1926-07-31")
    assert ff.loc["1926-08-31", "RF"] == pytest.approx(0.0025)
