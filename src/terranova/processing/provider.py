"""Terranova Processing provider — registers all algorithms in QGIS Processing."""

from __future__ import annotations

from pathlib import Path

from qgis.core import QgsProcessingProvider

from ..version import __version__
from .indices_algs import NbrAlgorithm, NdmiAlgorithm, NdsiAlgorithm, NdwiAlgorithm
from .ndvi_alg import NdviAlgorithm
from .postprocess_algs import MajorityFilterAlgorithm, SieveAlgorithm

ICON_PATH = Path(__file__).parent.parent / "ui" / "resources" / "icon.svg"


class TerranovaProcessingProvider(QgsProcessingProvider):
    """The provider that owns every Terranova Processing algorithm."""

    def id(self) -> str:
        return "terranova"

    def name(self) -> str:
        return "Terranova"

    def longName(self) -> str:
        return f"Terranova v{__version__}"

    def icon(self):  # type: ignore[no-untyped-def]
        from qgis.PyQt.QtGui import QIcon

        return QIcon(str(ICON_PATH)) if ICON_PATH.exists() else QgsProcessingProvider.icon(self)

    def loadAlgorithms(self) -> None:
        self.addAlgorithm(NdviAlgorithm())
        self.addAlgorithm(NdwiAlgorithm())
        self.addAlgorithm(NdmiAlgorithm())
        self.addAlgorithm(NbrAlgorithm())
        self.addAlgorithm(NdsiAlgorithm())
        self.addAlgorithm(MajorityFilterAlgorithm())
        self.addAlgorithm(SieveAlgorithm())
