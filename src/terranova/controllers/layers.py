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
    """Return the field names of a vector identified by ``path``.

    First checks loaded QGIS layers; if no match (the user picked a file
    via the Browse button rather than choosing a loaded layer), opens
    the path as a transient :class:`QgsVectorLayer` just long enough to
    read the schema.  The transient layer is GC'd as soon as we return,
    so it doesn't pollute the project tree.
    """
    from qgis.core import QgsProject, QgsVectorLayer

    path = payload.get("path", "")
    if not path:
        return {"fields": []}

    # 1) Match a loaded layer by source string.
    for layer in QgsProject.instance().mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.source() == path:
            return {"fields": [f.name() for f in layer.fields()]}

    # 2) Fall back to opening the file directly.  Name + provider are
    #    deliberately minimal — the layer never gets added to the
    #    project.  Returns empty if the file isn't a readable vector.
    layer = QgsVectorLayer(path, "terranova_field_probe", "ogr")
    if not layer.isValid():
        return {"fields": []}
    return {"fields": [f.name() for f in layer.fields()]}
