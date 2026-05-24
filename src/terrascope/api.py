"""Stable public surface for scripting TerraScope from notebooks / Python console.

The intent is that everything reachable from this module is considered API and
covered by semantic versioning.  Internal modules (``terrascope.core.*``,
``terrascope.controllers.*``) may change between minor versions; ``terrascope.api``
may not.

Example:
    >>> from terrascope import api
    >>> items = api.search_sentinel2(
    ...     bbox=(-0.5, 51.3, 0.3, 51.7),
    ...     datetime="2024-06-01/2024-09-30",
    ...     max_cloud=20,
    ... )
    >>> stack = api.lazy_stack(items, bands=("red", "green", "blue", "nir"))
    >>> composite = api.composite(stack, method="median")
"""

from __future__ import annotations

from .core.accuracy.metrics import assess
from .core.catalog.stac import (
    lazy_stack,
    open_earth_search,
    open_planetary_computer,
    search_landsat_c2_l2,
    search_s2_l2a,
)
from .core.ml.classical import build_estimator, cross_validate, train
from .core.ml.postprocess import majority_filter, reclassify, sieve
from .core.models import (
    BBox,
    CatalogSearch,
    ClassifierConfig,
    ClassifierKind,
    DateRange,
    STACEndpoint,
)
from .core.project.state import ProjectState
from .core.sensors import Sensor, asset_id, bands_for
from .core.stacking.lazy import composite, spatial_clip, temporal_clip
from .core.timeseries.indices import evi, nbr, ndmi, ndsi, ndvi, ndwi, savi
from .version import __version__

__all__ = [
    "__version__",
    # Models
    "BBox",
    "CatalogSearch",
    "ClassifierConfig",
    "ClassifierKind",
    "DateRange",
    "ProjectState",
    "Sensor",
    "STACEndpoint",
    # Catalog
    "lazy_stack",
    "open_earth_search",
    "open_planetary_computer",
    "search_landsat_c2_l2",
    "search_s2_l2a",
    "search_sentinel2",
    # Stacking
    "composite",
    "spatial_clip",
    "temporal_clip",
    # Indices
    "evi",
    "nbr",
    "ndmi",
    "ndsi",
    "ndvi",
    "ndwi",
    "savi",
    # ML
    "assess",
    "build_estimator",
    "cross_validate",
    "majority_filter",
    "reclassify",
    "sieve",
    "train",
    # Sensors
    "asset_id",
    "bands_for",
]


def search_sentinel2(
    bbox: tuple[float, float, float, float],
    datetime: str,
    *,
    max_cloud: int = 30,
    limit: int = 50,
):  # type: ignore[no-untyped-def]  # pystac return type is opaque
    """Convenience wrapper around :func:`core.catalog.stac.search_s2_l2a`.

    Uses Microsoft Planetary Computer as the default endpoint; if you need
    Earth Search instead, call :mod:`terrascope.core.catalog.stac` directly.
    """
    client = open_planetary_computer()
    return search_s2_l2a(client, bbox=bbox, datetime=datetime, max_cloud=max_cloud, limit=limit)
