"""Tests for the small hashing utilities."""

from __future__ import annotations

import pytest

from terranova.core.utils.hashing import file_hash, short_hash

pytestmark = pytest.mark.unit


def test_short_hash_deterministic() -> None:
    a = short_hash({"x": 1, "y": 2})
    b = short_hash({"y": 2, "x": 1})  # different order
    assert a == b


def test_short_hash_length() -> None:
    assert len(short_hash("anything", length=12)) == 12
    assert len(short_hash("anything", length=8)) == 8


def test_short_hash_distinguishes_payloads() -> None:
    assert short_hash({"a": 1}) != short_hash({"a": 2})


def test_file_hash_round_trip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.bin"
    p.write_bytes(b"hello world")
    h1 = file_hash(p)
    h2 = file_hash(p)
    assert h1 == h2
    assert len(h1) == 12


def test_file_hash_changes_with_content(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.bin"
    p.write_bytes(b"first")
    a = file_hash(p)
    p.write_bytes(b"second")
    b = file_hash(p)
    assert a != b
