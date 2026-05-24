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
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")

    raw = (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())
    src_label = src_crs.authid() or src_crs.description() or "<unknown>"

    if not src_crs.isValid():
        raise ValueError(
            "Canvas has no valid CRS.  Set one via Project → Properties → CRS "
            "and try again."
        )

    if src_crs.authid() == "EPSG:4326":
        wgs_extent = extent
    else:
        xform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
        # Ask the transform to detect antimeridian wrap if the binding
        # supports the keyword.  PyQt5/older builds reject it; fall
        # back to the positional form and we'll catch wrap below.
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
