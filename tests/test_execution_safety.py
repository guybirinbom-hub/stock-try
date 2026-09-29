"""Account preflight, hardening, the three kill-switch layers, dry-run default and live gating."""

from __future__ import annotations

from dataclasses import replace

import pytest

from stocktry.execution.guards import GuardViolation, KillSwitchEngaged
from stocktry.execution.killswitch import (
    RELEASE_CONFIRMATION,
    check_kill_switches,
    engage_broker_kill_switch,
    live_authorized,
    release_broker_kill_switch,
)
from stocktry.execution.preflight import harden_account
from stocktry.execution.runner import RunConfig
from stocktry.execution.simbroker import HARDENED_CONFIG
from stocktry.execution.testing import scenario


def refuse(sc, code, exc=GuardViolation):
    with pytest.raises(exc) as ei:
        sc.run()
    assert ei.value.code == code, ei.value
    assert sc.broker.orders == []
    return ei.value


# ------------------------------------------------------------ account (11)
@pytest.mark.parametrize("change, code", [
    ({"max_margin_multiplier": "2"}, "margin_enabled"),
    ({"max_margin_multiplier": "4"}, "margin_enabled"),
    ({"no_shorting": False}, "shorting_enabled"),
    ({"max_options_trading_level": 2}, "options_enabled"),
    ({"max_options_trading_level": None}, "options_level_unknown"),
])
def test_unsafe_account_configuration_aborts(tmp_path, change, code):
    sc = scenario(tmp_path, config=replace(HARDENED_CONFIG, **change))
    refuse(sc, code)


def test_blocked_account_aborts(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.trading_blocked = True
    refuse(sc, "account_blocked")


def test_non_empty_crypto_whitelist_aborts_and_missing_endpoint_is_tolerated(tmp_path):
    sc = scenario(tmp_path, crypto_whitelist=[{"address": "x"}])
    refuse(sc, "crypto_whitelist_not_empty")
    sc2 = scenario(tmp_path / "gone")
    sc2.broker.crypto_whitelist = None  # endpoint sunset -> best effort, logged
    assert sc2.run().status == "completed"


def test_harden_account_fixes_config_and_verifies(tmp_path):
    bad = replace(HARDENED_CONFIG, max_margin_multiplier="2", no_shorting=False, max_options_trading_level=3,
                  trade_confirm_email="none", disable_overnight_trading=False)
    sc = scenario(tmp_path, config=bad)
    report = harden_account(sc.broker)
    assert set(report.values()) == {"confirmed"}
    assert sc.run().status == "completed"


def test_harden_account_tolerates_broker_without_overnight_field(tmp_path):
    from stocktry.execution.broker import BrokerHTTPError

    sc = scenario(tmp_path, config=replace(HARDENED_CONFIG, max_margin_multiplier="4",
                                           disable_overnight_trading=None))
    real = sc.broker.set_account_configuration

    def picky(**fields):
        if "disable_overnight_trading" in fields:
            raise BrokerHTTPError(422, "unknown field")
        return real(**fields)

    sc.broker.set_account_configuration = picky
    report = harden_account(sc.broker)
    assert report["max_margin_multiplier"] == "confirmed"
    assert report["disable_overnight_trading"].startswith("unconfirmed")
    assert sc.broker.config.max_margin_multiplier == "1"


def test_harden_account_reports_mismatch(tmp_path):
    sc = scenario(tmp_path)
    sc.broker.set_account_configuration = lambda **kw: sc.broker.config  # broker ignores the change
    sc.broker.config = replace(HARDENED_CONFIG, no_shorting=False)
    with pytest.raises(GuardViolation) as ei:
        harden_account(sc.broker)
    assert ei.value.code == "hardening_failed"


# ------------------------------------------------------------ kill switches (12)
@pytest.mark.parametrize("value", ["on", "1", "true", "", "OFF", "off please"])
def test_env_kill_switch_aborts_for_anything_but_off(tmp_path, value):
    sc = scenario(tmp_path, cfg_overrides={"env": {"KILL_SWITCH": value}})
    refuse(sc, "kill_switch_env", KillSwitchEngaged)


def test_env_kill_switch_off_allows(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"env": {"KILL_SWITCH": "off"}})
    assert sc.run().status == "completed"


@pytest.mark.parametrize("content", ["on", "", "stop\n"])
def test_file_kill_switch_aborts(tmp_path, content):
    sc = scenario(tmp_path)
    sc.cfg.kill_switch_path.write_text(content)
    refuse(sc, "kill_switch_file", KillSwitchEngaged)


