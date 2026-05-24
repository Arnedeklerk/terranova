"""Terranova — modern semi-automatic classification for QGIS.

This module exposes the QGIS plugin entry-point, ``classFactory``.  All heavier
imports (Qt, qfluentwidgets, QtWebEngine) are deferred to :mod:`terranova.plugin`
so that simply importing the package — for example during ``pytest`` collection
of the pure-Python ``core`` layer — does not require a QGIS runtime.
"""

from __future__ import annotations

from .version import __version__

__all__ = ["__version__", "classFactory"]


def classFactory(iface):  # type: ignore[no-untyped-def]
    """QGIS plugin entry point.

    QGIS calls ``classFactory(iface)`` once when the plugin is loaded.  The
    returned object must implement ``initGui()`` and ``unload()``.
    """
    # Deferred import so that ``import terranova`` from non-QGIS contexts
    # (CI, headless tests of the ``core`` layer) does not fail.
    from .plugin import TerranovaPlugin

    return TerranovaPlugin(iface)
