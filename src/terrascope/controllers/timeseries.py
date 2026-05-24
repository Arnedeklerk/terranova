"""Time-series + change-detection controller.

Mirrors the Qt TimeSeriesDialog: STAC search → cube → index → per-pixel
change detection → break + magnitude rasters + optional MP4.  Emits
progress events on a job_id channel via :func:`bridge.push_event`.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any


def run(payload: dict[str, Any]) -> dict[str, Any]:
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        bbox = payload["bbox"]
        out_dir = Path(payload["out_dir"])
        history_start = _parse_date(payload["history_start"])
        monitor_start = _parse_date(payload["monitor_start"])
        end = _parse_date(payload["end"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    task = _build_task(
        job_id=job_id,
        bbox=(
            float(bbox["west"]),
            float(bbox["south"]),
            float(bbox["east"]),
            float(bbox["north"]),
        ),
        history_start=history_start,
        monitor_start=monitor_start,
        end=end,
        endpoint=str(payload.get("endpoint", "planetary_computer")),
        index_kind=str(payload.get("index", "ndvi")),
        max_cloud=int(payload.get("max_cloud", 20)),
        resolution=int(payload.get("resolution", 30)),
        method=str(payload.get("method", "cusum")),
        threshold=float(payload.get("threshold", 2.0)),
        export_mp4=bool(payload.get("export_mp4", True)),
        out_dir=out_dir,
    )
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _parse_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _TimeSeriesJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__("TerraScope: time-series", QgsTask.CanCancel)
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.break_path: Path | None = None
            self.magnitude_path: Path | None = None
            self.mp4_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_timeseries(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _TimeSeriesJobTask()


def _do_timeseries(task: Any) -> bool:  # noqa: PLR0915 — pipeline is what it is
    from qgis.core import Qgis, QgsMessageLog

    try:
        import numpy as np
        import odc.stac

        from ..core.catalog import stac as cstac
        from ..core.models import STACEndpoint
        from ..core.stacking.cloudmask import mask_from_scl
        from ..core.timeseries.change import detect_change
        from ..core.timeseries.indices import _normalised_difference  # type: ignore[attr-defined]

        _emit(task, 5, "Searching catalogue…")
        client = (
            cstac.open_planetary_computer()
            if STACEndpoint(task.endpoint) is STACEndpoint.PLANETARY_COMPUTER
            else cstac.open_earth_search()
        )
        items = cstac.search_s2_l2a(
            client,
            bbox=task.bbox,
            datetime=f"{task.history_start.isoformat()}/{task.end.isoformat()}",
            max_cloud=task.max_cloud,
            limit=500,
        )
        n = len(list(items))
        if n == 0:
            raise RuntimeError("No items matched the catalogue search.")
        _emit(task, 10, f"Found {n} scenes — loading lazy cube…")

        bands = _bands_for_index(task.index_kind)
        extra = ["scl"] if task.index_kind in {"ndvi", "nbr", "ndmi"} else []
        cube = odc.stac.load(
            items,
            bands=list(bands) + extra,
            resolution=task.resolution,
            bbox=task.bbox,
            chunks={"x": 1024, "y": 1024},
        )
        if "scl" in cube.data_vars:
            _emit(task, 20, "Applying SCL cloud mask…")
            cube = mask_from_scl(cube, cube["scl"])

        _emit(task, 30, f"Computing {task.index_kind.upper()} per time…")
        index_da = _compute_index(task.index_kind, cube, _normalised_difference)
        index_da = index_da.persist()

        _emit(task, 55, f"Running {task.method} per pixel…")
        monitor_index = int(
            (np.array(index_da.time.values) >= np.datetime64(task.monitor_start)).argmax()
        )
        change = detect_change(
            index_da,
            method=task.method,  # type: ignore[arg-type]
            monitor_start_index=monitor_index,
            threshold=task.threshold,
            progress_cb=lambda p: _emit(task, 55 + p * 30, ""),
        )
        if task.isCanceled():
            return False

        _emit(task, 88, "Writing rasters…")
        task.out_dir.mkdir(parents=True, exist_ok=True)
        task.break_path = task.out_dir / f"{task.index_kind}_break_index.tif"
        task.magnitude_path = task.out_dir / f"{task.index_kind}_magnitude.tif"
        change["break_index"].rio.write_crs(index_da.rio.crs).rio.to_raster(
            str(task.break_path), compress="deflate"
        )
        change["magnitude"].rio.write_crs(index_da.rio.crs).rio.to_raster(
            str(task.magnitude_path), compress="deflate"
        )

        if task.export_mp4:
            try:
                from ..core.viz.figures import export_animation

                _emit(task, 95, "Rendering MP4…")
                task.mp4_path = task.out_dir / f"{task.index_kind}_timeseries.mp4"
                export_animation(index_da, task.mp4_path, fps=4)
            except Exception as exc:  # noqa: BLE001
                QgsMessageLog.logMessage(
                    f"MP4 export skipped: {exc!r}",
                    "TerraScope",
                    Qgis.MessageLevel.Warning,
                )
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Time-series failed: {exc!r}", "TerraScope", Qgis.MessageLevel.Critical
        )
        return False


def _bands_for_index(kind: str) -> tuple[str, ...]:
    if kind == "ndvi":
        return ("red", "nir")
    if kind == "nbr":
        return ("nir", "swir22")
    if kind == "ndmi":
        return ("nir", "swir16")
    raise ValueError(f"unknown index: {kind!r}")


def _compute_index(kind: str, cube: Any, nd_fn: Any) -> Any:
    bands = _bands_for_index(kind)
    a = cube[bands[0]].astype("float32")
    b = cube[bands[1]].astype("float32")
    if kind == "ndvi":
        return nd_fn(b, a)
    return nd_fn(a, b)  # nbr / ndmi


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    if ok:
        push_event(
            {
                "type": "task.complete",
                "job_id": task.job_id,
                "result": {
                    "break_path": str(task.break_path) if task.break_path else None,
                    "magnitude_path": str(task.magnitude_path)
                    if task.magnitude_path
                    else None,
                    "mp4_path": str(task.mp4_path) if task.mp4_path else None,
                },
            }
        )
        # Auto-add the break-index raster to QGIS.
        try:
            from qgis.core import QgsProject, QgsRasterLayer

            if task.break_path:
                layer = QgsRasterLayer(str(task.break_path), task.break_path.stem)
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
