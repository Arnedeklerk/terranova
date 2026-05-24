"""Build a time-series Zarr cube from a STAC search — off the GUI thread.

Phase 3 will implement the real ``run`` body.  The class is shipped now so
controllers can target it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qgis.core import Qgis, QgsMessageLog, QgsTask


@dataclass(slots=True)
class CubeJob:
    items: list[Any]            # pystac items
    bands: list[str]
    resolution: int
    out_path: Path
    cloud_mask: str = "omnicloudmask"


class BuildCubeTask(QgsTask):
    """Materialise an odc-stac lazy stack to a Zarr cube on disk."""

    def __init__(self, job: CubeJob) -> None:
        super().__init__(f"TerraScope: build cube {job.out_path.name}", QgsTask.CanCancel)
        self.job = job
        self._exc: BaseException | None = None

    def run(self) -> bool:
        try:
            from ..core.catalog.stac import lazy_stack

            self.setProgress(5)
            stack = lazy_stack(
                self.job.items, bands=tuple(self.job.bands), resolution=self.job.resolution
            )
            self.setProgress(20)
            # Phase 3: cloud mask + dask compute → Zarr.  For now write a
            # single time slice as a smoke test.
            self.job.out_path.parent.mkdir(parents=True, exist_ok=True)
            stack.to_zarr(str(self.job.out_path), mode="w")
            self.setProgress(100)
            return True
        except Exception as exc:
            self._exc = exc
            return False

    def finished(self, ok: bool) -> None:
        if ok:
            QgsMessageLog.logMessage(
                f"Cube ready: {self.job.out_path}",
                "TerraScope",
                Qgis.MessageLevel.Success,
            )
        elif self._exc is not None:
            QgsMessageLog.logMessage(
                f"Cube build failed: {self._exc!r}",
                "TerraScope",
                Qgis.MessageLevel.Critical,
            )
