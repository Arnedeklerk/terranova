"""Processing algorithms for the rest of the standard spectral indices.

Each algorithm is a thin Qt wrapper around a numpy function in
:mod:`terrascope.core.timeseries.indices`.  They share the band-pair pattern
of NDVI (``band_a, band_b → float32``) so we expose a single base class to
avoid copy-pasting parameter declarations.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterBand,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)


class _TwoBandIndexAlgorithm(QgsProcessingAlgorithm):
    """Shared boilerplate for two-band normalised-difference indices."""

    INPUT = "INPUT"
    BAND_A = "BAND_A"
    BAND_B = "BAND_B"
    OUTPUT = "OUTPUT"

    # Subclasses override these:
    INDEX_NAME = "INDEX"
    INDEX_LABEL = "Index"
    BAND_A_LABEL = "Band A"
    BAND_B_LABEL = "Band B"
    BAND_A_DEFAULT = 1
    BAND_B_DEFAULT = 2
    HELP = ""

    def name(self) -> str:
        return self.INDEX_NAME.lower()

    def displayName(self) -> str:
        return f"Compute {self.INDEX_NAME}"

    def group(self) -> str:
        return "Indices"

    def groupId(self) -> str:
        return "indices"

    def shortHelpString(self) -> str:
        return self.HELP

    def _index_function(self) -> Callable[[Any, Any], Any]:
        raise NotImplementedError

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Input raster"))
        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND_A,
                self.BAND_A_LABEL,
                parentLayerParameterName=self.INPUT,
                defaultValue=self.BAND_A_DEFAULT,
            )
        )
        self.addParameter(
            QgsProcessingParameterBand(
                self.BAND_B,
                self.BAND_B_LABEL,
                parentLayerParameterName=self.INPUT,
                defaultValue=self.BAND_B_DEFAULT,
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(self.OUTPUT, f"{self.INDEX_NAME} output")
        )

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        try:
            import numpy as np
            import rasterio
        except ImportError as exc:  # pragma: no cover
            raise QgsProcessingException(
                "TerraScope needs numpy and rasterio.  Install them in your QGIS "
                "Python environment (pip install numpy rasterio)."
            ) from exc

        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band_a = self.parameterAsInt(parameters, self.BAND_A, context)
        band_b = self.parameterAsInt(parameters, self.BAND_B, context)
        out_path = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT, context))

        feedback.pushInfo(
            f"Computing {self.INDEX_NAME} from {layer.source()} (bands {band_a}, {band_b})"
        )
        with rasterio.open(layer.source()) as src:
            profile = src.profile
            a = src.read(band_a)
            if feedback.isCanceled():
                return {}
            b = src.read(band_b)

        feedback.setProgress(50)
        result = self._index_function()(a, b)
        feedback.setProgress(80)

        profile.update(
            dtype="float32",
            count=1,
            nodata=float("nan"),
            compress="deflate",
            tiled=True,
            blockxsize=512,
            blockysize=512,
            predictor=3,
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(result.astype(np.float32), 1)
        feedback.setProgress(100)
        feedback.pushInfo(f"Wrote {out_path}")
        return {self.OUTPUT: str(out_path)}


# --------------------------------------------------------------------------- #
class NdwiAlgorithm(_TwoBandIndexAlgorithm):
    INDEX_NAME = "NDWI"
    BAND_A_LABEL = "Green band"
    BAND_B_LABEL = "NIR band"
    BAND_A_DEFAULT = 2
    BAND_B_DEFAULT = 4
    HELP = (
        "Normalised Difference Water Index (McFeeters 1996) — surface water detection.\n\n"
        "NDWI = (Green - NIR) / (Green + NIR), clipped to [-1, 1]."
    )

    def createInstance(self) -> "NdwiAlgorithm":
        return NdwiAlgorithm()

    def _index_function(self) -> Callable[[Any, Any], Any]:
        from ..core.timeseries.indices import ndwi

        return ndwi


class NdmiAlgorithm(_TwoBandIndexAlgorithm):
    INDEX_NAME = "NDMI"
    BAND_A_LABEL = "NIR band"
    BAND_B_LABEL = "SWIR1 band"
    BAND_A_DEFAULT = 4
    BAND_B_DEFAULT = 5
    HELP = (
        "Normalised Difference Moisture Index — vegetation moisture content.\n\n"
        "NDMI = (NIR - SWIR1) / (NIR + SWIR1)."
    )

    def createInstance(self) -> "NdmiAlgorithm":
        return NdmiAlgorithm()

    def _index_function(self) -> Callable[[Any, Any], Any]:
        from ..core.timeseries.indices import ndmi

        return ndmi


class NbrAlgorithm(_TwoBandIndexAlgorithm):
    INDEX_NAME = "NBR"
    BAND_A_LABEL = "NIR band"
    BAND_B_LABEL = "SWIR2 band"
    BAND_A_DEFAULT = 4
    BAND_B_DEFAULT = 6
    HELP = (
        "Normalised Burn Ratio — burn severity mapping.\n\n"
        "NBR = (NIR - SWIR2) / (NIR + SWIR2).  Compute dNBR = NBR_pre - NBR_post."
    )

    def createInstance(self) -> "NbrAlgorithm":
        return NbrAlgorithm()

    def _index_function(self) -> Callable[[Any, Any], Any]:
        from ..core.timeseries.indices import nbr

        return nbr


class NdsiAlgorithm(_TwoBandIndexAlgorithm):
    INDEX_NAME = "NDSI"
    BAND_A_LABEL = "Green band"
    BAND_B_LABEL = "SWIR1 band"
    BAND_A_DEFAULT = 2
    BAND_B_DEFAULT = 5
    HELP = (
        "Normalised Difference Snow Index — snow / ice mapping.\n\n"
        "NDSI = (Green - SWIR1) / (Green + SWIR1)."
    )

    def createInstance(self) -> "NdsiAlgorithm":
        return NdsiAlgorithm()

    def _index_function(self) -> Callable[[Any, Any], Any]:
        from ..core.timeseries.indices import ndsi

        return ndsi
