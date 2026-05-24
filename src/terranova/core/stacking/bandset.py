"""Band-set construction helpers.

The SCP "Band set" concept maps onto a list of band names + central
wavelengths sourced from a single raster.  This module turns a raster path
(or rasterio profile) into a :class:`BandSet` Pydantic model.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..project.state import BandSet

if TYPE_CHECKING:  # pragma: no cover
    pass


# Heuristics for guessing roles from descriptions.  Matches GDAL's
# convention (rasterio surfaces the ``description`` tag) but also falls back
# to wavelength lookups via central_wavelength_for_band.
_DESCRIPTION_KEYWORDS: dict[str, str] = {
    "B01": "coastal", "B02": "blue",  "B03": "green", "B04": "red",
    "B05": "rededge1", "B06": "rededge2", "B07": "rededge3",
    "B08": "nir", "B8A": "nir_narrow", "B09": "water_vapour",
    "B10": "swir_cirrus", "B11": "swir1", "B12": "swir2",
    "SR_B1": "coastal", "SR_B2": "blue", "SR_B3": "green",
    "SR_B4": "red", "SR_B5": "nir", "SR_B6": "swir1", "SR_B7": "swir2",
}


def from_raster(path: Path, *, name: str | None = None) -> BandSet:
    """Build a :class:`BandSet` from a multi-band raster on disk.

    Reads band descriptions where present (Sentinel-2 STAC COGs ship band ids
    like ``B04`` in the description), falling back to ``band1, band2, ...``.
    Central wavelengths are filled when the description matches a known
    sensor convention via :data:`_DESCRIPTION_KEYWORDS` plus
    :mod:`terranova.core.sensors`.
    """
    import rasterio

    path = Path(path)
    if name is None:
        name = path.stem

    with rasterio.open(path) as src:
        descriptions = list(src.descriptions)
        n_bands = src.count

    names: list[str] = []
    waves: list[float] = []
    for i, desc in enumerate(descriptions, start=1):
        label = desc if desc else f"band{i}"
        names.append(label)
        wave = _central_wavelength_for(label)
        if wave is not None:
            waves.append(wave)

    return BandSet(
        name=name,
        raster_paths=[path],
        band_names=names,
        central_wavelengths_nm=waves if len(waves) == n_bands else [],
    )


def _central_wavelength_for(description: str) -> float | None:
    from ..sensors import (
        LANDSAT_4_7_BANDS,
        LANDSAT_8_9_BANDS,
        SENTINEL_2_BANDS,
    )

    role = _DESCRIPTION_KEYWORDS.get(description)
    if role is None:
        return None
    for registry in (SENTINEL_2_BANDS, LANDSAT_8_9_BANDS, LANDSAT_4_7_BANDS):
        if role in registry:
            return registry[role].wavelength_nm
    return None
