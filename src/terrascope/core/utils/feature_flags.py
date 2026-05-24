"""Tiny feature-flag helper — env-var-driven so CI can toggle behaviours.

This is deliberately not a dependency-injected DI system; it's a key-value
peek at environment with sensible defaults.
"""

from __future__ import annotations

import os

_PREFIX = "TERRASCOPE_FLAG_"


def is_enabled(flag: str, *, default: bool = False) -> bool:
    """Check whether ``flag`` is enabled in the environment.

    Accepts ``1``, ``true``, ``yes``, ``on`` (any case) as truthy.
    """
    raw = os.environ.get(_PREFIX + flag.upper(), None)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get(flag: str, default: str = "") -> str:
    """Read the raw value of a flag.  Returns ``default`` when unset."""
    return os.environ.get(_PREFIX + flag.upper(), default)
