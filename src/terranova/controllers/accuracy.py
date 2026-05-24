"""Accuracy controller — runs the validation pipeline as a QgsTask.

Same job-id streaming pattern as classify.  Result payload:
``{"output_path": "...pdf", "overall_accuracy": 0.85, "kappa": 0.78}``.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import _keepalive


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Start an accuracy-report job.  Returns the job_id immediately."""
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        raster_path = Path(payload["raster_path"])
        vector_path = Path(payload["vector_path"])
        class_field = str(payload["class_field"])
        output_pdf = Path(payload["output_pdf"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    task = _build_task(
        job_id=job_id,
        raster_path=raster_path,
        vector_path=vector_path,
        class_field=class_field,
        output_pdf=output_pdf,
    )
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _AccuracyJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"Terranova: accuracy {kwargs['raster_path'].name}", QgsTask.CanCancel
            )
            self.job_id: str = kwargs["job_id"]
            self.raster_path: Path = kwargs["raster_path"]
            self.vector_path: Path = kwargs["vector_path"]
            self.class_field: str = kwargs["class_field"]
            self.output_pdf: Path = kwargs["output_pdf"]
            self.overall: float | None = None
            self.kappa: float | None = None
            self.n_samples: int | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_accuracy(self)

        def finished(self, ok: bool) -> None:  # noqa: N802 (QGIS API)
            _on_finished(self, ok)

    return _AccuracyJobTask()


def _do_accuracy(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    try:
        import numpy as np

        from ..core.accuracy.metrics import assess
        from ..core.accuracy.report import render_pdf
        from ..core.ml.classical import extract_training_samples

        _emit(task, 10, "Sampling raster at validation geometries…")
        x, y_true = extract_training_samples(
            task.raster_path, task.vector_path, task.class_field
        )
        if task.isCanceled():
            return False
        if x.shape[0] == 0:
            raise RuntimeError("No validation pixels intersected the raster.")

        # band 1 of a classification raster carries the class codes
        y_pred = x[:, 0].astype(np.int64)
        _emit(task, 50, f"Computing metrics on {y_true.size} samples…")
        report = assess(y_true, y_pred)
        task.overall = float(report.overall_accuracy)
        task.kappa = float(report.kappa)
        task.n_samples = int(report.n_samples)
        QgsMessageLog.logMessage(
            f"Accuracy: OA={task.overall:.3f}, κ={task.kappa:.3f}, n={task.n_samples}",
            "Terranova",
            Qgis.MessageLevel.Info,
        )

        _emit(task, 80, f"Writing PDF to {task.output_pdf.name}…")
        render_pdf(report, task.output_pdf, title="Terranova — Accuracy report")
        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Accuracy report failed: {exc!r}", "Terranova", Qgis.MessageLevel.Critical
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
                        "output_path": str(task.output_pdf),
                        "overall_accuracy": task.overall,
                        "kappa": task.kappa,
                        "n_samples": task.n_samples,
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
        QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
