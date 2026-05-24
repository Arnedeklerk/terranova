"""Reprojection helper — match one raster to another's CRS + grid."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

Resampling = Literal[
    "nearest", "bilinear", "cubic", "cubic_spline", "lanczos", "average", "mode", "max", "min"
]


def reproject_to_match(
    src_path: Path,
    template_path: Path,
    out_path: Path,
    *,
    resampling: Resampling = "bilinear",
    dst_nodata: float | int | None = None,
) -> Path:
    """Reproject ``src_path`` onto ``template_path``'s CRS, transform, and shape.

    Use ``nearest`` for categorical rasters (class maps).  Default ``bilinear``
    is right for continuous data like NDVI.
    """
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling as RioRes
    from rasterio.warp import reproject

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rio_res = {
        "nearest": RioRes.nearest,
        "bilinear": RioRes.bilinear,
        "cubic": RioRes.cubic,
        "cubic_spline": RioRes.cubic_spline,
        "lanczos": RioRes.lanczos,
        "average": RioRes.average,
        "mode": RioRes.mode,
        "max": RioRes.max,
        "min": RioRes.min,
    }[resampling]

    with rasterio.open(template_path) as tpl, rasterio.open(src_path) as src:
        profile = tpl.profile.copy()
        profile.update(count=src.count, dtype=src.dtypes[0], compress="deflate")
        if dst_nodata is not None:
            profile.update(nodata=dst_nodata)

        with rasterio.open(out_path, "w", **profile) as dst:
            for band in range(1, src.count + 1):
                out_band = np.zeros((tpl.height, tpl.width), dtype=src.dtypes[band - 1])
                reproject(
                    source=rasterio.band(src, band),
                    destination=out_band,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=tpl.transform,
                    dst_crs=tpl.crs,
                    resampling=rio_res,
                    dst_nodata=dst_nodata,
                )
                dst.write(out_band, band)
    return out_path
