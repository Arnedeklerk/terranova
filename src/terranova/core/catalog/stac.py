"""Thin wrappers around :mod:`pystac_client` and :mod:`odc.stac`.

These functions deliberately use module-level imports of :mod:`pystac_client`
and :mod:`odc.stac` so that they fail loudly at call time on environments that
do not have them installed — rather than mysteriously failing during a long
QgsTask.  The wrappers default to Microsoft Planetary Computer because it is
free, quota-less, and returns signed COG URLs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr
    from pystac import Item
    from pystac_client import Client, ItemSearch

PC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
ES_URL = "https://earth-search.aws.element84.com/v1"
CDSE_URL = "https://catalogue.dataspace.copernicus.eu/stac"


# --------------------------------------------------------------------------- #
# Clients                                                                     #
# --------------------------------------------------------------------------- #
def open_planetary_computer() -> "Client":
    """Open a pystac-client to Microsoft Planetary Computer with auto-signing."""
    import planetary_computer as pc
    import pystac_client

    return pystac_client.Client.open(PC_URL, modifier=pc.sign_inplace)


def open_earth_search() -> "Client":
    """Open a pystac-client to Element 84 Earth Search (AWS, anonymous)."""
    import pystac_client

    return pystac_client.Client.open(ES_URL)


def open_cdse() -> "Client":
    """Open a pystac-client to Copernicus Data Space Ecosystem.

    Note: CDSE STAC currently requires no token for search, but downloads
    require OAuth.  See :mod:`terranova.core.catalog.cdse` for the device-code
    flow.
    """
    import pystac_client

    return pystac_client.Client.open(CDSE_URL)


# --------------------------------------------------------------------------- #
# Search                                                                      #
# --------------------------------------------------------------------------- #
def search_s2_l2a(
    client: "Client",
    bbox: tuple[float, float, float, float],
    datetime: str,
    *,
    max_cloud: int = 30,
    limit: int = 50,
) -> "ItemSearch":
    """Search Sentinel-2 L2A items with a cloud-cover ceiling.

    ``datetime`` follows the STAC convention: a single ISO 8601 instant,
    a slash-separated range, or one half of a range with ``..`` for open.
    """
    return client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=datetime,
        query={"eo:cloud_cover": {"lt": max_cloud}},
        max_items=limit,
    ).item_collection()


def search_landsat_c2_l2(
    client: "Client",
    bbox: tuple[float, float, float, float],
    datetime: str,
    *,
    max_cloud: int = 30,
    limit: int = 50,
    platforms: Iterable[str] = ("landsat-8", "landsat-9"),
) -> "ItemSearch":
    """Search Landsat Collection 2 Level 2 items."""
    return client.search(
        collections=["landsat-c2-l2"],
        bbox=bbox,
        datetime=datetime,
        query={
            "eo:cloud_cover": {"lt": max_cloud},
            "platform": {"in": list(platforms)},
        },
        max_items=limit,
    ).item_collection()


# --------------------------------------------------------------------------- #
# Lazy stack                                                                  #
# --------------------------------------------------------------------------- #
def lazy_stack(
    items: Iterable["Item"],
    *,
    bands: Iterable[str] = ("red", "green", "blue", "nir"),
    resolution: int = 10,
    chunks: dict[str, int] | None = None,
    crs: str | None = None,
    **kwargs: Any,
) -> "xr.DataArray":
    """Build a lazy ``xarray.DataArray`` cube from a STAC ItemCollection.

    Uses :mod:`odc.stac` (preferred) because it groups items by date better
    than :mod:`stackstac` for Sentinel-2 L2A.  The returned array is dask-backed
    and is **not** materialised until ``.compute()`` or ``.to_raster()``.
    """
    import odc.stac

    return odc.stac.load(
        items,
        bands=list(bands),
        resolution=resolution,
        chunks=chunks or {"x": 2048, "y": 2048},
        crs=crs,
        **kwargs,
    )
