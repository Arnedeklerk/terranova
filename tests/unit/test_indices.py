"""NDVI smoke tests — the Phase 0 algorithm."""

from __future__ import annotations

import numpy as np
import pytest

from terrascope.core.timeseries.indices import ndvi

pytestmark = pytest.mark.unit


def test_ndvi_known_values() -> None:
    red = np.array([[0.1, 0.2], [0.3, 0.5]], dtype=np.float32)
    nir = np.array([[0.5, 0.4], [0.3, 0.5]], dtype=np.float32)
    out = ndvi(red, nir)
    # (nir - red) / (nir + red)
    expected = np.array(
        [
            [(0.5 - 0.1) / (0.5 + 0.1), (0.4 - 0.2) / (0.4 + 0.2)],
            [0.0, 0.0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_allclose(out, expected, atol=1e-6)


def test_ndvi_zero_sum_is_nan() -> None:
    red = np.array([[0.0]], dtype=np.float32)
    nir = np.array([[0.0]], dtype=np.float32)
    out = ndvi(red, nir)
    assert np.isnan(out).all()


def test_ndvi_dtype_is_float32() -> None:
    red = np.array([[100]], dtype=np.uint16)
    nir = np.array([[400]], dtype=np.uint16)
    out = ndvi(red, nir)
    assert out.dtype == np.float32
    np.testing.assert_allclose(out, [[0.6]], atol=1e-6)


def test_ndvi_shape_preserved() -> None:
    rng = np.random.default_rng(0)
    red = rng.integers(0, 10_000, size=(64, 64)).astype(np.uint16)
    nir = rng.integers(0, 10_000, size=(64, 64)).astype(np.uint16)
    out = ndvi(red, nir)
    assert out.shape == (64, 64)


# --------------------------------------------------------------------------- #
# Other normalised-difference indices                                         #
# --------------------------------------------------------------------------- #
from terrascope.core.timeseries.indices import evi, nbr, ndmi, ndsi, ndwi, savi


def test_ndwi_water_is_positive() -> None:
    # Water reflects more in green than NIR.
    green = np.array([[0.4]], dtype=np.float32)
    nir = np.array([[0.05]], dtype=np.float32)
    assert ndwi(green, nir)[0, 0] > 0


def test_ndmi_dry_vegetation_is_lower() -> None:
    nir = np.array([[0.4, 0.4]], dtype=np.float32)
    swir1_wet = np.array([[0.1, 0.4]], dtype=np.float32)
    moist = ndmi(nir, swir1_wet)
    assert moist[0, 0] > moist[0, 1]


def test_nbr_burn_severity() -> None:
    # Strong burn → low NIR, high SWIR2 → negative NBR.
    nir = np.array([[0.5, 0.1]], dtype=np.float32)
    swir2 = np.array([[0.1, 0.5]], dtype=np.float32)
    pre = nbr(nir[:, :1], swir2[:, :1])
    post = nbr(nir[:, 1:], swir2[:, 1:])
    dnbr = pre - post
    assert dnbr[0, 0] > 0  # positive dNBR means a burn occurred


def test_ndsi_snow() -> None:
    # Snow is high in green, low in SWIR1.
    green = np.array([[0.9]], dtype=np.float32)
    swir1 = np.array([[0.1]], dtype=np.float32)
    assert ndsi(green, swir1)[0, 0] > 0.5


def test_evi_dense_vegetation() -> None:
    red = np.array([[0.04]], dtype=np.float32)
    nir = np.array([[0.6]], dtype=np.float32)
    blue = np.array([[0.02]], dtype=np.float32)
    out = evi(red, nir, blue)
    assert 0.5 < out[0, 0] < 1.5


def test_savi_zero_l_equals_ndvi() -> None:
    red = np.array([[0.1, 0.2]], dtype=np.float32)
    nir = np.array([[0.5, 0.4]], dtype=np.float32)
    np.testing.assert_allclose(savi(red, nir, l=0.0), ndvi(red, nir), atol=1e-6)


def test_all_indices_float32() -> None:
    a = np.ones((4, 4), dtype=np.uint16) * 100
    b = np.ones((4, 4), dtype=np.uint16) * 200
    for fn in (ndvi, ndwi, ndmi, nbr, ndsi):
        assert fn(a, b).dtype == np.float32
