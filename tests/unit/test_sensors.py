"""Tests for the sensor band registry."""

from __future__ import annotations

import pytest

from terrascope.core.sensors import (
    SENTINEL_2_BANDS,
    Sensor,
    asset_id,
    bands_for,
    resolve_index,
)

pytestmark = pytest.mark.unit


def test_sentinel2_red_is_B04() -> None:
    assert asset_id(Sensor.SENTINEL_2, "red") == "B04"


def test_sentinel2_nir_is_B08() -> None:
    assert asset_id(Sensor.SENTINEL_2, "nir") == "B08"


def test_landsat8_red_is_SR_B4() -> None:
    assert asset_id(Sensor.LANDSAT_8_9, "red") == "SR_B4"


def test_resolve_index_returns_one_based() -> None:
    order = ["B02", "B03", "B04", "B08"]
    assert resolve_index(Sensor.SENTINEL_2, "red", order) == 3
    assert resolve_index(Sensor.SENTINEL_2, "blue", order) == 1


def test_unknown_role_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        asset_id(Sensor.SENTINEL_2, "purple")


def test_unknown_sensor_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        bands_for("not-a-sensor")  # type: ignore[arg-type]


def test_central_wavelengths_make_sense() -> None:
    # Sanity check — bands should be roughly increasing in wavelength when
    # listed in their canonical order in the dict.
    waves = [b.wavelength_nm for b in SENTINEL_2_BANDS.values()]
    # Allow for the cirrus + water vapour bands being out of order; just
    # spot-check the visible/NIR ramp.
    rgb = [SENTINEL_2_BANDS["blue"], SENTINEL_2_BANDS["green"], SENTINEL_2_BANDS["red"]]
    assert rgb[0].wavelength_nm < rgb[1].wavelength_nm < rgb[2].wavelength_nm
    assert SENTINEL_2_BANDS["nir"].wavelength_nm > SENTINEL_2_BANDS["red"].wavelength_nm
    assert all(w > 0 for w in waves)
