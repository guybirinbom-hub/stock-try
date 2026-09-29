"""Three independent kill-switch layers plus the live-trading authorization.

Layer 1 (local): a file named ``KILL_SWITCH`` at the repository root (or at the
path in env ``KILL_SWITCH_FILE``), or env var ``KILL_SWITCH``. Any value other
than exactly ``off`` aborts the run -- including an empty file or an empty
variable. Checked at the start of every run and again before every order.

Layer 2 (broker): Alpaca's account configuration ``suspend_trade=true`` makes
the broker refuse new orders even if this code is buggy. ``engage_broker_kill_switch``
sets it; the dashboard fallback is documented in docs/runbook-paper-trading.md.
The runner's preflight also aborts when it is set.

Layer 3 (mode): dry-run is the default. Submitting to a *live* broker needs all
three of env ``LIVE_TRADING=yes-live``, the ``--i-understand-live`` flag and
``live=True``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from .broker import AccountConfig, Broker
from .guards import GuardViolation, KillSwitchEngaged

__all__ = [
    "KILL_SWITCH_ENV",
    "KILL_SWITCH_FILE_ENV",
    "LIVE_ENV",
    "LIVE_ENV_VALUE",
    "RELEASE_CONFIRMATION",
    "default_kill_switch_path",
    "check_kill_switches",
    "engage_broker_kill_switch",
    "release_broker_kill_switch",
    "live_authorized",
    "check_submission_mode",
    "source_checkout_root",
]

KILL_SWITCH_ENV = "KILL_SWITCH"
KILL_SWITCH_FILE_ENV = "KILL_SWITCH_FILE"
LIVE_ENV = "LIVE_TRADING"
LIVE_ENV_VALUE = "yes-live"
RELEASE_CONFIRMATION = "release-broker-kill-switch"


def source_checkout_root() -> Path:
    """The repository root, derived from this file's location (``src/stocktry/execution/``).

    Correct only for a source checkout or an editable install; after a non-editable
    ``pip install .`` this file lives in site-packages and the derived "root" is
    not the repository, so a committed ``KILL_SWITCH`` file would be silently
    ignored. The root must contain ``pyproject.toml``; otherwise this raises.
    """
    root = Path(__file__).resolve().parents[3]
    if not (root / "pyproject.toml").is_file():
        raise RuntimeError(
            f"stocktry is not running from a source checkout ({root} has no pyproject.toml); install it with "
            "`pip install -e .` or set KILL_SWITCH_FILE and pass --ledger explicitly")
    return root


def default_kill_switch_path(env: Mapping[str, str] | None = None) -> Path:
    """``$KILL_SWITCH_FILE`` if set, else ``<repo root>/KILL_SWITCH`` (source checkout only, see
    :func:`source_checkout_root`)."""
    env = os.environ if env is None else env
    if env.get(KILL_SWITCH_FILE_ENV):
        return Path(env[KILL_SWITCH_FILE_ENV])
    try:
        return source_checkout_root() / "KILL_SWITCH"
    except RuntimeError as exc:
        # Fail safe: without a verifiable kill-switch location nothing may trade.
        raise KillSwitchEngaged("kill_switch_path_unknown", str(exc)) from None


def check_kill_switches(env: Mapping[str, str], path: Path) -> None:
    """Raise ``KillSwitchEngaged`` if the env or file kill switch is anything but 'off'."""
    if KILL_SWITCH_ENV in env and env[KILL_SWITCH_ENV].strip() != "off":
        raise KillSwitchEngaged("kill_switch_env", "environment variable KILL_SWITCH is engaged")
    try:
        exists = path.exists()
    except OSError:
        exists = True  # cannot tell -> treat as engaged
    if exists:
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError:
            content = "<unreadable>"
        if content != "off":
            raise KillSwitchEngaged("kill_switch_file", f"kill-switch file {path.name} is present")


def engage_broker_kill_switch(broker: Broker) -> AccountConfig:
    """Set ``suspend_trade=True`` at the broker and verify it stuck."""
    cfg = broker.set_account_configuration(suspend_trade=True)
    again = broker.get_account_configuration()
    if not (cfg.suspend_trade and again.suspend_trade):
        raise GuardViolation("kill_switch_not_confirmed", "broker did not confirm suspend_trade=true")
    return again


def release_broker_kill_switch(broker: Broker, confirm: str) -> AccountConfig:
    """Clear ``suspend_trade``. Requires ``confirm == RELEASE_CONFIRMATION``."""
    if confirm != RELEASE_CONFIRMATION:
        raise GuardViolation("release_not_confirmed", "pass the exact release confirmation string")
    broker.set_account_configuration(suspend_trade=False)
    return broker.get_account_configuration()


def live_authorized(env: Mapping[str, str], live: bool, i_understand_live: bool) -> bool:
    """True only if all three live conditions hold."""
    return bool(live) and bool(i_understand_live) and env.get(LIVE_ENV) == LIVE_ENV_VALUE


def check_submission_mode(
    *, broker_is_live: bool, dry_run: bool, live: bool, i_understand_live: bool, env: Mapping[str, str]
) -> None:
    """Refuse any live request that lacks one of the three conditions.

    Dry runs never submit, so they are always allowed (even against a live
    broker, for read-only inspection).
    """
    if live and not live_authorized(env, live, i_understand_live):
        raise KillSwitchEngaged(
            "live_not_authorized", "live requested without LIVE_TRADING=yes-live and --i-understand-live"
        )
    if dry_run:
        return
    if broker_is_live and not live_authorized(env, live, i_understand_live):
        raise KillSwitchEngaged("live_not_authorized", "broker is live but live trading is not fully authorized")
    if live and not broker_is_live:
        raise GuardViolation("live_broker_mismatch", "live requested but the broker is not a live broker")
