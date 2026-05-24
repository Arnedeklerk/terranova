"""BandSet auto-detection — needs rasterio to write a fixture raster."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from terranova.core.stacking.bandset import from_raster  # noqa: E402

pytestmark = pytest.mark.unit


def _write_fixture(path, descriptions: list[str]) -> None:  # type: ignore[no-untyped-def]
    """Write a tiny 4-band raster with the given description tags."""
    n = len(descriptions)
    data = (np.arange(n * 4 * 4, dtype=np.float32).reshape(n, 4, 4))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=n,
        dtype="float32",
        crs="EPSG:4326",
        transform=rasterio.transform.from_bounds(0, 0, 1, 1, 4, 4),
    ) as dst:
        dst.write(data)
        dst.descriptions = tuple(descriptions)


def test_from_raster_uses_descriptions(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "s2_like.tif"
    _write_fixture(path, ["B02", "B03", "B04", "B08"])
    bs = from_raster(path)
    assert bs.band_names == ["B02", "B03", "B04", "B08"]
    # All four bands matched the S2 registry, so wavelengths are populated.
    assert len(bs.central_wavelengths_nm) == 4


def test_from_raster_falls_back_to_bandN(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "unknown.tif"
    _write_fixture(path, ["", "", ""])
    bs = from_raster(path)
    assert bs.band_names == ["band1", "band2", "band3"]
    # No wavelengths recognised → empty list (avoid partial fill).
    assert bs.central_wavelengths_nm == []


def test_from_raster_uses_stem_as_default_name(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "my_scene.tif"
    _write_fixture(path, ["B04"])
    bs = from_raster(path)
    assert bs.name == "my_scene"
