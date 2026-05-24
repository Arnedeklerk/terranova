"""Feature-flag helper tests."""

from __future__ import annotations

import pytest

from terranova.core.utils import feature_flags as ff

pytestmark = pytest.mark.unit


def test_unset_returns_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("TERRANOVA_FLAG_FOO", raising=False)
    assert ff.is_enabled("foo") is False
    assert ff.is_enabled("foo", default=True) is True


def test_truthy_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for raw in ("1", "true", "True", "YES", "on"):
        monkeypatch.setenv("TERRANOVA_FLAG_FOO", raw)
        assert ff.is_enabled("foo") is True


def test_falsy_values(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for raw in ("0", "false", "no", "off", "", "banana"):
        monkeypatch.setenv("TERRANOVA_FLAG_FOO", raw)
        assert ff.is_enabled("foo") is False


def test_get_returns_raw(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("TERRANOVA_FLAG_BAR", "custom-value")
    assert ff.get("bar") == "custom-value"
    monkeypatch.delenv("TERRANOVA_FLAG_BAR")
    assert ff.get("bar", default="fallback") == "fallback"
