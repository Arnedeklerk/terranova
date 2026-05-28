"""SAM-prompted segmentation dialog.

Two prompt modes: text (Grounded-SAM-style) and points clicked on the canvas.
Runs the segment-geospatial wrapper in a background task and writes a
GeoPackage of polygons.
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
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


class SamDialog(QDialog):
    """SAM-prompted segmentation."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_SamTask | None" = None
        self._out_path: Path | None = None
        self._points: list[tuple[float, float]] = []
        self._point_tool = None

        self.setWindowTitle("Terranova — Segment with SAM")
        self.resize(620, 380)

        self._build_ui()
        self._refresh_layers()

        QgsProject.instance().layersAdded.connect(self._refresh_layers)
        QgsProject.instance().layersRemoved.connect(self._refresh_layers)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.raster_combo = QComboBox()
        form.addRow("Input raster", self.raster_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItem("SAM 2 base", "sam2_b")
        self.model_combo.addItem("SAM 2 large", "sam2_l")
        self.model_combo.addItem("SAM 3", "sam3")
        form.addRow("Model", self.model_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Text prompt", "text")
        self.mode_combo.addItem("Point prompts", "points")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("Mode", self.mode_combo)

        # Mode-specific widgets stacked.
        self.mode_stack = QStackedWidget()

        # --- text mode ---
        text_box = QWidget()
        text_layout = QFormLayout(text_box)
        text_layout.setContentsMargins(0, 0, 0, 0)
        self.prompt_edit = QLineEdit("buildings")
        text_layout.addRow("Text prompt", self.prompt_edit)
        self.box_threshold = QDoubleSpinBox()
        self.box_threshold.setRange(0.05, 0.95)
        self.box_threshold.setSingleStep(0.05)
        self.box_threshold.setValue(0.24)
        text_layout.addRow("Box threshold", self.box_threshold)
        self.text_threshold = QDoubleSpinBox()
        self.text_threshold.setRange(0.05, 0.95)
        self.text_threshold.setSingleStep(0.05)
        self.text_threshold.setValue(0.24)
        text_layout.addRow("Text threshold", self.text_threshold)
        self.mode_stack.addWidget(text_box)

        # --- points mode ---
        points_box = QWidget()
        points_layout = QVBoxLayout(points_box)
        points_layout.setContentsMargins(0, 0, 0, 0)
        self.pick_btn = QPushButton("Pick points on map (Esc to finish)")
        self.pick_btn.clicked.connect(self._start_picking)
        points_layout.addWidget(self.pick_btn)
        self.points_label = QLabel("0 points")
        self.points_label.setStyleSheet("color:#8A93A0")
        points_layout.addWidget(self.points_label)
        clear_btn = QPushButton("Clear points")
        clear_btn.clicked.connect(self._clear_points)
        points_layout.addWidget(clear_btn)
        self.mode_stack.addWidget(points_box)

        form.addRow("Prompt", self.mode_stack)
        root.addLayout(form)

        # Output path
        out_row = QHBoxLayout()
        self.out_label = QLabel("(choose output GeoPackage…)")
        self.out_label.setWordWrap(True)
        out_row.addWidget(self.out_label, stretch=1)
        btn_pick = QPushButton("Browse…")
        btn_pick.clicked.connect(self._pick_output)
        out_row.addWidget(btn_pick)
        out_widget = QWidget()
        out_widget.setLayout(out_row)
        root.addWidget(QLabel("Output polygons"))
        root.addWidget(out_widget)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel()
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.btn_run = QPushButton("Segment")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)
        actions.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    def _refresh_layers(self) -> None:
        self.raster_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.raster_combo.addItem(layer.name(), layer.source())

    def _on_mode_changed(self) -> None:
        self.mode_stack.setCurrentIndex(self.mode_combo.currentIndex())

    def _pick_output(self) -> None:
        default = str(Path.home() / "terranova_sam.gpkg")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save polygon output", default, "GeoPackage (*.gpkg)"
        )
        if path:
            self._out_path = Path(path)
            self.out_label.setText(path)

    # ------------------------------------------------------------------ #
    # Point picking on the canvas                                        #
    # ------------------------------------------------------------------ #
    def _start_picking(self) -> None:
        from qgis.gui import QgsMapToolEmitPoint

        canvas = self.iface.mapCanvas()
        tool = QgsMapToolEmitPoint(canvas)

        def _on_click(pt, _btn):  # type: ignore[no-untyped-def]
            self._points.append((pt.x(), pt.y()))
            self.points_label.setText(f"{len(self._points)} point(s)")

        tool.canvasClicked.connect(_on_click)
        canvas.setMapTool(tool)
        self._point_tool = tool
        self.iface.messageBar().pushInfo(
            "Terranova", "Click foreground points on the map. Press Escape when done."
        )

    def _clear_points(self) -> None:
        self._points.clear()
        self.points_label.setText("0 points")

    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        raster = self.raster_combo.currentData()
        if not raster:
            QMessageBox.warning(self, "Missing input", "Pick an input raster.")
            return
        if not self._out_path:
            QMessageBox.warning(self, "Missing output", "Pick an output GeoPackage path.")
            return

        mode = self.mode_combo.currentData()
        if mode == "text" and not self.prompt_edit.text().strip():
            QMessageBox.warning(self, "Missing prompt", "Enter a text prompt.")
            return
        if mode == "points" and not self._points:
            QMessageBox.warning(self, "Missing points", "Click at least one point on the map.")
            return

        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Loading model and embeddings…")

        self._task = _SamTask(
            mode=mode,
            raster_path=Path(raster),
            out_path=self._out_path,
            model=self.model_combo.currentData(),
            prompt=self.prompt_edit.text() if mode == "text" else None,
            points=list(self._points) if mode == "points" else None,
            box_threshold=self.box_threshold.value(),
            text_threshold=self.text_threshold.value(),
        )
        self._task.progressChanged.connect(self.progress.setValue)
        self._task.statusChanged.connect(self.status.setText)
        self._task.taskCompleted.connect(self._on_done)
        self._task.taskTerminated.connect(self._on_failed)
        QgsApplication.taskManager().addTask(self._task)

    def _on_done(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        if self._task and self._task.result_path:
            layer = QgsVectorLayer(str(self._task.result_path), self._task.result_path.stem, "ogr")
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            self.status.setText(f"Done — wrote {self._task.result_path.name}")
            self.iface.messageBar().pushSuccess(
                "Terranova", f"Segmented {self._task.result_path.name}"
            )

    def _on_failed(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Task failed."
        self.status.setText(err)
        QMessageBox.critical(self, "SAM segmentation failed", err)


# --------------------------------------------------------------------------- #
class _SamTask(QgsTask):
    statusChanged = pyqtSignal(str)

    def __init__(
        self,
        mode: str,
        raster_path: Path,
        out_path: Path,
        model: str,
        prompt: str | None,
        points: list[tuple[float, float]] | None,
        box_threshold: float,
        text_threshold: float,
    ) -> None:
        super().__init__(f"Terranova: SAM {raster_path.name}", QgsTask.CanCancel)
        self.mode = mode
        self.raster_path = raster_path
        self.out_path = out_path
        self.model = model
        self.prompt = prompt
        self.points = points or []
        self.box_threshold = box_threshold
        self.text_threshold = text_threshold
        self.result_path: Path | None = None
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            from ...core.ml.sam import segment_from_points, segment_from_text

            self._emit(10, "Running SAM…")
            if self.mode == "text":
                self.result_path = segment_from_text(
                    self.raster_path,
                    self.out_path,
                    prompt=self.prompt or "",
                    box_threshold=self.box_threshold,
                    text_threshold=self.text_threshold,
                    model=self.model,  # type: ignore[arg-type]
                    progress_cb=lambda p: self._emit(10 + p * 85, ""),
                )
            else:
                self.result_path = segment_from_points(
                    self.raster_path,
                    self.out_path,
                    points=self.points,
                    model=self.model,  # type: ignore[arg-type]
                    progress_cb=lambda p: self._emit(10 + p * 85, ""),
                )
            self._emit(100, "Done.")
            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"SAM segmentation failed: {exc!r}",
                "Terranova",
                Qgis.MessageLevel.Critical,
            )
            return False

    def _emit(self, percent: float, status: str) -> None:
        self.setProgress(percent)
        if status:
            self.statusChanged.emit(status)
            QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
