"""Tests for the catalog-search controller — pystac is mocked."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from terrascope.controllers import catalog as ctl
from terrascope.controllers.dispatch import Controllers
from terrascope.core.catalog import stac

pytestmark = pytest.mark.unit


def _fake_item(item_id: str, cloud: float, platform: str) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.datetime = datetime(2024, 7, 1)
    item.properties = {"eo:cloud_cover": cloud, "platform": platform}
    return item


def test_search_passes_through_to_pystac(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake_client = MagicMock()
    items = [
        _fake_item("S2A_1", 5.0, "Sentinel-2A"),
        _fake_item("S2A_2", 8.5, "Sentinel-2A"),
    ]

    monkeypatch.setattr(stac, "open_planetary_computer", lambda: fake_client)
    monkeypatch.setattr(stac, "search_s2_l2a", lambda *a, **k: items)

    payload = {
        "endpoint": "planetary_computer",
        "collection": "sentinel-2-l2a",
        "bbox": {"west": 0.0, "south": 50.0, "east": 1.0, "north": 51.0},
        "datetime": {"start": "2024-06-01T00:00:00", "end": "2024-09-30T00:00:00"},
        "max_cloud": 20,
        "limit": 10,
    }
    result = ctl.search(payload)
    assert len(result["items"]) == 2
    assert result["items"][0]["id"] == "S2A_1"
    assert result["items"][0]["cloud"] == 5.0
    assert result["items"][1]["platform"] == "Sentinel-2A"


def test_dispatch_wraps_in_command_result(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    fake_client = MagicMock()
    monkeypatch.setattr(stac, "open_planetary_computer", lambda: fake_client)
    monkeypatch.setattr(stac, "search_s2_l2a", lambda *a, **k: [])

    c = Controllers()
    r = c.dispatch(
        "catalog.search",
        {
            "endpoint": "planetary_computer",
            "collection": "sentinel-2-l2a",
            "bbox": {"west": 0.0, "south": 50.0, "east": 1.0, "north": 51.0},
            "datetime": {"start": "2024-06-01T00:00:00", "end": "2024-09-30T00:00:00"},
            "max_cloud": 20,
        },
    )
    assert r.ok is True
    assert r.result == {"items": [], "count": 0}


def test_invalid_payload_returns_error() -> None:
    c = Controllers()
    r = c.dispatch("catalog.search", {"endpoint": "not-a-thing"})
    assert r.ok is False
    assert r.error is not None
