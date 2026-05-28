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

    output_xlsx_raw = payload.get("output_xlsx")
    output_xlsx = Path(output_xlsx_raw) if output_xlsx_raw else None

    task = _build_task(
        job_id=job_id,
        raster_path=raster_path,
        vector_path=vector_path,
        class_field=class_field,
        output_pdf=output_pdf,
        output_xlsx=output_xlsx,
    )
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def run_on_points(payload: dict[str, Any]) -> dict[str, Any]:
    """Compute the accuracy report directly from a points GeoPackage.

    Reads the GPKG's ``predicted`` and ``truth`` integer columns, builds
    the confusion matrix, computes OA / kappa / per-class UA / PA / F1,
    and optionally writes PDF + Excel.  Returns the full report inline
    so the UI can display metrics without re-reading any files.

    Unlike :func:`run` (which samples a classified raster at every
    pixel covered by a validation vector), this path doesn't touch the
    raster at all — the points file IS the predicted-vs-truth dataset
    after the user has labelled it with :mod:`labeling`.
    """
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    try:
        points_path = Path(payload["points_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    output_pdf = payload.get("output_pdf")
    output_xlsx = payload.get("output_xlsx")
    task = _build_points_task(
        job_id=job_id,
        points_path=points_path,
        output_pdf=Path(output_pdf) if output_pdf else None,
        output_xlsx=Path(output_xlsx) if output_xlsx else None,
    )
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def probe_classes(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the unique class codes present in a classified raster.

    Used by the points-generator UI to show the user how many classes
    they're sampling against BEFORE they pick stratified / equalized
    parameters.  Cheap (single rasterio read + np.unique).
    """
    try:
        raster_path = Path(payload["raster_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    import numpy as np
    import rasterio

    with rasterio.open(str(raster_path)) as src:
        arr = src.read(1)
        nodata = {0}
        if src.nodata is not None:
            nodata.add(int(src.nodata))
        classes = sorted(int(c) for c in np.unique(arr) if int(c) not in nodata)
    return {"classes": classes, "n_classes": len(classes)}


def generate_points(payload: dict[str, Any]) -> dict[str, Any]:
    """Sample validation points from a classified raster.

    Payload:
      - ``raster_path`` (required): classified raster to sample.
      - ``out_path``    (required): GeoPackage path to write.
      - ``strategy``    ('random' | 'stratified' | 'equalized_stratified')
      - ``n_total``     (random / stratified, default 300)
      - ``points_per_class`` (equalized, default 30)
      - ``min_per_class``    (stratified floor, default 5)

    Synchronous — fast enough not to need a QgsTask (we're just reading
    the raster band, sampling indices, writing N points).  Returns the
    summary dict from :func:`generate_validation_points` plus a
    'sampled the file as a layer too' side effect.
    """
    from ..core.accuracy.sampling import generate_validation_points

    try:
        raster_path = Path(payload["raster_path"])
        out_path = Path(payload["out_path"])
    except KeyError as exc:
        raise ValueError(f"missing required field: {exc}") from exc

    strategy = str(payload.get("strategy", "stratified"))
    result = generate_validation_points(
        raster_path=raster_path,
        out_path=out_path,
        strategy=strategy,  # type: ignore[arg-type]
        n_total=int(payload.get("n_total", 300)),
        points_per_class=int(payload.get("points_per_class", 30)),
        min_per_class=int(payload.get("min_per_class", 5)),
    )

    # Drop the points layer into the project so the user can immediately
    # start editing the `truth` column.
    try:
        from qgis.core import QgsProject, QgsVectorLayer

        layer = QgsVectorLayer(str(out_path), out_path.stem, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
    except Exception:  # noqa: BLE001
        pass

    return result


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
            self.output_xlsx: Path | None = kwargs.get("output_xlsx")
            self.overall: float | None = None
            self.kappa: float | None = None
            self.n_samples: int | None = None
            self.report_data: dict[str, Any] | None = None
            self.xlsx_written: Path | None = None
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

        task.report_data = _serialise_report(report)

        _emit(task, 70, f"Writing PDF to {task.output_pdf.name}…")
        render_pdf(report, task.output_pdf, title="Terranova — Accuracy report")

        if task.output_xlsx is not None:
            _emit(task, 85, f"Writing Excel to {task.output_xlsx.name}…")
            from ..core.accuracy.excel import write_excel_report

            write_excel_report(
                report,
                task.output_xlsx,
                raster_name=task.raster_path.name,
                vector_name=task.vector_path.name,
            )
            task.xlsx_written = task.output_xlsx
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
                        "output_xlsx": str(task.xlsx_written)
                        if task.xlsx_written
                        else None,
                        "overall_accuracy": task.overall,
                        "kappa": task.kappa,
                        "n_samples": task.n_samples,
                        "report": task.report_data,
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


def _build_points_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _PointsAccuracyTask(QgsTask):
        def __init__(self) -> None:
            super().__init__(
                "Terranova: accuracy from labelled points", QgsTask.CanCancel
            )
            self.job_id: str = kwargs["job_id"]
            self.points_path: Path = kwargs["points_path"]
            self.output_pdf: Path | None = kwargs.get("output_pdf")
            self.output_xlsx: Path | None = kwargs.get("output_xlsx")
            self.overall: float | None = None
            self.kappa: float | None = None
            self.n_samples: int | None = None
            self.report_data: dict[str, Any] | None = None
            self.xlsx_written: Path | None = None
            self.pdf_written: Path | None = None
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_points_accuracy(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_points_finished(self, ok)

    return _PointsAccuracyTask()


def _do_points_accuracy(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog
    from osgeo import ogr

    try:
        _emit(task, 10, "Reading predicted + truth columns…")
        ds = ogr.Open(str(task.points_path))
        if ds is None:
            raise RuntimeError(f"could not open {task.points_path}")
        layer = ds.GetLayer(0)
        predicted: list[int] = []
        truth: list[int] = []
        for feat in layer:
            p = int(feat.GetFieldAsInteger("predicted") or 0)
            t = int(feat.GetFieldAsInteger("truth") or 0)
            # Only points with a user-supplied truth count toward the
            # confusion matrix — predicted-only points are unlabelled.
            if t == 0:
                continue
            predicted.append(p)
            truth.append(t)
        ds = None

        if not truth:
            raise RuntimeError(
                "No labelled points found.  Step through the points using the "
                "'Label points' pad above (or edit the `truth` column in QGIS) "
                "before computing accuracy."
            )

        import numpy as np

        from ..core.accuracy.metrics import assess

        _emit(task, 50, f"Computing metrics on {len(truth)} labelled points…")
        report = assess(np.asarray(truth, dtype=np.int64),
                        np.asarray(predicted, dtype=np.int64))
        task.overall = float(report.overall_accuracy)
        task.kappa = float(report.kappa)
        task.n_samples = int(report.n_samples)
        task.report_data = _serialise_report(report)
        QgsMessageLog.logMessage(
            f"Accuracy from points: OA={task.overall:.3f}, κ={task.kappa:.3f}, "
            f"n={task.n_samples}",
            "Terranova",
            Qgis.MessageLevel.Info,
        )

        if task.output_pdf is not None:
            _emit(task, 75, f"Writing PDF to {task.output_pdf.name}…")
            from ..core.accuracy.report import render_pdf

            render_pdf(report, task.output_pdf, title="Terranova — Accuracy report")
            task.pdf_written = task.output_pdf

        if task.output_xlsx is not None:
            _emit(task, 90, f"Writing Excel to {task.output_xlsx.name}…")
            from ..core.accuracy.excel import write_excel_report

            write_excel_report(
                report,
                task.output_xlsx,
                raster_name="(from labelled points)",
                vector_name=task.points_path.name,
            )
            task.xlsx_written = task.output_xlsx

        _emit(task, 100, "Done.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"Accuracy from points failed: {exc!r}",
            "Terranova",
            Qgis.MessageLevel.Critical,
        )
        return False


def _on_points_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    try:
        if ok:
            push_event(
                {
                    "type": "task.complete",
                    "job_id": task.job_id,
                    "result": {
                        "output_path": str(task.pdf_written)
                        if task.pdf_written
                        else None,
                        "output_xlsx": str(task.xlsx_written)
                        if task.xlsx_written
                        else None,
                        "overall_accuracy": task.overall,
                        "kappa": task.kappa,
                        "n_samples": task.n_samples,
                        "report": task.report_data,
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


def _serialise_report(report: Any) -> dict[str, Any]:
    """Convert an AccuracyReport dataclass into a JSON-safe dict.

    Used by both the vector and points accuracy paths so the UI sees
    the same shape regardless of which Compute button kicked it off:
    confusion matrix as a nested list, NaNs replaced with None.
    """
    import math

    def _nan_safe(v: float) -> float | None:
        try:
            return None if math.isnan(float(v)) else float(v)
        except Exception:  # noqa: BLE001
            return None

    return {
        "class_labels": [int(c) for c in report.class_labels],
        "confusion_matrix": [
            [int(v) for v in row] for row in report.confusion_matrix
        ],
        "users_accuracy": [_nan_safe(v) for v in report.users_accuracy],
        "producers_accuracy": [_nan_safe(v) for v in report.producers_accuracy],
        "f1_per_class": [_nan_safe(v) for v in report.f1_per_class],
        "overall_accuracy": float(report.overall_accuracy),
        "kappa": float(report.kappa),
        "n_samples": int(report.n_samples),
    }


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
