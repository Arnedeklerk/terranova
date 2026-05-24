"""CDSE OAuth login dialog — Phase 1.

Drives the device-code flow from :mod:`core.catalog.cdse`.  We never embed
the user's password; they sign in to CDSE in their browser, type the
displayed user code, and the plugin polls for the token.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import QUrl, pyqtSignal
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover
    from qgis.gui import QgisInterface


class CdseLoginDialog(QDialog):
    """Run the CDSE device-code flow and surface progress to the user."""

    def __init__(self, iface: "QgisInterface", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.iface = iface
        self._task: "_CdseLoginTask | None" = None

        self.setWindowTitle("Terranova — Sign in to Copernicus Data Space")
        self.resize(520, 280)

        root = QVBoxLayout(self)
        self.headline = QLabel(
            "Sign in to your Copernicus Data Space account to enable CDSE "
            "downloads.  We never see your password — sign-in happens in your "
            "browser."
        )
        self.headline.setWordWrap(True)
        root.addWidget(self.headline)

        self.code_label = QLabel("")
        self.code_label.setStyleSheet("font-family:monospace; font-size:18px;")
        root.addWidget(self.code_label)

        url_row = QHBoxLayout()
        self.url_label = QLabel("")
        self.url_label.setWordWrap(True)
        url_row.addWidget(self.url_label, stretch=1)
        self.open_btn = QPushButton("Open in browser")
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(self._open_browser)
        url_row.addWidget(self.open_btn)
        root.addLayout(url_row)

        self.status = QLabel("Click 'Start sign-in' to begin.")
        self.status.setStyleSheet("color:#8A93A0")
        root.addWidget(self.status)

        actions = QHBoxLayout()
        self.btn_start = QPushButton("Start sign-in")
        self.btn_start.setDefault(True)
        self.btn_start.clicked.connect(self._start)
        actions.addWidget(self.btn_start)

        self.btn_signout = QPushButton("Sign out")
        self.btn_signout.clicked.connect(self._signout)
        actions.addWidget(self.btn_signout)

        actions.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        root.addLayout(actions)

        self._verification_uri: str | None = None

    # ------------------------------------------------------------------ #
    def _start(self) -> None:
        self.btn_start.setEnabled(False)
        self.status.setText("Requesting device code…")
        self._task = _CdseLoginTask()
        self._task.challengeReady.connect(self._on_challenge)
        self._task.statusChanged.connect(self.status.setText)
        self._task.taskCompleted.connect(self._on_done)
        self._task.taskTerminated.connect(self._on_failed)
        QgsApplication.taskManager().addTask(self._task)

    def _on_challenge(self, user_code: str, verification_uri: str) -> None:
        self.code_label.setText(user_code)
        self.url_label.setText(verification_uri)
        self._verification_uri = verification_uri
        self.open_btn.setEnabled(True)

    def _open_browser(self) -> None:
        if self._verification_uri:
            QDesktopServices.openUrl(QUrl(self._verification_uri))

    def _on_done(self) -> None:
        self.btn_start.setEnabled(True)
        self.status.setText("Signed in.  CDSE downloads are enabled.")
        self.iface.messageBar().pushSuccess("Terranova", "Signed in to CDSE.")

    def _on_failed(self) -> None:
        self.btn_start.setEnabled(True)
        err = (self._task.error_text if self._task else None) or "Sign-in failed."
        self.status.setText(err)
        QMessageBox.warning(self, "CDSE sign-in failed", err)

    def _signout(self) -> None:
        from ...core.catalog.cdse import forget_token

        forget_token()
        self.code_label.setText("")
        self.url_label.setText("")
        self.status.setText("Signed out.  Cached token wiped.")
        self.iface.messageBar().pushInfo("Terranova", "Signed out of CDSE.")


# --------------------------------------------------------------------------- #
class _CdseLoginTask(QgsTask):
    challengeReady = pyqtSignal(str, str)  # user_code, verification_uri
    statusChanged = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__("Terranova: CDSE sign-in", QgsTask.CanCancel)
        self.error_text: str | None = None

    def run(self) -> bool:
        try:
            from ...core.catalog.cdse import begin_device_flow, poll_for_token, save_token

            self.statusChanged.emit("Requesting device code…")
            challenge = begin_device_flow()
            self.challengeReady.emit(challenge.user_code, challenge.verification_uri_complete)
            self.statusChanged.emit("Waiting for browser sign-in…")
            token = poll_for_token(
                challenge,
                on_pending=lambda elapsed: self.statusChanged.emit(
                    f"Waiting for browser sign-in… ({int(elapsed)}s)"
                ),
            )
            save_token(token)
            return True
        except Exception as exc:
            self.error_text = f"{type(exc).__name__}: {exc}"
            QgsMessageLog.logMessage(
                f"CDSE sign-in failed: {exc!r}",
                "Terranova",
                Qgis.MessageLevel.Critical,
            )
            return False
