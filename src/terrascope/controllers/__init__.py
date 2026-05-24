"""Controllers — thin adapters between Qt UI / web bridge and pure-Python core.

A controller's job is:

1. Validate the inbound message (Pydantic).
2. Convert QGIS objects (layers, paths) into pure-Python inputs.
3. Spawn a :class:`QgsTask` (or run synchronously for cheap work).
4. On completion, register results back with :class:`QgsProject`.

Controllers must keep all heavy / blocking work off the GUI thread.
"""

from __future__ import annotations

from .dispatch import Controllers

__all__ = ["Controllers"]
