"""``terranova`` CLI — runs the pure-Python core layer outside QGIS.

Lets users batch-classify scenes, build cubes, and run NDVI/etc from CI or a
shell.  The CLI must not import from ``qgis.*`` — that is what allows it to
run on a headless server.
"""

from __future__ import annotations

from .main import main

__all__ = ["main"]
