"""Long-running classification task — runs domain code off the GUI thread."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import Qgis, QgsMessageLog, QgsProject, QgsRasterLayer, QgsTask

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


@dataclass(slots=True)
class ClassifyJob:
    """Plain data describing a classification run.

    Kept as a frozen-ish dataclass rather than Pydantic so it is cheap to pass
    between QGIS GUI code and the QgsTask thread.
    """

    raster_path: Path
    out_path: Path
    X: "np.ndarray"
    y: "np.ndarray"
    classifier_kwargs: dict[str, Any]
    layer_display_name: str = "Terranova classification"


class ClassifyTask(QgsTask):
    """Train a classical model and apply it to a raster, writing a COG."""

    def __init__(self, job: ClassifyJob) -> None:
        super().__init__(f"Terranova: classify {job.raster_path.name}", QgsTask.CanCancel)
        self.job = job
        self.result_path: Path | None = None
        self._exc: BaseException | None = None

    def run(self) -> bool:
        from ..core.ml.classical import build_estimator, predict_to_cog, train
        from ..core.models import ClassifierConfig

        try:
            cfg = ClassifierConfig(**self.job.classifier_kwargs)
            est = build_estimator(cfg)
            train(est, self.job.X, self.job.y, progress_cb=lambda p: self.setProgress(p * 50))
            self.result_path = predict_to_cog(
                est,
                self.job.raster_path,
                self.job.out_path,
                progress_cb=lambda p: self.setProgress(50 + p * 50),
                cancel_cb=self.isCanceled,
            )
            return True
        except Exception as exc:
            self._exc = exc
            return False

    def finished(self, ok: bool) -> None:
        if ok and self.result_path is not None:
            QgsProject.instance().addMapLayer(
                QgsRasterLayer(str(self.result_path), self.job.layer_display_name)
            )
            QgsMessageLog.logMessage(
                f"Classification finished: {self.result_path}",
                "Terranova",
                Qgis.MessageLevel.Success,
            )
        elif self._exc is not None:
            QgsMessageLog.logMessage(
                f"Classification failed: {self._exc!r}",
                "Terranova",
                Qgis.MessageLevel.Critical,
            )
