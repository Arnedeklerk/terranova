"""SAM-prompted segmentation controller.

Two modes: text prompt (Grounded-SAM-style) and point prompts.  Point
prompts come from the React side as an array of ``[x, y]`` map coordinates
in the input raster's CRS.

The harder UX bit — letting the user click points directly on the canvas —
is exposed as a separate ``sam.pick_points`` action that activates a
QgsMapToolEmitPoint and forwards each click as a ``sam.point.added`` event.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


def run(payload: dict[str, Any]) -> dict[str, Any]:
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        raster_path = Path(payload["raster_path"])
        out_path = Path(payload["out_path"])
        mode = str(payload.get("mode", "text"))
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    task = _build_task(
        job_id=job_id,
        raster_path=raster_path,
        out_path=out_path,
        model=str(payload.get("model", "sam2_b")),
        mode=mode,
        prompt=payload.get("prompt"),
        points=list(payload.get("points") or []),
        box_threshold=float(payload.get("box_threshold", 0.24)),
        text_threshold=float(payload.get("text_threshold", 0.24)),
    )
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _SamJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"TerraScope: SAM {kwargs['raster_path'].name}", QgsTask.CanCancel
            )
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.result_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_sam(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _SamJobTask()


def _do_sam(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        from ..core.ml.sam import segment_from_points, segment_from_text

        _emit(task, 10, "Loading SAM model and embeddings…")
        if task.mode == "text":
            if not task.prompt:
                raise RuntimeError("Text mode needs a prompt.")
            task.result_path = segment_from_text(
                task.raster_path,
                task.out_path,
                prompt=task.prompt,
                box_threshold=task.box_threshold,
                text_threshold=task.text_threshold,
                model=task.model,
                progress_cb=lambda p: _emit(task, 10 + p * 85, ""),
            )
        else:
            if not task.points:
                raise RuntimeError("Point mode needs at least one point.")
            task.result_path = segment_from_points(
                task.raster_path,
                task.out_path,
                points=[(float(x), float(y)) for x, y in task.points],
                model=task.model,
                progress_cb=lambda p: _emit(task, 10 + p * 85, ""),
            )
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"SAM segmentation failed: {exc!r}",
            "TerraScope",
            Qgis.MessageLevel.Critical,
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    if ok and task.result_path is not None:
        push_event(
            {
                "type": "task.complete",
                "job_id": task.job_id,
                "result": {"output_path": str(task.result_path)},
            }
        )
        try:
            from qgis.core import QgsProject, QgsVectorLayer

            layer = QgsVectorLayer(str(task.result_path), task.result_path.stem, "ogr")
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


# --------------------------------------------------------------------------- #
# Map-click point picking                                                     #
# --------------------------------------------------------------------------- #
_picker: Any = None  # module-level so we can deactivate from another action


def start_pick_points(_payload: dict[str, Any]) -> dict[str, Any]:
    """Activate a map-click tool; each click emits ``sam.point.added``."""
    from qgis.gui import QgsMapToolEmitPoint
    from qgis.utils import iface

    from ..bridge import push_event

    global _picker
    if iface is None:
        raise RuntimeError("QGIS iface unavailable")

    canvas = iface.mapCanvas()
    tool = QgsMapToolEmitPoint(canvas)

    def _on_click(pt, _btn) -> None:  # type: ignore[no-untyped-def]
        push_event(
            {"type": "sam.point.added", "x": float(pt.x()), "y": float(pt.y())}
        )

    tool.canvasClicked.connect(_on_click)
    canvas.setMapTool(tool)
    _picker = tool  # keep alive
    return {"active": True}


def stop_pick_points(_payload: dict[str, Any]) -> dict[str, Any]:
    """Deactivate the picker (revert to whatever map tool was active before)."""
    from qgis.utils import iface

    global _picker
    if iface is not None and _picker is not None:
        iface.mapCanvas().unsetMapTool(_picker)
    _picker = None
    return {"active": False}
