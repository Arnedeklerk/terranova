"""Domain-layer exceptions.

Used so callers can ``except TerraScopeError`` to catch anything raised by the
plugin's own code without also swallowing unrelated ``ValueError`` /
``RuntimeError`` from dependencies.
"""

from __future__ import annotations


class TerraScopeError(Exception):
    """Base class for every TerraScope-defined exception."""


class CatalogError(TerraScopeError):
    """STAC search / OAuth / download failure."""


class CloudMaskError(TerraScopeError):
    """Cloud masking failed (model load / inference)."""


class ClassificationError(TerraScopeError):
    """Classification training or prediction failure."""


class TimeSeriesError(TerraScopeError):
    """Time-series cube building or analysis failure."""


class ProjectStateError(TerraScopeError):
    """Project state load / save / migration failure."""


class CancelledError(TerraScopeError):
    """User cancelled a running task."""
