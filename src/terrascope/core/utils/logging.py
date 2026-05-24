"""A tiny logger wrapper so domain code uses one source of truth.

In QGIS we route to ``QgsMessageLog`` via a sink installed at plugin init;
outside QGIS (CLI, tests, notebooks) we use stdlib :mod:`logging`.

The package logger has a PII-scrubbing filter installed by default
(:class:`ScrubFilter`) — careless ``logger.info(f"{user_email}")`` calls
won't ship raw emails to the log buffer.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

_LOG = logging.getLogger("terrascope")
_qgis_sink: Callable[[str, str, int], None] | None = None


def set_qgis_sink(sink: Callable[[str, str, int], None] | None) -> None:
    """Install (or remove) a QGIS sink.

    The sink is invoked as ``sink(message, tag, level)`` where ``level`` is a
    standard :mod:`logging` level integer.  When the plugin loads it installs
    a sink that calls ``QgsMessageLog.logMessage(...)``.
    """
    global _qgis_sink
    _qgis_sink = sink


def log(message: str, *, level: int = logging.INFO, tag: str = "TerraScope") -> None:
    """Emit a log message via both stdlib logging and the QGIS sink (if set)."""
    _LOG.log(level, message)
    if _qgis_sink is not None:
        try:
            _qgis_sink(message, tag, level)
        except Exception:
            pass


def info(message: str, *, tag: str = "TerraScope") -> None:
    log(message, level=logging.INFO, tag=tag)


def warning(message: str, *, tag: str = "TerraScope") -> None:
    log(message, level=logging.WARNING, tag=tag)


def error(message: str, *, tag: str = "TerraScope") -> None:
    log(message, level=logging.ERROR, tag=tag)


# --------------------------------------------------------------------------- #
# Lightweight PII scrubbing for log output                                    #
# --------------------------------------------------------------------------- #
_PII_PATTERNS = [
    # Email addresses (RFC-ish, captures most cases without false positives).
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<email>"),
    # Bearer tokens / JWTs (long base64-ish strings preceded by Bearer/token=).
    (re.compile(r"(?i)(bearer\s+|token=)[A-Za-z0-9._\-+/]{20,}"), r"\1<token>"),
    # User home paths (Windows): "C:\Users\<name>\" → "C:\Users\<user>\".
    (re.compile(r"([A-Z]:\\Users\\)[^\\]+"), r"\1<user>"),
    # User home paths (Unix): "/Users/<name>/" or "/home/<name>/".
    (re.compile(r"(/(?:Users|home)/)[^/]+"), r"\1<user>"),
]


def scrub(message: str) -> str:
    """Best-effort PII scrubbing for log messages.

    Not a security boundary — we run the obvious patterns to keep careless
    log lines from carrying emails, bearer tokens, or full home-paths.
    """
    for pattern, replacement in _PII_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class ScrubFilter(logging.Filter):
    """A :mod:`logging` filter that runs :func:`scrub` on every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = scrub(record.msg)
        return True


_LOG.addFilter(ScrubFilter())
