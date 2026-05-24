"""Tests for the auto-update check."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from terrascope.core import update_check
from terrascope.core.update_check import is_newer_version

pytestmark = pytest.mark.unit


# ---- pure version comparison ----
def test_newer_patch() -> None:
    assert is_newer_version("0.1.1", "0.1.0")


def test_newer_minor() -> None:
    assert is_newer_version("0.2.0", "0.1.9")


def test_newer_major() -> None:
    assert is_newer_version("1.0.0", "0.99.9")


def test_same_version_is_not_newer() -> None:
    assert not is_newer_version("1.2.3", "1.2.3")


def test_older_is_not_newer() -> None:
    assert not is_newer_version("1.0.0", "1.2.3")


def test_numeric_not_lexical() -> None:
    """1.2.10 should be newer than 1.2.9 — lexicographic compare would get this wrong."""
    assert is_newer_version("1.2.10", "1.2.9")


def test_prerelease_suffix_ignored() -> None:
    assert is_newer_version("1.0.0rc1", "0.9.9")
    assert not is_newer_version("1.0.0rc1", "1.0.0")


# ---- network behaviour ----
def test_check_returns_none_when_network_fails(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "update_check.json")

    def boom(*_a, **_k):  # type: ignore[no-untyped-def]
        raise RuntimeError("network down")

    fake_requests = MagicMock()
    fake_requests.get = boom
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    assert update_check.check_for_updates() is None


def test_check_uses_cache_within_24h(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "update_check.json")
    # Seed cache.
    info = update_check.UpdateInfo("9.9.9", "https://example.com", True)
    update_check._write_cache(info)
    fetched = []
    fake_requests = MagicMock()
    fake_requests.get = lambda *a, **k: fetched.append(1) or MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    result = update_check.check_for_updates(now=datetime.now(UTC))
    assert result is not None
    assert result.latest_version == "9.9.9"
    assert not fetched  # cache hit — no HTTP call


def test_check_refetches_after_24h(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(update_check, "_cache_path", lambda: tmp_path / "update_check.json")
    info = update_check.UpdateInfo("9.9.9", "https://example.com", True)
    update_check._write_cache(info)

    # Pretend the cached check is from 2 days ago.
    cache_path = update_check._cache_path()
    import json

    raw = json.loads(cache_path.read_text(encoding="utf-8"))
    raw["checked_at"] = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    cache_path.write_text(json.dumps(raw), encoding="utf-8")

    resp = MagicMock()
    resp.json.return_value = {"version": "0.2.0", "release_notes_url": "https://x"}
    resp.raise_for_status.return_value = None
    fake_requests = MagicMock()
    fake_requests.get.return_value = resp
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    result = update_check.check_for_updates()
    assert result is not None
    assert result.latest_version == "0.2.0"
    fake_requests.get.assert_called_once()
