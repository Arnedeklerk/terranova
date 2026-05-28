"""Interactive point-by-point validation labelling.

The Accuracy panel generates validation points; this controller drives
the next step — stepping through each point, panning the QGIS canvas
to it, dropping a highlight marker, and writing the user's chosen
truth class back into the GeoPackage in place.

Bridge actions:

- ``accuracy.label.start``           — load features + class codes + names
- ``accuracy.label.update``          — write truth to one feature
- ``accuracy.label.set_class_names`` — persist a code -> name map
- ``accuracy.label.pan_to``          — pan canvas (optionally zoom-to-pixel)
- ``accuracy.label.clear``           — remove the marker (called on exit)

State: only the rubber-band marker layer persists between calls (module
level).  Everything else lives in the GeoPackage / sidecar JSON on disk
so a user can walk away mid-session and resume.

Class-name sidecar: a JSON next to the GeoPackage at
``<gpkg>.classes.json`` mapping code (str) -> name (str).  Optional;
if absent we just show numeric codes.
"""

from __future__ import annotations

import json
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
    skipped_types: dict[int, int] = {}
    for feat in layer:
        geom = feat.GetGeometryRef()
        if geom is None:
            continue
        if not _is_point_type(ogr, geom.GetGeometryType()):
            skipped_types[geom.GetGeometryType()] = (
                skipped_types.get(geom.GetGeometryType(), 0) + 1
            )
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
    total_features = layer.GetFeatureCount()
    ds = None  # close

    if not features:
        # Include diagnostics so we don't end up debugging another silent
        # 'no features' a year from now.
        details = []
        if total_features == 0:
            details.append("the layer is empty")
        if skipped_types:
            names = ", ".join(
                f"{ogr.GeometryTypeToName(t)} ({n})"
                for t, n in skipped_types.items()
            )
            details.append(f"skipped non-point geometries: {names}")
        suffix = f"  ({'; '.join(details)})" if details else ""
        raise RuntimeError(
            "No point features in the picked GeoPackage — generate a "
            f"validation set first.{suffix}"
        )

    classes = _class_codes(payload.get("raster_path"), features)
    class_names = _read_class_names(Path(path))

    return {
        "src_crs": src_crs_id,
        "features": features,
        "classes": classes,
        "class_names": class_names,
    }


