"""Foundation-model fine-tune controller.

Wraps :func:`terrascope.core.ml.foundation.finetune` in a QgsTask, then
exports the trained checkpoint to ONNX.  Same event channel as the other
long jobs.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import _keepalive


def run(payload: dict[str, Any]) -> dict[str, Any]:
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        out_dir = Path(payload["out_dir"])
        pairs = payload["pairs"]  # list of {"raster": "...", "mask": "..."}
        if not pairs:
            raise ValueError("at least one scene/mask pair is required")
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    train_rasters = [Path(p["raster"]) for p in pairs]
    train_masks = [Path(p["mask"]) for p in pairs]

    task = _build_task(
        job_id=job_id,
        backbone=str(payload.get("backbone", "prithvi_eo_v2_300")),
        n_classes=int(payload.get("n_classes", 5)),
        max_epochs=int(payload.get("max_epochs", 20)),
        batch_size=int(payload.get("batch_size", 8)),
        learning_rate=float(payload.get("learning_rate", 1e-4)),
        accelerator=str(payload.get("accelerator", "auto")),
        train_rasters=train_rasters,
        train_masks=train_masks,
        out_dir=out_dir,
    )
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _FoundationJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"TerraScope: fine-tune {kwargs['backbone']}", QgsTask.CanCancel
            )
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.checkpoint_path: Path | None = None
            self.onnx_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_finetune(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _FoundationJobTask()


def _do_finetune(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        from ..core.ml.foundation import (
            FoundationFinetuneConfig,
            export_finetuned_to_onnx,
            finetune,
        )

        cfg = FoundationFinetuneConfig(
            backbone=task.backbone,  # type: ignore[arg-type]
            n_classes=task.n_classes,
            max_epochs=task.max_epochs,
            batch_size=task.batch_size,
            learning_rate=task.learning_rate,
            accelerator=task.accelerator,
        )
        _emit(task, 5, f"Loading {task.backbone} weights…")
        task.checkpoint_path = finetune(
            cfg,
            task.train_rasters,
            task.train_masks,
            out_dir=task.out_dir,
            progress_cb=lambda p: _emit(
                task, 5 + p * 90, f"Training (epoch {int(p * task.max_epochs)}/{task.max_epochs})"
            ),
        )
        if task.isCanceled():
            return False
        _emit(task, 95, "Exporting to ONNX…")
        task.onnx_path = export_finetuned_to_onnx(
            task.checkpoint_path,
            task.out_dir / "model.onnx",
            n_input_bands=6,
        )
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Foundation fine-tune failed: {exc!r}",
            "TerraScope",
            Qgis.MessageLevel.Critical,
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    try:
        if ok:
            push_event(
                {
                    "type": "task.complete",
                    "job_id": task.job_id,
                    "result": {
                        "checkpoint_path": str(task.checkpoint_path)
                        if task.checkpoint_path
                        else None,
                        "onnx_path": str(task.onnx_path) if task.onnx_path else None,
                    },
                }
            )
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
