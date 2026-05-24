"""Foundation-model fine-tune dialog — Phase 2.

Wraps :func:`terranova.core.ml.foundation.finetune` with a Qt form.  The
user supplies paired training rasters + mask rasters (typically one tile
per scene-of-interest), picks a backbone, kicks off training as a
``QgsTask``.  When done, the checkpoint is exported to ONNX for the fast
inference path.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsMessageLog,
    QgsTask,
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
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


class FoundationDialog(QDialog):
    """Fine-tune Prithvi / Clay / TerraMind on user-supplied scene + mask pairs."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_FoundationTask | None" = None
        self._out_dir: Path | None = None

        self.setWindowTitle("Terranova — Fine-tune foundation model")
        self.resize(680, 480)
        self._build_ui()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        self.backbone_combo = QComboBox()
        for label, value in (
            ("Prithvi-EO-2.0 300M", "prithvi_eo_v2_300"),
            ("Prithvi-EO-2.0 600M", "prithvi_eo_v2_600"),
            ("Clay v1.5", "clay_v1_5"),
            ("TerraMind", "terramind"),
        ):
            self.backbone_combo.addItem(label, value)
        form.addRow("Backbone", self.backbone_combo)

        self.n_classes = QSpinBox()
        self.n_classes.setRange(2, 50)
        self.n_classes.setValue(5)
        form.addRow("Number of classes", self.n_classes)

        self.max_epochs = QSpinBox()
        self.max_epochs.setRange(1, 200)
        self.max_epochs.setValue(20)
        form.addRow("Max epochs", self.max_epochs)

        self.batch_size = QSpinBox()
        self.batch_size.setRange(1, 64)
        self.batch_size.setValue(8)
        form.addRow("Batch size", self.batch_size)

        self.learning_rate = QDoubleSpinBox()
        self.learning_rate.setRange(1e-6, 1e-1)
        self.learning_rate.setDecimals(6)
        self.learning_rate.setValue(1e-4)
        self.learning_rate.setSingleStep(1e-5)
        form.addRow("Learning rate", self.learning_rate)

        self.accelerator_combo = QComboBox()
        for label, value in (("Auto", "auto"), ("GPU (CUDA)", "gpu"), ("CPU", "cpu")):
            self.accelerator_combo.addItem(label, value)
        form.addRow("Accelerator", self.accelerator_combo)

        root.addLayout(form)

        # Training pairs list
        root.addWidget(QLabel("Training scene/mask pairs"))
        self.pairs_list = QListWidget()
        root.addWidget(self.pairs_list, stretch=1)

        pair_btns = QHBoxLayout()
        add_btn = QPushButton("Add scene + mask pair…")
        add_btn.clicked.connect(self._add_pair)
        pair_btns.addWidget(add_btn)
        rm_btn = QPushButton("Remove selected")
        rm_btn.clicked.connect(self._remove_pair)
        pair_btns.addWidget(rm_btn)
        root.addLayout(pair_btns)

        # Output dir
        out_row = QHBoxLayout()
        self.out_label = QLabel("(choose output directory…)")
        self.out_label.setWordWrap(True)
        out_row.addWidget(self.out_label, stretch=1)
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self._pick_outdir)
        out_row.addWidget(out_btn)
        out_widget = QWidget()
        out_widget.setLayout(out_row)
        root.addWidget(QLabel("Output directory (checkpoint + ONNX)"))
        root.addWidget(out_widget)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel()
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.btn_run = QPushButton("Fine-tune")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)
        actions.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    def _add_pair(self) -> None:
        raster, _ = QFileDialog.getOpenFileName(
            self, "Pick a training raster", str(Path.home()), "Rasters (*.tif *.tiff)"
        )
        if not raster:
            return
        mask, _ = QFileDialog.getOpenFileName(
            self,
            "Pick the matching mask raster (single band, class ids)",
            str(Path.home()),
            "Rasters (*.tif *.tiff)",
        )
        if not mask:
            return
        item = QListWidgetItem(f"{Path(raster).name}  ↔  {Path(mask).name}")
        item.setData(0x0100, (raster, mask))  # Qt::UserRole = 0x0100
        self.pairs_list.addItem(item)

    def _remove_pair(self) -> None:
        for item in self.pairs_list.selectedItems():
            self.pairs_list.takeItem(self.pairs_list.row(item))

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pick output directory", str(Path.home()))
        if path:
            self._out_dir = Path(path)
            self.out_label.setText(path)

    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        if self.pairs_list.count() == 0:
            QMessageBox.warning(self, "Missing data", "Add at least one scene + mask pair.")
            return
        if not self._out_dir:
            QMessageBox.warning(self, "Missing output", "Pick an output directory.")
            return

        pairs = []
        for row in range(self.pairs_list.count()):
            item = self.pairs_list.item(row)
            pairs.append(item.data(0x0100))
        train_rasters = [Path(p[0]) for p in pairs]
        train_masks = [Path(p[1]) for p in pairs]

        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Loading backbone weights…")

        self._task = _FoundationTask(
            backbone=self.backbone_combo.currentData(),
            n_classes=self.n_classes.value(),
            max_epochs=self.max_epochs.value(),
            batch_size=self.batch_size.value(),
            learning_rate=self.learning_rate.value(),
            accelerator=self.accelerator_combo.currentData(),
            train_rasters=train_rasters,
            train_masks=train_masks,
            out_dir=self._out_dir,
        )
        self._task.progressChanged.connect(self.progress.setValue)
        self._task.statusChanged.connect(self.status.setText)
        self._task.taskCompleted.connect(self._on_done)
        self._task.taskTerminated.connect(self._on_failed)
        QgsApplication.taskManager().addTask(self._task)

    def _on_done(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        if self._task and self._task.checkpoint_path:
            self.status.setText(
                f"Done — checkpoint at {self._task.checkpoint_path}; "
                f"ONNX at {self._task.onnx_path}"
            )
            self.iface.messageBar().pushSuccess(
                "Terranova", f"Fine-tuned backbone saved to {self._task.checkpoint_path.parent}"
            )

    def _on_failed(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Task failed."
        self.status.setText(err)
        QMessageBox.critical(self, "Fine-tune failed", err)


# --------------------------------------------------------------------------- #
class _FoundationTask(QgsTask):
    statusChanged = pyqtSignal(str)

    def __init__(
        self,
        backbone: str,
        n_classes: int,
        max_epochs: int,
        batch_size: int,
        learning_rate: float,
        accelerator: str,
        train_rasters: list[Path],
        train_masks: list[Path],
        out_dir: Path,
    ) -> None:
        super().__init__(f"Terranova: fine-tune {backbone}", QgsTask.CanCancel)
        self.backbone = backbone
        self.n_classes = n_classes
        self.max_epochs = max_epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.accelerator = accelerator
        self.train_rasters = train_rasters
        self.train_masks = train_masks
        self.out_dir = out_dir
        self.checkpoint_path: Path | None = None
        self.onnx_path: Path | None = None
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            from ...core.ml.foundation import (
                FoundationFinetuneConfig,
                export_finetuned_to_onnx,
                finetune,
            )

            cfg = FoundationFinetuneConfig(
                backbone=self.backbone,  # type: ignore[arg-type]
                n_classes=self.n_classes,
                max_epochs=self.max_epochs,
                batch_size=self.batch_size,
                learning_rate=self.learning_rate,
                accelerator=self.accelerator,
            )
            self._emit(5, f"Training {self.backbone} for {self.max_epochs} epochs…")
            self.checkpoint_path = finetune(
                cfg,
                self.train_rasters,
                self.train_masks,
                out_dir=self.out_dir,
                progress_cb=lambda p: self._emit(5 + p * 90, ""),
            )
            if self.isCanceled():
                return False
            self._emit(95, "Exporting to ONNX…")
            self.onnx_path = export_finetuned_to_onnx(
                self.checkpoint_path,
                self.out_dir / "model.onnx",
                n_input_bands=6,  # Prithvi/Clay/TerraMind all use 6 bands by default.
            )
            self._emit(100, "Done.")
            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"Foundation fine-tune failed: {exc!r}",
                "Terranova",
                Qgis.MessageLevel.Critical,
            )
            return False

    def _emit(self, percent: float, status: str) -> None:
        self.setProgress(percent)
        if status:
            self.statusChanged.emit(status)
            QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
