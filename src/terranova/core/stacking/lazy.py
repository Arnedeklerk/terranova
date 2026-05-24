"""Mosaic and composite operations over a lazy xarray cube."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr

MosaicMethod = Literal["median", "mean", "p25", "p75", "first_valid", "least_cloudy"]


def composite(cube: "xr.DataArray", *, method: MosaicMethod = "median") -> "xr.DataArray":
    """Reduce the ``time`` dimension to a single composite per pixel.

    Methods:

    - ``median`` — robust to clouds; default
    - ``mean`` — sensitive to remaining cloud contamination
    - ``p25`` / ``p75`` — useful for darkest/brightest pixel composites
    - ``first_valid`` — pick the first observation that is not NaN
    - ``least_cloudy`` — pick the value from the time slice with the lowest
      ``eo:cloud_cover`` coordinate (requires that coord to be present)

    The cube must have ``time`` as a dimension; everything else is preserved.
    """
    import numpy as np

    if "time" not in cube.dims:
        raise ValueError("composite() requires a `time` dimension on the cube")

    if method == "median":
        return cube.median(dim="time", skipna=True)
    if method == "mean":
        return cube.mean(dim="time", skipna=True)
    if method == "p25":
        return cube.quantile(0.25, dim="time", skipna=True).drop_vars("quantile")
    if method == "p75":
        return cube.quantile(0.75, dim="time", skipna=True).drop_vars("quantile")
    if method == "first_valid":
        # Pick the first non-NaN value along `time` per pixel.
        valid = ~np.isnan(cube)
        first_idx = valid.argmax(dim="time")
        out = cube.isel(time=first_idx)
        # Where everything was NaN, argmax returns 0 — restore NaN.
        no_valid = ~valid.any(dim="time")
        return out.where(~no_valid)
    if method == "least_cloudy":
        if "eo:cloud_cover" not in cube.coords:
            raise ValueError("`least_cloudy` requires an `eo:cloud_cover` coord")
        cloudiest = cube["eo:cloud_cover"].argmin(dim="time")
        return cube.isel(time=cloudiest)
    raise ValueError(f"unknown composite method: {method!r}")


def temporal_clip(cube: "xr.DataArray", start: str, end: str) -> "xr.DataArray":
    """Restrict the cube to the inclusive ``[start, end]`` ISO 8601 window."""
    return cube.sel(time=slice(start, end))


def spatial_clip(
    cube: "xr.DataArray", bbox: tuple[float, float, float, float], *, bbox_crs: str = "EPSG:4326"
) -> "xr.DataArray":
    """Clip the cube to a WGS84 bbox; reprojects bbox into the cube CRS.

    Parameters
    ----------
    cube
        DataArray with a rioxarray-registered CRS.
    bbox
        ``(west, south, east, north)`` in ``bbox_crs``.
    bbox_crs
        CRS of ``bbox``; default WGS84.  Use the cube CRS to skip reprojection.
    """
    import rioxarray  # noqa: F401 — registers .rio accessor

    cube_crs = cube.rio.crs
    if cube_crs is None:
        raise ValueError("cube has no CRS; call cube.rio.write_crs(...) first")

    if str(cube_crs) != bbox_crs:
        from pyproj import Transformer

        transformer = Transformer.from_crs(bbox_crs, cube_crs, always_xy=True)
        west, south = transformer.transform(bbox[0], bbox[1])
        east, north = transformer.transform(bbox[2], bbox[3])
    else:
        west, south, east, north = bbox

    return cube.rio.clip_box(minx=west, miny=south, maxx=east, maxy=north)


def harmonise_bands(cubes: list["xr.DataArray"], bands: list[str]) -> list["xr.DataArray"]:
    """Reorder each cube so that band 0..n-1 is in the requested order.

    Helpful when stacking Sentinel-2 with Landsat — the band names differ
    (``B04`` vs ``red``) and odc-stac will keep whichever name the catalogue
    uses.  Pass the canonical names you want and a list with the alternate
    names dropped.
    """
    return [cube.sel(band=bands) for cube in cubes]
