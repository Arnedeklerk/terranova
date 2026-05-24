"""``terrascope.api`` is the stable surface — test the shape doesn't regress."""

from __future__ import annotations

import pytest

from terrascope import api

pytestmark = pytest.mark.unit

# The API surface should be intentionally additive — removing a name here is
# a breaking change.  Pin the set so any deletion fails CI.
EXPECTED_NAMES = {
    "__version__",
    "BBox",
    "CatalogSearch",
    "ClassifierConfig",
    "ClassifierKind",
    "DateRange",
    "ProjectState",
    "Sensor",
    "STACEndpoint",
    "lazy_stack",
    "open_earth_search",
    "open_planetary_computer",
    "search_landsat_c2_l2",
    "search_s2_l2a",
    "search_sentinel2",
    "composite",
    "spatial_clip",
    "temporal_clip",
    "evi",
    "nbr",
    "ndmi",
    "ndsi",
    "ndvi",
    "ndwi",
    "savi",
    "assess",
    "build_estimator",
    "cross_validate",
    "majority_filter",
    "reclassify",
    "sieve",
    "train",
    "asset_id",
    "bands_for",
}


def test_api_surface_complete() -> None:
    """Every name in `__all__` must be importable."""
    for name in api.__all__:
        assert hasattr(api, name), f"api.{name} declared in __all__ but not present"


def test_api_surface_doesnt_lose_names() -> None:
    """The published API never *removes* names without a major version bump."""
    missing = EXPECTED_NAMES - set(api.__all__)
    assert not missing, f"api.* lost public names: {missing}"


def test_version_string_is_semver_ish() -> None:
    import re

    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[a-z0-9.+-]+)?", api.__version__)
