"""Tests for the numpy region-grow ROI tool."""

from __future__ import annotations

import numpy as np
import pytest

from terranova.core.roi.region_grow import region_grow

pytestmark = pytest.mark.unit


def test_uniform_band_grows_to_max_pixels() -> None:
    """A perfectly uniform image grows to ``max_pixels`` and stops."""
    bands = np.zeros((4, 10, 10), dtype=np.float32)
    mask = region_grow(bands, seed=(5, 5), threshold=0.01, max_pixels=20)
    assert mask.sum() == 20


def test_high_contrast_boundary_is_respected() -> None:
    """Two flat half-images split by a hard edge: growth stays on its side."""
    bands = np.zeros((1, 10, 10), dtype=np.float32)
    bands[0, :, 5:] = 1.0  # right half is "different" land cover
    mask = region_grow(bands, seed=(5, 2), threshold=0.05, max_pixels=10_000)
    assert mask[:, :5].all()
    assert not mask[:, 5:].any()


def test_threshold_zero_keeps_only_seed_for_smooth_gradient() -> None:
    bands = np.linspace(0.0, 1.0, 100, dtype=np.float32).reshape(1, 10, 10)
    mask = region_grow(bands, seed=(0, 0), threshold=0.0, max_pixels=10_000)
    # Only the seed pixel itself.
    assert mask.sum() == 1
    assert mask[0, 0]


def test_invalid_seed_raises() -> None:
    bands = np.zeros((1, 4, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="outside raster"):
        region_grow(bands, seed=(10, 10))


def test_invalid_band_shape() -> None:
    bad = np.zeros((4, 4), dtype=np.float32)
    with pytest.raises(ValueError, match="must be"):
        region_grow(bad, seed=(0, 0))  # type: ignore[arg-type]


def test_spectral_angle_metric() -> None:
    """SAM metric ignores scaling factors."""
    bands = np.zeros((3, 5, 5), dtype=np.float32)
    bands[:, 0, 0] = [0.1, 0.2, 0.3]
    bands[:, 0, 1] = [0.2, 0.4, 0.6]  # same direction, twice the magnitude
    mask = region_grow(
        bands, seed=(0, 0), threshold=0.01, metric="spectral_angle", max_pixels=10_000
    )
    # The "scaled" pixel should be accepted because the angle to the seed is 0.
    assert mask[0, 1]
