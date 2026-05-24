"""Dispatch table tests — exercises the controller boundary without QGIS."""

from __future__ import annotations

import pytest

from terrascope.controllers import Controllers
from terrascope.version import __version__

pytestmark = pytest.mark.unit


def test_unknown_action_returns_error() -> None:
    c = Controllers()
    r = c.dispatch("does.not.exist", {})
    assert r.ok is False
    assert r.error is not None
    assert "unknown action" in r.error


def test_ping_round_trip() -> None:
    c = Controllers()
    r = c.dispatch("app.ping", {"hello": "world"})
    assert r.ok is True
    assert r.result == {"pong": True, "echo": {"hello": "world"}}


def test_version() -> None:
    c = Controllers()
    r = c.dispatch("app.version", {})
    assert r.ok is True
    assert r.result == {"version": __version__}


def test_handler_exception_becomes_error_result() -> None:
    """A controller that raises should surface as ok=False, not crash dispatch."""
    c = Controllers()

    def boom(_payload: dict) -> dict:
        raise RuntimeError("kaboom")

    c._handlers["test.boom"] = boom
    r = c.dispatch("test.boom", {})
    assert r.ok is False
    assert "kaboom" in (r.error or "")


def test_telemetry_inspect_payload_shape() -> None:
    c = Controllers()
    r = c.dispatch("app.telemetry.inspect", {"event_name": "smoke"})
    assert r.ok is True
    assert set(r.result.keys()) == {
        "event_name",
        "plugin_version",
        "qgis_version",
        "os",
        "installation_id",
        "timestamp",
    }
    assert r.result["event_name"] == "smoke"


def test_telemetry_status_returns_decision() -> None:
    c = Controllers()
    r = c.dispatch("app.telemetry.status", {})
    assert r.ok is True
    assert "decision" in r.result


def test_telemetry_set_invalid_decision() -> None:
    c = Controllers()
    r = c.dispatch("app.telemetry.set", {"decision": "maybe"})
    assert r.ok is False
    assert "invalid" in (r.error or "")