def set_class_names(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a {code: name} map alongside the GeoPackage as a sidecar.

    Keeps names out of the GPKG schema (the .gpkg stays simple, predicted
    + truth + note) but survives across sessions for the same file.
    """
    path = Path(str(payload["path"]))
    names_raw = payload.get("names") or {}
    if not isinstance(names_raw, dict):
        raise ValueError("names must be an object {code: name}")
    # Normalise to {str: str} (JSON keys are always strings anyway).
    clean = {str(k): str(v) for k, v in names_raw.items() if str(v).strip()}
    sidecar = _names_sidecar_path(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(sidecar)}


def _names_sidecar_path(gpkg: Path) -> Path:
    return gpkg.with_suffix(gpkg.suffix + ".classes.json")


def _read_class_names(gpkg: Path) -> dict[str, str]:
    sidecar = _names_sidecar_path(gpkg)
    if not sidecar.exists():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


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

    Payload:
      - ``x``, ``y``: target coordinate in source CRS.
      - ``crs``: source CRS id (default 'EPSG:4326').
      - ``fit_zoom``: if true, zoom to ~40 pixels of the raster around
        the point so the user can actually SEE the pixel.  The classify
        flow's auto-zoom equivalent.  Subsequent calls (False) preserve
        whatever zoom the user has set.
      - ``raster_path``: needed when ``fit_zoom`` is true; we read the
        raster's pixel size to compute the zoom extent.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsPointXY,
        QgsProject,
        QgsRectangle,
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
    fit_zoom = bool(payload.get("fit_zoom", False))
    raster_path = payload.get("raster_path")

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

    if fit_zoom and raster_path:
        half = _pixel_zoom_half_extent(str(raster_path), dst_crs)
        if half is not None:
            canvas.setExtent(
                QgsRectangle(
                    pt.x() - half[0], pt.y() - half[1],
                    pt.x() + half[0], pt.y() + half[1],
                )
            )
        else:
            canvas.setCenter(pt)
    else:
        canvas.setCenter(pt)
    canvas.refresh()

    if _marker_band is None:
        _marker_band = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        # Bright cyan circle, semi-transparent fill — contrasts against
        # both light street basemaps and dark satellite imagery without
        # masking the underlying pixel like a filled cross would.
        _marker_band.setColor(QColor(64, 196, 255))
        _marker_band.setFillColor(QColor(64, 196, 255, 80))
        _marker_band.setIconSize(20)
        _marker_band.setWidth(3)
        for icon_attr in ("ICON_CIRCLE", "ICON_FULL_BOX", "ICON_BOX"):
            icon = getattr(QgsRubberBand, icon_attr, None)
            if icon is not None:
                try:
                    _marker_band.setIcon(icon)
                    break
                except Exception:  # noqa: BLE001
                    continue
    _marker_band.reset(QgsWkbTypes.PointGeometry)
    _marker_band.addPoint(pt, True)
    return {"ok": True}


def _pixel_zoom_half_extent(
    raster_path: str, dst_crs: Any
) -> tuple[float, float] | None:
    """Compute the (half-width, half-height) in canvas-CRS units that
    encloses ~40 raster pixels around a target point.

    Uses the raster's own QGIS layer for the CRS transform so we honour
    whatever PROJ context QGIS itself has.  Returns None if the raster
    can't be opened.
    """
    from qgis.core import (
        QgsCoordinateTransform,
        QgsProject,
        QgsRasterLayer,
    )

    layer = QgsRasterLayer(raster_path, "terranova_zoom_probe")
    if not layer.isValid():
        return None
    extent = layer.extent()
    if (
        layer.crs().isValid()
        and dst_crs.isValid()
        and layer.crs().authid() != dst_crs.authid()
    ):
        try:
            xform = QgsCoordinateTransform(
                layer.crs(), dst_crs, QgsProject.instance()
            )
            extent = xform.transformBoundingBox(extent)
        except Exception:  # noqa: BLE001
            return None
    try:
        pixel_w = extent.width() / max(1, layer.width())
        pixel_h = extent.height() / max(1, layer.height())
    except Exception:  # noqa: BLE001
        return None
    # ~40 pixels visible total (20 each side).  Big enough to see context,
    # small enough that a single 10-m Sentinel pixel is comfortably
    # clickable.
    return (pixel_w * 20, pixel_h * 20)


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


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def _is_point_type(ogr_mod: Any, t: int) -> bool:
    """True if ``t`` is wkbPoint or any of its Z/M/ZM variants.

    GDAL exposes Z/M point types as separate integer codes (wkbPoint25D,
    wkbPointM, wkbPointZM) — comparing the raw ``GetGeometryType()``
    against ``wkbPoint`` alone falsely rejects them.  The clean way to
    normalise is ``ogr.GT_Flatten()`` which strips the dimensionality
    flags; some older bindings don't expose it (or expose it under
    the C++ macro name ``wkbFlatten``), so we try both then fall back
    to explicit membership.
    """
    for name in ("GT_Flatten", "wkbFlatten"):
        fn = getattr(ogr_mod, name, None)
        if callable(fn):
            try:
                return int(fn(t)) == int(ogr_mod.wkbPoint)
            except Exception:  # noqa: BLE001
                break
    # Fallback: explicit set membership.  Every Z/M variant we care about.
    point_codes = {int(ogr_mod.wkbPoint)}
    for name in ("wkbPoint25D", "wkbPointM", "wkbPointZM"):
        val = getattr(ogr_mod, name, None)
        if val is not None:
            point_codes.add(int(val))
    return int(t) in point_codes
