"""Naming helper tests."""

from __future__ import annotations

import pytest

from terranova.core.utils.naming import layer_display_name, safe_filename, unique_path

pytestmark = pytest.mark.unit


def test_safe_filename_ascii_passes_through() -> None:
    assert safe_filename("my_layer-1") == "my_layer-1"


def test_safe_filename_strips_punctuation() -> None:
    assert safe_filename("my/dir\\layer:1*") == "my_dir_layer_1"


def test_safe_filename_unicode_normalised() -> None:
    out = safe_filename("Khartoûm — Sentinel-2")
    assert "ô" not in out
    assert "Khartoum" in out


def test_safe_filename_length_capped() -> None:
    long = "x" * 200
    out = safe_filename(long, max_length=32)
    assert len(out) == 32


def test_safe_filename_default_when_empty() -> None:
    assert safe_filename("***") == "untitled"


def test_unique_path_returns_input_when_absent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.tif"
    assert unique_path(p) == p


def test_unique_path_picks_next_index(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "x.tif"
    p.touch()
    assert unique_path(p) == tmp_path / "x-2.tif"
    (tmp_path / "x-2.tif").touch()
    assert unique_path(p) == tmp_path / "x-3.tif"


def test_layer_display_name() -> None:
    assert (
        layer_display_name("Classification", "RF", "Khartoum 2024-06")
        == "Classification — RF — Khartoum 2024-06"
    )
