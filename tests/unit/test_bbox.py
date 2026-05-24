"""BBox utility tests."""

from __future__ import annotations

import pytest

from terrascope.core.models import BBox
from terrascope.core.utils.bbox import (
    area_deg2,
    buffer,
    height,
    intersection,
    intersects,
    width,
)

pytestmark = pytest.mark.unit


def _bbox(*coords: float) -> BBox:
    return BBox(west=coords[0], south=coords[1], east=coords[2], north=coords[3])


def test_buffer_clamps_to_global() -> None:
    b = _bbox(-179.5, -89.5, 179.5, 89.5)
    bigger = buffer(b, degrees=10)
    assert bigger.west == -180
    assert bigger.north == 90


def test_intersects_overlap() -> None:
    a = _bbox(0, 0, 10, 10)
    b = _bbox(5, 5, 15, 15)
    assert intersects(a, b)


def test_intersects_separate() -> None:
    a = _bbox(0, 0, 10, 10)
    b = _bbox(11, 0, 20, 10)
    assert not intersects(a, b)


def test_intersects_touching_is_not_overlap() -> None:
    a = _bbox(0, 0, 10, 10)
    b = _bbox(10, 0, 20, 10)
    # Touching only on a single line should not count as overlap.
    assert not intersects(a, b)


def test_intersection_clipping() -> None:
    a = _bbox(0, 0, 10, 10)
    b = _bbox(5, 5, 15, 15)
    inter = intersection(a, b)
    assert inter == _bbox(5, 5, 10, 10)


def test_intersection_none_when_disjoint() -> None:
    a = _bbox(0, 0, 1, 1)
    b = _bbox(10, 10, 11, 11)
    assert intersection(a, b) is None


def test_width_height_area() -> None:
    b = _bbox(0, 0, 3, 4)
    assert width(b) == 3
    assert height(b) == 4
    assert area_deg2(b) == 12
