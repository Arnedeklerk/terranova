"""Domain-layer exceptions.

Used so callers can ``except TerranovaError`` to catch anything raised by the
plugin's own code without also swallowing unrelated ``ValueError`` /
``RuntimeError`` from dependencies.
"""

from __future__ import annotations


class TerranovaError(Exception):
    """Base class for every Terranova-defined exception."""


class CatalogError(TerranovaError):
    """STAC search / OAuth / download failure."""


class CloudMaskError(TerranovaError):
    """Cloud masking failed (model load / inference)."""


class ClassificationError(TerranovaError):
    """Classification training or prediction failure."""


class TimeSeriesError(TerranovaError):
    """Time-series cube building or analysis failure."""


class ProjectStateError(TerranovaError):
    """Project state load / save / migration failure."""


class CancelledError(TerranovaError):
    """User cancelled a running task."""
