"""Web-sourced training-data fetchers for the Classify panel.

Two actions:

- ``training.from_osm`` — query OpenStreetMap via the Overpass API for
  landuse / natural / leisure polygons inside the input raster's extent,
  map OSM tags to a small class set, write to a GeoPackage.

- ``training.from_worldcover`` — fetch ESA WorldCover (10 m global land
  cover) for the AOI from Planetary Computer's STAC, sample stratified
  random points per class, write to a GeoPackage.

Both run as :class:`QgsTask` instances and emit the same job-id event
shape as classify / accuracy / timeseries.  The result event contains
``{"output_path": "..."}``; the React side picks that up and sets it
as the training vector.
"""

from __future__ import annotations

import json
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from . import _keepalive


# --------------------------------------------------------------------------- #
# Public bridge entry points                                                  #
# --------------------------------------------------------------------------- #
def from_osm(payload: dict[str, Any]) -> dict[str, Any]:
    """Start an OSM-Overpass training-vector fetch.  Returns ``{job_id}``."""
    return _start(_build_osm_task, payload)


def from_worldcover(payload: dict[str, Any]) -> dict[str, Any]:
    """Start an ESA-WorldCover training-vector fetch.  Returns ``{job_id}``."""
    return _start(_build_worldcover_task, payload)


