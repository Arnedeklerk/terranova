"""``terranova:ndvi`` — Compute NDVI from a single multi-band raster.

This is the smoke test algorithm.  It deliberately uses only NumPy
and rasterio so it works on a vanilla QGIS install with no optional deps.
"""

from __future__ import annotations

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


class NdviAlgorithm(QgsProcessingAlgorithm):
    """Computes ``(NIR - Red) / (NIR + Red)`` and writes a float32 GeoTIFF."""

    INPUT = "INPUT"
    RED_BAND = "RED_BAND"
    NIR_BAND = "NIR_BAND"
    OUTPUT = "OUTPUT"

    def createInstance(self) -> "NdviAlgorithm":
        return NdviAlgorithm()

    def name(self) -> str:
        return "ndvi"

    def displayName(self) -> str:
        return "Compute NDVI"

    def group(self) -> str:
        return "Indices"

    def groupId(self) -> str:
        return "indices"

    def shortHelpString(self) -> str:
        return (
            "Compute the Normalised Difference Vegetation Index from a single "
            "multi-band raster.\n\n"
            "NDVI = (NIR - Red) / (NIR + Red), clipped to [-1, 1].\n\n"
            "Pixels where NIR + Red == 0 are written as NaN."
        )

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(
            QgsProcessingParameterRasterLayer(self.INPUT, "Input raster")
        )
        self.addParameter(
            QgsProcessingParameterBand(
                self.RED_BAND, "Red band", parentLayerParameterName=self.INPUT, defaultValue=1
            )
        )
        self.addParameter(
            QgsProcessingParameterBand(
                self.NIR_BAND, "NIR band", parentLayerParameterName=self.INPUT, defaultValue=2
            )
        )
        self.addParameter(
            QgsProcessingParameterRasterDestination(self.OUTPUT, "NDVI output")
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
                "Terranova needs numpy and rasterio.  Install them in your QGIS "
                "Python environment (pip install numpy rasterio)."
            ) from exc

        from ..core.timeseries.indices import ndvi

        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        red_band = self.parameterAsInt(parameters, self.RED_BAND, context)
        nir_band = self.parameterAsInt(parameters, self.NIR_BAND, context)
        out_path = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT, context))

        feedback.pushInfo(f"Reading {layer.source()} (bands {red_band}, {nir_band})")
        with rasterio.open(layer.source()) as src:
            profile = src.profile
            red = src.read(red_band)
            if feedback.isCanceled():
                return {}
            nir = src.read(nir_band)

        feedback.setProgress(50)
        out = ndvi(red, nir)
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
            dst.write(out.astype(np.float32), 1)
        feedback.setProgress(100)
        feedback.pushInfo(f"Wrote {out_path}")
        return {self.OUTPUT: str(out_path)}
