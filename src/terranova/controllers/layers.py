"""Bridge actions for enumerating QGIS layers + their fields.

Used by the React panels to populate raster / vector pickers.  Returns
plain JSON so the bridge can serialise.
"""

from __future__ import annotations

from typing import Any


def list_rasters(_payload: dict[str, Any]) -> dict[str, Any]:
    from qgis.core import QgsProject, QgsRasterLayer

    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsRasterLayer):
            layers.append({"name": layer.name(), "source": layer.source()})
    return {"layers": layers}


def list_vectors(_payload: dict[str, Any]) -> dict[str, Any]:
    from qgis.core import QgsProject, QgsVectorLayer

    layers = []
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer):
            layers.append({"name": layer.name(), "source": layer.source()})
    return {"layers": layers}


def fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the field names of a vector layer identified by ``path``."""
    from qgis.core import QgsProject, QgsVectorLayer

    path = payload.get("path", "")
    if not path:
        return {"fields": []}
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.source() == path:
            return {"fields": [f.name() for f in layer.fields()]}
    return {"fields": []}