def test_file_kill_switch_off_allows(tmp_path):
    sc = scenario(tmp_path)
    sc.cfg.kill_switch_path.write_text("off\n")
    assert sc.run().status == "completed"


def test_file_kill_switch_engaged_mid_run_stops_next_order(tmp_path):
    sc = scenario(tmp_path)

    def engage_after_first(cid):
        sc.cfg.kill_switch_path.write_text("on")
        sc.broker.before_submit_hook = None

    sc.broker.before_submit_hook = engage_after_first
    with pytest.raises(KillSwitchEngaged):
        sc.run()
    assert len(sc.broker.orders) == 1


def test_broker_suspend_trade_kill_switch(tmp_path):
    sc = scenario(tmp_path)
    engage_broker_kill_switch(sc.broker)
    refuse(sc, "broker_suspend_trade", KillSwitchEngaged)
    with pytest.raises(GuardViolation):
        release_broker_kill_switch(sc.broker, "yes")
    assert sc.broker.config.suspend_trade is True
    release_broker_kill_switch(sc.broker, RELEASE_CONFIRMATION)
    assert sc.run().status == "completed"


def test_kill_switch_helper_unit(tmp_path):
    check_kill_switches({}, tmp_path / "absent")
    with pytest.raises(KillSwitchEngaged):
        check_kill_switches({"KILL_SWITCH": "yes"}, tmp_path / "absent")


# ------------------------------------------------------ dry run and live (13)
def test_default_mode_is_dry_run(tmp_path):
    assert RunConfig(strategy="x", universe=("SPY",)).dry_run is True
    sc = scenario(tmp_path)
    cfg = replace(sc.cfg, dry_run=True)
    res = sc.run(cfg=cfg)
    assert res.status == "dry_run"
    assert sc.broker.orders == [] and sc.broker.submit_calls == 0
    assert [cid for _, cid in res.planned] == [
        "demo-2026-10-01-SPY-sell-a1", "demo-2026-10-01-GLD-buy-a1", "demo-2026-10-01-IEF-buy-a1"]
    assert "client_order_id" in res.plan_text and "est_qty" in res.plan_text


def test_dry_run_outside_market_hours_still_shows_plan(tmp_path):
    from stocktry.execution.testing import et

    sc = scenario(tmp_path, now=et(2026, 10, 1, 20, 0))
    res = sc.run(cfg=replace(sc.cfg, dry_run=True))
    assert res.status == "dry_run" and "market_closed" in res.reason
    assert res.planned and sc.broker.orders == []


class LiveSim:
    """Wrap a sim broker and claim to be live."""

    def __init__(self, inner):
        self._inner = inner
        self.is_live = True
        self.name = "fake-live"

    def __getattr__(self, item):
        return getattr(self._inner, item)


@pytest.mark.parametrize("env, live, ack", [
    ({}, True, True),
    ({"LIVE_TRADING": "yes-live"}, False, True),
    ({"LIVE_TRADING": "yes-live"}, True, False),
    ({"LIVE_TRADING": "yes"}, True, True),
])
def test_live_requires_all_three_conditions(tmp_path, env, live, ack):
    sc = scenario(tmp_path, cfg_overrides={"env": env, "live": live, "i_understand_live": ack})
    live_broker = LiveSim(sc.broker)
    from stocktry.execution.runner import rebalance_once

    with pytest.raises(KillSwitchEngaged) as ei:
        rebalance_once(sc.targets, live_broker, sc.cfg, prices=sc.quotes, rebalance_id=sc.rebalance_id)
    assert ei.value.code == "live_not_authorized"
    assert sc.broker.orders == []


def test_live_with_all_three_conditions_submits(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"env": {"LIVE_TRADING": "yes-live"}, "live": True,
                                           "i_understand_live": True})
    from stocktry.execution.runner import rebalance_once

    res = rebalance_once(sc.targets, LiveSim(sc.broker), sc.cfg, prices=sc.quotes, rebalance_id=sc.rebalance_id)
    assert res.status == "completed" and len(sc.broker.orders) == 3


def test_live_flag_against_paper_broker_is_refused(tmp_path):
    sc = scenario(tmp_path, cfg_overrides={"env": {"LIVE_TRADING": "yes-live"}, "live": True,
                                           "i_understand_live": True})
    refuse(sc, "live_broker_mismatch")


def test_live_authorized_unit():
    assert live_authorized({"LIVE_TRADING": "yes-live"}, True, True)
    assert not live_authorized({"LIVE_TRADING": "yes-live "}, True, True)
    assert not live_authorized({}, True, True)
