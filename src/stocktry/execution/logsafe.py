"""Log and stdout scrubbing: API keys, secrets and account numbers never print.

``Scrubber`` redacts (a) the literal values of secret environment variables
(Alpaca keys, ntfy topic, healthcheck URL, any ``*_KEY``/``*_SECRET``/
``*_TOKEN``/``*_PAT``/``*_PASSWORD`` variable) and (b) patterns that look like
Alpaca key ids, 40-character secrets, Alpaca account numbers and long digit
runs. ``configure_logging`` installs it on every handler so that records from
any library (including alpaca-py and requests) are scrubbed, and optionally
wraps stdout/stderr so ``print`` output is scrubbed too.
"""

from __future__ import annotations

import io
import logging
import os
import re
import sys
from typing import Iterable, Mapping, TextIO

__all__ = ["Scrubber", "ScrubbingFilter", "ScrubbingStream", "configure_logging", "REDACTED"]

REDACTED = "[REDACTED]"

_SECRET_ENV_NAMES = (
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "NTFY_TOPIC",
    "HEALTHCHECK_URL",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
_SECRET_NAME_RE = re.compile(r"(KEY|SECRET|TOKEN|PAT|PASSWORD)(_ID)?$", re.IGNORECASE)
_PATTERNS = [
    re.compile(r"(APCA-API-(?:KEY-ID|SECRET-KEY)['\"]?\s*[:=]\s*['\"]?)[^'\",\s}]+"),
    re.compile(r"(\"?account_number\"?\s*[:=]\s*\"?)[^\",\s}]+"),
    re.compile(r"\b[PA]K[A-Z0-9]{14,}\b"),  # Alpaca key ids: PK... (paper), AK... (live)
    re.compile(r"\bPA[A-Z0-9]{8,}\b"),  # Alpaca paper account numbers
    re.compile(r"\b[A-Za-z0-9/+]{40}\b"),  # 40-char secrets (Alpaca secret keys)
    re.compile(r"\b\d{8,}\b"),  # long digit runs (account numbers)
]


class Scrubber:
    """Callable that redacts secrets from text. Built from an env mapping."""

    def __init__(self, env: Mapping[str, str] | None = None, extra_secrets: Iterable[str] = ()) -> None:
        env = os.environ if env is None else env
        secrets = set(extra_secrets)
        for name, value in env.items():
            if name in _SECRET_ENV_NAMES or _SECRET_NAME_RE.search(name):
                if value and len(value) >= 4:
                    secrets.add(value)
        # longest first so a secret containing another is fully redacted
        self._secrets = sorted(secrets, key=len, reverse=True)

    def __call__(self, text: str) -> str:
        if not text:
            return text
        for s in self._secrets:
            if s in text:
                text = text.replace(s, REDACTED)
        for pat in _PATTERNS:
            if pat.groups:
                text = pat.sub(lambda m: m.group(1) + REDACTED, text)
            else:
                text = pat.sub(REDACTED, text)
        return text


class ScrubbingFilter(logging.Filter):
    """Logging filter that scrubs the formatted message, exception and stack text."""

    def __init__(self, scrubber: Scrubber) -> None:
        super().__init__()
        self.scrub = scrubber

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - malformed format args
            msg = str(record.msg)
        record.msg = self.scrub(msg)
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.scrub(record.exc_text)
        if record.stack_info:
            record.stack_info = self.scrub(record.stack_info)
        return True


class ScrubbingStream(io.TextIOBase):
    """Text stream wrapper that scrubs everything written through it."""

    def __init__(self, inner: TextIO, scrubber: Scrubber) -> None:
        self._inner = inner
        self._scrub = scrubber

    def write(self, s: str) -> int:  # type: ignore[override]
        self._inner.write(self._scrub(s))
        return len(s)

    def flush(self) -> None:
        self._inner.flush()

    def writable(self) -> bool:
        return True


def configure_logging(
    level: int = logging.INFO,
    *,
    stream: TextIO | None = None,
    env: Mapping[str, str] | None = None,
    wrap_std_streams: bool = False,
) -> Scrubber:
    """Send logs to ``stream`` (default stdout) with scrubbing on every handler."""
    scrubber = Scrubber(env)
    root = logging.getLogger()
    root.setLevel(level)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.set_name("stocktry-scrubbed")
    for h in list(root.handlers):
        if h.get_name() == "stocktry-scrubbed":
            root.removeHandler(h)
    root.addHandler(handler)
    filt = ScrubbingFilter(scrubber)
    for h in root.handlers:
        h.addFilter(filt)
    if wrap_std_streams:
        if not isinstance(sys.stdout, ScrubbingStream):
            sys.stdout = ScrubbingStream(sys.stdout, scrubber)  # type: ignore[assignment]
        if not isinstance(sys.stderr, ScrubbingStream):
            sys.stderr = ScrubbingStream(sys.stderr, scrubber)  # type: ignore[assignment]
    return scrubber
