"""The right-side TerraScope dock — holds the welcome screen, project explorer,
and the embedded React panel mounted into a :class:`QWebEngineView`.

QtWebEngine has been safe to embed inside QGIS plugins since 3.36 (per the
3.36 visual changelog).  We import it defensively: on Linux distros that ship
QGIS without ``python3-pyqtwebengine``, we degrade to native widgets only.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import QDockWidget, QLabel, QVBoxLayout, QWidget

from ..bridge import Bridge

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface

WEB_DIST = Path(__file__).parent.parent / "ui_web" / "dist"


class TerraScopeDock(QDockWidget):
    """Right-side dock — welcome screen + embedded React panel."""

    def __init__(self, iface: "QgisInterface") -> None:
        super().__init__("TerraScope")
        self.iface = iface
        self.setObjectName("TerraScopeDock")
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setMinimumWidth(360)

        self.bridge = Bridge()
        self.setWidget(self._build_body())

    # ------------------------------------------------------------------ #
    def _build_body(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            from qgis.PyQt.QtWebChannel import QWebChannel
            from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            layout.addWidget(self._build_fallback())
            return container

        index_html = WEB_DIST / "index.html"
        if not index_html.exists():
            layout.addWidget(self._build_dev_hint())
            return container

        view = QWebEngineView(container)
        channel = QWebChannel(view.page())
        channel.registerObject("bridge", self.bridge)
        view.page().setWebChannel(channel)
        view.setUrl(QUrl.fromLocalFile(str(index_html.resolve())))
        layout.addWidget(view)
        # Keep a reference so the channel is not garbage-collected.
        self._view = view
        self._channel = channel
        return container

    # ------------------------------------------------------------------ #
    def _build_fallback(self) -> QWidget:
        msg = QLabel(
            "QtWebEngine is not available in this QGIS build.\n\n"
            "TerraScope's web panels are disabled, but native dialogs and the\n"
            "Processing algorithms still work.\n\n"
            "On Debian/Ubuntu: sudo apt install python3-pyqtwebengine"
        )
        msg.setWordWrap(True)
        msg.setMargin(16)
        return msg

    def _build_dev_hint(self) -> QWidget:
        msg = QLabel(
            "TerraScope web bundle not found.\n\n"
            "Build it with:  make ui-build\n"
            "Or run the dev server:  make ui-dev\n\n"
            f"Expected at:\n{WEB_DIST / 'index.html'}"
        )
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setMargin(16)
        return msg
