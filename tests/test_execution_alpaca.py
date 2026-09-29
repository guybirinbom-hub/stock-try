"""alpaca-py 0.44.0 adapter: retries neutralized, timeout mounted, submit looks up before failing.

No network: requests are served by an in-process fake HTTP adapter.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
import requests
from requests.adapters import BaseAdapter

from stocktry.execution.broker import BrokerError

pytest.importorskip("alpaca")

import alpaca.common.constants as alpaca_constants  # noqa: E402
from alpaca.trading.client import TradingClient  # noqa: E402

from stocktry.execution.alpaca_broker import (  # noqa: E402
    RETRY_ATTRIBUTES,
    AlpacaBroker,
    TimeoutHTTPAdapter,
    neutralize_retries,
)
from stocktry.execution.broker import BrokerHTTPError, BrokerTimeout, DuplicateClientOrderId  # noqa: E402

ENV = {"APCA_API_KEY_ID": "PKDUMMYDUMMYDUMMY123", "APCA_API_SECRET_KEY": "d" * 40}

ORDER_JSON = {
    "id": "904837e3-3b76-47ec-b432-046db621571b", "client_order_id": "demo-2026-10-01-SPY-buy-a1",
    "created_at": "2026-10-01T15:00:00.123456789Z", "submitted_at": "2026-10-01T15:00:00.123456789Z",
    "symbol": "SPY", "side": "buy", "type": "market", "time_in_force": "day", "status": "accepted",
    "notional": "12.34", "qty": None, "filled_qty": "0", "filled_avg_price": None,
}


class FakeAlpaca(BaseAdapter):
    """Serves canned responses; records every request (method, url, timeout)."""

    def __init__(self, routes):
        super().__init__()
        self.routes = routes  # list of (method, path_fragment, status, body_or_exception)
        self.calls = []

    def send(self, request, **kwargs):
        return self.serve(request, **kwargs)

    def serve(self, request, **kwargs):
        self.calls.append((request.method, request.url, kwargs.get("timeout")))
        for method, frag, status, body in self.routes:
            if request.method == method and frag in request.url:
                if isinstance(body, Exception):
                    raise body
                resp = requests.Response()
                resp.status_code = status
                resp._content = json.dumps(body).encode() if not isinstance(body, bytes) else body
                resp.url = request.url
                resp.request = request
                return resp
        raise AssertionError(f"unexpected request {request.method} {request.url}")

    def close(self):
        pass


@pytest.fixture
def mount(monkeypatch):
    """Serve every HTTPAdapter.send from a fake, keeping the adapters the code mounted.

    Patching the base ``HTTPAdapter.send`` (rather than mounting the fake)
    means ``TimeoutHTTPAdapter.send`` still runs first, so the timeout it
    injects is observable.
    """
    from requests.adapters import HTTPAdapter

    def _mount(broker, routes):
        fake = FakeAlpaca(routes)
        monkeypatch.setattr(HTTPAdapter, "send", lambda self, request, **kw: fake.serve(request, **kw))
        return fake

    return _mount


def test_retry_attributes_exist_and_are_neutralized_after_construction():
    raw = TradingClient(ENV["APCA_API_KEY_ID"], ENV["APCA_API_SECRET_KEY"], paper=True)
    for attr in RETRY_ATTRIBUTES:  # the private attributes we depend on still exist in this SDK version
        assert hasattr(raw, attr), attr
    assert raw._retry_codes == [429, 504] and raw._retry == 3  # the hazard is on by default

    b = AlpacaBroker(env=ENV)
    for client in (b._client, b._data):
        assert client._retry_codes == []
        assert client._retry == 0 and client._retry_wait == 0
        assert client._retry_codes is not alpaca_constants.DEFAULT_RETRY_EXCEPTION_CODES
        adapter = client._session.get_adapter("https://paper-api.alpaca.markets/v2/orders")
        assert isinstance(adapter, TimeoutHTTPAdapter) and adapter.default_timeout == (5.0, 15.0)
    assert alpaca_constants.DEFAULT_RETRY_EXCEPTION_CODES == [429, 504]  # shared default not mutated


def test_neutralize_refuses_unknown_sdk_shape():
    class NotAClient:
        pass

    with pytest.raises(RuntimeError, match="internals changed"):
        neutralize_retries(NotAClient())


def test_504_on_post_is_sent_once_and_order_is_looked_up(mount):
    """HTTP level: the SDK would POST 4 times; after neutralizing, exactly one POST."""
    b = AlpacaBroker(env=ENV, sleep=lambda s: None)
    fake = mount(b, [
        ("POST", "/v2/orders", 504, b"<html>504 Gateway Time-out</html>"),
        ("GET", "orders:by_client_order_id", 200, ORDER_JSON),
    ])
    order = b.submit_order("SPY", "buy", notional=Decimal("12.34"), client_order_id=ORDER_JSON["client_order_id"])
    posts = [c for c in fake.calls if c[0] == "POST"]
    assert len(posts) == 1
    assert order.client_order_id == ORDER_JSON["client_order_id"] and order.notional == Decimal("12.34")
    assert all(c[2] == (5.0, 15.0) for c in fake.calls)  # explicit timeout on every request


def test_unneutralized_sdk_would_duplicate_the_post(mount):
    raw = TradingClient(ENV["APCA_API_KEY_ID"], ENV["APCA_API_SECRET_KEY"], paper=True)
    raw._retry_wait = 0
    fake = mount(None, [("POST", "/v2/orders", 504, b"gateway timeout")])
    from alpaca.common.exceptions import APIError

    with pytest.raises(APIError):
        raw.post("/orders", {"symbol": "SPY"})
    posts = [c for c in fake.calls if c[0] == "POST"]
    assert len(posts) == 4  # 1 + 3 automatic retries: the duplicate-order hazard
    assert posts[0][2] is None  # ...and no timeout at all


def test_timeout_on_post_then_not_found_raises_timeout(mount):
    b = AlpacaBroker(env=ENV, sleep=lambda s: None)
    fake = mount(b, [
        ("POST", "/v2/orders", 0, requests.ReadTimeout("read timed out")),
        ("GET", "orders:by_client_order_id", 404, {"code": 40410000, "message": "order not found"}),
    ])
    with pytest.raises(BrokerTimeout):
        b.submit_order("SPY", "buy", notional=Decimal("5.00"), client_order_id="x-a1")
    assert len([c for c in fake.calls if c[0] == "POST"]) == 1
    assert len([c for c in fake.calls if c[0] == "GET"]) == 3  # looked up (with brief waits) before giving up


def test_duplicate_client_order_id_maps_to_typed_error(mount):
    b = AlpacaBroker(env=ENV, sleep=lambda s: None)
    mount(b, [("POST", "/v2/orders", 422, {"code": 40010001, "message": "client_order_id must be unique"})])
    with pytest.raises(DuplicateClientOrderId):
        b.submit_order("SPY", "buy", notional=Decimal("5.00"), client_order_id="dup-a1")


def test_notional_is_sent_as_exact_string_without_qty():
    b = AlpacaBroker(env=ENV)
    seen = {}

    class Capture(FakeAlpaca):
        def send(self, request, **kw):
            if request.method == "POST":
                seen.update(json.loads(request.body))
            return super().send(request, **kw)

    cap = Capture([("POST", "/v2/orders", 200, ORDER_JSON)])
    b._client._session.mount("https://", cap)  # replaces the timeout adapter; fine for body capture
    b.submit_order("SPY", "buy", notional=Decimal("12.34"), client_order_id=ORDER_JSON["client_order_id"])
    assert seen["notional"] == "12.34" and "qty" not in seen
    assert seen["type"] == "market" and seen["time_in_force"] == "day"
    with pytest.raises(ValueError):
        b.submit_order("SPY", "buy", notional=Decimal("12.345"), client_order_id="y")
    with pytest.raises(ValueError):
        b.submit_order("SPY", "buy", notional=Decimal("1"), qty=Decimal("1"), client_order_id="z")


def test_paper_is_default_and_live_needs_env_and_flag():
    assert AlpacaBroker(env=ENV).base_url == "https://paper-api.alpaca.markets"
    # flag without env -> refused (EXEC-07: it used to fall back to a paper client, silently)
    with pytest.raises(BrokerError, match="LIVE_TRADING"):
        AlpacaBroker(env=ENV, live=True)
    b = AlpacaBroker(env=ENV)
    assert not b.is_live and b.base_url == "https://paper-api.alpaca.markets"
    b = AlpacaBroker(env={**ENV, "LIVE_TRADING": "yes-live"})  # env without flag -> paper
    assert not b.is_live
    b = AlpacaBroker(env={**ENV, "LIVE_TRADING": "yes-live"}, live=True)
    assert b.is_live and b.base_url == "https://api.alpaca.markets"


def test_response_mapping(mount):
    b = AlpacaBroker(env=ENV)
    mount(b, [
        ("GET", "/v2/clock", 200, {"timestamp": "2026-10-01T11:00:00.1-04:00", "is_open": True,
                                    "next_open": "2026-10-02T09:30:00-04:00",
                                    "next_close": "2026-10-01T16:00:00-04:00"}),
        ("GET", "/v2/calendar", 200, [{"date": "2026-11-27", "open": "09:30", "close": "13:00",
                                       "session_open": "0400", "session_close": "2000"}]),
        ("GET", "/v2/account/configurations", 200, {
            "max_margin_multiplier": "1", "no_shorting": True, "max_options_trading_level": 0,
            "suspend_trade": False, "trade_confirm_email": "all", "fractional_trading": True,
            "ptp_no_exception_entry": False}),
        ("GET", "/v2/account", 200, {"account_number": "PA3SECRET", "cash": "100.50", "equity": "130.00",
                                     "non_marginable_buying_power": "100.50", "buying_power": "201.00",
                                     "multiplier": "2", "shorting_enabled": True, "options_trading_level": 0,
                                     "trading_blocked": False, "account_blocked": False,
                                     "trade_suspended_by_user": False, "status": "ACTIVE"}),
        ("GET", "/v2/stocks/trades/latest", 200, {"trades": {"SPY": {"p": 571.23, "t": "2026-10-01T15:00:00Z"}}}),
        ("GET", "/v2/wallets/whitelists", 404, {"code": 40410000, "message": "not found"}),
    ])
    clock = b.get_clock()
    assert clock.is_open and clock.now.hour == 11
    (day,) = b.get_calendar(date(2026, 11, 27), date(2026, 11, 27))
    assert day.close.hour == 13 and day.close.tzinfo is not None
    acct = b.get_account()
    assert acct.multiplier == "2" and acct.shorting_enabled and acct.cash == Decimal("100.50")
    assert "PA3SECRET" not in repr(acct)
    cfg = b.get_account_configuration()
    assert cfg.max_options_trading_level == 0 and cfg.disable_overnight_trading is None
    lp = b.get_latest_price("SPY")
    assert lp.price == Decimal("571.23")
    assert b.get_crypto_whitelist() is None  # endpoint gone -> None, not an error


def test_http_errors_are_typed(mount):
    b = AlpacaBroker(env=ENV)
    mount(b, [("GET", "/v2/clock", 500, {"message": "internal"})])
    with pytest.raises(BrokerHTTPError) as ei:
        b.get_clock()
    assert ei.value.status == 500
