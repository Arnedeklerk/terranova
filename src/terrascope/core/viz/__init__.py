"""Matplotlib visualisation helpers shared between the PDF report and the
JupyterPython API surface.  Pure-Python; no QGIS.
"""

from __future__ import annotations

from .figures import export_animation, plot_confusion_matrix, plot_spectral_signatures

__all__ = ["export_animation", "plot_confusion_matrix", "plot_spectral_signatures"]
