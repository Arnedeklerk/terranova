"""Read a windowed numpy array from a raster — convenience over rasterio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


def read_window(
    path: Path,
    *,
    row_off: int,
    col_off: int,
    height: int,
    width: int,
    bands: list[int] | None = None,
) -> "np.ndarray":
    """Read ``height x width`` pixels starting at ``(row_off, col_off)``.

    Returns a ``(n_bands, h, w)`` array.  ``bands`` is 1-based and defaults to
    all bands.
    """
    import rasterio
    from rasterio.windows import Window

    window = Window(col_off, row_off, width, height)
    with rasterio.open(path) as src:
        indexes = bands or list(range(1, src.count + 1))
        return src.read(indexes, window=window)


def read_centred_window(
    path: Path,
    *,
    centre_xy: tuple[float, float],
    half_window: int,
    bands: list[int] | None = None,
) -> "np.ndarray":
    """Read a ``(2*half_window + 1)`` square centred on a CRS-coord point.

    Useful for the spectral-signature panel: the user clicks the map, we read
    a small patch and compute mean/std per band.
    """
    import rasterio

    with rasterio.open(path) as src:
        row, col = src.index(centre_xy[0], centre_xy[1])
    size = 2 * half_window + 1
    return read_window(
        path,
        row_off=max(0, row - half_window),
        col_off=max(0, col - half_window),
        height=size,
        width=size,
        bands=bands,
    )
