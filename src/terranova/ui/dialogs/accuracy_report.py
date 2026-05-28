"""Accuracy report dialog.

Pick a classified raster + validation vector layer + class field, compute
the confusion matrix / kappa / per-class metrics, and render a one-page
PDF report.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsTask,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


class AccuracyReportDialog(QDialog):
    """Validate a classification against a labelled vector layer."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_AccuracyTask | None" = None
        self._out_path: Path | None = None

        self.setWindowTitle("Terranova — Accuracy report")
        self.resize(560, 320)

        self._build_ui()
        self._refresh_layers()

        QgsProject.instance().layersAdded.connect(self._refresh_layers)
        QgsProject.instance().layersRemoved.connect(self._refresh_layers)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.raster_combo = QComboBox()
        form.addRow("Classified raster", self.raster_combo)

        self.validation_combo = QComboBox()
        self.validation_combo.currentIndexChanged.connect(self._refresh_field_combo)
        form.addRow("Validation vector", self.validation_combo)

        self.field_combo = QComboBox()
        form.addRow("Class field", self.field_combo)

        out_row = QHBoxLayout()
        self.out_label = QLabel("(choose output PDF…)")
        self.out_label.setWordWrap(True)
        out_row.addWidget(self.out_label, stretch=1)
        btn_pick = QPushButton("Browse…")
        btn_pick.clicked.connect(self._pick_output)
        out_row.addWidget(btn_pick)
        out_widget = QWidget()
        out_widget.setLayout(out_row)
        form.addRow("Output PDF", out_widget)

        root.addLayout(form)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel()
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.btn_run = QPushButton("Generate report")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)
        actions.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        root.addLayout(actions)

    def _refresh_layers(self) -> None:
        self.raster_combo.clear()
        self.validation_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.raster_combo.addItem(layer.name(), layer.source())
            elif isinstance(layer, QgsVectorLayer):
                self.validation_combo.addItem(layer.name(), layer.source())
        self._refresh_field_combo()

    def _refresh_field_combo(self) -> None:
        self.field_combo.clear()
        path = self.validation_combo.currentData()
        if not path:
            return
        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.source() == path
                and layer.fields()
            ):
                for f in layer.fields():
                    self.field_combo.addItem(f.name())
                for guess in ("class", "Class", "CLASS", "label", "category"):
                    idx = self.field_combo.findText(guess)
                    if idx >= 0:
                        self.field_combo.setCurrentIndex(idx)
                        break
                return

    def _pick_output(self) -> None:
        default = str(Path.home() / "terranova_accuracy.pdf")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save accuracy PDF", default, "PDF (*.pdf)"
        )
        if path:
            self._out_path = Path(path)
            self.out_label.setText(path)

    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        raster = self.raster_combo.currentData()
        vector = self.validation_combo.currentData()
        field = self.field_combo.currentText()
        out = self._out_path
        if not raster or not vector or not field or not out:
            QMessageBox.warning(
                self, "Missing input", "Pick a raster, a validation layer, a field, and a PDF path."
            )
            return

        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText("Sampling raster at validation points…")

        self._task = _AccuracyTask(
            raster_path=Path(raster),
            vector_path=Path(vector),
            class_field=field,
            out_pdf=out,
        )
        self._task.progressChanged.connect(self.progress.setValue)
        self._task.statusChanged.connect(self.status.setText)
        self._task.taskCompleted.connect(self._on_done)
        self._task.taskTerminated.connect(self._on_failed)
        QgsApplication.taskManager().addTask(self._task)

    def _on_done(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        if self._task and self._task.report_summary:
            self.status.setText(self._task.report_summary)
            self.iface.messageBar().pushSuccess(
                "Terranova", f"Accuracy PDF written to {self._task.out_pdf.name}"
            )

    def _on_failed(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Task failed."
        self.status.setText(err)
        QMessageBox.critical(self, "Accuracy report failed", err)


# --------------------------------------------------------------------------- #
class _AccuracyTask(QgsTask):
    """Sample raster at validation points → confusion matrix → PDF."""

    statusChanged = pyqtSignal(str)

    def __init__(
        self,
        raster_path: Path,
        vector_path: Path,
        class_field: str,
        out_pdf: Path,
    ) -> None:
        super().__init__(f"Terranova: accuracy {raster_path.name}", QgsTask.CanCancel)
        self.raster_path = raster_path
        self.vector_path = vector_path
        self.class_field = class_field
        self.out_pdf = out_pdf
        self.report_summary: str | None = None
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            import numpy as np

            from ...core.accuracy.metrics import assess
            from ...core.accuracy.report import render_pdf
            from ...core.ml.classical import extract_training_samples

            self._emit(10, "Sampling raster at validation geometries…")
            X, y_true = extract_training_samples(
                self.raster_path, self.vector_path, self.class_field
            )
            if self.isCanceled():
                return False
            if X.shape[0] == 0:
                raise RuntimeError("No validation pixels intersected the raster.")

            # The raster is the classification itself — band 1 carries class codes.
            # `extract_training_samples` returns X as all-band features; take band-1.
            y_pred = X[:, 0].astype(np.int64)
            self._emit(50, f"Computing metrics on {y_true.size} samples…")
            report = assess(y_true, y_pred)
            self.report_summary = (
                f"OA = {report.overall_accuracy:.3f}, "
                f"κ = {report.kappa:.3f}, "
                f"n = {report.n_samples}"
            )

            self._emit(80, f"Writing PDF to {self.out_pdf.name}…")
            render_pdf(report, self.out_pdf, title="Terranova — Accuracy report")
            self._emit(100, "Done.")
            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"Accuracy report failed: {exc!r}", "Terranova", Qgis.MessageLevel.Critical
            )
            return False

    def _emit(self, percent: float, status: str) -> None:
        self.setProgress(percent)
        if status:
            self.statusChanged.emit(status)
            QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
