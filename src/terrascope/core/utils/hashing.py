"""Deterministic short hashes for caching keys (models, embeddings, AOIs)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def short_hash(payload: Any, *, length: int = 12) -> str:
    """SHA-256 of the JSON-canonical form of ``payload``, truncated to ``length``.

    Uses ``sort_keys=True`` so dict orderings don't change the hash.  Useful
    for naming embedding caches: ``{raster_hash}__{model_hash}.npy``.
    """
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:length]


def file_hash(path: Path, *, length: int = 12, block_size: int = 1 << 20) -> str:
    """Streaming SHA-256 of a file's contents.

    Reads in ``block_size`` chunks so memory stays bounded even for big COGs.
    """
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:length]
