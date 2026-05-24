"""LandTrendr-lite — piecewise-linear time-series segmentation.

This is a faithful but simplified port of Kennedy et al. 2010, suitable for
yearly NDVI / NBR trajectories from Landsat or Sentinel-2 composites.  The
full upstream implementation has more bells and whistles (vertex damping,
desawtooth, MMU filtering); we ship the core algorithm so the change-
detection workflow has a non-GPU option for trajectory segmentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


@dataclass(slots=True)
class Segmentation:
    """Result of one pixel's LandTrendr-lite segmentation."""

    vertex_indices: list[int]
    vertex_values: list[float]
    fit: "np.ndarray"  # the piecewise-linear fit at every time step


def segment_pixel(
    series: "np.ndarray",
    *,
    max_segments: int = 4,
    min_observation_per_segment: int = 3,
) -> Segmentation:
    """Find a piecewise-linear fit with at most ``max_segments`` segments.

    Algorithm:

    1. Start with the endpoints as the only two vertices.
    2. Greedily add the time step with the worst residual until we have
       ``max_segments + 1`` vertices or no more candidates respect the
       ``min_observation_per_segment`` constraint.
    3. Return the vertex indices, vertex values, and the full piecewise-
       linear fit.

    NaNs in ``series`` are treated as gaps — the fit interpolates across them.
    """
    import numpy as np

    n = series.size
    if n < 2:
        return Segmentation(vertex_indices=[0], vertex_values=[float(series[0])], fit=series.copy())

    valid = ~np.isnan(series)
    if valid.sum() < 2:
        return Segmentation(
            vertex_indices=[0, n - 1],
            vertex_values=[float(np.nan_to_num(series[0])), float(np.nan_to_num(series[-1]))],
            fit=series.copy(),
        )

    vertices = [0, n - 1]

    for _ in range(max_segments - 1):
        # Compute the current piecewise-linear fit.
        fit = _piecewise_linear_fit(series, vertices, n)
        residuals = np.where(valid, series - fit, 0.0)
        # Don't pick an existing vertex or a step inside the constraint.
        candidates = _candidate_indices(vertices, n, min_observation_per_segment)
        if not candidates:
            break
        # Pick the candidate with the largest absolute residual.
        candidate_residuals = np.abs(residuals[candidates])
        if candidate_residuals.max() < 1e-6:
            break
        new_vertex = candidates[int(candidate_residuals.argmax())]
        vertices = sorted(vertices + [new_vertex])

    fit = _piecewise_linear_fit(series, vertices, n)
    return Segmentation(
        vertex_indices=list(vertices),
        vertex_values=[float(series[i]) for i in vertices],
        fit=fit,
    )


def _piecewise_linear_fit(series: "np.ndarray", vertices: list[int], n: int) -> "np.ndarray":
    import numpy as np

    fit = np.empty(n, dtype=np.float32)
    for v0, v1 in zip(vertices[:-1], vertices[1:]):
        y0, y1 = float(np.nan_to_num(series[v0])), float(np.nan_to_num(series[v1]))
        xs = np.arange(v1 - v0 + 1)
        fit[v0 : v1 + 1] = y0 + (y1 - y0) * xs / max(v1 - v0, 1)
    return fit


def _candidate_indices(vertices: list[int], n: int, min_per_seg: int) -> list[int]:
    cands: list[int] = []
    sv = sorted(vertices)
    for v0, v1 in zip(sv[:-1], sv[1:]):
        for k in range(v0 + min_per_seg, v1 - min_per_seg + 1):
            cands.append(k)
    return cands
