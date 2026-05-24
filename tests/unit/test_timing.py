"""Timing helper tests."""

from __future__ import annotations

import time

import pytest

from terranova.core.utils.timing import humanise_duration, timed

pytestmark = pytest.mark.unit


def test_timed_measures_a_block() -> None:
    with timed() as t:
        time.sleep(0.02)
    assert t.elapsed >= 0.02
    assert t.elapsed < 1.0  # sanity


def test_timed_zero_for_empty_block() -> None:
    with timed() as t:
        pass
    assert t.elapsed >= 0.0
    assert t.elapsed < 0.1


def test_humanise_under_minute() -> None:
    assert humanise_duration(0.5) == "0.5s"
    assert humanise_duration(7.4) == "7.4s"


def test_humanise_minutes() -> None:
    assert humanise_duration(72) == "1m12s"
    assert humanise_duration(125) == "2m05s"


def test_humanise_hours() -> None:
    assert humanise_duration(3725) == "1h02m"
    assert humanise_duration(7325) == "2h02m"
