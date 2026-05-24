"""Smoke-test the exception hierarchy is wired correctly."""

from __future__ import annotations

import pytest

from terranova.core import errors

pytestmark = pytest.mark.unit


def test_subclasses_share_base() -> None:
    for sub in (
        errors.CatalogError,
        errors.CloudMaskError,
        errors.ClassificationError,
        errors.TimeSeriesError,
        errors.ProjectStateError,
        errors.CancelledError,
    ):
        assert issubclass(sub, errors.TerranovaError)


def test_catch_base_catches_everything() -> None:
    with pytest.raises(errors.TerranovaError):
        raise errors.CatalogError("nope")
    with pytest.raises(errors.TerranovaError):
        raise errors.ClassificationError("nope")


def test_specific_catch_doesnt_swallow_unrelated() -> None:
    with pytest.raises(errors.CatalogError):
        raise errors.CatalogError("specific")
    # ClassificationError must not be caught as CatalogError.
    with pytest.raises(errors.ClassificationError):
        try:
            raise errors.ClassificationError("c")
        except errors.CatalogError:
            pytest.fail("CatalogError caught a ClassificationError")
