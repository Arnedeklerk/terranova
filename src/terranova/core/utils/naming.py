"""Layer / file naming helpers.

The QGIS Layer Tree gets crowded fast.  Centralising naming here keeps
output rasters identifiable and lets us enforce filesystem-safe characters in
one place.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._\- ]+")


def safe_filename(stem: str, *, max_length: int = 80) -> str:
    """Make ``stem`` filesystem-safe across OSes.

    - Unicode normalised (NFKD) so accented chars become ASCII-ish.
    - Non `[A-Z, a-z, 0-9, ., _, -, space]` collapse to ``_``.
    - Trimmed and length-capped.
    """
    normalised = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    cleaned = _UNSAFE.sub("_", normalised).strip("._- ")
    if not cleaned:
        cleaned = "untitled"
    return cleaned[:max_length]


def unique_path(base: Path) -> Path:
    """If ``base`` exists, return ``base`` with ``-2``, ``-3``, ... appended."""
    if not base.exists():
        return base
    stem = base.stem
    suffix = base.suffix
    parent = base.parent
    for i in range(2, 10_000):
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError("could not find a unique path within 10k tries")


def layer_display_name(kind: str, *details: str) -> str:
    """Build a layer display name like ``Classification — RF — Khartoum 2024-06``."""
    parts = [kind] + [d for d in details if d]
    return " — ".join(parts)
