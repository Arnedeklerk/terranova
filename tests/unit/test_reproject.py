"""Reproject-to-match smoke tests using synthetic rasters."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from terrascope.core.io import reproject_to_match  # noqa: E402

pytestmark = pytest.mark.unit


def _write_const_raster(path, crs: str, value: int) -> None:  # type: ignore[no-untyped-def]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=8,
        width=8,
        count=1,
        dtype="int16",
        crs=crs,
        transform=rasterio.transform.from_bounds(0, 0, 1, 1, 8, 8),
    ) as dst:
        dst.write(np.full((8, 8), value, dtype=np.int16), 1)


def test_match_template_shape(tmp_path) -> None:  # type: ignore[no-untyped-def]
    src = tmp_path / "src.tif"
    tpl = tmp_path / "tpl.tif"
    out = tmp_path / "out.tif"
    _write_const_raster(src, "EPSG:4326", value=5)
    _write_const_raster(tpl, "EPSG:4326", value=0)

    reproject_to_match(src, tpl, out, resampling="nearest")
    assert out.exists()
    with rasterio.open(out) as dst:
        assert dst.height == 8
        assert dst.width == 8
        assert dst.crs.to_string() == "EPSG:4326"
        data = dst.read(1)
        # Same CRS + transform → value preserved.
        assert (data == 5).all()


def test_reproject_cross_crs(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A WGS84 raster reprojected into Web Mercator should land in EPSG:3857."""
    src = tmp_path / "src.tif"
    tpl = tmp_path / "tpl.tif"
    out = tmp_path / "out.tif"
    _write_const_raster(src, "EPSG:4326", value=7)

    # Template in Web Mercator.
    with rasterio.open(
        tpl,
        "w",
        driver="GTiff",
        height=16,
        width=16,
        count=1,
        dtype="int16",
        crs="EPSG:3857",
        transform=rasterio.transform.from_bounds(0, 0, 1000, 1000, 16, 16),
    ) as dst:
        dst.write(np.zeros((16, 16), dtype=np.int16), 1)

    reproject_to_match(src, tpl, out, resampling="bilinear")
    with rasterio.open(out) as dst:
        assert dst.crs.to_string() == "EPSG:3857"
        assert dst.height == 16
        assert dst.width == 16
