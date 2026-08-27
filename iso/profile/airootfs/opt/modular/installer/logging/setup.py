"""Installer logging (spec §24).

Logs to /var/log/modular-installer.log when running as root (live ISO),
otherwise to ./modular-installer.log for development.

Passwords and other secrets are redacted before any record is written.
"""

from __future__ import annotations

import logging
import os
import re

DEFAULT_SYSTEM_LOG = "/var/log/modular/installer.log"
DEFAULT_DEV_LOG = "modular-installer.log"

_REDACTIONS: list[tuple[re.Pattern[str], str]] = []


def redact(message: str) -> str:
    out = message
    for pattern, replacement in _REDACTIONS:
        out = pattern.sub(replacement, out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if isinstance(record.args, tuple):
            record.args = tuple(redact(str(a)) for a in record.args)
        return True


def register_secret(value: str) -> None:
    """Register a secret value so it never reaches the log file."""
    if not value:
        return
    escaped = re.escape(value)
    compiled = re.compile(escaped)
    for pattern, _ in _REDACTIONS:
        if pattern.pattern == escaped:
            return
    _REDACTIONS.append((compiled, "[REDACTED]"))


def get_logger(name: str = "modular-installer") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.addFilter(RedactingFilter())

    path = DEFAULT_SYSTEM_LOG
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8"):
            pass
    except OSError:
        path = os.path.join(os.getcwd(), DEFAULT_DEV_LOG)

    handler = logging.FileHandler(path)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)

    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(stream)
    return logger
