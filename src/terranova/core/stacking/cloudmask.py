"""Cloud, cloud-shadow, and quality masking strategies.

Default for Sentinel-2 is OmniCloudMask (DPIRD-DMA) — sensor-agnostic, strong
shadow detection.  Fallbacks: s2cloudless, SCL, Cloud Score+.

Currently ships interface declarations and the SCL implementation (which is a
simple lookup over the L2A scene classification layer and does not require any
heavy dependencies).
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr


class CloudMasker(str, Enum):
    OMNI = "omnicloudmask"      # default; sensor-agnostic
    S2CLOUDLESS = "s2cloudless"  # CV-based, S2 only
    SCL = "scl"                  # built-in S2 L2A scene-classification band
    CLOUD_SCORE_PLUS = "cloud_score_plus"  # Sentinel Hub / GEE


# SCL class numbers (Sentinel-2 L2A Scene Classification Layer)
SCL_NO_DATA = 0
SCL_SATURATED = 1
SCL_DARK = 2
SCL_CLOUD_SHADOW = 3
SCL_VEGETATION = 4
SCL_NOT_VEGETATED = 5
SCL_WATER = 6
SCL_UNCLASSIFIED = 7
SCL_CLOUD_MEDIUM = 8
SCL_CLOUD_HIGH = 9
SCL_CIRRUS = 10
SCL_SNOW = 11

SCL_INVALID = {
    SCL_NO_DATA,
    SCL_SATURATED,
    SCL_DARK,
    SCL_CLOUD_SHADOW,
    SCL_CLOUD_MEDIUM,
    SCL_CLOUD_HIGH,
    SCL_CIRRUS,
}


def mask_from_scl(cube: "xr.DataArray", scl: "xr.DataArray") -> "xr.DataArray":
    """Mask cloudy / shadow / no-data pixels using the SCL band.

    Both arrays must share dims ``(time, y, x)`` and CRS.  Returns ``cube`` with
    NaN where ``scl`` is in :data:`SCL_INVALID`.
    """
    invalid = scl.isin(list(SCL_INVALID))
    return cube.where(~invalid)


def mask_with_omnicloudmask(
    cube: "xr.DataArray",
    *,
    red_band: str = "red",
    green_band: str = "green",
    nir_band: str = "nir",
    device: str = "auto",
) -> "xr.DataArray":
    """Run OmniCloudMask on each time slice; mask cloudy + shadow pixels.

    Requires the optional :mod:`omnicloudmask` package.  Per the upstream
    docs, OmniCloudMask is sensor-agnostic and processes a PlanetScope tile
    in ~1–2 s on a modern NVIDIA GPU.  Set ``device="cpu"`` to force CPU.

    Parameters
    ----------
    cube
        DataArray with at least ``(time, band, y, x)`` and a ``band``
        coordinate naming the red/green/NIR bands as below.
    red_band, green_band, nir_band
        The coordinate values picking the three bands the model needs.
    device
        Forwarded to OmniCloudMask.  ``"auto"`` picks CUDA when available.
    """
    import numpy as np
    import omnicloudmask
    import xarray as xr

    if "time" not in cube.dims:
        raise ValueError("mask_with_omnicloudmask requires a `time` dim")

    masked_slices = []
    for t in cube.time.values:
        slice_t = cube.sel(time=t)
        # Stack the three bands the model expects.
        rgb_nir = np.stack(
            [
                slice_t.sel(band=red_band).values,
                slice_t.sel(band=green_band).values,
                slice_t.sel(band=nir_band).values,
            ],
            axis=0,
        )
        # OmniCloudMask returns a (h, w) class raster:
        # 0 = clear, 1 = thick cloud, 2 = thin cloud, 3 = cloud shadow.
        cls = omnicloudmask.predict_from_array(rgb_nir, device=device)
        invalid = cls > 0
        masked = slice_t.where(~invalid)
        masked_slices.append(masked)

    return xr.concat(masked_slices, dim="time")
