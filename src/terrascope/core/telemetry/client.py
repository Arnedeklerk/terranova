"""Telemetry transport.

A single, opaque function: :func:`emit`.  Callers describe an event by name;
the client fills in version + OS + installation id and POSTs to the endpoint
configured in :class:`TelemetrySettings` — only when the user has opted in.
Network errors are swallowed; telemetry must never break the plugin.
"""

from __future__ import annotations

import platform
import time
from datetime import UTC, datetime
from threading import Lock, Thread
from typing import Any

from ...version import __version__
from .settings import TelemetryDecision, load_settings

_MIN_INTERVAL = 1.0  # seconds — rate limit per the privacy policy
_last_send = 0.0
_LOCK = Lock()


def build_payload(event_name: str, *, qgis_version: str = "unknown") -> dict[str, Any]:
    """Build the exact, minimal payload the privacy policy describes.

    Pure function so it can be used by the "inspector" UI (Settings → Privacy
    → Show next outbound payload) without sending anything.
    """
    s = load_settings()
    return {
        "event_name": event_name,
        "plugin_version": __version__,
        "qgis_version": qgis_version,
        "os": f"{platform.system()} {platform.release()}",
        "installation_id": str(s.installation_id),
        "timestamp": datetime.now(UTC).isoformat(),
    }


def inspect_next_payload(event_name: str, *, qgis_version: str = "unknown") -> dict[str, Any]:
    """Return what *would* be sent for ``event_name``.  No network call."""
    return build_payload(event_name, qgis_version=qgis_version)


def emit(event_name: str, *, qgis_version: str = "unknown") -> None:
    """Send a telemetry event if and only if the user has opted in.

    Non-blocking — the POST happens on a daemon thread so even a slow endpoint
    doesn't lock up the UI.
    """
    global _last_send

    settings = load_settings()
    if settings.decision is not TelemetryDecision.OPTED_IN:
        return

    with _LOCK:
        now = time.time()
        if now - _last_send < _MIN_INTERVAL:
            return
        _last_send = now

    payload = build_payload(event_name, qgis_version=qgis_version)
    Thread(target=_post, args=(settings.endpoint, payload), daemon=True).start()


def _post(endpoint: str, payload: dict[str, Any]) -> None:
    try:
        import requests

        requests.post(endpoint, json=payload, timeout=5)
    except Exception:
        pass
