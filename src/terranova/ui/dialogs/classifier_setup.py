"""Classification setup dialog.

Picks an input raster, a training vector layer + class field, a classifier
kind, and an output COG path.  Runs the full ``extract → train → predict_to_cog``
pipeline as a ``QgsTask`` so the GUI stays responsive.
"""

from __future__ import annotations

from dataclasses import dataclass
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


@dataclass(slots=True)
class _ClassifyConfig:
    """Plain bag of UI choices passed to the worker task."""

    raster_path: Path
    vector_path: Path
    class_field: str
    classifier: str
    n_estimators: int
    cv_folds: int
    out_path: Path


class ClassifierSetupDialog(QDialog):
    """Train a classical classifier and apply it to a raster."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_FullClassifyTask | None" = None

        self.setWindowTitle("Terranova — Classify scene")
        self.resize(640, 380)

        self._build_ui()
        self._refresh_layer_combos()

        QgsProject.instance().layersAdded.connect(self._refresh_layer_combos)
        QgsProject.instance().layersRemoved.connect(self._refresh_layer_combos)

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        intro = QLabel(
            "Trains a classifier on every pixel covered by your training "
            "polygons, then applies it to the input raster.\n"
            "Tip: open the Log Messages panel (View → Panels → Log "
            "Messages → Terranova) — diagnostics about the training set "
            "and output land there as the task runs."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#8A93A0; padding-bottom:6px;")
        root.addWidget(intro)

        form = QFormLayout()

        self.raster_combo = QComboBox()
        form.addRow("Input raster", self.raster_combo)

        self.vector_combo = QComboBox()
        self.vector_combo.currentIndexChanged.connect(self._refresh_field_combo)
        form.addRow("Training vector", self.vector_combo)

        self.field_combo = QComboBox()
        form.addRow("Class field", self.field_combo)

        self.classifier_combo = QComboBox()
        # Match the ClassifierKind enum values.
        for label, value in (
            ("Random Forest", "random_forest"),
            ("Extra Trees", "extra_trees"),
            ("Gradient Boosting", "gradient_boosting"),
            ("LightGBM", "lightgbm"),
            ("XGBoost", "xgboost"),
            ("K-Nearest Neighbours", "knn"),
            ("Logistic Regression", "logistic_regression"),
            ("Multi-layer Perceptron", "mlp"),
        ):
            self.classifier_combo.addItem(label, value)
        form.addRow("Classifier", self.classifier_combo)

        self.n_estimators = QSpinBox()
        self.n_estimators.setRange(10, 2000)
        self.n_estimators.setValue(300)
        self.n_estimators.setSingleStep(50)
        self.n_estimators.setToolTip(
            "Number of decision trees in the ensemble (or boosting rounds for "
            "LightGBM / XGBoost).  This is NOT the number of training samples — "
            "training samples are read automatically from every pixel covered by "
            "your training polygons.\n\n"
            "Rule of thumb: 100–500 trees is the sweet spot for Random Forest. "
            "Above 500 you get diminishing returns; below 50 the model under-"
            "averages and noise leaks through.  No effect for KNN / Logistic "
            "Regression / MLP."
        )
        form.addRow("Trees / boosting rounds", self.n_estimators)

        self.cv_folds = QSpinBox()
        self.cv_folds.setRange(2, 10)
        self.cv_folds.setValue(5)
        self.cv_folds.setToolTip(
            "K-fold stratified cross-validation used during accuracy assessment "
            "(not directly used by this dialog yet — the Accuracy Report dialog "
            "is where folds come into play).  Each class must have at least this "
            "many training pixels."
        )
        form.addRow("Cross-validation folds", self.cv_folds)

        out_row = QHBoxLayout()
        self.out_label = QLabel("(temp file)")
        self.out_label.setWordWrap(True)
        out_row.addWidget(self.out_label, stretch=1)
        btn_pick = QPushButton("Browse…")
        btn_pick.clicked.connect(self._pick_output)
        out_row.addWidget(btn_pick)
        out_widget = QWidget()
        out_widget.setLayout(out_row)
        form.addRow("Output COG", out_widget)

        root.addLayout(form)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel()
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        # Action row
        actions = QHBoxLayout()
        self.btn_run = QPushButton("Train + classify")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)
        actions.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        root.addLayout(actions)

        self._out_path: Path | None = None

    # ------------------------------------------------------------------ #
    def _refresh_layer_combos(self) -> None:
        self.raster_combo.clear()
        self.vector_combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.raster_combo.addItem(layer.name(), layer.source())
            elif isinstance(layer, QgsVectorLayer):
                self.vector_combo.addItem(layer.name(), layer.source())
        self._refresh_field_combo()

    def _refresh_field_combo(self) -> None:
        self.field_combo.clear()
        path = self.vector_combo.currentData()
        if not path:
            return
        # Find the active layer to grab fields without re-opening.
        for layer in QgsProject.instance().mapLayers().values():
            if (
                isinstance(layer, QgsVectorLayer)
                and layer.source() == path
                and layer.fields()
            ):
                for f in layer.fields():
                    self.field_combo.addItem(f.name())
                # Best-guess default.
                for guess in ("class", "Class", "CLASS", "label", "category"):
                    idx = self.field_combo.findText(guess)
                    if idx >= 0:
                        self.field_combo.setCurrentIndex(idx)
                        break
                return

    def _pick_output(self) -> None:
        default = str(Path.home() / "terranova_classification.tif")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save classified COG", default, "Cloud-Optimised GeoTIFF (*.tif)"
        )
        if path:
            self._out_path = Path(path)
            self.out_label.setText(path)

    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        try:
            cfg = self._validate()
        except ValueError as e:
            QMessageBox.warning(self, "Missing input", str(e))
            return

        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.status.setText("Extracting training samples…")

        self._task = _FullClassifyTask(cfg)
        # Signals are queued via Qt::AutoConnection so the slots run on the
        # GUI thread even though `progressChanged`/`statusChanged` are emitted
        # from the worker thread.
        self._task.progressChanged.connect(self._on_task_progress)
        self._task.statusChanged.connect(self._on_task_status)
        self._task.taskCompleted.connect(self._on_task_completed)
        self._task.taskTerminated.connect(self._on_task_terminated)
        QgsApplication.taskManager().addTask(self._task)

    def _validate(self) -> _ClassifyConfig:
        raster = self.raster_combo.currentData()
        vector = self.vector_combo.currentData()
        field = self.field_combo.currentText()
        if not raster:
            raise ValueError("Pick an input raster.")
        if not vector:
            raise ValueError("Pick a training vector layer.")
        if not field:
            raise ValueError("Pick the class field on the training layer.")

        out = self._out_path or Path.home() / "terranova_classification.tif"
        return _ClassifyConfig(
            raster_path=Path(raster),
            vector_path=Path(vector),
            class_field=field,
            classifier=self.classifier_combo.currentData(),
            n_estimators=self.n_estimators.value(),
            cv_folds=self.cv_folds.value(),
            out_path=out,
        )

    def _on_task_progress(self, percent: float) -> None:
        # QgsTask reports progress as a percent (0..100, possibly float).
        self.progress.setValue(int(percent))

    def _on_task_status(self, text: str) -> None:
        if text:
            self.status.setText(text)

    def _on_task_completed(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        out_path = self._task.result_path if self._task else None  # type: ignore[union-attr]
        if out_path is not None:
            layer = QgsRasterLayer(str(out_path), out_path.stem)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
            self.status.setText(f"Done — wrote {out_path.name}")
            self.iface.messageBar().pushSuccess("Terranova", f"Classified {out_path.name}")

    def _on_task_terminated(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Cancelled or failed."  # type: ignore[union-attr]
        self.status.setText(err)
        QMessageBox.critical(self, "Classification failed", err)


# --------------------------------------------------------------------------- #
class _FullClassifyTask(QgsTask):
    """Background extract → train → predict → write COG.

    Communicates with the dialog via :class:`QgsTask` built-in signals
    (``progressChanged``, ``taskCompleted``, ``taskTerminated``) plus a custom
    ``statusChanged`` signal — all of which are queued back to the GUI thread
    automatically by Qt::AutoConnection.
    """

    statusChanged = pyqtSignal(str)

    def __init__(self, cfg: _ClassifyConfig) -> None:
        super().__init__(f"Terranova: classify {cfg.raster_path.name}", QgsTask.CanCancel)
        self.cfg = cfg
        self.result_path: Path | None = None
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            from ...core.ml.classical import (
                build_estimator,
                extract_training_samples,
                predict_to_cog,
                train,
            )
            from ...core.models import ClassifierConfig, ClassifierKind

            self._emit(2, "Extracting training samples from polygons…")
            X, y = extract_training_samples(
                self.cfg.raster_path, self.cfg.vector_path, self.cfg.class_field
            )
            if self.isCanceled():
                return False

            import numpy as np

            n_samples = int(X.shape[0])
            unique, counts = np.unique(y, return_counts=True)
            class_breakdown = ", ".join(
                f"class {int(c)}={int(n)}" for c, n in zip(unique, counts, strict=False)
            )
            QgsMessageLog.logMessage(
                f"Training inputs: {n_samples} pixels, {X.shape[1]} bands, "
                f"{len(unique)} classes ({class_breakdown})",
                "Terranova",
                Qgis.MessageLevel.Info,
            )

            if n_samples < 5:
                raise RuntimeError(
                    f"Only {n_samples} valid training pixels found.  Check that\n"
                    "  - the training polygons actually overlap the raster (matching CRS),\n"
                    "  - the raster has valid (non-NaN) values where the polygons cover,\n"
                    "  - the class field on the vector layer is the one you picked."
                )
            if len(unique) < 2:
                raise RuntimeError(
                    f"All {n_samples} training pixels have the same class id "
                    f"({int(unique[0])}).  A classifier needs at least two classes.\n"
                    "  Check: is your class field varying across polygons?  Open the\n"
                    "  attribute table on the vector layer and confirm the values."
                )
            min_count = int(counts.min())
            if min_count < self.cfg.cv_folds:
                QgsMessageLog.logMessage(
                    f"Warning: smallest class has only {min_count} pixels which is below "
                    f"cv_folds={self.cfg.cv_folds}.  Cross-validation may fail; consider "
                    f"reducing CV folds or adding more polygons for that class.",
                    "Terranova",
                    Qgis.MessageLevel.Warning,
                )

            self._emit(10, f"Training {self.cfg.classifier} on {n_samples} pixels…")
            cfg = ClassifierConfig(
                kind=ClassifierKind(self.cfg.classifier),
                hyperparameters={"n_estimators": self.cfg.n_estimators}
                if self.cfg.classifier
                in {"random_forest", "extra_trees", "lightgbm", "xgboost"}
                else {},
                cross_validation_folds=self.cfg.cv_folds,
            )
            estimator = build_estimator(cfg)
            train(estimator, X, y, progress_cb=lambda p: self._emit(10 + p * 20, ""))
            if self.isCanceled():
                return False

            self._emit(30, "Applying classifier to the raster…")
            self.result_path = predict_to_cog(
                estimator,
                self.cfg.raster_path,
                self.cfg.out_path,
                progress_cb=lambda p: self._emit(30 + p * 70, ""),
                cancel_cb=self.isCanceled,
            )

            # Sanity-check the output — read it back and report what class
            # codes ended up in the raster.  If all pixels are the same class
            # something is wrong; the dialog will surface this to the user.
            try:
                import rasterio

                with rasterio.open(self.result_path) as src:
                    out_arr = src.read(1)
                vals, n = np.unique(out_arr, return_counts=True)
                summary = ", ".join(
                    f"class {int(v)}={int(c)}" for v, c in zip(vals, n, strict=False)
                )
                QgsMessageLog.logMessage(
                    f"Output pixel breakdown: {summary}",
                    "Terranova",
                    Qgis.MessageLevel.Info,
                )
                # Excluding nodata (0), how many distinct classes did we end up with?
                non_nodata = vals[vals != 0]
                if non_nodata.size <= 1:
                    QgsMessageLog.logMessage(
                        "Warning: classified raster has at most one non-nodata class — "
                        "the model collapsed to a single prediction.  Common causes: "
                        "training data dominated by one class, all polygons in similar "
                        "spectral neighbourhoods, or wrong band selection on the input "
                        "raster.  Check the Training inputs log line above.",
                        "Terranova",
                        Qgis.MessageLevel.Warning,
                    )
            except Exception as exc:  # noqa: BLE001 — diagnostic only
                QgsMessageLog.logMessage(
                    f"Could not summarise output raster ({exc!r})",
                    "Terranova",
                    Qgis.MessageLevel.Warning,
                )

            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"Classification failed: {exc!r}", "Terranova", Qgis.MessageLevel.Critical
            )
            return False

    def _emit(self, percent: float, status: str) -> None:
        """Safe to call from the worker — both signals are queued by Qt."""
        self.setProgress(percent)  # QgsTask.progressChanged is queued.
        if status:
            self.statusChanged.emit(status)
            QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
