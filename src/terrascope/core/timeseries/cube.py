"""Time-series cube I/O — Zarr persistence under the project directory."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr
    from pystac import Item


def build_cube(
    items: Iterable["Item"],
    *,
    bands: Iterable[str],
    resolution: int,
    out_path: Path,
    bbox: tuple[float, float, float, float] | None = None,
    chunks: dict[str, int] | None = None,
) -> Path:
    """Stack ``items`` into a ``(time, band, y, x)`` cube and persist as Zarr.

    Uses :mod:`odc.stac` under the hood; clips to ``bbox`` when supplied to
    keep the cube small.  Returns the path written to.
    """
    import odc.stac

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cube = odc.stac.load(
        list(items),
        bands=list(bands),
        resolution=resolution,
        chunks=chunks or {"x": 2048, "y": 2048},
        bbox=bbox,
    )
    cube.to_zarr(str(out_path), mode="w")
    return out_path


def open_cube(path: Path) -> "xr.DataArray":
    """Open a previously written Zarr cube as a lazy xarray."""
    import xarray as xr

    return xr.open_zarr(str(path))


def cube_summary(path: Path) -> dict:
    """Return a small, JSON-friendly summary — used by the project explorer."""
    cube = open_cube(path)
    return {
        "path": str(path),
        "dims": dict(cube.sizes),
        "bands": list(cube.coords.get("band", [])),
        "time_extent": [
            str(cube.time.min().values),
            str(cube.time.max().values),
        ]
        if "time" in cube.dims
        else None,
    }
