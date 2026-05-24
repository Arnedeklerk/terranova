"""Domain-layer logging wrapper tests."""

from __future__ import annotations

import logging

import pytest

from terranova.core.utils.logging import error, info, set_qgis_sink, warning

pytestmark = pytest.mark.unit


def test_levels_route_through_sink() -> None:
    captured: list = []
    set_qgis_sink(lambda msg, tag, level: captured.append((msg, tag, level)))
    try:
        info("hi", tag="t")
        warning("uh oh", tag="t")
        error("nope", tag="t")
    finally:
        set_qgis_sink(None)
    levels = [c[2] for c in captured]
    assert levels == [logging.INFO, logging.WARNING, logging.ERROR]
    assert captured[0][0] == "hi"


def test_sink_exception_is_swallowed() -> None:
    def explode(*_args, **_kwargs) -> None:  # type: ignore[no-untyped-def]
        raise RuntimeError("boom")

    set_qgis_sink(explode)
    try:
        # Should not raise.
        info("safe")
    finally:
        set_qgis_sink(None)


def test_without_sink_only_stdlib() -> None:
    set_qgis_sink(None)
    # Should not raise; nothing to assert beyond that.
    info("plain")


# ---------------------- PII scrub ----------------------
from terranova.core.utils.logging import scrub  # noqa: E402


def test_scrub_redacts_email() -> None:
    assert scrub("contact arne@knetminer.com about it") == "contact <email> about it"


def test_scrub_redacts_bearer_token() -> None:
    out = scrub("Authorization: Bearer abcDEF1234567890_LONG_TOKEN_HERE")
    assert "<token>" in out
    assert "abcDEF" not in out


def test_scrub_redacts_windows_home() -> None:
    assert scrub(r"C:\Users\dekle\file.tif") == r"C:\Users\<user>\file.tif"


def test_scrub_redacts_unix_home() -> None:
    assert scrub("/home/arne/project") == "/home/<user>/project"
    assert scrub("/Users/arne/project") == "/Users/<user>/project"


def test_scrub_leaves_normal_text_alone() -> None:
    assert scrub("nothing special here") == "nothing special here"
