"""Controller for canvas-related bridge actions.

Exposes:

- ``canvas.bbox`` — read the QGIS map canvas's current extent,
  project it to WGS84, and return ``[west, south, east, north]``.
  Used by the Catalogue Search panel's "Use canvas extent" button.

- ``catalog.preview_footprint`` — drop a temporary outlined polygon on
  the canvas showing where a selected STAC item lives, so users don't
  blindly download a scene whose actual coverage is a thin sliver of
  their AOI.  Replaces the previous preview, doesn't pollute the layer
  panel with stale shapes.

- ``catalog.clear_preview`` — remove the preview overlay.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    pass

# Module-level handle to the currently-displayed preview layer so we can
# replace it on every preview-footprint call and remove it on clear.
# QgsProject would otherwise accumulate dozens of stale "preview" layers
# as the user clicks through search results.
_preview_layer_id: str | None = None


def bbox(_payload: dict[str, Any]) -> dict[str, Any]:
    """Return the canvas extent in WGS84 as ``{"bbox": [west, south, east, north]}``.

    Behaviour notes the UI's "Use canvas extent" button inherits:

    - The bbox is the *full* canvas viewport, including any padding the
      window's aspect ratio forces.  If your QGIS window is wide-screen
      the bbox extends further left/right than the layer you're looking
      at — that's correct, not a bug.
    - ``transformBoundingBox`` samples the source rectangle's edges
      before projecting, so warped projections (Lambert, polar Web
      Mercator) give a sensible bbox rather than just the four corners.
    - Antimeridian-crossing extents (around longitude 180°) are detected
      and reported as an error rather than returned as nonsense.
    - The source CRS, raw extent, and projected bbox are logged on every
      call (TerraScope tab) so 'why is the AOI box different from what
      I see?' is one log line away from an answer.
    """
    from qgis.core import (
        Qgis,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsMessageLog,
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
    # OGC:CRS84 is WGS84 with EXPLICIT lon,lat axis order.  Using EPSG:4326
    # here is a trap on QGIS 4 / PROJ 9: that CRS has lat,lon axis order
    # and the resulting QgsRectangle stores latitudes in x.  Symptom:
    # "the latitude values are right but the longitudes are wrong."
    wgs84 = QgsCoordinateReferenceSystem("OGC:CRS84")
    if not wgs84.isValid():
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    raw = (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())
    src_label = src_crs.authid() or src_crs.description() or "<unknown>"

    if not src_crs.isValid():
        raise ValueError(
            "Canvas has no valid CRS.  Set one via Project → Properties → CRS "
            "and try again."
        )

    # Always transform through CRS84 — even when the source IS EPSG:4326,
    # because in 4326's canonical axis order the QgsRectangle stores
    # latitude in x.  Going through CRS84 normalises axis order to lon,lat.
    xform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
    # Ask the transform to detect antimeridian wrap if the binding
    # supports the keyword.  PyQt5/older builds reject it; fall back to
    # the positional form and we'll catch wrap below.
    try:
        wgs_extent = xform.transformBoundingBox(extent, handle180Crossover=True)
    except TypeError:
        wgs_extent = xform.transformBoundingBox(extent)

    west = wgs_extent.xMinimum()
    south = wgs_extent.yMinimum()
    east = wgs_extent.xMaximum()
    north = wgs_extent.yMaximum()

    QgsMessageLog.logMessage(
        f"canvas.bbox: src_crs={src_label} raw_extent={raw} "
        f"-> wgs84=({west:.6f}, {south:.6f}, {east:.6f}, {north:.6f})",
        "TerraScope",
        Qgis.MessageLevel.Info,
    )

    # Antimeridian crossing — `transformBoundingBox` can return west>east
    # in that case.  Don't return garbage; tell the user clearly.
    if west >= east:
        raise ValueError(
            f"Canvas extent crosses the antimeridian (west={west:.3f}, "
            f"east={east:.3f}).  STAC catalogues can't accept that as a "
            "single bbox — pan so the area sits inside one hemisphere "
            "and try again."
        )

    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(
            f"Canvas extent projects to ({west:.3f}, {south:.3f}, "
            f"{east:.3f}, {north:.3f}) which isn't a valid WGS84 bbox.  "
            f"Source CRS was {src_label}.  Try zooming in — projections "
            "near the poles or past the Web Mercator limits can produce "
            "invalid results."
        )

    return {"bbox": [west, south, east, north]}


# --------------------------------------------------------------------------- #
# Footprint preview overlay                                                   #
# --------------------------------------------------------------------------- #
def preview_footprint(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop a temporary outlined polygon on the canvas for a STAC item.

    Payload (one of ``geometry`` or ``bbox`` is required):

    - ``geometry``: GeoJSON polygon/multipolygon in WGS84 lon,lat.
    - ``bbox``: ``[west, south, east, north]`` in WGS84.
    - ``item_id`` (optional): used as the layer name so users can tell
      which scene is highlighted if they have several previews stacked.

    The previous preview, if any, is removed before the new one is added —
    we never accumulate stale preview layers in the project tree.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsFeature,
        QgsGeometry,
        QgsProject,
        QgsVectorLayer,
    )

    global _preview_layer_id

    geometry = payload.get("geometry")
    bbox_xy = payload.get("bbox")
    if geometry is None and bbox_xy is None:
        raise ValueError("preview_footprint needs either 'geometry' or 'bbox'")

    if geometry is not None:
        # GeoJSON straight into QGIS.  QgsGeometry.fromJson handles
        # Polygon and MultiPolygon (STAC footprints can be either).
        geo_str = geometry if isinstance(geometry, str) else json.dumps(geometry)
        qgs_geom = QgsGeometry.fromJson(geo_str)
        if qgs_geom is None or qgs_geom.isEmpty():
            raise ValueError(
                f"could not parse footprint geometry: {geo_str[:120]}…"
            )
    else:
        west, south, east, north = (float(v) for v in bbox_xy)
        qgs_geom = QgsGeometry.fromWkt(
            f"POLYGON(({west} {south}, {east} {south}, "
            f"{east} {north}, {west} {north}, {west} {south}))"
        )
    if qgs_geom.isEmpty():
        raise ValueError("preview_footprint received an empty geometry")

    item_id = str(payload.get("item_id") or "footprint")
    layer_name = f"TerraScope preview: {item_id}"

    # Replace any existing preview layer.
    _remove_preview_layer()

    # In-memory layer in WGS84 — QGIS will reproject for display.
    layer = QgsVectorLayer("Polygon?crs=EPSG:4326", layer_name, "memory")
    layer.setCustomProperty("terrascope.preview", "1")
    provider = layer.dataProvider()
    feat = QgsFeature()
    feat.setGeometry(qgs_geom)
    provider.addFeatures([feat])
    layer.updateExtents()

    # Style: cyan-blue outline, no fill, 2px line.  Visible on both light
    # and dark basemaps; won't obscure the imagery underneath.
    _style_preview(layer)

    QgsProject.instance().addMapLayer(layer)
    _preview_layer_id = layer.id()

    # Zoom is intentionally NOT changed — users hate that.  The footprint
    # is now visible; they can pan/zoom themselves if they want a closer
    # look at the relationship between their AOI and the scene coverage.
    return {"layer_id": layer.id(), "name": layer_name}


def clear_preview(_payload: dict[str, Any]) -> dict[str, Any]:
    """Remove the current preview overlay, if any."""
    removed = _remove_preview_layer()
    return {"removed": removed}


def _remove_preview_layer() -> bool:
    """Drop the tracked preview layer from the project.  Idempotent."""
    from qgis.core import QgsProject

    global _preview_layer_id
    if _preview_layer_id is None:
        return False
    try:
        QgsProject.instance().removeMapLayer(_preview_layer_id)
    except Exception:  # noqa: BLE001 — layer may have been removed by user
        pass
    _preview_layer_id = None
    return True


def _style_preview(layer: Any) -> None:
    """Cyan-blue outline, no fill — visible on any basemap."""
    from qgis.core import QgsSimpleFillSymbolLayer, QgsSymbol
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtGui import QColor

    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    if symbol.symbolLayerCount() > 0:
        symbol.deleteSymbolLayer(0)
    fill = QgsSimpleFillSymbolLayer()
    fill.setColor(QColor(0, 0, 0, 0))  # transparent fill
    fill.setStrokeColor(QColor(64, 196, 255))  # cyan-blue
    fill.setStrokeWidth(0.6)
    try:
        fill.setStrokeStyle(Qt.PenStyle.SolidLine)
    except AttributeError:  # PyQt5
        fill.setStrokeStyle(Qt.SolidLine)
    symbol.appendSymbolLayer(fill)
    try:
        from qgis.core import QgsSingleSymbolRenderer

        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    except Exception:  # noqa: BLE001 — older QGIS APIs
        pass
    layer.triggerRepaint()


