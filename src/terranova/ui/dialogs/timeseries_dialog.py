"""Time-series + change detection dialog.

End-to-end:
  1. STAC search → ItemCollection (reuses Phase-1 catalog code)
  2. Build a Zarr cube (odc-stac → xarray → zarr)
  3. Compute NDVI / NBR / NDMI per time slice
  4. Run CuSum / BFAST / LandTrendr per pixel
  5. Write break-index + magnitude rasters; optional MP4 animation
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsMessageLog,
    QgsProject,
    QgsRasterLayer,
    QgsTask,
)
from qgis.PyQt.QtCore import QDate, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
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


class TimeSeriesDialog(QDialog):
    """Build a cube and detect per-pixel change."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_TimeSeriesTask | None" = None
        self._out_dir: Path | None = None

        self.setWindowTitle("Terranova — Time-series + change detection")
        self.resize(680, 540)
        self._build_ui()
        self._populate_aoi_from_canvas()

    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        form = QFormLayout()

        # --- AOI ---
        bbox_row = QHBoxLayout()
        self.west = QDoubleSpinBox()
        self.south = QDoubleSpinBox()
        self.east = QDoubleSpinBox()
        self.north = QDoubleSpinBox()
        for sb, vmin, vmax in (
            (self.west, -180, 180),
            (self.south, -90, 90),
            (self.east, -180, 180),
            (self.north, -90, 90),
        ):
            sb.setRange(vmin, vmax)
            sb.setDecimals(6)
        for label, sb in (("W", self.west), ("S", self.south), ("E", self.east), ("N", self.north)):
            bbox_row.addWidget(QLabel(label))
            bbox_row.addWidget(sb)
        btn_canvas = QPushButton("Use canvas extent")
        btn_canvas.clicked.connect(self._populate_aoi_from_canvas)
        bbox_row.addWidget(btn_canvas)
        bbox_widget = QWidget()
        bbox_widget.setLayout(bbox_row)
        form.addRow("BBox (WGS84)", bbox_widget)

        # --- date range ---
        today = datetime.utcnow().date()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate(today.year - 3, today.month, 1))
        form.addRow("History start", self.start_date)

        self.monitor_start = QDateEdit()
        self.monitor_start.setCalendarPopup(True)
        self.monitor_start.setDate(QDate(today.year - 1, 1, 1))
        form.addRow("Monitoring start", self.monitor_start)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate(today.year, today.month, today.day))
        form.addRow("End", self.end_date)

        # --- catalog + index ---
        self.endpoint_combo = QComboBox()
        self.endpoint_combo.addItem("Planetary Computer", "planetary_computer")
        self.endpoint_combo.addItem("Earth Search (Element 84)", "earth_search")
        form.addRow("Endpoint", self.endpoint_combo)

        self.index_combo = QComboBox()
        for label, value in (("NDVI", "ndvi"), ("NBR", "nbr"), ("NDMI", "ndmi")):
            self.index_combo.addItem(label, value)
        form.addRow("Index", self.index_combo)

        self.max_cloud = QSpinBox()
        self.max_cloud.setRange(0, 100)
        self.max_cloud.setValue(20)
        self.max_cloud.setSuffix(" %")
        form.addRow("Max cloud cover", self.max_cloud)

        self.resolution = QSpinBox()
        self.resolution.setRange(10, 300)
        self.resolution.setValue(30)
        self.resolution.setSuffix(" m")
        form.addRow("Resolution", self.resolution)

        # --- change method ---
        self.method_combo = QComboBox()
        for label, value in (
            ("CuSum (numpy, no extra deps)", "cusum"),
            ("BFAST Lite (needs bfast pkg, GPU helpful)", "bfast"),
            ("LandTrendr-lite (numpy)", "landtrendr"),
        ):
            self.method_combo.addItem(label, value)
        form.addRow("Method", self.method_combo)

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.5, 10.0)
        self.threshold.setSingleStep(0.5)
        self.threshold.setValue(2.0)
        form.addRow("Threshold (σ for CuSum)", self.threshold)

        self.export_mp4 = QCheckBox("Also export MP4 animation of the index cube")
        self.export_mp4.setChecked(True)
        form.addRow("", self.export_mp4)

        root.addLayout(form)

        # --- output dir ---
        out_row = QHBoxLayout()
        self.out_label = QLabel("(choose output directory…)")
        self.out_label.setWordWrap(True)
        out_row.addWidget(self.out_label, stretch=1)
        out_btn = QPushButton("Browse…")
        out_btn.clicked.connect(self._pick_outdir)
        out_row.addWidget(out_btn)
        out_widget = QWidget()
        out_widget.setLayout(out_row)
        root.addWidget(QLabel("Output directory (cube + rasters + MP4)"))
        root.addWidget(out_widget)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.status = QLabel()
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.btn_run = QPushButton("Build cube + detect change")
        self.btn_run.setDefault(True)
        self.btn_run.clicked.connect(self._on_run)
        actions.addWidget(self.btn_run)
        actions.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        actions.addWidget(btn_close)
        root.addLayout(actions)

    # ------------------------------------------------------------------ #
    def _populate_aoi_from_canvas(self) -> None:
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        src_crs = canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if src_crs == wgs84:
            w, s, e, n = (
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            )
        else:
            xf = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
            sw = xf.transform(extent.xMinimum(), extent.yMinimum())
            ne = xf.transform(extent.xMaximum(), extent.yMaximum())
            w, s, e, n = sw.x(), sw.y(), ne.x(), ne.y()
        self.west.setValue(w)
        self.south.setValue(s)
        self.east.setValue(e)
        self.north.setValue(n)

    def _pick_outdir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Pick output directory", str(Path.home()))
        if path:
            self._out_dir = Path(path)
            self.out_label.setText(path)

    # ------------------------------------------------------------------ #
    def _on_run(self) -> None:
        if not self._out_dir:
            QMessageBox.warning(self, "Missing output", "Pick an output directory.")
            return
        if self.end_date.date() <= self.start_date.date():
            QMessageBox.warning(self, "Invalid range", "End must be after history start.")
            return
        if self.monitor_start.date() < self.start_date.date():
            QMessageBox.warning(
                self,
                "Invalid monitor start",
                "Monitoring start must be on or after history start.",
            )
            return

        self.btn_run.setEnabled(False)
        self.progress.setVisible(True)
        self.status.setText("Searching catalogue…")

        self._task = _TimeSeriesTask(
            bbox=(
                self.west.value(),
                self.south.value(),
                self.east.value(),
                self.north.value(),
            ),
            history_start=self.start_date.date().toPyDate(),
            monitor_start=self.monitor_start.date().toPyDate(),
            end=self.end_date.date().toPyDate(),
            endpoint=self.endpoint_combo.currentData(),
            index_kind=self.index_combo.currentData(),
            max_cloud=self.max_cloud.value(),
            resolution=self.resolution.value(),
            method=self.method_combo.currentData(),
            threshold=self.threshold.value(),
            export_mp4=self.export_mp4.isChecked(),
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
        if not self._task:
            return
        if self._task.break_path and self._task.break_path.exists():
            layer = QgsRasterLayer(str(self._task.break_path), self._task.break_path.stem)
            if layer.isValid():
                QgsProject.instance().addMapLayer(layer)
        self.status.setText(self._task.summary or "Done.")
        self.iface.messageBar().pushSuccess(
            "Terranova", "Change-detection rasters written."
        )

    def _on_failed(self) -> None:
        self.progress.setVisible(False)
        self.btn_run.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Task failed."
        self.status.setText(err)
        QMessageBox.critical(self, "Time-series failed", err)


# --------------------------------------------------------------------------- #
class _TimeSeriesTask(QgsTask):
    statusChanged = pyqtSignal(str)

    def __init__(
        self,
        bbox: tuple[float, float, float, float],
        history_start,  # type: ignore[no-untyped-def]
        monitor_start,  # type: ignore[no-untyped-def]
        end,  # type: ignore[no-untyped-def]
        endpoint: str,
        index_kind: str,
        max_cloud: int,
        resolution: int,
        method: str,
        threshold: float,
        export_mp4: bool,
        out_dir: Path,
    ) -> None:
        super().__init__("Terranova: time-series", QgsTask.CanCancel)
        self.bbox = bbox
        self.history_start = history_start
        self.monitor_start = monitor_start
        self.end = end
        self.endpoint = endpoint
        self.index_kind = index_kind
        self.max_cloud = max_cloud
        self.resolution = resolution
        self.method = method
        self.threshold = threshold
        self.export_mp4 = export_mp4
        self.out_dir = out_dir
        self.break_path: Path | None = None
        self.magnitude_path: Path | None = None
        self.mp4_path: Path | None = None
        self.summary: str | None = None
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            import numpy as np

            from ...core.catalog import stac as cstac
            from ...core.models import STACEndpoint
            from ...core.stacking.cloudmask import mask_from_scl
            from ...core.timeseries.change import detect_change
            from ...core.timeseries.indices import (
                _normalised_difference,  # type: ignore[attr-defined]
            )

            # ---- 1. STAC search ---------------------------------------- #
            self._emit(5, "Searching catalogue…")
            client = (
                cstac.open_planetary_computer()
                if STACEndpoint(self.endpoint) is STACEndpoint.PLANETARY_COMPUTER
                else cstac.open_earth_search()
            )
            items = cstac.search_s2_l2a(
                client,
                bbox=self.bbox,
                datetime=f"{self.history_start.isoformat()}/{self.end.isoformat()}",
                max_cloud=self.max_cloud,
                limit=500,
            )
            n = len(list(items))
            if n == 0:
                raise RuntimeError("No items matched the catalogue search.")
            self._emit(10, f"Found {n} scenes — loading lazy cube…")

            # ---- 2. Lazy cube + cloud mask ----------------------------- #
            import odc.stac

            band_names = self._bands_for_index()
            extra_bands = ["scl"] if self.index_kind in {"ndvi", "nbr", "ndmi"} else []
            cube = odc.stac.load(
                items,
                bands=list(band_names) + extra_bands,
                resolution=self.resolution,
                bbox=self.bbox,
                chunks={"x": 1024, "y": 1024},
            )
            if "scl" in cube.data_vars:
                self._emit(20, "Applying SCL cloud mask…")
                cube = mask_from_scl(cube, cube["scl"])

            # ---- 3. Compute index per time slice ----------------------- #
            self._emit(30, f"Computing {self.index_kind.upper()} per time…")
            index_da = self._compute_index(cube, _normalised_difference)
            index_da = index_da.persist()  # trigger dask compute

            # ---- 4. Per-pixel change detection ------------------------- #
            self._emit(55, f"Running {self.method} per pixel…")
            monitor_index = int(
                (np.array(index_da.time.values) >= np.datetime64(self.monitor_start))
                .argmax()
            )
            change = detect_change(
                index_da,
                method=self.method,  # type: ignore[arg-type]
                monitor_start_index=monitor_index,
                threshold=self.threshold,
                progress_cb=lambda p: self._emit(55 + p * 30, ""),
            )
            if self.isCanceled():
                return False

            # ---- 5. Write rasters -------------------------------------- #
            self._emit(88, "Writing rasters…")
            self.out_dir.mkdir(parents=True, exist_ok=True)
            self.break_path = self.out_dir / f"{self.index_kind}_break_index.tif"
            self.magnitude_path = self.out_dir / f"{self.index_kind}_magnitude.tif"
            change["break_index"].rio.write_crs(index_da.rio.crs).rio.to_raster(
                str(self.break_path), compress="deflate"
            )
            change["magnitude"].rio.write_crs(index_da.rio.crs).rio.to_raster(
                str(self.magnitude_path), compress="deflate"
            )

            # ---- 6. Optional MP4 --------------------------------------- #
            if self.export_mp4:
                try:
                    from ...core.viz.figures import export_animation

                    self._emit(95, "Rendering MP4…")
                    self.mp4_path = self.out_dir / f"{self.index_kind}_timeseries.mp4"
                    export_animation(index_da, self.mp4_path, fps=4)
                except Exception as exc:
                    QgsMessageLog.logMessage(
                        f"MP4 export skipped: {exc!r}",
                        "Terranova",
                        Qgis.MessageLevel.Warning,
                    )

            self.summary = (
                f"Done — {n} scenes, {self.method}, break={self.break_path.name}"
            )
            self._emit(100, self.summary)
            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"Time-series task failed: {exc!r}",
                "Terranova",
                Qgis.MessageLevel.Critical,
            )
            return False

    def _bands_for_index(self) -> tuple[str, ...]:
        if self.index_kind == "ndvi":
            return ("red", "nir")
        if self.index_kind == "nbr":
            return ("nir", "swir22")
        if self.index_kind == "ndmi":
            return ("nir", "swir16")
        raise ValueError(f"unknown index: {self.index_kind!r}")

    def _compute_index(self, cube, nd_fn):  # type: ignore[no-untyped-def]
        bands = self._bands_for_index()
        a = cube[bands[0]].astype("float32")
        b = cube[bands[1]].astype("float32")
        if self.index_kind == "ndvi":
            return nd_fn(b, a)  # (nir - red)/(nir+red)
        if self.index_kind == "nbr":
            return nd_fn(a, b)
        if self.index_kind == "ndmi":
            return nd_fn(a, b)
        raise ValueError(self.index_kind)

    def _emit(self, percent: float, status: str) -> None:
        self.setProgress(percent)
        if status:
            self.statusChanged.emit(status)
            QgsMessageLog.logMessage(status, "Terranova", Qgis.MessageLevel.Info)
