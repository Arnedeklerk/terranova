"""Tests for the CDSE OAuth helpers (request mocking)."""

from __future__ import annotations

import time

import pytest

from terranova.core.catalog.cdse import (
    CDSEToken,
    DeviceFlowChallenge,
    forget_token,
    load_cached_token,
    save_token,
)

pytestmark = pytest.mark.unit


def test_token_expiry_logic() -> None:
    fresh = CDSEToken("a", "b", expires_at=time.time() + 3600)
    stale = CDSEToken("a", "b", expires_at=time.time() - 1)
    assert not fresh.is_expired()
    assert stale.is_expired()


def test_token_skew() -> None:
    # 10s in the future, skew of 30s → already considered expired.
    near = CDSEToken("a", "b", expires_at=time.time() + 10)
    assert near.is_expired(skew=30)


def test_device_flow_challenge_is_frozen() -> None:
    c = DeviceFlowChallenge(
        device_code="dev",
        user_code="abc",
        verification_uri="https://example.com",
        verification_uri_complete="https://example.com?code=abc",
        interval=5,
        expires_in=600,
    )
    with pytest.raises((TypeError, AttributeError)):
        c.user_code = "xyz"  # type: ignore[misc]


def test_token_cache_round_trip(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "cdse_token.json"
    monkeypatch.setattr("terranova.core.catalog.cdse.token_cache_path", lambda: p)
    token = CDSEToken("acc", "ref", expires_at=time.time() + 3600)
    save_token(token)
    loaded = load_cached_token()
    assert loaded is not None
    assert loaded.access_token == "acc"
    forget_token()
    assert load_cached_token() is None


def test_corrupt_cache_returns_none(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "cdse_token.json"
    p.write_text("not json")
    monkeypatch.setattr("terranova.core.catalog.cdse.token_cache_path", lambda: p)
    assert load_cached_token() is None
