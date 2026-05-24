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
    items = list(
        stac.search_s2_l2a(
            client,
            bbox=bbox,
            datetime=cfg.datetime.as_stac(),
            max_cloud=cfg.max_cloud,
            limit=cfg.limit,
        )
    )
    return {
        "items": [
            {
                "id": it.id,
                "datetime": str(it.datetime),
                "cloud": it.properties.get("eo:cloud_cover"),
                "platform": it.properties.get("platform"),
            }
            for it in items
        ],
        "count": len(items),
    }


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
                f"TerraScope: download {kwargs['item_id']}", QgsTask.CanCancel
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
            "TerraScope",
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

        _emit(task, 50, "Clipping to AOI…")
        cube = cube.rio.clip_box(*task.bbox, crs="EPSG:4326")
        if task.isCanceled():
            return False

        _emit(task, 70, f"Downloading pixels + writing {task.out_path.name}…")
        task.out_path.parent.mkdir(parents=True, exist_ok=True)
        cube.rio.to_raster(str(task.out_path), compress="deflate", tiled=True)
        task.result_path = task.out_path
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Download failed: {exc!r}", "TerraScope", Qgis.MessageLevel.Critical
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
        QgsMessageLog.logMessage(status, "TerraScope", Qgis.MessageLevel.Info)


# --------------------------------------------------------------------------- #
def _open_client(endpoint: STACEndpoint):  # type: ignore[no-untyped-def]
    if endpoint is STACEndpoint.PLANETARY_COMPUTER:
        return stac.open_planetary_computer()
    if endpoint is STACEndpoint.EARTH_SEARCH:
        return stac.open_earth_search()
    if endpoint is STACEndpoint.CDSE:
        return stac.open_cdse()
    raise ValueError(f"unknown endpoint: {endpoint!r}")
