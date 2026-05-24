"""Small utilities — colormaps, raster I/O helpers, etc.

This module re-exports the most commonly used helpers from sub-modules so
callers can write ``from terranova.core.utils import safe_filename`` without
hunting for the right sub-package.
"""

from __future__ import annotations

from .bbox import area_deg2, buffer, intersection, intersects, to_crs
from .colormap import get_cmap, name_for
from .feature_flags import get as flag_get
from .feature_flags import is_enabled as flag_is_enabled
from .hashing import file_hash, short_hash
from .logging import error, info, log, scrub, set_qgis_sink, warning
from .naming import layer_display_name, safe_filename, unique_path
from .parallel import map_chunks
from .progress import ProgressReporter
from .timing import humanise_duration, timed

__all__ = [
    "ProgressReporter",
    "area_deg2",
    "buffer",
    "error",
    "file_hash",
    "flag_get",
    "flag_is_enabled",
    "get_cmap",
    "humanise_duration",
    "info",
    "intersection",
    "intersects",
    "layer_display_name",
    "log",
    "map_chunks",
    "name_for",
    "safe_filename",
    "scrub",
    "set_qgis_sink",
    "short_hash",
    "timed",
    "to_crs",
    "unique_path",
    "warning",
]
