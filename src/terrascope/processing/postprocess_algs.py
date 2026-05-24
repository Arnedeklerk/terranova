"""Processing algorithms for classification post-processing (sieve, majority)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qgis.core import (
    QgsProcessingAlgorithm,
    QgsProcessingContext,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
)


class MajorityFilterAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    SIZE = "SIZE"
    NODATA = "NODATA"
    OUTPUT = "OUTPUT"

    def createInstance(self) -> "MajorityFilterAlgorithm":
        return MajorityFilterAlgorithm()

    def name(self) -> str:
        return "majority_filter"

    def displayName(self) -> str:
        return "Majority filter"

    def group(self) -> str:
        return "Post-processing"

    def groupId(self) -> str:
        return "postprocessing"

    def shortHelpString(self) -> str:
        return (
            "Replace each pixel of a classification raster with the most common\n"
            "value in its size x size window.  Use to smooth salt-and-pepper noise."
        )

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Classification raster"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.SIZE,
                "Window size (odd)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=3,
                minValue=3,
                maxValue=11,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NODATA,
                "Nodata value",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Output"))

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover
            raise QgsProcessingException("Install rasterio in your QGIS Python.") from exc

        from ..core.ml.postprocess import majority_filter

        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        size = self.parameterAsInt(parameters, self.SIZE, context)
        nodata = self.parameterAsInt(parameters, self.NODATA, context)
        out_path = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT, context))

        if size % 2 == 0:
            raise QgsProcessingException(f"Window size must be odd, got {size}")

        with rasterio.open(layer.source()) as src:
            data = src.read(1)
            profile = src.profile

        feedback.setProgress(20)
        out = majority_filter(data, size=size, nodata=nodata)
        feedback.setProgress(80)

        profile.update(count=1, compress="deflate", tiled=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(out, 1)
        feedback.setProgress(100)
        return {self.OUTPUT: str(out_path)}


class SieveAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    MIN_PIXELS = "MIN_PIXELS"
    CONNECTIVITY = "CONNECTIVITY"
    NODATA = "NODATA"
    OUTPUT = "OUTPUT"

    def createInstance(self) -> "SieveAlgorithm":
        return SieveAlgorithm()

    def name(self) -> str:
        return "sieve"

    def displayName(self) -> str:
        return "Sieve filter"

    def group(self) -> str:
        return "Post-processing"

    def groupId(self) -> str:
        return "postprocessing"

    def shortHelpString(self) -> str:
        return (
            "Remove small connected components from a classification raster,\n"
            "reassigning them to the most common neighbouring class.  Pure-Python\n"
            "port of GDAL's sieve filter."
        )

    def initAlgorithm(self, config: dict[str, Any] | None = None) -> None:
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, "Classification raster"))
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MIN_PIXELS,
                "Minimum component size (pixels)",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=4,
                minValue=2,
                maxValue=1_000_000,
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.CONNECTIVITY,
                "Connectivity",
                options=["4", "8"],
                defaultValue=0,
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.NODATA,
                "Nodata value",
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=0,
            )
        )
        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, "Output"))

    def processAlgorithm(
        self,
        parameters: dict[str, Any],
        context: QgsProcessingContext,
        feedback: QgsProcessingFeedback,
    ) -> dict[str, Any]:
        try:
            import rasterio
        except ImportError as exc:  # pragma: no cover
            raise QgsProcessingException("Install rasterio in your QGIS Python.") from exc

        from ..core.ml.postprocess import sieve

        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        min_pixels = self.parameterAsInt(parameters, self.MIN_PIXELS, context)
        connectivity = 4 if self.parameterAsEnum(parameters, self.CONNECTIVITY, context) == 0 else 8
        nodata = self.parameterAsInt(parameters, self.NODATA, context)
        out_path = Path(self.parameterAsOutputLayer(parameters, self.OUTPUT, context))

        with rasterio.open(layer.source()) as src:
            data = src.read(1)
            profile = src.profile

        feedback.setProgress(20)
        out = sieve(data, min_pixels=min_pixels, connectivity=connectivity, nodata=nodata)
        feedback.setProgress(80)

        profile.update(count=1, compress="deflate", tiled=True)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(out, 1)
        feedback.setProgress(100)
        return {self.OUTPUT: str(out_path)}
