"""LandTrendr-lite per-pixel segmentation tests."""

from __future__ import annotations

import numpy as np
import pytest

from terrascope.core.timeseries.landtrendr import segment_pixel

pytestmark = pytest.mark.unit


def test_linear_series_no_break() -> None:
    """A perfectly linear trajectory should fit with two vertices."""
    series = np.linspace(0.2, 0.8, 20, dtype=np.float32)
    seg = segment_pixel(series, max_segments=4)
    # Endpoints only — two vertices, two values.
    assert seg.vertex_indices[0] == 0
    assert seg.vertex_indices[-1] == 19
    np.testing.assert_allclose(seg.fit, series, atol=1e-5)


def test_v_shape_finds_break() -> None:
    """A V-shaped trajectory (down then up) should have a middle vertex."""
    n = 20
    series = np.concatenate([np.linspace(0.8, 0.2, 10), np.linspace(0.2, 0.8, 10)]).astype(
        np.float32
    )
    seg = segment_pixel(series, max_segments=4, min_observation_per_segment=3)
    # At least 3 vertices (endpoints + at least one break).
    assert len(seg.vertex_indices) >= 3
    # The break should be near the trough at index 9 / 10.
    middle = [i for i in seg.vertex_indices if 5 <= i <= 14]
    assert middle, f"no middle vertex found in {seg.vertex_indices}"


def test_max_segments_respected() -> None:
    """Fit complexity is bounded by ``max_segments``."""
    rng = np.random.default_rng(0)
    series = rng.normal(0.5, 0.1, size=30).astype(np.float32)
    seg = segment_pixel(series, max_segments=3, min_observation_per_segment=2)
    # At most max_segments + 1 vertices.
    assert len(seg.vertex_indices) <= 4


def test_handles_short_series() -> None:
    seg = segment_pixel(np.array([0.5], dtype=np.float32))
    assert seg.vertex_indices == [0]


def test_handles_all_nan_series() -> None:
    seg = segment_pixel(np.array([np.nan, np.nan, np.nan], dtype=np.float32))
    # Should not crash; returns endpoints.
    assert seg.vertex_indices == [0, 2]
