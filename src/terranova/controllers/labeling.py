"""Interactive point-by-point validation labelling.

The Accuracy panel generates validation points; this controller drives
the next step — stepping through each point, panning the QGIS canvas
to it, dropping a highlight marker, and writing the user's chosen
truth class back into the GeoPackage in place.

Bridge actions:

- ``accuracy.label.start``     — load features + class codes
- ``accuracy.label.update``    — write truth to one feature
- ``accuracy.label.pan_to``    — pan canvas + drop marker at a coord
- ``accuracy.label.clear``     — remove the marker (called on exit)

State: only the rubber-band marker layer persists between calls (module
level).  Everything else lives in the GeoPackage on disk so a user can
walk away mid-session and resume.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_marker_band: Any = None  # active QgsRubberBand, if any


# --------------------------------------------------------------------------- #
# Load + write                                                                #
# --------------------------------------------------------------------------- #
def start(payload: dict[str, Any]) -> dict[str, Any]:
    """Return every point's id/coords/predicted/truth + the class set.

    Payload:
      - ``path`` (required): validation GeoPackage path.
      - ``raster_path`` (optional): if provided, the unique class codes
        come from the raster — more accurate than deriving from the
        points file alone, which only sees classes that landed on a
        sampled pixel.
    """
    from osgeo import ogr

    path = str(payload.get("path", ""))
    if not path:
        raise ValueError("missing path")

    ds = ogr.Open(path)
    if ds is None:
        raise RuntimeError(f"could not open: {path}")
    layer = ds.GetLayer(0)

    # Capture the layer's CRS so the pan_to action can project correctly.
    src_crs_id = "EPSG:4326"
    srs = layer.GetSpatialRef()
    if srs is not None:
        try:
            srs.AutoIdentifyEPSG()
            code = srs.GetAuthorityCode(None)
            if code:
                src_crs_id = f"EPSG:{code}"
        except Exception:  # noqa: BLE001
            pass

    features: list[dict[str, Any]] = []
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None or geom.GetGeometryType() != ogr.wkbPoint:
            continue
        features.append(
            {
                "fid": int(feat.GetFID()),
                "x": float(geom.GetX()),
                "y": float(geom.GetY()),
                "predicted": int(feat.GetFieldAsInteger("predicted")),
                "truth": int(feat.GetFieldAsInteger("truth")),
                "note": feat.GetFieldAsString("note") or "",
            }
        )
    ds = None  # close

    if not features:
        raise RuntimeError(
            "No point features in the picked GeoPackage — generate a "
            "validation set first."
        )

    classes = _class_codes(payload.get("raster_path"), features)

    return {
        "src_crs": src_crs_id,
        "features": features,
        "classes": classes,
    }


def update(payload: dict[str, Any]) -> dict[str, Any]:
    """Write the truth (and optionally note) for one feature in place."""
    from osgeo import ogr

    path = str(payload["path"])
    fid = int(payload["fid"])
    truth = int(payload.get("truth", 0))
    note = payload.get("note")

    ds = ogr.Open(path, 1)  # 1 = update
    if ds is None:
        raise RuntimeError(f"could not open for write: {path}")
    layer = ds.GetLayer(0)
    feat = layer.GetFeature(fid)
    if feat is None:
        raise RuntimeError(f"no feature with FID {fid}")
    feat.SetField("truth", truth)
    if note is not None:
        feat.SetField("note", str(note))
    layer.SetFeature(feat)
    feat = None
    ds = None  # close + flush
    return {"ok": True}


def _class_codes(
    raster_path: Any, features: list[dict[str, Any]]
) -> list[int]:
    """Pick the source for the class-code picker dropdown.

    Prefer the raster's unique values (more complete), fall back to the
    distinct `predicted` values present in the points.
    """
    if raster_path:
        try:
            import numpy as np
            import rasterio

            with rasterio.open(str(raster_path)) as src:
                arr = src.read(1)
                nd = {0}
                if src.nodata is not None:
                    nd.add(int(src.nodata))
                vals = [int(c) for c in np.unique(arr) if int(c) not in nd]
                if vals:
                    return sorted(vals)
        except Exception:  # noqa: BLE001
            pass
    return sorted({int(f["predicted"]) for f in features if f["predicted"]})


# --------------------------------------------------------------------------- #
# Canvas pan + marker                                                         #
# --------------------------------------------------------------------------- #
def pan_to(payload: dict[str, Any]) -> dict[str, Any]:
    """Pan the canvas to ``(x, y)`` in ``crs`` and drop the highlight marker.

    Does NOT change zoom level — the user picks a sensible zoom once, then
    stepping through points just re-centres each time.  Trying to auto-fit
    a single point requires guessing the "right" scale and gets in the
    way.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsPointXY,
        QgsProject,
        QgsWkbTypes,
    )
    from qgis.gui import QgsRubberBand
    from qgis.PyQt.QtGui import QColor
    from qgis.utils import iface

    global _marker_band

    if iface is None:
        raise RuntimeError("iface unavailable")

    x = float(payload["x"])
    y = float(payload["y"])
    src_crs_id = str(payload.get("crs", "EPSG:4326"))

    canvas = iface.mapCanvas()
    dst_crs = canvas.mapSettings().destinationCrs()
    src_crs = QgsCoordinateReferenceSystem(src_crs_id)
    if (
        src_crs.isValid()
        and dst_crs.isValid()
        and src_crs.authid() != dst_crs.authid()
    ):
        xform = QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())
        pt = xform.transform(QgsPointXY(x, y))
    else:
        pt = QgsPointXY(x, y)

    canvas.setCenter(pt)
    canvas.refresh()

    if _marker_band is None:
        _marker_band = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        _marker_band.setColor(QColor(255, 80, 80))
        _marker_band.setFillColor(QColor(255, 80, 80, 120))
        _marker_band.setIconSize(16)
        _marker_band.setWidth(3)
        try:
            # Cross icon — easier to see against the imagery than a dot.
            _marker_band.setIcon(QgsRubberBand.ICON_CROSS)
        except Exception:  # noqa: BLE001
            pass
    _marker_band.reset(QgsWkbTypes.PointGeometry)
    _marker_band.addPoint(pt, True)
    return {"ok": True}


def clear(_payload: dict[str, Any]) -> dict[str, Any]:
    """Remove the marker — called when the user exits labelling mode."""
    from qgis.core import QgsWkbTypes

    global _marker_band
    if _marker_band is not None:
        try:
            _marker_band.reset(QgsWkbTypes.PointGeometry)
        except Exception:  # noqa: BLE001
            pass
        _marker_band = None
    return {"ok": True}
