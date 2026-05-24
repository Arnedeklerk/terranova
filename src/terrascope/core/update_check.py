"""Auto-update check — Phase 4.

Polls a small JSON file on terrascope.app once per day, compares the
``latest`` version to the running one, and surfaces an info-message in the
QGIS bar if a newer release is available.  Never auto-installs; we just tell
the user.

The check is **opt-in** by default in the per-user :class:`Settings` — we
inherit the same posture as telemetry: never phone home without permission.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ..version import __version__

LATEST_URL = "https://terrascope.app/latest.json"
USER_AGENT = f"TerraScope/{__version__} (update-check)"


@dataclass(slots=True, frozen=True)
class UpdateInfo:
    latest_version: str
    release_notes_url: str
    is_newer: bool


def _cache_path() -> Path:
    try:
        import platformdirs

        return Path(platformdirs.user_cache_dir("terrascope")) / "update_check.json"
    except ImportError:  # pragma: no cover
        return Path.home() / ".cache" / "terrascope" / "update_check.json"


def _read_cache() -> tuple[datetime, UpdateInfo] | None:
    p = _cache_path()
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(raw["checked_at"])
        info = UpdateInfo(
            latest_version=raw["latest_version"],
            release_notes_url=raw["release_notes_url"],
            is_newer=raw["is_newer"],
        )
        return when, info
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _write_cache(info: UpdateInfo) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "checked_at": datetime.now(UTC).isoformat(),
                "latest_version": info.latest_version,
                "release_notes_url": info.release_notes_url,
                "is_newer": info.is_newer,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def check_for_updates(*, now: datetime | None = None) -> UpdateInfo | None:
    """Return :class:`UpdateInfo` for the latest release, or ``None``.

    Uses a 24-hour cache to avoid hammering the endpoint.  Network errors
    return ``None`` silently — update-check failures must never disrupt the
    plugin.
    """
    import requests

    now = now or datetime.now(UTC)
    cached = _read_cache()
    if cached is not None:
        when, info = cached
        if (now - when) < timedelta(hours=24):
            return info

    try:
        resp = requests.get(LATEST_URL, timeout=5, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        payload = resp.json()
        latest = str(payload["version"])
        notes = str(payload.get("release_notes_url", LATEST_URL))
    except Exception:
        return cached[1] if cached else None

    info = UpdateInfo(
        latest_version=latest,
        release_notes_url=notes,
        is_newer=is_newer_version(latest, __version__),
    )
    _write_cache(info)
    return info


def is_newer_version(candidate: str, current: str) -> bool:
    """Lexicographic-on-numeric-tuples version comparison.

    ``"1.2.10"`` is newer than ``"1.2.9"`` (real numeric compare).  Pre-release
    suffixes are ignored — ``"1.0.0rc1"`` is treated as ``"1.0.0"``.
    """
    return _parse(candidate) > _parse(current)


def _parse(v: str) -> tuple[int, ...]:
    import re

    parts: list[int] = []
    for piece in v.split(".")[:3]:
        # Strip any non-digit suffix (rc1, a0, .dev3, etc.).
        match = re.match(r"\d+", piece)
        parts.append(int(match.group(0)) if match else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)
