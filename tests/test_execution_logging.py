"""Log scrubbing: API keys, secrets, account numbers and the ntfy topic never print."""

from __future__ import annotations

import io
import logging
import sys

import pytest

from stocktry.execution.alerts import Alerter, safe_alert_text
from stocktry.execution.logsafe import REDACTED, Scrubber, ScrubbingStream, configure_logging
from stocktry.execution.testing import RecordingTransport, scenario

KEY_ID = "PKZ7Q2XW4ELMNOPQRS12"
SECRET = "sEcReT0123456789abcdefghijklmnopqrstuvwx"  # 40 chars
TOPIC = "stocktry-alerts-8f3k2"
ACCOUNT_NO = "PA3XYZ123ABC"
ENV = {"APCA_API_KEY_ID": KEY_ID, "APCA_API_SECRET_KEY": SECRET, "NTFY_TOPIC": TOPIC,
       "HEALTHCHECK_URL": "https://hc-ping.com/1234abcd-uuid", "SOME_OTHER_TOKEN": "tok-9999-secret"}
SENSITIVE = [KEY_ID, SECRET, TOPIC, ACCOUNT_NO, "hc-ping.com/1234abcd-uuid", "tok-9999-secret", "123456789012"]


@pytest.fixture
def scrubbed_log():
    buf = io.StringIO()
    root = logging.getLogger()
    old_handlers, old_level = list(root.handlers), root.level
    configure_logging(logging.DEBUG, stream=buf, env=ENV)
    yield buf
    for h in list(root.handlers):
        if h not in old_handlers:
            root.removeHandler(h)
    root.setLevel(old_level)


def assert_clean(text):
    for s in SENSITIVE:
        assert s not in text, f"leaked {s!r}"


def test_scrubber_redacts_values_and_patterns():
    s = Scrubber(ENV)
    text = (f"key={KEY_ID} secret={SECRET} topic {TOPIC} account {ACCOUNT_NO} acct# 123456789012 "
            f'{{"account_number": "987654321"}} APCA-API-SECRET-KEY: {SECRET} other tok-9999-secret')
    out = s(text)
    assert_clean(out)
    assert "987654321" not in out
    assert REDACTED in out
    assert "2026-10-01" in s("rebalance 2026-10-01 SPY $12.34")  # ordinary content survives


def test_logging_filter_scrubs_messages_args_and_tracebacks(scrubbed_log):
    log = logging.getLogger("stocktry.test")
    log.info("using key %s and secret %s", KEY_ID, SECRET)
    log.warning("account %s", ACCOUNT_NO)
    try:
        raise RuntimeError(f"auth failed for {KEY_ID}/{SECRET}")
    except RuntimeError:
        log.exception("boom")
    logging.getLogger("alpaca.common.rest").error("header APCA-API-KEY-ID=%s", KEY_ID)
    out = scrubbed_log.getvalue()
    assert "boom" in out and "RuntimeError" in out
    assert_clean(out)


def test_stdout_wrapper_scrubs_print(capsys):
    stream = ScrubbingStream(sys.stdout, Scrubber(ENV))
    print(f"oops {SECRET} {KEY_ID}", file=stream)
    out = capsys.readouterr().out
    assert "oops" in out
    assert_clean(out)


def test_full_run_with_alerts_leaks_nothing(tmp_path, scrubbed_log, capsys):
    transport = RecordingTransport()
    sc = scenario(tmp_path, cfg_overrides={"env": {**ENV, "KILL_SWITCH": "off"},
                                           "alerter": Alerter(ntfy_topic=TOPIC, transport=transport)})
    sc.broker.inject_failure("submit", "http_504_after_record")
    res = sc.run()
    assert res.alerts  # the 504 produced an alert
    logging.getLogger("stocktry").error("diagnostic dump %s %s", KEY_ID, SECRET)
    out = scrubbed_log.getvalue() + capsys.readouterr().out
    assert_clean(out)
    for _method, _url, kwargs in transport.calls:
        body = kwargs.get("data", b"").decode()
        assert "$" not in body and "SPY" not in body  # no amounts or positions in external alerts
        assert_clean(body)


def test_alert_text_is_restricted():
    cleaned = safe_alert_text('demo 2026-10-01 {"cash": "$1,234.56"}')
    assert not set(cleaned) & set('${}",')
    a = Alerter(ntfy_topic="bad topic/../x", transport=RecordingTransport())
    a.alert("code", "detail")
    assert a.transport.calls == []  # invalid topic -> not sent


def test_ledger_contains_no_secrets(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"env": ENV})
    sc.run()
    assert_clean(sc.cfg.ledger_path.read_text())


def test_alpaca_broker_repr_and_errors_do_not_leak():
    pytest.importorskip("alpaca")
    from stocktry.execution.alpaca_broker import AlpacaBroker
    from stocktry.execution.broker import BrokerError

    b = AlpacaBroker(env={"APCA_API_KEY_ID": KEY_ID, "APCA_API_SECRET_KEY": SECRET})
    assert KEY_ID not in repr(b) and SECRET not in repr(b)
    assert not any(v in (KEY_ID, SECRET) for v in vars(b).values() if isinstance(v, str))
    with pytest.raises(BrokerError) as ei:
        AlpacaBroker(env={"APCA_API_KEY_ID": KEY_ID})
    assert KEY_ID not in str(ei.value)