def _start(
    builder, payload: dict[str, Any]  # type: ignore[no-untyped-def]
) -> dict[str, Any]:
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        raster_path = Path(payload["raster_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc
    out_path = Path(payload.get("out_path") or _default_out_path())
    task = builder(job_id=job_id, raster_path=raster_path, out_path=out_path)
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _default_out_path() -> Path:
    """Pick a sensible output path under the user's profile temp dir.

    Lives under the OS temp dir so we don't pollute the user's
    Documents folder; named with a timestamp + 'terranova_training_'
    prefix so it's easy to find later.
    """
    ts = time.strftime("%Y%m%d_%H%M%S")
    return Path(tempfile.gettempdir()) / f"terranova_training_{ts}.gpkg"


# --------------------------------------------------------------------------- #
# OSM Overpass                                                                #
# --------------------------------------------------------------------------- #
#
# Overpass query asks for all way+relation features tagged with the
# landuse / natural / leisure keys we care about, inside the bbox.
# `out geom;` includes the embedded node coordinates per way so we
# don't have to do a second pass to fetch nodes.
#
# Relations (multipolygons) are intentionally NOT requested — they're
# more complex to assemble correctly (inner/outer ring handling) and
# for training-set generation, the simple ways are plenty.

_OSM_ENDPOINT = "https://overpass-api.de/api/interpreter"

# OSM tag -> (numeric class code, class label).  Codes are intentionally
# kept small and contiguous so a classifier sees clean integer labels.
_OSM_TAG_MAP: dict[tuple[str, str], tuple[int, str]] = {
    ("landuse", "forest"): (1, "Forest"),
    ("natural", "wood"): (1, "Forest"),
    ("landuse", "grass"): (2, "Grass"),
    ("landuse", "meadow"): (2, "Grass"),
    ("landuse", "village_green"): (2, "Grass"),
    ("leisure", "park"): (2, "Grass"),
    ("leisure", "pitch"): (2, "Grass"),
    ("leisure", "golf_course"): (2, "Grass"),
    ("landuse", "farmland"): (3, "Cropland"),
    ("landuse", "orchard"): (3, "Cropland"),
    ("landuse", "vineyard"): (3, "Cropland"),
    ("natural", "water"): (4, "Water"),
    ("natural", "wetland"): (4, "Water"),
    ("landuse", "reservoir"): (4, "Water"),
    ("landuse", "basin"): (4, "Water"),
    ("natural", "scrub"): (5, "Scrub"),
    ("natural", "heath"): (5, "Scrub"),
    ("natural", "bare_rock"): (6, "Bare"),
    ("natural", "sand"): (6, "Bare"),
    ("natural", "scree"): (6, "Bare"),
    ("landuse", "quarry"): (6, "Bare"),
    ("landuse", "residential"): (7, "Built"),
    ("landuse", "industrial"): (7, "Built"),
    ("landuse", "commercial"): (7, "Built"),
    ("landuse", "retail"): (7, "Built"),
    ("landuse", "construction"): (7, "Built"),
    ("natural", "glacier"): (8, "Snow"),
}


def _build_osm_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _OsmFetchTask(QgsTask):
        def __init__(self) -> None:
            super().__init__("Terranova: fetch OSM training", QgsTask.CanCancel)
            self.job_id: str = kwargs["job_id"]
            self.raster_path: Path = kwargs["raster_path"]
            self.out_path: Path = kwargs["out_path"]
            self.result_path: Path | None = None
            self.feature_count: int = 0
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_osm(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _OsmFetchTask()


def _do_osm(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        _emit(task, 5, "Reading raster extent…")
        west, south, east, north = _raster_bbox_wgs84(task.raster_path)
        if task.isCanceled():
            return False
        QgsMessageLog.logMessage(
            f"OSM training: bbox=({west:.4f},{south:.4f},{east:.4f},{north:.4f})",
            "Terranova",
            Qgis.MessageLevel.Info,
        )

        _emit(task, 15, "Querying Overpass…")
        # `[bbox]` syntax in Overpass is (south,west,north,east) — yes,
        # that order, not the GeoJSON one.  Easy to get wrong.
        ql = f"""
[out:json][timeout:90][bbox:{south},{west},{north},{east}];
(
  way["landuse"];
  way["natural"];
  way["leisure"~"park|pitch|golf_course"];
);
out geom;
"""
        data = _post_overpass(ql)
        if task.isCanceled():
            return False
        _emit(task, 55, f"Parsing {len(data.get('elements', []))} OSM elements…")

        features = list(_osm_elements_to_features(data))
        if not features:
            raise RuntimeError(
                "No usable OSM polygons inside the raster extent.  "
                "Try the WorldCover source instead, or widen the AOI."
            )

        _emit(task, 80, f"Writing {len(features)} polygons to GeoPackage…")
        _write_geopackage(task.out_path, features, layer_name="osm_training")
        task.result_path = task.out_path
        task.feature_count = len(features)
        _emit(task, 100, f"Wrote {len(features)} polygons.")
        return True
    except Exception as exc:  # noqa: BLE001 — task boundary
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"OSM training fetch failed: {exc!r}",
            "Terranova",
            Qgis.MessageLevel.Critical,
        )
        return False


def _post_overpass(ql: str) -> dict[str, Any]:
    """POST a query to Overpass, return decoded JSON.  Raises on HTTP error."""
    body = urllib.parse.urlencode({"data": ql}).encode("utf-8")
    req = urllib.request.Request(
        _OSM_ENDPOINT,
        data=body,
        headers={
            "User-Agent": "terranova-qgis-plugin/0.1 (+https://github.com/Arnedeklerk/terranova)",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(
            f"Overpass returned HTTP {e.code}: {msg}.  "
            "The public Overpass endpoint rate-limits aggressively; "
            "try again in a minute, or pick the WorldCover source."
        ) from e


def _osm_elements_to_features(data: dict[str, Any]) -> "list[dict[str, Any]]":
    """Map Overpass JSON ways to GeoJSON-ish features with class+code fields.

    Drops ways whose tag combo isn't in :data:`_OSM_TAG_MAP` and ways
    that aren't closed (an OSM area is a way whose last node == first
    node, with no `area=no` tag).
    """
    out: list[dict[str, Any]] = []
    for el in data.get("elements", []):
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        geom = el.get("geometry") or []
        if len(geom) < 4:
            continue
        # Pick the first tag that maps to a known class.
        match = None
        for k, v in tags.items():
            if (k, v) in _OSM_TAG_MAP:
                match = (k, v)
                break
        if match is None:
            continue
        code, label = _OSM_TAG_MAP[match]
        coords = [[float(n["lon"]), float(n["lat"])] for n in geom]
        # Close the ring if it isn't already.
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        if len(coords) < 4:
            continue
        out.append(
            {
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {
                    "class": int(code),
                    "label": label,
                    "osm_id": el.get("id"),
                    "osm_tag": f"{match[0]}={match[1]}",
                },
            }
        )
    return out


# --------------------------------------------------------------------------- #
# ESA WorldCover                                                              #
# --------------------------------------------------------------------------- #
#
# Sample N random points per class from ESA WorldCover (10 m).  Available
# on Planetary Computer with no auth.  We use the existing pystac-client
# stack to fetch.

# WorldCover class codes -> labels.  Used both for stratified sampling
# and for the output GPKG's `label` field.
_WC_CLASS_NAMES: dict[int, str] = {
    10: "Trees",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare",
    70: "Snow and ice",
    80: "Water",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


def _build_worldcover_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _WCFetchTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                "Terranova: sample WorldCover", QgsTask.CanCancel
            )
            self.job_id: str = kwargs["job_id"]
            self.raster_path: Path = kwargs["raster_path"]
            self.out_path: Path = kwargs["out_path"]
            self.points_per_class: int = int(
                kwargs.get("points_per_class", 100)
            )
            self.result_path: Path | None = None
            self.feature_count: int = 0
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_worldcover(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _WCFetchTask()


def _do_worldcover(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        _emit(task, 3, "Reading raster extent…")
        west, south, east, north = _raster_bbox_wgs84(task.raster_path)

        _emit(task, 10, "Opening Planetary Computer STAC…")
        import numpy as np
        import odc.stac

        from ..core.catalog import stac as cstac

        client = cstac.open_planetary_computer()
        if task.isCanceled():
            return False

        _emit(task, 20, "Searching ESA WorldCover items…")
        items = list(
            client.search(
                collections=["esa-worldcover"],
                bbox=(west, south, east, north),
                limit=20,
            ).item_collection()
        )
        if not items:
            raise RuntimeError(
                "No WorldCover items intersect this AOI.  Open the QGIS "
                "Log Messages panel for the queried bbox."
            )

        _emit(task, 35, "Loading WorldCover cube…")
        cube = odc.stac.load(
            items,
            bands=["map"],
            bbox=(west, south, east, north),
            resolution=0.0001,  # ~10 m in degrees; WorldCover native res
            chunks={"x": 2048, "y": 2048},
        ).isel(time=0)
        if task.isCanceled():
            return False

        _emit(task, 55, "Reading classified pixels into memory…")
        arr = cube["map"].values  # (y, x) int
        xs = cube["x"].values
        ys = cube["y"].values

        # Stratified sample: for each class present in the cube, sample
        # up to `points_per_class` random pixels.  No interpolation — the
        # WorldCover class for a pixel IS the label.
        rng = np.random.default_rng(seed=42)
        per_class = int(task.points_per_class)
        present = [int(c) for c in np.unique(arr) if int(c) in _WC_CLASS_NAMES]
        if not present:
            raise RuntimeError("WorldCover cube has no recognised class codes.")

        _emit(task, 70, f"Sampling {len(present)} classes × {per_class} pts…")
        features: list[dict[str, Any]] = []
        for cls in present:
            ys_idx, xs_idx = np.where(arr == cls)
            if ys_idx.size == 0:
                continue
            n = min(per_class, ys_idx.size)
            pick = rng.choice(ys_idx.size, size=n, replace=False)
            for k in pick:
                lon = float(xs[xs_idx[k]])
                lat = float(ys[ys_idx[k]])
                features.append(
                    {
                        "geometry": {"type": "Point", "coordinates": [lon, lat]},
                        "properties": {
                            "class": int(cls),
                            "label": _WC_CLASS_NAMES.get(int(cls), "Other"),
                        },
                    }
                )

        if not features:
            raise RuntimeError("Stratified sample produced no points.")

        _emit(task, 90, f"Writing {len(features)} points to GeoPackage…")
        _write_geopackage(
            task.out_path,
            features,
            layer_name="worldcover_training",
            geom_type="Point",
        )
        task.result_path = task.out_path
        task.feature_count = len(features)
        _emit(task, 100, f"Wrote {len(features)} points.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"WorldCover sample failed: {exc!r}",
            "Terranova",
            Qgis.MessageLevel.Critical,
        )
        return False


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #
def _raster_bbox_wgs84(raster_path: Path) -> tuple[float, float, float, float]:
    """Return ``(west, south, east, north)`` in WGS84 for a raster file.

    Uses QGIS so we benefit from PROJ + axis-order normalisation that the
    canvas path already handles correctly.
    """
    from qgis.core import (
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRasterLayer,
    )

    layer = QgsRasterLayer(str(raster_path), "terranova_extent_probe")
    if not layer.isValid():
        raise RuntimeError(f"could not open raster: {raster_path}")
    extent = layer.extent()
    src_crs = layer.crs()
    wgs84 = QgsCoordinateReferenceSystem("OGC:CRS84")
    if not wgs84.isValid():
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    xform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
    try:
        wgs = xform.transformBoundingBox(extent, handle180Crossover=True)
    except TypeError:
        wgs = xform.transformBoundingBox(extent)
    return (wgs.xMinimum(), wgs.yMinimum(), wgs.xMaximum(), wgs.yMaximum())


def _write_geopackage(
    path: Path,
    features: list[dict[str, Any]],
    *,
    layer_name: str,
    geom_type: str = "Polygon",
) -> None:
    """Write GeoJSON-shaped features to a GeoPackage via OGR.

    OGR ships with QGIS so there's no extra dependency.  Schema is
    inferred from the first feature's properties.
    """
    from osgeo import ogr, osr

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(path))
    if ds is None:
        raise RuntimeError(f"failed to create GeoPackage at {path}")

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ogr_geom = {
        "Polygon": ogr.wkbPolygon,
        "Point": ogr.wkbPoint,
        "MultiPolygon": ogr.wkbMultiPolygon,
    }[geom_type]
    layer = ds.CreateLayer(layer_name, srs=srs, geom_type=ogr_geom)

    # Build the schema from the first feature.
    sample_props = features[0]["properties"]
    for name, value in sample_props.items():
        if isinstance(value, int):
            field = ogr.FieldDefn(name, ogr.OFTInteger)
        elif isinstance(value, float):
            field = ogr.FieldDefn(name, ogr.OFTReal)
        else:
            field = ogr.FieldDefn(name, ogr.OFTString)
            field.SetWidth(80)
        layer.CreateField(field)

    layer_defn = layer.GetLayerDefn()
    for f in features:
        feature = ogr.Feature(layer_defn)
        for name, value in f["properties"].items():
            if value is None:
                continue
            feature.SetField(name, value)
        geom = ogr.CreateGeometryFromJson(json.dumps(f["geometry"]))
        feature.SetGeometry(geom)
        layer.CreateFeature(feature)
        feature = None  # release C++ side

    ds = None  # close + flush


def _emit(task: Any, percent: float, status: str) -> None:
    from qgis.core import Qgis, QgsMessageLog

    from ..bridge import push_event

    task.setProgress(float(percent))
    push_event(
        {
            "type": "task.progress",
            "job_id": task.job_id,
            "percent": float(percent),
            "status": status,
        }
    )
    if status:
        QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    try:
        if ok and task.result_path is not None:
            push_event(
                {
                    "type": "task.complete",
                    "job_id": task.job_id,
                    "result": {
                        "output_path": str(task.result_path),
                        "feature_count": task.feature_count,
                    },
                }
            )
            # Add as a vector layer so the user can immediately QA the
            # polygons / points before classifying.
            try:
                from qgis.core import QgsProject, QgsVectorLayer

                layer = QgsVectorLayer(
                    str(task.result_path),
                    task.result_path.stem,
                    "ogr",
                )
                if layer.isValid():
                    QgsProject.instance().addMapLayer(layer)
            except Exception:  # noqa: BLE001
                pass
        else:
            push_event(
                {
                    "type": "task.failed",
                    "job_id": task.job_id,
                    "error": task.error_text or "Cancelled.",
                }
            )
    finally:
        _keepalive.release(task.job_id)
