"""Per-pixel change-detection drivers — wires CuSum and LandTrendr-lite to
xarray time-series cubes with a uniform interface and progress reporting.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr

Method = Literal["cusum", "bfast", "landtrendr"]


def detect_change(
    cube: "xr.DataArray",
    *,
    method: Method = "cusum",
    monitor_start_index: int = 0,
    threshold: float = 2.0,
    max_segments: int = 4,
    progress_cb: Callable[[float], None] | None = None,
) -> "xr.Dataset":
    """Run change detection on an NDVI / NBR / NDMI cube.

    Returns a Dataset with at least ``break_index`` (int) and ``magnitude``
    (float) rasters.  LandTrendr also adds ``n_segments`` (number of vertices
    in the piecewise-linear fit minus one).
    """
    if "time" not in cube.dims:
        raise ValueError("detect_change requires a `time` dim on the cube")

    if method == "cusum":
        from .bfast import detect_breaks_cusum

        return detect_breaks_cusum(
            cube,
            threshold=threshold,
            monitor_start_index=monitor_start_index,
        )
    if method == "bfast":
        # Optional GPU/OpenCL dependency.  Surfaces a clearer error if missing.
        try:
            from .bfast import detect_breaks
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "bfast (the GPU package) isn't installed.  pip install bfast, "
                "or pick the 'cusum' method which has no extra deps."
            ) from exc
        return detect_breaks(
            cube,
            start_monitor=str(cube.time.values[monitor_start_index]),
        )
    if method == "landtrendr":
        return _landtrendr_apply(cube, max_segments=max_segments, progress_cb=progress_cb)
    raise ValueError(f"unknown change-detection method: {method!r}")


def _landtrendr_apply(
    cube: "xr.DataArray",
    *,
    max_segments: int,
    progress_cb: Callable[[float], None] | None,
) -> "xr.Dataset":
    """Apply :func:`landtrendr.segment_pixel` to every pixel of the cube."""
    import numpy as np
    import xarray as xr

    from .landtrendr import segment_pixel

    values = cube.values  # (T, y, x)
    if values.ndim != 3:
        raise ValueError(f"cube must be (time, y, x); got {values.shape}")
    t, h, w = values.shape

    n_segments = np.zeros((h, w), dtype=np.int32)
    magnitude = np.full((h, w), np.nan, dtype=np.float32)
    break_index = np.full((h, w), -1, dtype=np.int32)

    total = h * w
    done = 0
    for y in range(h):
        for x in range(w):
            seg = segment_pixel(values[:, y, x], max_segments=max_segments)
            n_segments[y, x] = max(len(seg.vertex_indices) - 1, 0)
            if len(seg.vertex_indices) > 2:
                # Largest absolute residual between vertices → break.
                vertex_values = np.asarray(seg.vertex_values, dtype=np.float32)
                diffs = np.abs(np.diff(vertex_values))
                if diffs.size > 0:
                    k = int(diffs.argmax())
                    break_index[y, x] = seg.vertex_indices[k + 1]
                    magnitude[y, x] = float(
                        vertex_values[k + 1] - vertex_values[k]
                    )
        done += w
        if progress_cb is not None and y % max(1, h // 20) == 0:
            progress_cb(done / total)

    return xr.Dataset(
        {
            "break_index": (("y", "x"), break_index),
            "magnitude": (("y", "x"), magnitude),
            "n_segments": (("y", "x"), n_segments),
        },
        coords={"y": cube.y, "x": cube.x},
    )
