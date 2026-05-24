"""Non-blocking STAC search — keep the UI responsive on large date ranges."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..core.catalog import stac
from ..core.models import CatalogSearch, STACEndpoint


@dataclass(slots=True)
class CatalogSearchJob:
    cfg: CatalogSearch
    on_results: Callable[[list[dict[str, Any]]], None] | None = None


class CatalogSearchTask(QgsTask):
    """Run a STAC search on a worker thread; deliver items to ``on_results``."""

    def __init__(self, job: CatalogSearchJob) -> None:
        super().__init__("TerraScope: catalogue search", QgsTask.CanCancel)
        self.job = job
        self._results: list[dict[str, Any]] = []
        self._exc: BaseException | None = None

    def run(self) -> bool:
        try:
            client = _open(self.job.cfg.endpoint)
            items = stac.search_s2_l2a(
                client,
                bbox=self.job.cfg.bbox.as_tuple(),
                datetime=self.job.cfg.datetime.as_stac(),
                max_cloud=self.job.cfg.max_cloud,
                limit=self.job.cfg.limit,
            )
            self._results = [
                {
                    "id": it.id,
                    "datetime": str(it.datetime),
                    "cloud": it.properties.get("eo:cloud_cover"),
                    "platform": it.properties.get("platform"),
                }
                for it in items
            ]
            return True
        except Exception as exc:
            self._exc = exc
            return False

    def finished(self, ok: bool) -> None:
        if ok and self.job.on_results is not None:
            self.job.on_results(self._results)
        elif self._exc is not None:
            QgsMessageLog.logMessage(
                f"Catalogue search failed: {self._exc!r}",
                "TerraScope",
                Qgis.MessageLevel.Critical,
            )


def _open(endpoint: STACEndpoint):  # type: ignore[no-untyped-def]
    if endpoint is STACEndpoint.PLANETARY_COMPUTER:
        return stac.open_planetary_computer()
    if endpoint is STACEndpoint.EARTH_SEARCH:
        return stac.open_earth_search()
    if endpoint is STACEndpoint.CDSE:
        return stac.open_cdse()
    raise ValueError(f"unknown endpoint: {endpoint!r}")
