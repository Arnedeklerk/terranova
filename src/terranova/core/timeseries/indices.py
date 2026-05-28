"""Spectral indices computed with :mod:`spyndex`.

We deliberately keep a hand-rolled NDVI because it has no extra
dependencies and is the smoke-test algorithm used by the NDVI Processing
algorithm (planned).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


def _normalised_difference(a: "np.ndarray", b: "np.ndarray") -> "np.ndarray":
    """``(a - b) / (a + b)`` with safe NaN propagation where the sum is zero."""
    import numpy as np

    a_f = a.astype(np.float32, copy=False)
    b_f = b.astype(np.float32, copy=False)
    denom = a_f + b_f
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom == 0, np.nan, (a_f - b_f) / denom)
    return out.astype(np.float32, copy=False)


def ndvi(red: "np.ndarray", nir: "np.ndarray") -> "np.ndarray":
    """Normalised Difference Vegetation Index — ``(nir - red) / (nir + red)``."""
    return _normalised_difference(nir, red)


def ndwi(green: "np.ndarray", nir: "np.ndarray") -> "np.ndarray":
    """McFeeters' NDWI for surface water — ``(green - nir) / (green + nir)``."""
    return _normalised_difference(green, nir)


def ndmi(nir: "np.ndarray", swir1: "np.ndarray") -> "np.ndarray":
    """Normalised Difference Moisture Index — ``(nir - swir1) / (nir + swir1)``."""
    return _normalised_difference(nir, swir1)


def nbr(nir: "np.ndarray", swir2: "np.ndarray") -> "np.ndarray":
    """Normalised Burn Ratio — ``(nir - swir2) / (nir + swir2)``.

    Lower values after a fire indicate higher burn severity (``dNBR = NBR_pre - NBR_post``).
    """
    return _normalised_difference(nir, swir2)


def ndsi(green: "np.ndarray", swir1: "np.ndarray") -> "np.ndarray":
    """Normalised Difference Snow Index — ``(green - swir1) / (green + swir1)``."""
    return _normalised_difference(green, swir1)


def evi(
    red: "np.ndarray",
    nir: "np.ndarray",
    blue: "np.ndarray",
    *,
    g: float = 2.5,
    c1: float = 6.0,
    c2: float = 7.5,
    l: float = 1.0,
) -> "np.ndarray":
    """Enhanced Vegetation Index (Huete et al. 2002).

    ``EVI = G * (NIR - Red) / (NIR + C1*Red - C2*Blue + L)``.

    Default coefficients ``G=2.5, C1=6, C2=7.5, L=1`` are the MODIS values
    used for Sentinel-2 and Landsat as well.
    """
    import numpy as np

    r = red.astype(np.float32, copy=False)
    n = nir.astype(np.float32, copy=False)
    b = blue.astype(np.float32, copy=False)
    denom = n + c1 * r - c2 * b + l
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom == 0, np.nan, g * (n - r) / denom)
    return out.astype(np.float32, copy=False)


def savi(red: "np.ndarray", nir: "np.ndarray", *, l: float = 0.5) -> "np.ndarray":
    """Soil-Adjusted Vegetation Index (Huete 1988).

    ``SAVI = (1 + L) * (NIR - Red) / (NIR + Red + L)``.  ``L=0.5`` works for
    moderate cover; use ``L=0`` (equivalent to NDVI) for dense cover or
    ``L=1`` for sparse cover.
    """
    import numpy as np

    r = red.astype(np.float32, copy=False)
    n = nir.astype(np.float32, copy=False)
    denom = n + r + l
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.where(denom == 0, np.nan, (1.0 + l) * (n - r) / denom)
    return out.astype(np.float32, copy=False)


def index_via_spyndex(name: str, **bands: "np.ndarray") -> "np.ndarray":  # pragma: no cover
    """Compute any index supported by :mod:`spyndex`.

    Example:
        >>> ndmi = index_via_spyndex("NDMI", N=nir, S1=swir1)
    """
    import spyndex

    return spyndex.computeIndex(index=name, params=bands)
