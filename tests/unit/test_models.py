"""Pydantic model validation tests — pure Python, no QGIS."""

from __future__ import annotations

from datetime import datetime

import pytest

from terranova.core.models import (
    BBox,
    CatalogSearch,
    ClassifierConfig,
    ClassifierKind,
    CommandMessage,
    CommandResult,
    DateRange,
    STACEndpoint,
)

pytestmark = pytest.mark.unit


class TestBBox:
    def test_valid(self) -> None:
        bb = BBox(west=-0.5, south=51.3, east=0.3, north=51.7)
        assert bb.as_tuple() == (-0.5, 51.3, 0.3, 51.7)

    def test_west_must_be_less_than_east(self) -> None:
        with pytest.raises(ValueError, match="east must be > west"):
            BBox(west=1.0, south=0.0, east=0.5, north=1.0)

    def test_south_must_be_less_than_north(self) -> None:
        with pytest.raises(ValueError, match="north must be > south"):
            BBox(west=0.0, south=10.0, east=1.0, north=5.0)

    def test_out_of_range_longitude(self) -> None:
        with pytest.raises(ValueError):
            BBox(west=-181, south=0, east=10, north=10)

    def test_frozen(self) -> None:
        bb = BBox(west=0, south=0, east=1, north=1)
        with pytest.raises((TypeError, ValueError)):
            bb.west = 2  # type: ignore[misc]


class TestDateRange:
    def test_stac_format(self) -> None:
        dr = DateRange(start=datetime(2024, 6, 1), end=datetime(2024, 9, 30))
        assert dr.as_stac() == "2024-06-01/2024-09-30"


class TestCatalogSearch:
    def test_defaults(self) -> None:
        cs = CatalogSearch(
            bbox=BBox(west=0, south=0, east=1, north=1),
            datetime=DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 12, 31)),
        )
        assert cs.endpoint is STACEndpoint.PLANETARY_COMPUTER
        assert cs.collection == "sentinel-2-l2a"
        assert cs.max_cloud == 30

    def test_invalid_cloud(self) -> None:
        with pytest.raises(ValueError):
            CatalogSearch(
                bbox=BBox(west=0, south=0, east=1, north=1),
                datetime=DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 12, 31)),
                max_cloud=120,
            )


class TestClassifierConfig:
    def test_default_is_random_forest(self) -> None:
        cfg = ClassifierConfig()
        assert cfg.kind is ClassifierKind.RANDOM_FOREST

    def test_test_size_bounds(self) -> None:
        with pytest.raises(ValueError):
            ClassifierConfig(test_size=0.9)


class TestBridgeMessages:
    def test_command_round_trip(self) -> None:
        msg = CommandMessage(action="app.ping", payload={"hello": "world"})
        raw = msg.model_dump_json()
        round = CommandMessage.model_validate_json(raw)
        assert round.action == "app.ping"
        assert round.payload == {"hello": "world"}

    def test_result_error_default(self) -> None:
        r = CommandResult(ok=False, error="boom")
        assert r.result is None
        assert r.kind == "sync"
