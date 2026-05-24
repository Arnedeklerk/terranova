"""STAC catalogue search dialog — Phase 1.

A native QtWidgets dialog so the search workflow doesn't depend on the React
panel being built.  AOI defaults to the current canvas extent; users can pick
a different vector layer's bounding box.  Searches run in a background
``CatalogSearchTask`` so the dialog stays responsive.

Selecting a row and clicking *Download as COG* materialises the chosen item
to disk via ``odc-stac`` and adds it to the active QGIS project.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRasterLayer,
)
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


class CatalogSearchDialog(QDialog):
    """STAC catalogue search dialog (Sentinel-2 L2A across PC / ES / CDSE)."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task = None
        self._items: list[dict[str, Any]] = []

        self.setWindowTitle("TerraScope — Catalogue Search")
        self.resize(820, 560)

        self._build_ui()
        self._populate_aoi_from_canvas()

    # ------------------------------------------------------------------ #
    # UI                                                                 #
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # ---- form ---------------------------------------------------- #
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)

        self.endpoint_combo = QComboBox()
        self.endpoint_combo.addItem("Planetary Computer", "planetary_computer")
        self.endpoint_combo.addItem("Earth Search (Element 84)", "earth_search")
        self.endpoint_combo.addItem("Copernicus Data Space", "cdse")
        form.addRow("Endpoint", self.endpoint_combo)

        self.collection_combo = QComboBox()
        self.collection_combo.addItem("Sentinel-2 L2A", "sentinel-2-l2a")
        self.collection_combo.addItem("Landsat C2 L2", "landsat-c2-l2")
        form.addRow("Collection", self.collection_combo)

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
            sb.setSingleStep(0.1)
        for label, sb in (("W", self.west), ("S", self.south), ("E", self.east), ("N", self.north)):
            bbox_row.addWidget(QLabel(label))
            bbox_row.addWidget(sb)
        self.btn_aoi_canvas = QPushButton("Use canvas extent")
        self.btn_aoi_canvas.clicked.connect(self._populate_aoi_from_canvas)
        bbox_row.addWidget(self.btn_aoi_canvas)
        bbox_widget = QWidget()
        bbox_widget.setLayout(bbox_row)
        form.addRow("BBox (WGS84)", bbox_widget)

        today = datetime.utcnow().date()
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(_qdate(today - timedelta(days=120)))
        form.addRow("Start date", self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(_qdate(today))
        form.addRow("End date", self.end_date)

        self.max_cloud = QSpinBox()
        self.max_cloud.setRange(0, 100)
        self.max_cloud.setValue(20)
        self.max_cloud.setSuffix(" %")
        form.addRow("Max cloud cover", self.max_cloud)

        self.limit = QSpinBox()
        self.limit.setRange(1, 500)
        self.limit.setValue(25)
        form.addRow("Limit", self.limit)

        root.addWidget(form_widget)

        # ---- search button + progress ------------------------------- #
        action_row = QHBoxLayout()
        self.btn_search = QPushButton("Search")
        self.btn_search.setDefault(True)
        self.btn_search.clicked.connect(self._on_search)
        action_row.addWidget(self.btn_search)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # busy indicator
        self.progress.setVisible(False)
        action_row.addWidget(self.progress, stretch=1)
        root.addLayout(action_row)

        # ---- results table ------------------------------------------ #
        self.results = QTableWidget(0, 4)
        self.results.setHorizontalHeaderLabels(["ID", "Datetime", "Cloud (%)", "Platform"])
        self.results.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.results.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        root.addWidget(self.results, stretch=1)

        # ---- footer buttons ----------------------------------------- #
        footer = QHBoxLayout()
        self.btn_download = QPushButton("Download selected as COG…")
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._on_download)
        footer.addWidget(self.btn_download)
        footer.addStretch()
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)
        root.addLayout(footer)

        self.results.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------ #
    # AOI helpers                                                        #
    # ------------------------------------------------------------------ #
    def _populate_aoi_from_canvas(self) -> None:
        canvas = self.iface.mapCanvas()
        extent = canvas.extent()
        src_crs = canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if src_crs == wgs84:
            west, south, east, north = (
                extent.xMinimum(),
                extent.yMinimum(),
                extent.xMaximum(),
                extent.yMaximum(),
            )
        else:
            xform = QgsCoordinateTransform(src_crs, wgs84, QgsProject.instance())
            sw = xform.transform(extent.xMinimum(), extent.yMinimum())
            ne = xform.transform(extent.xMaximum(), extent.yMaximum())
            west, south, east, north = sw.x(), sw.y(), ne.x(), ne.y()
        self.west.setValue(west)
        self.south.setValue(south)
        self.east.setValue(east)
        self.north.setValue(north)

    def _bbox(self) -> tuple[float, float, float, float]:
        return (
            self.west.value(),
            self.south.value(),
            self.east.value(),
            self.north.value(),
        )

    def _datetime_string(self) -> str:
        s = self.start_date.date().toString("yyyy-MM-dd")
        e = self.end_date.date().toString("yyyy-MM-dd")
        return f"{s}/{e}"

    # ------------------------------------------------------------------ #
    # Search                                                             #
    # ------------------------------------------------------------------ #
    def _on_search(self) -> None:
        try:
            self._validate_inputs()
        except ValueError as e:
            QMessageBox.warning(self, "Invalid input", str(e))
            return

        self.results.setRowCount(0)
        self.btn_download.setEnabled(False)
        self.btn_search.setEnabled(False)
        self.progress.setVisible(True)

        # Import here so the dialog module loads cheaply.
        from ...core.models import BBox, CatalogSearch, DateRange, STACEndpoint
        from ...tasks.catalog_task import CatalogSearchJob, CatalogSearchTask

        west, south, east, north = self._bbox()
        cfg = CatalogSearch(
            endpoint=STACEndpoint(self.endpoint_combo.currentData()),
            collection=self.collection_combo.currentData(),
            bbox=BBox(west=west, south=south, east=east, north=north),
            datetime=DateRange(
                start=datetime.combine(self.start_date.date().toPyDate(), datetime.min.time()),
                end=datetime.combine(self.end_date.date().toPyDate(), datetime.max.time()),
            ),
            max_cloud=self.max_cloud.value(),
            limit=self.limit.value(),
        )
        self._task = CatalogSearchTask(CatalogSearchJob(cfg=cfg, on_results=self._on_results))
        self._task.taskTerminated.connect(self._on_task_done)
        self._task.taskCompleted.connect(self._on_task_done)
        QgsApplication.taskManager().addTask(self._task)

    def _validate_inputs(self) -> None:
        w, s, e, n = self._bbox()
        if e <= w:
            raise ValueError("East must be greater than West.")
        if n <= s:
            raise ValueError("North must be greater than South.")
        if self.end_date.date() < self.start_date.date():
            raise ValueError("End date must be on or after start date.")

    def _on_results(self, items: list[dict[str, Any]]) -> None:
        # Called on the main thread by QgsTask.finished.
        self._items = items
        self.results.setRowCount(len(items))
        for row, item in enumerate(items):
            self._set(row, 0, item.get("id", ""))
            self._set(row, 1, item.get("datetime", ""))
            cloud = item.get("cloud")
            self._set(row, 2, f"{cloud:.1f}" if isinstance(cloud, int | float) else "")
            self._set(row, 3, item.get("platform", "") or "")

    def _on_task_done(self) -> None:
        self.progress.setVisible(False)
        self.btn_search.setEnabled(True)
        if self.results.rowCount() == 0:
            self.iface.messageBar().pushInfo(
                "TerraScope", "No items matched the search criteria."
            )

    def _set(self, row: int, col: int, value: str) -> None:
        self.results.setItem(row, col, QTableWidgetItem(str(value)))

    def _on_selection_changed(self) -> None:
        self.btn_download.setEnabled(len(self.results.selectedItems()) > 0)

    # ------------------------------------------------------------------ #
    # Download                                                           #
    # ------------------------------------------------------------------ #
    def _on_download(self) -> None:
        selected = self.results.selectedItems()
        if not selected:
            return
        row = selected[0].row()
        if row >= len(self._items):
            return
        item = self._items[row]
        default_name = f"{item.get('id', 'scene')}_rgbnir.tif"

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save as COG",
            str(Path.home() / default_name),
            "Cloud-Optimised GeoTIFF (*.tif)",
        )
        if not out_path:
            return

        try:
            self._download_item(item, Path(out_path))
        except Exception as exc:
            QMessageBox.critical(self, "Download failed", f"{type(exc).__name__}: {exc}")
            return

        layer = QgsRasterLayer(out_path, Path(out_path).stem)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            self.iface.messageBar().pushSuccess("TerraScope", f"Added {Path(out_path).name}")
        else:
            QMessageBox.warning(self, "Layer invalid", "QGIS could not open the written raster.")

    def _download_item(self, item_summary: dict[str, Any], out_path: Path) -> None:
        """Re-search for the single item (so we have a real pystac Item), then materialise it."""
        import odc.stac

        from ...core.catalog import stac as catalog_stac
        from ...core.models import STACEndpoint

        endpoint = STACEndpoint(self.endpoint_combo.currentData())
        if endpoint is STACEndpoint.PLANETARY_COMPUTER:
            client = catalog_stac.open_planetary_computer()
        elif endpoint is STACEndpoint.EARTH_SEARCH:
            client = catalog_stac.open_earth_search()
        else:
            client = catalog_stac.open_cdse()

        results = client.search(ids=[item_summary["id"]], max_items=1).item_collection()
        items = list(results)
        if not items:
            raise RuntimeError(f"could not refetch item {item_summary['id']!r}")

        bands = ("red", "green", "blue", "nir")
        cube = odc.stac.load(items, bands=list(bands), resolution=10).isel(time=0)
        cube = cube.rio.clip_box(*self._bbox(), crs="EPSG:4326")
        cube.rio.to_raster(str(out_path), compress="deflate", tiled=True)


# --------------------------------------------------------------------------- #
def _qdate(date) -> Any:  # type: ignore[no-untyped-def]
    """Build a QDate from a python date object (kept out of the type-check noise)."""
    from qgis.PyQt.QtCore import QDate

    return QDate(date.year, date.month, date.day)
