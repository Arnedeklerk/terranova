"""Catalogue-search controller — adapter between the dispatch table and pystac."""

from __future__ import annotations

from typing import Any

from ..core.catalog import stac
from ..core.models import CatalogSearch, STACEndpoint


def search(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle ``catalog.search``.

    Payload shape mirrors :class:`CatalogSearch`.  Returns a JSON-friendly list
    of items with ``id``, ``datetime``, ``cloud``, ``platform``.
    """
    cfg = CatalogSearch.model_validate(payload)
    client = _open_client(cfg.endpoint)
    bbox = cfg.bbox.as_tuple()
    items = stac.search_s2_l2a(
        client,
        bbox=bbox,
        datetime=cfg.datetime.as_stac(),
        max_cloud=cfg.max_cloud,
        limit=cfg.limit,
    )

    return {
        "items": [
            {
                "id": it.id,
                "datetime": str(it.datetime),
                "cloud": it.properties.get("eo:cloud_cover"),
                "platform": it.properties.get("platform"),
            }
            for it in items
        ],
        "count": len(list(items)) if hasattr(items, "__len__") else None,
    }


def _open_client(endpoint: STACEndpoint):  # type: ignore[no-untyped-def]
    if endpoint is STACEndpoint.PLANETARY_COMPUTER:
        return stac.open_planetary_computer()
    if endpoint is STACEndpoint.EARTH_SEARCH:
        return stac.open_earth_search()
    if endpoint is STACEndpoint.CDSE:
        return stac.open_cdse()
    raise ValueError(f"unknown endpoint: {endpoint!r}")
