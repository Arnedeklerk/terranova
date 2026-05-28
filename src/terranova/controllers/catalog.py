"""Catalogue-search + download controller.

``catalog.search``  — sync; returns items as JSON.
``catalog.download`` — long-running; starts a QgsTask, returns ``{job_id}``.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from ..core.catalog import stac
from ..core.models import CatalogSearch, STACEndpoint
from . import _keepalive


def search(payload: dict[str, Any]) -> dict[str, Any]:
    """Handle ``catalog.search``.  Returns ``{items: [...], count: N}``."""
    cfg = CatalogSearch.model_validate(payload)
    client = _open_client(cfg.endpoint)
    bbox = cfg.bbox.as_tuple()
    dt_range = cfg.datetime.as_stac()
    _log_search(cfg, bbox, dt_range)
    items = list(
        stac.search_s2_l2a(
            client,
            bbox=bbox,
            datetime=dt_range,
            max_cloud=cfg.max_cloud,
            limit=cfg.limit,
        )
    )
    _log_search_result(cfg, bbox, dt_range, len(items))
    return {
        "items": [
            {
                "id": it.id,
                "datetime": str(it.datetime),
                "cloud": it.properties.get("eo:cloud_cover"),
                "platform": it.properties.get("platform"),
                # bbox + geometry let the React side ask QGIS to draw a
                # preview footprint on the map without a second round trip.
                "bbox": list(it.bbox) if it.bbox else None,
                "geometry": it.geometry,
            }
            for it in items
        ],
        "count": len(items),
    }


def _log_search(cfg: CatalogSearch, bbox: tuple, dt_range: str) -> None:
    """Mirror every search to QGIS log so users can self-diagnose 0-item runs."""
    try:
        from qgis.core import Qgis, QgsMessageLog

        QgsMessageLog.logMessage(
            f"catalog.search: endpoint={cfg.endpoint.value} "
            f"bbox={bbox} datetime={dt_range} max_cloud={cfg.max_cloud}% "
            f"limit={cfg.limit}",
            "Terranova",
            Qgis.MessageLevel.Info,
        )
    except Exception:  # noqa: BLE001
        pass


def _log_search_result(
    cfg: CatalogSearch, bbox: tuple, dt_range: str, n: int
) -> None:
    try:
        from qgis.core import Qgis, QgsMessageLog

        if n == 0:
            # 0 items is almost always a user-config problem — give them
            # something concrete to compare against.  Common causes:
            # AOI in ocean, dates outside any acquisition window, cloud
            # cover at 0%, NW/SE corners swapped.
            west, south, east, north = bbox
            issues = []
            if west >= east:
                issues.append("west >= east (NW/SE swapped?)")
            if south >= north:
                issues.append("south >= north (NW/SE swapped?)")
            if cfg.max_cloud == 0:
                issues.append("max_cloud is 0% — try raising it")
            hint = ("  Issues: " + ", ".join(issues)) if issues else ""
            QgsMessageLog.logMessage(
                f"catalog.search returned 0 items.  bbox={bbox} "
                f"datetime={dt_range}{hint}",
                "Terranova",
                Qgis.MessageLevel.Warning,
            )
        else:
            QgsMessageLog.logMessage(
                f"catalog.search returned {n} items.",
                "Terranova",
                Qgis.MessageLevel.Info,
            )
    except Exception:  # noqa: BLE001
        pass


def composite(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a multi-item composite job.  Returns ``{job_id}`` immediately.

    Loads every item_id supplied as a lazy cube via odc.stac.load,
    reduces over the time dimension with the chosen method (``mean``
    or ``median``), and writes the result as a Cloud-Optimised
    GeoTIFF.  Optional AOI clip mirrors the single-item download path.
    """
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        endpoint = STACEndpoint(payload["endpoint"])
        collection = str(payload["collection"])
        item_ids = list(payload["item_ids"])
        if len(item_ids) < 2:
            raise ValueError("composite needs at least 2 items")
        bbox = payload["bbox"]
        out_path = Path(payload["out_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    method = str(payload.get("method", "median")).lower()
    if method not in {"mean", "median"}:
        raise ValueError(
            f"unknown composite method: {method!r} (expected 'mean' or 'median')"
        )

    task = _build_composite_task(
        job_id=job_id,
        endpoint=endpoint,
        collection=collection,
        item_ids=item_ids,
        bbox=(
            float(bbox["west"]),
            float(bbox["south"]),
            float(bbox["east"]),
            float(bbox["north"]),
        ),
        bands=list(payload.get("bands") or ["red", "green", "blue", "nir"]),
        resolution=int(payload.get("resolution", 10)),
        out_path=out_path,
        mask_to_aoi=bool(payload.get("mask_to_aoi", False)),
        method=method,
    )
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def download(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a single-item download.  Returns ``{job_id}`` immediately."""
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        endpoint = STACEndpoint(payload["endpoint"])
        collection = str(payload["collection"])
        item_id = str(payload["item_id"])
        bbox = payload["bbox"]
        out_path = Path(payload["out_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    task = _build_download_task(
        job_id=job_id,
        endpoint=endpoint,
        collection=collection,
        item_id=item_id,
        bbox=(
            float(bbox["west"]),
            float(bbox["south"]),
            float(bbox["east"]),
            float(bbox["north"]),
        ),
        bands=list(payload.get("bands") or ["red", "green", "blue", "nir"]),
        resolution=int(payload.get("resolution", 10)),
        out_path=out_path,
        # Default OFF — clipping silently was confusing.  The UI's
        # "Mask to AOI" toggle in the map header sets this.
        mask_to_aoi=bool(payload.get("mask_to_aoi", False)),
    )
    # Pin the Python reference BEFORE addTask — taskManager keeps only a
    # C++ side reference, so without this the QgsTask is garbage-collected
    # before its run() executes and the job vanishes silently.
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_download_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _DownloadJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"Terranova: download {kwargs['item_id']}", QgsTask.CanCancel
            )
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.result_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_download(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _DownloadJobTask()


def _do_download(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    # Emit the first heartbeat BEFORE any heavy import so the user sees that
    # the task actually started.  The odc.stac + rioxarray imports can take
    # several seconds on first run; without this the bar sits at 0% with no
    # status text and looks frozen.
    try:
        _emit(task, 1, "Starting download…")
    except Exception:  # noqa: BLE001 — last-ditch
        QgsMessageLog.logMessage(
            "Download task started but couldn't emit progress event — "
            "bridge may be disconnected.  Result will still land in the layer "
            "panel when done.",
            "Terranova",
            Qgis.MessageLevel.Warning,
        )

    try:
        _emit(task, 2, "Loading geospatial libraries…")
        import odc.stac
        import rioxarray  # noqa: F401  (registers .rio accessor)

        _emit(task, 5, f"Refetching item {task.item_id} from STAC…")
        client = _open_client(task.endpoint)
        if task.isCanceled():
            return False

        # Planetary Computer's STAC API rejects id-only searches with
        # "collection is required" — pass collections= explicitly.  Earth
        # Search and CDSE both accept it too, so it's safe everywhere.
        items = list(
            client.search(
                ids=[task.item_id],
                collections=[task.collection],
                max_items=1,
            ).item_collection()
        )
        if not items:
            raise RuntimeError(
                f"could not refetch item {task.item_id!r} from collection "
                f"{task.collection!r} on {task.endpoint.value}"
            )
        _emit(task, 20, f"Item resolved.  Bands: {', '.join(task.bands)}")
        if task.isCanceled():
            return False

        _emit(task, 30, "Reading band manifests + signing URLs…")
        cube = odc.stac.load(
            items,
            bands=task.bands,
            resolution=task.resolution,
        ).isel(time=0)
        if task.isCanceled():
            return False

        if task.mask_to_aoi:
            _emit(task, 50, "Clipping to AOI…")
            cube = cube.rio.clip_box(*task.bbox, crs="EPSG:4326")
            if task.isCanceled():
                return False
        else:
            # Full-scene mode.  The pixel count can be ~10× the masked
            # version; surface that in the status line so the user isn't
            # surprised when the write step takes longer / produces a
            # much larger GeoTIFF.
            _emit(
                task,
                50,
                "Mask to AOI is OFF — downloading the full scene tile "
                "(this will be a much larger file).",
            )

        _emit(task, 70, f"Downloading pixels + writing {task.out_path.name}…")
        task.out_path.parent.mkdir(parents=True, exist_ok=True)
        cube.rio.to_raster(str(task.out_path), compress="deflate", tiled=True)
        task.result_path = task.out_path
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Download failed: {exc!r}", "Terranova", Qgis.MessageLevel.Critical
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    try:
        if ok and task.result_path is not None:
            push_event(
                {
                    "type": "task.complete",
                    "job_id": task.job_id,
                    "result": {"output_path": str(task.result_path)},
                }
            )
            try:
                from qgis.core import QgsProject, QgsRasterLayer

                layer = QgsRasterLayer(str(task.result_path), task.result_path.stem)
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
        # Drop the strong reference held in _keepalive so the QgsTask can
        # be garbage-collected now that QGIS is done with it.
        _keepalive.release(task.job_id)


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


# --------------------------------------------------------------------------- #
def _open_client(endpoint: STACEndpoint):  # type: ignore[no-untyped-def]
    if endpoint is STACEndpoint.PLANETARY_COMPUTER:
        return stac.open_planetary_computer()
    if endpoint is STACEndpoint.EARTH_SEARCH:
        return stac.open_earth_search()
    if endpoint is STACEndpoint.CDSE:
        return stac.open_cdse()
    raise ValueError(f"unknown endpoint: {endpoint!r}")


# --------------------------------------------------------------------------- #
# Composite (multi-item temporal reduction)                                   #
# --------------------------------------------------------------------------- #
def _build_composite_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _CompositeJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"Terranova: composite {len(kwargs['item_ids'])} scenes",
                QgsTask.CanCancel,
            )
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.result_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_composite(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _CompositeJobTask()


def _do_composite(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        _emit(task, 1, "Starting composite…")
    except Exception:  # noqa: BLE001
        QgsMessageLog.logMessage(
            "Composite task started but couldn't emit progress event.",
            "Terranova",
            Qgis.MessageLevel.Warning,
        )

    try:
        _emit(task, 2, "Loading geospatial libraries…")
        import odc.stac
        import rioxarray  # noqa: F401  — registers .rio accessor

        _emit(
            task,
            5,
            f"Refetching {len(task.item_ids)} items from STAC…",
        )
        client = _open_client(task.endpoint)
        if task.isCanceled():
            return False

        # One bulk id-search, not N round-trips — every STAC server we
        # target accepts the `ids` filter as a list.
        items = list(
            client.search(
                ids=list(task.item_ids),
                collections=[task.collection],
                max_items=len(task.item_ids),
            ).item_collection()
        )
        if len(items) < 2:
            raise RuntimeError(
                f"Resolved only {len(items)} item(s) from "
                f"{len(task.item_ids)} ids — need at least 2 for a composite."
            )
        _emit(
            task,
            20,
            f"Resolved {len(items)} items.  Bands: {', '.join(task.bands)}",
        )
        if task.isCanceled():
            return False

        _emit(task, 30, "Loading lazy cube + signing asset URLs…")
        cube = odc.stac.load(
            items,
            bands=task.bands,
            resolution=task.resolution,
        )
        if task.isCanceled():
            return False

        if task.mask_to_aoi:
            _emit(task, 45, "Clipping cube to AOI…")
            cube = cube.rio.clip_box(*task.bbox, crs="EPSG:4326")
        else:
            _emit(
                task,
                45,
                "Mask to AOI is OFF — compositing the full scene footprint "
                "(larger output GeoTIFF).",
            )
        if task.isCanceled():
            return False

        _emit(task, 55, f"Reducing time dimension with {task.method}…")
        # Cast to float32 BEFORE reducing — Sentinel-2 reflectance is
        # int16 with nodata=0; mean/median on the integer path zero-biases.
        cube_f = cube.astype("float32")
        # 0 -> NaN so the reduction ignores nodata pixels instead of
        # averaging them in.
        cube_f = cube_f.where(cube_f != 0)
        if task.method == "mean":
            composite = cube_f.mean(dim="time", skipna=True)
        else:
            composite = cube_f.median(dim="time", skipna=True)
        # Back to int16 for a sensibly-sized COG.  NaNs become 0 (nodata).
        composite = composite.fillna(0).astype("int16")
        if task.isCanceled():
            return False

        _emit(task, 75, f"Writing {task.out_path.name}…")
        task.out_path.parent.mkdir(parents=True, exist_ok=True)
        composite.rio.to_raster(
            str(task.out_path),
            compress="deflate",
            tiled=True,
        )
        task.result_path = task.out_path
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Composite failed: {exc!r}",
            "Terranova",
            Qgis.MessageLevel.Critical,
        )
        return False
