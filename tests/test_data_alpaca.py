"""Alpaca Market Data bars (R4): the licence-clean price source for the paper runner. Mocked clients only."""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("alpaca")

from alpaca.data.enums import Adjustment, DataFeed  # noqa: E402

from stocktry.data import alpaca_bars as AB  # noqa: E402
from stocktry.data.universe import BAR_COLUMNS  # noqa: E402

END = date(2026, 9, 28)


def _raw_bars(symbol: str, n: int = 450, start: str = "2024-12-02", base: float = 100.0) -> list[dict]:
    days = pd.bdate_range(start, periods=n)
    closes = base * np.exp(np.linspace(0.0, 0.2, n))
    # Alpaca stamps daily bars at midnight New York time, in UTC ("...T04:00:00Z" in summer, "T05:00:00Z" in winter)
    ts = [d.tz_localize("America/New_York").tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ") for d in days]
    return [{"t": t, "o": c * 0.999, "h": c * 1.01, "l": c * 0.99, "c": c, "v": 1000 + i, "n": 10, "vw": c}
            for i, (t, c) in enumerate(zip(ts, closes))]


class FakeBarsClient:
    def __init__(self, bars: dict[str, list[dict]]):
        self.bars = bars
        self.requests = []

    def get_stock_bars(self, req):
        self.requests.append(req)
        return {s: self.bars.get(s, []) for s in req.symbol_or_symbols}


class FakeCorporateActions:
    def __init__(self, rows=None, fail: bool = False):
        self.rows, self.fail, self.requests = rows or [], fail, []

    def get_corporate_actions(self, req):
        self.requests.append(req)
        if self.fail:
            raise RuntimeError("forbidden")
        return {"cash_dividends": self.rows}


def test_bars_have_the_get_bars_schema_and_new_york_session_dates():
    client = FakeBarsClient({"SPY": _raw_bars("SPY"), "IEF": _raw_bars("IEF", base=95.0)})
    out = AB.get_bars_alpaca(["SPY", "IEF"], end=END, client=client, env={}, dividends=False)
    assert set(out) == {"SPY", "IEF"}
    df = out["SPY"]
    assert list(df.columns) == BAR_COLUMNS and df.index.name == "date" and df.index.tz is None
    assert df.index[0] == pd.Timestamp("2024-12-02")  # 05:00Z in winter is still the New York session date
    assert (df.index == df.index.normalize()).all() and df.index.is_monotonic_increasing
    assert (df["close_raw"] == df["close"]).all() and (df["dividend"] == 0).all()
    assert df["volume"].dtype == "int64"


def test_request_is_all_adjusted_daily_iex_by_default_with_at_least_18_months():
    client = FakeBarsClient({"SPY": _raw_bars("SPY")})
    AB.get_bars_alpaca(["SPY"], end=END, client=client, env={}, dividends=False, history_days=100)
    req = client.requests[0]
    assert req.adjustment == Adjustment.ALL and req.feed == DataFeed.IEX
    assert str(req.timeframe) in ("1Day", "1D") or req.timeframe.amount_value == 1
    assert (END - req.start.date()).days >= 540  # never less than ~18 months of history
    assert req.end.date() > END  # the end day itself is included


def test_feed_is_configurable_but_only_iex_or_sip():
    client = FakeBarsClient({"SPY": _raw_bars("SPY")})
    AB.get_bars_alpaca(["SPY"], end=END, client=client, env={"APCA_DATA_FEED": "sip"}, dividends=False)
    assert client.requests[-1].feed == DataFeed.SIP
    AB.get_bars_alpaca(["SPY"], end=END, client=client, env={"APCA_DATA_FEED": "sip"}, feed="iex", dividends=False)
    assert client.requests[-1].feed == DataFeed.IEX  # an explicit argument wins over the environment
    with pytest.raises(ValueError):
        AB.get_bars_alpaca(["SPY"], end=END, client=client, env={}, feed="delayed_sip")


def test_missing_symbol_raises_and_no_keys_raises():
    client = FakeBarsClient({"SPY": _raw_bars("SPY")})
    with pytest.raises(AB.AlpacaDataError, match="GLD"):
        AB.get_bars_alpaca(["SPY", "GLD"], end=END, client=client, env={}, dividends=False)
    with pytest.raises(AB.AlpacaDataError, match="APCA_API_KEY_ID"):
        AB.get_bars_alpaca(["SPY"], end=END, env={})


def test_sdk_errors_are_wrapped_without_details():
    class Boom:
        def get_stock_bars(self, req):
            raise ConnectionError("https://data.alpaca.markets/... secret-ish detail")

    with pytest.raises(AB.AlpacaDataError) as ei:
        AB.get_bars_alpaca(["SPY"], end=END, client=Boom(), env={}, dividends=False)
    assert "secret-ish" not in str(ei.value) and "ConnectionError" in str(ei.value)


def test_cash_dividends_land_on_their_ex_dates_best_effort(caplog):
    client = FakeBarsClient({"SPY": _raw_bars("SPY")})
    ca = FakeCorporateActions([{"symbol": "SPY", "rate": 1.83, "ex_date": "2025-06-20", "special": False},
                               {"symbol": "QQQ", "rate": 0.5, "ex_date": "2025-06-20"}])
    out = AB.get_bars_alpaca(["SPY"], end=END, client=client, corporate_actions_client=ca, env={})
    divs = out["SPY"]["dividend"]
    assert divs[divs > 0].to_dict() == {pd.Timestamp("2025-06-20"): pytest.approx(1.83)}
    with caplog.at_level("WARNING"):
        out = AB.get_bars_alpaca(["SPY"], end=END, client=client, corporate_actions_client=FakeCorporateActions(
            fail=True), env={})
    assert (out["SPY"]["dividend"] == 0).all() and "dividends set to 0" in caplog.text


def test_runner_inputs_from_alpaca_record_source_and_feed(monkeypatch):
    """inputs_from_registry(price_source='alpaca') uses Alpaca bars and says so; a failure falls back to the
    research cache with a warning, and the fallback is recorded."""
    pytest.importorskip("stocktry.strategies.registry")
    from stocktry.execution import strategy_io

    idx = pd.bdate_range("2024-06-03", "2026-09-30")
    frame = pd.DataFrame({"SPY": np.linspace(400, 600, len(idx))}, index=idx)
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends_alpaca",
                        lambda symbols, *, end, feed=None, env=None: (frame[symbols], {}, feed or "iex"))
    inp = strategy_io.inputs_from_registry("spy_buy_hold", decision_date=date(2026, 9, 30),
                                           last_session=date(2026, 9, 30), refresh=False, price_source="alpaca")
    assert (inp.price_source, inp.data_feed, inp.targets) == ("alpaca", "iex", {"SPY": 1.0})

    def broken(symbols, *, end, feed=None, env=None):
        raise AB.AlpacaDataError("no bars")

    def no_download(symbols, *, refresh):
        raise AssertionError("the Alpaca fallback must not go through the downloading cache path")

    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends_alpaca", broken)
    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends", no_download)
    monkeypatch.setattr(strategy_io, "read_cached_closes_and_dividends", lambda symbols: (frame[symbols], {}))
    inp = strategy_io.inputs_from_registry("spy_buy_hold", decision_date=date(2026, 9, 30),
                                           last_session=date(2026, 9, 30), refresh=True, price_source="alpaca")
    assert inp.price_source.startswith("cache (fallback: alpaca") and inp.data_feed is None
    assert "not refreshed" in inp.price_source


