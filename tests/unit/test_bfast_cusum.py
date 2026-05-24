"""Numpy CuSum fallback tests."""

from __future__ import annotations

import numpy as np
import pytest

xr = pytest.importorskip("xarray")

from terranova.core.timeseries.bfast import detect_breaks_cusum  # noqa: E402

pytestmark = pytest.mark.unit


def _series(values: np.ndarray, times: list[str]) -> "xr.DataArray":
    return xr.DataArray(
        values.astype(np.float32),
        dims=("time", "y", "x"),
        coords={"time": np.array(times, dtype="datetime64[ns]")},
    )


def test_no_break_when_constant_within_noise() -> None:
    rng = np.random.default_rng(0)
    vals = 0.7 + rng.normal(0, 0.01, size=(20, 2, 2))
    times = [f"2024-{m:02d}-01" for m in range(1, 21)] if False else [
        f"2024-{(i % 12) + 1:02d}-01" for i in range(20)
    ]
    da = _series(vals, times)
    out = detect_breaks_cusum(da, threshold=5.0, monitor_start_index=10)
    # Threshold deliberately high → no breaks anywhere.
    assert (out.break_index == -1).all()


def test_breaks_detected_after_jump() -> None:
    """A clear step change should be picked up."""
    vals = np.zeros((20, 1, 1), dtype=np.float32)
    vals[:10, 0, 0] = 0.7
    vals[10:, 0, 0] = 0.2  # disturbance
    times = [f"2024-{(i % 12) + 1:02d}-01" for i in range(20)]
    da = _series(vals, times)
    # Use a low std workaround — inject some history noise so std != 0.
    vals[:10, 0, 0] += np.random.default_rng(0).normal(0, 0.01, size=10).astype(np.float32)
    da = _series(vals, times)

    out = detect_breaks_cusum(da, threshold=2.0, monitor_start_index=10)
    assert int(out.break_index.values[0, 0]) >= 10


def test_requires_time_dim() -> None:
    bad = xr.DataArray(np.zeros((2, 2), dtype=np.float32), dims=("y", "x"))
    with pytest.raises(ValueError, match="time"):
        detect_breaks_cusum(bad)
