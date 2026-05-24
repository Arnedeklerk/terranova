"""Classify controller — starts a long-running classification task and streams
progress + completion to the React panel via :func:`bridge.push_event`.

The handler returns ``{job_id: "..."}`` immediately; the React side filters
events by job_id.  Event types emitted:

- ``{"type": "task.progress", "job_id": ..., "percent": 0-100, "status": "..."}``
- ``{"type": "task.complete", "job_id": ..., "result": {"output_path": "..."}}``
- ``{"type": "task.failed",   "job_id": ..., "error": "..."}``

All ``qgis.*`` imports are deferred to function bodies so this module can be
imported in headless-test environments where QGIS isn't available.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a classify job.  Returns the job_id immediately."""
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        raster_path = Path(payload["raster_path"])
        vector_path = Path(payload["vector_path"])
        class_field = str(payload["class_field"])
        output_path = Path(payload["output_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    task = _build_task(
        job_id=job_id,
        raster_path=raster_path,
        vector_path=vector_path,
        class_field=class_field,
        classifier=str(payload.get("classifier", "random_forest")),
        n_estimators=int(payload.get("n_estimators", 300)),
        cv_folds=int(payload.get("cv_folds", 5)),
        output_path=output_path,
    )
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    """Construct the QgsTask subclass — qgis only imported here."""
    from qgis.core import QgsTask

    class _ClassifyJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"TerraScope: classify {kwargs['raster_path'].name}",
                QgsTask.CanCancel,
            )
            self.job_id: str = kwargs["job_id"]
            self.raster_path: Path = kwargs["raster_path"]
            self.vector_path: Path = kwargs["vector_path"]
            self.class_field: str = kwargs["class_field"]
            self.classifier: str = kwargs["classifier"]
            self.n_estimators: int = kwargs["n_estimators"]
            self.cv_folds: int = kwargs["cv_folds"]
            self.output_path: Path = kwargs["output_path"]
            self.result_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:  # noqa: D401 — QgsTask API
            return _do_classify(self)

        def finished(self, ok: bool) -> None:  # noqa: N802 (QGIS API)
            _on_finished(self, ok)

    return _ClassifyJobTask()


def _do_classify(task: Any) -> bool:
    """Worker-thread body — runs inside ``QgsTask.run``."""
    from qgis.core import Qgis, QgsMessageLog

    try:
        import numpy as np

        from ..core.ml.classical import (
            build_estimator,
            extract_training_samples,
            predict_to_cog,
            train,
        )
        from ..core.models import ClassifierConfig, ClassifierKind

        _emit(task, 2, "Extracting training samples from polygons…")
        x, y = extract_training_samples(task.raster_path, task.vector_path, task.class_field)
        if task.isCanceled():
            return False

        n_samples = int(x.shape[0])
        unique = np.unique(y)
        QgsMessageLog.logMessage(
            f"Training: {n_samples} pixels, {x.shape[1]} bands, {len(unique)} classes",
            "TerraScope",
            Qgis.MessageLevel.Info,
        )
        if n_samples < 5:
            raise RuntimeError(
                f"Only {n_samples} valid training pixels — check that the "
                "polygons overlap the raster and the class field is correct."
            )
        if len(unique) < 2:
            raise RuntimeError(
                f"All {n_samples} training pixels have class {int(unique[0])}.  "
                "A classifier needs at least two classes."
            )

        _emit(task, 10, f"Training {task.classifier} on {n_samples} pixels…")
        cfg = ClassifierConfig(
            kind=ClassifierKind(task.classifier),
            hyperparameters={"n_estimators": task.n_estimators}
            if task.classifier in {"random_forest", "extra_trees", "lightgbm", "xgboost"}
            else {},
            cross_validation_folds=task.cv_folds,
        )
        estimator = build_estimator(cfg)
        train(estimator, x, y, progress_cb=lambda p: _emit(task, 10 + p * 20, ""))
        if task.isCanceled():
            return False

        _emit(task, 30, "Applying classifier to the raster…")
        task.result_path = predict_to_cog(
            estimator,
            task.raster_path,
            task.output_path,
            progress_cb=lambda p: _emit(task, 30 + p * 70, ""),
            cancel_cb=task.isCanceled,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — task boundary
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Classification failed: {exc!r}", "TerraScope", Qgis.MessageLevel.Critical
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    """Main-thread callback — emit the terminal event and add the layer."""
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


def _emit(task: Any, percent: float, status: str) -> None:
    """Push progress to the React side.  Safe from worker thread (Qt queues)."""
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
