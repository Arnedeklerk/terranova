"""Windowed-read I/O helper tests."""

from __future__ import annotations

import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")

from terrascope.core.io import read_centred_window, read_window  # noqa: E402

pytestmark = pytest.mark.unit


def _write_fixture(path) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Write a 4-band 16x16 raster where band b at pixel (r, c) is b*1000 + r*100 + c."""
    h, w, n_bands = 16, 16, 4
    data = np.zeros((n_bands, h, w), dtype=np.int32)
    for b in range(n_bands):
        for r in range(h):
            for c in range(w):
                data[b, r, c] = (b + 1) * 1000 + r * 100 + c
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=n_bands,
        dtype="int32",
        crs="EPSG:4326",
        transform=rasterio.transform.from_bounds(0, 0, 1, 1, w, h),
    ) as dst:
        dst.write(data)
    return h, w


def test_read_window_returns_correct_subset(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "in.tif"
    _write_fixture(path)
    out = read_window(path, row_off=4, col_off=6, height=3, width=2)
    assert out.shape == (4, 3, 2)
    # Band 1, row 4, col 6 → 1 * 1000 + 4*100 + 6 = 1406.
    assert out[0, 0, 0] == 1406
    # Band 4, row 6, col 7 → 4*1000 + 6*100 + 7 = 4607.
    assert out[3, 2, 1] == 4607


def test_read_window_band_subset(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "in.tif"
    _write_fixture(path)
    out = read_window(path, row_off=0, col_off=0, height=2, width=2, bands=[2, 4])
    assert out.shape == (2, 2, 2)
    # Band 2, row 0, col 0 → 2*1000 = 2000.
    assert out[0, 0, 0] == 2000
    # Band 4, row 1, col 1 → 4*1000 + 100 + 1 = 4101.
    assert out[1, 1, 1] == 4101


def test_read_centred_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "in.tif"
    _write_fixture(path)
    # The CRS spans (0, 0) → (1, 1).  Centre of pixel (8, 8) is (0.5, 0.5).
    out = read_centred_window(path, centre_xy=(0.5, 0.5), half_window=1)
    assert out.shape[1] == 3
    assert out.shape[2] == 3
