"""QGIS-flavoured colour-ramp factory.

Lives outside ``core/`` because it touches ``qgis.*`` / ``PyQt6.*``.  Wraps
:func:`terrascope.core.utils.colormap.sample_ramp` and converts the sampled
RGB stops into a ``QgsGradientColorRamp`` ready to apply via
``QgsSingleBandPseudoColorRenderer`` / ``QgsRasterShader``.
"""

from __future__ import annotations

from qgis.core import QgsGradientColorRamp, QgsGradientStop
from qgis.PyQt.QtGui import QColor

from ..core.utils.colormap import RampKind, sample_ramp


def qgis_colour_ramp(kind: RampKind = "sequential", n_stops: int = 8) -> QgsGradientColorRamp:
    """Build a :class:`QgsGradientColorRamp` matching the chosen Crameri ramp."""
    samples = sample_ramp(kind, n_stops=n_stops)
    start_pos, sr, sg, sb = samples[0]
    end_pos, er, eg, eb = samples[-1]
    stops = [
        QgsGradientStop(pos, QColor.fromRgbF(r, g, b))
        for pos, r, g, b in samples[1:-1]
    ]
    return QgsGradientColorRamp(
        QColor.fromRgbF(sr, sg, sb),
        QColor.fromRgbF(er, eg, eb),
        stops=stops,
    )
