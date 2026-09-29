"""Alerts: always to the log; optionally to an ntfy.sh topic and a healthcheck ping.

* ``NTFY_TOPIC`` (env, optional): alerts are POSTed to ``https://ntfy.sh/<topic>``.
  Anyone who knows a topic name can read it, so the topic is treated as a
  password (scrubbed from logs) and messages carry only a stable code, the
  strategy and the rebalance date -- never positions, amounts, keys or account
  numbers. Details stay in the local log.
* ``HEALTHCHECK_URL`` (env, optional): pinged (GET) after a successful run only,
  so a dead-man service such as healthchecks.io alerts when runs stop.

Network errors from alerting are logged and swallowed: a failed alert must not
turn into a failed (or repeated) trading run. Tests inject ``transport``.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Mapping

__all__ = ["Alerter", "safe_alert_text"]

log = logging.getLogger("stocktry.execution.alerts")

Transport = Callable[[str, str, dict], None]  # (method, url, kwargs)

_SAFE_TEXT_RE = re.compile(r"[^A-Za-z0-9_.:\- ]")


def safe_alert_text(text: str, limit: int = 120) -> str:
    """Keep only a conservative character set and cap the length.

    Dollar signs, digits-with-decimals of amounts, braces and quotes are removed
    so that amounts or JSON payloads cannot be smuggled into an external alert.
    """
    cleaned = _SAFE_TEXT_RE.sub("", text)
    return cleaned[:limit]


def _requests_transport(method: str, url: str, kwargs: dict) -> None:
    import requests  # local import keeps module import cheap

    requests.request(method, url, timeout=10, **kwargs)


@dataclass
class Alerter:
    ntfy_topic: str | None = None
    healthcheck_url: str | None = None
    transport: Transport | None = None
    ntfy_server: str = "https://ntfy.sh"
    sent: list[tuple[str, str]] = field(default_factory=list)  # (code, external text) for tests

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, transport: Transport | None = None) -> "Alerter":
        env = os.environ if env is None else env
        return cls(
            ntfy_topic=env.get("NTFY_TOPIC") or None,
            healthcheck_url=env.get("HEALTHCHECK_URL") or None,
            transport=transport,
        )

    def alert(self, code: str, detail: str, *, context: str = "") -> None:
        """Log ``detail`` locally; send only ``code`` and ``context`` externally."""
        log.error("ALERT %s %s: %s", code, context, detail)
        external = safe_alert_text(f"{context} {code}".strip())
        self.sent.append((code, external))
        if not self.ntfy_topic:
            return
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.ntfy_topic):
            log.error("NTFY_TOPIC has invalid characters; external alert not sent")
            return
        try:
            (self.transport or _requests_transport)(
                "POST",
                f"{self.ntfy_server}/{self.ntfy_topic}",
                {"data": f"stocktry: {external}. See the run log.".encode(), "headers": {"Priority": "high"}},
            )
        except Exception as exc:  # noqa: BLE001 - alerting must never raise
            log.error("external alert failed: %s", type(exc).__name__)

    def ping_success(self) -> None:
        if not self.healthcheck_url:
            return
        try:
            (self.transport or _requests_transport)("GET", self.healthcheck_url, {})
        except Exception as exc:  # noqa: BLE001
            log.error("healthcheck ping failed: %s", type(exc).__name__)
