"""Tests for the composite / temporal_clip helpers."""

from __future__ import annotations

import numpy as np
import pytest

xr = pytest.importorskip("xarray")

from terranova.core.stacking.lazy import (  # noqa: E402
    composite,
    temporal_clip,
)

pytestmark = pytest.mark.unit


def _cube(values: np.ndarray, times: list[str]) -> "xr.DataArray":
    """Make a (time, y, x) DataArray for testing."""
    return xr.DataArray(
        values,
        dims=("time", "y", "x"),
        coords={
            "time": np.array(times, dtype="datetime64[ns]"),
            "y": [0, 1],
            "x": [0, 1],
        },
    )


def test_median_composite_collapses_time() -> None:
    values = np.array(
        [
            [[1.0, 2.0], [3.0, 4.0]],
            [[5.0, 6.0], [7.0, 8.0]],
            [[9.0, 10.0], [11.0, 12.0]],
        ],
        dtype=np.float32,
    )
    cube = _cube(values, ["2024-01-01", "2024-06-01", "2024-12-01"])
    out = composite(cube, method="median")
    assert "time" not in out.dims
    np.testing.assert_allclose(out.values, [[5.0, 6.0], [7.0, 8.0]])


def test_mean_skips_nan() -> None:
    values = np.array(
        [
            [[1.0, np.nan], [3.0, 4.0]],
            [[3.0, 2.0], [np.nan, 6.0]],
        ],
        dtype=np.float32,
    )
    cube = _cube(values, ["2024-01-01", "2024-06-01"])
    out = composite(cube, method="mean")
    np.testing.assert_allclose(out.values, [[2.0, 2.0], [3.0, 5.0]])


def test_temporal_clip() -> None:
    values = np.zeros((3, 2, 2), dtype=np.float32)
    cube = _cube(values, ["2024-01-01", "2024-06-01", "2024-12-01"])
    clipped = temporal_clip(cube, "2024-05-01", "2024-07-31")
    assert clipped.sizes["time"] == 1


def test_unknown_method_raises() -> None:
    cube = _cube(np.zeros((1, 2, 2), dtype=np.float32), ["2024-01-01"])
    with pytest.raises(ValueError, match="unknown composite method"):
        composite(cube, method="banana")  # type: ignore[arg-type]


def test_missing_time_dim_raises() -> None:
    bad = xr.DataArray(np.zeros((2, 2), dtype=np.float32), dims=("y", "x"))
    with pytest.raises(ValueError, match="time"):
        composite(bad)


def test_first_valid_picks_earliest_non_nan() -> None:
    values = np.array(
        [
            [[np.nan, 1.0], [np.nan, np.nan]],
            [[2.0, 3.0], [np.nan, 4.0]],
            [[5.0, 6.0], [7.0, 8.0]],
        ],
        dtype=np.float32,
    )
    cube = _cube(values, ["2024-01-01", "2024-06-01", "2024-12-01"])
    out = composite(cube, method="first_valid")
    expected = np.array([[2.0, 1.0], [7.0, 4.0]], dtype=np.float32)
    np.testing.assert_allclose(out.values, expected)


def test_first_valid_all_nan_stays_nan() -> None:
    values = np.full((2, 2, 2), np.nan, dtype=np.float32)
    cube = _cube(values, ["2024-01-01", "2024-06-01"])
    out = composite(cube, method="first_valid")
    assert np.isnan(out.values).all()


def test_p25_p75() -> None:
    """Quartile composites match numpy quantile semantics."""
    values = np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32).reshape(4, 1, 1)
    cube = xr.DataArray(
        values,
        dims=("time", "y", "x"),
        coords={
            "time": np.array(
                ["2024-01-01", "2024-04-01", "2024-07-01", "2024-10-01"],
                dtype="datetime64[ns]",
            ),
            "y": [0],
            "x": [0],
        },
    )
    out25 = composite(cube, method="p25")
    out75 = composite(cube, method="p75")
    assert float(out25.values[0, 0]) == pytest.approx(1.75)
    assert float(out75.values[0, 0]) == pytest.approx(3.25)
