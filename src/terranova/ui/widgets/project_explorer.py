"""Left-pane tree of band sets, training data, models and results.

(planned).  Stub.
"""

from __future__ import annotations

from qgis.PyQt.QtWidgets import QTreeView, QWidget


class ProjectExplorer(QTreeView):
    """Tree of Terranova project artefacts, sourced from :class:`ProjectState`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
