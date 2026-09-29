"""Account hardening and preflight checks (run at the start of every run).

``harden_account`` applies the broker-side safety settings from the research
report (s.10) and re-reads the configuration to prove they stuck. Run it once
on a new paper account, and on a live account *before any live key exists*
in an automated environment.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from .broker import Broker
from .guards import GuardViolation, check_account, check_crypto_whitelist

__all__ = ["HARDENED_SETTINGS", "harden_account", "run_preflight"]

log = logging.getLogger("stocktry.execution.preflight")

HARDENED_SETTINGS: dict[str, Any] = {
    "max_margin_multiplier": "1",  # cash account: no margin
    "no_shorting": True,  # long-only
    "max_options_trading_level": 0,  # options disabled
    "disable_overnight_trading": True,  # no 24/5 overnight session orders
    "trade_confirm_email": "all",  # an email for every fill: an independent audit trail
    "fractional_trading": True,  # needed for notional orders
}


def harden_account(broker: Broker) -> dict[str, str]:
    """Apply ``HARDENED_SETTINGS`` then re-read and assert each one.

    Returns ``{setting: "confirmed" | "unconfirmed (...)"}``. Raises
    ``GuardViolation("hardening_failed")`` if any reported value is wrong.
    ``disable_overnight_trading`` is newer than the SDK model: if the broker
    rejects it, the other settings are applied without it, and it is reported
    as unconfirmed (not a failure) whenever the broker does not echo it back.
    The runner never sends overnight orders (market DAY orders inside regular
    hours only), so this setting is defence in depth.
    """
    overnight_note = "unconfirmed (field not reported by broker)"
    try:
        broker.set_account_configuration(**HARDENED_SETTINGS)
    except Exception as exc:  # noqa: BLE001 - retry without the one optional, newer field
        log.warning("configuration update rejected (%s); retrying without disable_overnight_trading",
                    type(exc).__name__)
        core = {k: v for k, v in HARDENED_SETTINGS.items() if k != "disable_overnight_trading"}
        broker.set_account_configuration(**core)
        overnight_note = "unconfirmed (broker rejected the field)"
    cfg = broker.get_account_configuration()
    report: dict[str, str] = {}
    failures: list[str] = []
    for key, want in HARDENED_SETTINGS.items():
        got = getattr(cfg, key, None)
        if key == "disable_overnight_trading" and got is None:
            report[key] = overnight_note
            continue
        if key == "max_margin_multiplier":
            try:
                ok = Decimal(str(got)) == Decimal(want)
            except Exception:
                ok = False
        else:
            ok = got == want
        report[key] = "confirmed" if ok else f"MISMATCH (got {got!r})"
        if not ok:
            failures.append(key)
    if failures:
        raise GuardViolation("hardening_failed", f"settings not applied: {failures}")
    log.info("account hardened: %s", report)
    return report


def run_preflight(broker: Broker) -> dict[str, str]:
    """Account preflight: margin 1, no shorting, options 0, not blocked/suspended,
    empty crypto withdrawal whitelist (best effort)."""
    account = broker.get_account()
    config = broker.get_account_configuration()
    check_account(account, config)
    try:
        entries = broker.get_crypto_whitelist()
    except Exception as exc:  # noqa: BLE001 - best effort; the endpoint may be sunset
        log.info("crypto whitelist endpoint unavailable (%s); skipped", type(exc).__name__)
        entries = None
    state = check_crypto_whitelist(entries)
    if state == "unavailable":
        log.info("crypto withdrawal whitelist endpoint unavailable (sunset 2026-10-09?); check skipped")
    return {"account": "ok", "crypto_whitelist": state}
