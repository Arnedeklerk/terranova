"""Tests for classification post-processing utilities."""

from __future__ import annotations

import numpy as np
import pytest

scipy = pytest.importorskip("scipy")

from terrascope.core.ml.postprocess import majority_filter, reclassify, sieve  # noqa: E402

pytestmark = pytest.mark.unit


def test_majority_filter_smooths_isolated_pixel() -> None:
    arr = np.ones((5, 5), dtype=np.uint8)
    arr[2, 2] = 9  # one stray pixel of a different class
    out = majority_filter(arr, size=3, nodata=0)
    assert out[2, 2] == 1
    # Non-stray pixels are unchanged.
    assert out[0, 0] == 1


def test_majority_filter_requires_odd_size() -> None:
    with pytest.raises(ValueError, match="odd"):
        majority_filter(np.zeros((4, 4), dtype=np.uint8), size=2)


def test_majority_filter_preserves_nodata() -> None:
    arr = np.ones((4, 4), dtype=np.uint8)
    arr[0, 0] = 0  # nodata
    out = majority_filter(arr, size=3, nodata=0)
    assert out[0, 0] == 0


def test_sieve_removes_small_island() -> None:
    arr = np.ones((10, 10), dtype=np.uint8)
    arr[5, 5] = 2  # single-pixel island of class 2
    out = sieve(arr, min_pixels=4, connectivity=4, nodata=0)
    assert out[5, 5] == 1


def test_sieve_keeps_large_component() -> None:
    arr = np.ones((10, 10), dtype=np.uint8)
    arr[2:6, 2:6] = 2  # 16-pixel island
    out = sieve(arr, min_pixels=4, connectivity=4, nodata=0)
    assert (out[2:6, 2:6] == 2).all()


def test_reclassify_lookup() -> None:
    arr = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    out = reclassify(arr, {2: 20, 4: 40})
    np.testing.assert_array_equal(out, [[1, 20], [3, 40]])


def test_reclassify_empty_passthrough() -> None:
    arr = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    out = reclassify(arr, {})
    np.testing.assert_array_equal(out, arr)
