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

from . import _keepalive


def run(payload: dict[str, Any]) -> dict[str, Any]:
    """Start a classify job.  Branches on ``mode`` (default 'supervised').

    Supervised payload (existing):
      ``raster_path``, ``vector_path``, ``class_field``, ``output_path``,
      ``classifier``, ``n_estimators``, ``cv_folds``.

    Unsupervised payload (new):
      ``raster_path``, ``output_path``, ``algorithm`` ('kmeans' or
      'isodata'), ``n_clusters``, ``max_iter``.

    Returns ``{"job_id": "..."}`` immediately regardless of mode; the
    React panel filters task events by job id.
    """
    from qgis.core import QgsApplication

    mode = str(payload.get("mode", "supervised"))
    job_id = str(uuid.uuid4())

    if mode == "supervised":
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
    elif mode == "unsupervised":
        try:
            raster_path = Path(payload["raster_path"])
            output_path = Path(payload["output_path"])
        except KeyError as exc:
            raise ValueError(f"missing required field: {exc}") from exc
        algorithm = str(payload.get("algorithm", "kmeans"))
        if algorithm not in {"kmeans", "isodata"}:
            raise ValueError(
                f"unknown unsupervised algorithm: {algorithm!r} "
                "(expected 'kmeans' or 'isodata')"
            )
        task = _build_unsupervised_task(
            job_id=job_id,
            raster_path=raster_path,
            output_path=output_path,
            algorithm=algorithm,
            n_clusters=int(payload.get("n_clusters", 5)),
            max_iter=int(payload.get("max_iter", 50)),
            sample_size=int(payload.get("sample_size", 100_000)),
        )
    else:
        raise ValueError(
            f"unknown classify mode: {mode!r} (expected 'supervised' or 'unsupervised')"
        )

    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    """Construct the QgsTask subclass — qgis only imported here."""
    from qgis.core import QgsTask

    class _ClassifyJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"Terranova: classify {kwargs['raster_path'].name}",
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
            "Terranova",
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
            f"Classification failed: {exc!r}", "Terranova", Qgis.MessageLevel.Critical
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    """Main-thread callback — emit the terminal event and add the layer."""
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
        _keepalive.release(task.job_id)


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
        QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)


# --------------------------------------------------------------------------- #
# Unsupervised path                                                           #
# --------------------------------------------------------------------------- #
def _build_unsupervised_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _UnsupervisedJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                f"Terranova: cluster {kwargs['raster_path'].name}",
                QgsTask.CanCancel,
            )
            self.job_id: str = kwargs["job_id"]
            self.raster_path: Path = kwargs["raster_path"]
            self.output_path: Path = kwargs["output_path"]
            self.algorithm: str = kwargs["algorithm"]
            self.n_clusters: int = kwargs["n_clusters"]
            self.max_iter: int = kwargs["max_iter"]
            self.sample_size: int = kwargs["sample_size"]
            self.result_path: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_unsupervised(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _UnsupervisedJobTask()


def _do_unsupervised(task: Any) -> bool:
    """Worker body for the K-Means / ISODATA path.  Same lifecycle as supervised."""
    from qgis.core import Qgis, QgsMessageLog

    try:
        from ..core.ml.classical import predict_to_cog
        from ..core.ml.unsupervised import fit_unsupervised

        _emit(
            task,
            2,
            f"Sampling raster + fitting {task.algorithm.upper()} "
            f"(target k={task.n_clusters})…",
        )
        estimator = fit_unsupervised(
            kind=task.algorithm,  # type: ignore[arg-type]
            raster_path=task.raster_path,
            n_clusters=task.n_clusters,
            max_iter=task.max_iter,
            sample_size=task.sample_size,
            progress_cb=lambda p: _emit(task, 2 + p * 28, ""),
        )
        if task.isCanceled():
            return False

        # ISODATA's final cluster count can differ from the target after
        # split/merge — log it so the user isn't surprised the output
        # raster has 4 or 7 classes when they asked for 5.
        final_k = getattr(
            estimator,
            "n_clusters",
            getattr(estimator, "n_clusters_", None),
        )
        if final_k is not None:
            QgsMessageLog.logMessage(
                f"{task.algorithm.upper()} fitted with {int(final_k)} clusters.",
                "Terranova",
                Qgis.MessageLevel.Info,
            )

        _emit(task, 30, "Applying clusterer to the full raster…")
        # Cluster IDs are zero-based; nodata_output=0 would collide.
        # Shift by 1 via a wrapper estimator so 0 stays reserved for
        # nodata in the output raster.
        shifted = _ShiftedEstimator(estimator, shift=1)
        task.result_path = predict_to_cog(
            shifted,
            task.raster_path,
            task.output_path,
            progress_cb=lambda p: _emit(task, 30 + p * 70, ""),
            cancel_cb=task.isCanceled,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — task boundary
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Unsupervised classification failed: {exc!r}",
            "Terranova",
            Qgis.MessageLevel.Critical,
        )
        return False


class _ShiftedEstimator:
    """Wrap a sklearn-shaped estimator, adding ``shift`` to every prediction.

    Unsupervised cluster IDs are zero-based; the output COG reserves 0 for
    nodata.  Shifting predictions by +1 keeps cluster 0 visible without
    changing the underlying fit.
    """

    def __init__(self, inner: Any, shift: int) -> None:
        self._inner = inner
        self._shift = int(shift)

    def predict(self, X: Any) -> Any:
        return self._inner.predict(X) + self._shift
