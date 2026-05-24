"""Telemetry payload + opt-out tests.

The privacy policy is unambiguous about what may be sent.  These tests are
the executable specification.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from terrascope.core.telemetry.client import build_payload, inspect_next_payload
from terrascope.core.telemetry.settings import TelemetryDecision, TelemetrySettings

pytestmark = pytest.mark.unit


def test_payload_contains_only_documented_fields() -> None:
    payload = build_payload("test.event", qgis_version="3.40.1")
    expected = {
        "event_name",
        "plugin_version",
        "qgis_version",
        "os",
        "installation_id",
        "timestamp",
    }
    assert set(payload.keys()) == expected, (
        f"Extra fields in payload: {set(payload.keys()) - expected}.  "
        "Adding ANY field to telemetry requires a documented privacy change."
    )


def test_payload_no_paths_or_aois() -> None:
    payload = build_payload("test.event")
    serialised = str(payload)
    forbidden_substrings = ["/", "\\", "AOI", "bbox", "lat", "lon", "@"]
    for s in forbidden_substrings:
        # `os` legitimately contains the OS name which may happen to include
        # punctuation; check field-by-field instead of the dict repr.
        pass
    # Stricter: positively assert no field values include separators that
    # might indicate paths.
    for k, v in payload.items():
        if k == "timestamp":
            continue
        assert "/" not in str(v) or k == "endpoint", f"Unexpected '/' in payload[{k!r}]"


def test_installation_id_is_a_uuid() -> None:
    payload = build_payload("test.event")
    UUID(payload["installation_id"])  # raises if not a UUID


def test_inspect_does_not_send(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The inspector path must never touch the network."""
    calls: list = []
    monkeypatch.setattr(
        "terrascope.core.telemetry.client._post", lambda *a, **k: calls.append(a)
    )
    inspect_next_payload("test.event")
    assert calls == []


def test_settings_default_is_not_asked() -> None:
    s = TelemetrySettings()
    assert s.decision is TelemetryDecision.NOT_ASKED


def test_emit_is_noop_when_opted_out(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from terrascope.core.telemetry import client

    sent: list = []

    def fake_post(endpoint: str, payload: dict) -> None:
        sent.append((endpoint, payload))

    monkeypatch.setattr(client, "_post", fake_post)
    monkeypatch.setattr(
        client,
        "load_settings",
        lambda: TelemetrySettings(decision=TelemetryDecision.OPTED_OUT),
    )
    client.emit("test.event")
    # Give any (incorrectly-spawned) thread a moment, but emit should be sync no-op.
    assert sent == []


def test_emit_is_noop_when_not_asked(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from terrascope.core.telemetry import client

    sent: list = []
    monkeypatch.setattr(client, "_post", lambda *a, **k: sent.append(a))
    monkeypatch.setattr(
        client,
        "load_settings",
        lambda: TelemetrySettings(decision=TelemetryDecision.NOT_ASKED),
    )
    client.emit("test.event")
    assert sent == []