def _cached_bars(n: int = 300) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-09-30", periods=n)
    c = np.linspace(400.0, 600.0, n)
    df = pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1000,
                       "close_raw": c, "dividend": 0.0}, index=idx)
    df.index.name = "date"
    return df


def test_alpaca_fallback_reads_the_local_cache_without_any_download(monkeypatch, tmp_path):
    """If Alpaca fails, an existing local cache is read as is (hash-verified); nothing is fetched, even with
    refresh=True. With no local cache the run stops with a data error instead of downloading from Yahoo."""
    from stocktry.data import fetch as data_fetch
    from stocktry.execution import strategy_io

    monkeypatch.setenv("STOCKTRY_DATA_DIR", str(tmp_path))

    def broken(symbols, *, end, feed=None, env=None):
        raise AB.AlpacaDataError("no bars")

    def network(*a, **k):
        raise AssertionError("network fetch attempted by the Alpaca fallback")

    monkeypatch.setattr(strategy_io, "fetch_closes_and_dividends_alpaca", broken)
    monkeypatch.setattr(data_fetch, "fetch_bars", network)
    monkeypatch.setattr(data_fetch, "get_bars", network)
    with pytest.raises(RuntimeError, match="no local cache for SPY"):
        strategy_io.load_closes(["SPY"], price_source="alpaca", refresh=True, end=date(2026, 9, 30))

    data_fetch.write_bars_cache("SPY", _cached_bars(), "test")
    frame, divs, used, feed = strategy_io.load_closes(["SPY"], price_source="alpaca", refresh=True,
                                                      end=date(2026, 9, 30))
    assert used.startswith("cache (fallback: alpaca AlpacaDataError") and feed is None
    assert frame.index[-1] == pd.Timestamp("2026-09-30") and list(frame.columns) == ["SPY"]
