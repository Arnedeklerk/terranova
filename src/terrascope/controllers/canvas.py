"""Controller for canvas-related bridge actions.

Exposes ``canvas.bbox`` — read the QGIS map canvas's current extent,
project it to WGS84, and return ``[west, south, east, north]``.  Called by
the React Catalogue Search panel's "Use canvas extent" button.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass


def bbox(_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canvas extent in WGS84 as ``{"bbox": [west, south, east, north]}``."""
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
    )
    from qgis.utils import iface

    if iface is None:
        raise RuntimeError(
            "QGIS iface is not available — canvas.bbox can only be called "
            "from inside QGIS."
        )

    canvas = iface.mapCanvas()
    extent = canvas.extent()
    src_crs = canvas.mapSettings().destinationCrs()
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    if src_crs.authid() == "EPSG:4326":
        wgs_extent = extent
    else:
        xform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
        wgs_extent = xform.transformBoundingBox(extent)

    west = wgs_extent.xMinimum()
    south = wgs_extent.yMinimum()
    east = wgs_extent.xMaximum()
    north = wgs_extent.yMaximum()

    # Refuse to return garbage if the project lacks a CRS or the extent
    # comes back invalid.
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(
            f"Canvas extent ({west:.3f}, {south:.3f}, {east:.3f}, {north:.3f}) "
            "isn't a valid WGS84 bbox.  Set a project CRS "
            "(Project → Properties → CRS) and try again."
        )

    return {"bbox": [west, south, east, north]}
