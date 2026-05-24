"""QWebChannel host — Python ↔ embedded React panel.

Sits between :class:`QWebEngineView` (web tier) and :class:`Controllers`
(domain dispatch).  Two channels:

- ``invoke(action, payload)`` — sync request/response (returns JSON string)
- ``event`` (signal) — Python pushes events the web tier subscribes to

For long-running operations, controllers return a ``{job_id: ...}`` from a
sync ``invoke`` and stream progress via :func:`push_event` from a QgsTask.
The React side filters events by ``job_id``.

The Bridge also forwards QGIS message-log entries to the web tier as
``qgis.log`` events so the dock has a live log tail — vital when a task
hangs and the JobProgress bar alone isn't enough to know what's happening.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qgis.PyQt.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

from .controllers import Controllers
from .core.models import CommandMessage, CommandResult

if TYPE_CHECKING:  # pragma: no cover
    pass

# Module-level handle to the currently-active bridge so worker code
# (QgsTask subclasses, controllers) can emit events without holding a
# direct reference to the Bridge instance.  Set in __init__; cleared on
# delete.  Multi-bridge scenarios aren't supported (and don't exist in
# QGIS — one plugin, one dock).
_active_bridge: "Bridge | None" = None


def push_event(payload: dict[str, Any]) -> None:
    """Emit an event to the web tier from anywhere in the Python codebase.

    Safe to call from any thread — the Bridge guarantees the actual signal
    emission happens on the main thread via a queued internal signal hop.
    Logs (rather than silently dropping) if no bridge is active.
    """
    if _active_bridge is None:
        try:
            from qgis.core import Qgis, QgsMessageLog

            QgsMessageLog.logMessage(
                f"push_event dropped (no active bridge): {payload!r}",
                "TerraScope",
                Qgis.MessageLevel.Warning,
            )
        except Exception:  # noqa: BLE001
            pass  # headless tests / no QGIS — keep silent
        return
    _active_bridge.push_event(payload)


class Bridge(QObject):
    """QObject exposed to the web tier over QWebChannel."""

    # Public signal — QWebChannel forwards each emit to JS.
    event = pyqtSignal(str)  # JSON-encoded message → web

    # Internal self-signal used to marshal cross-thread emits onto the main
    # thread.  push_event() emits this; the connected _on_internal slot —
    # which lives on the main thread — does the actual `event.emit(...)`.
    _internal = pyqtSignal(str)

    def __init__(self, controllers: Controllers | None = None) -> None:
        super().__init__()
        self.controllers = controllers or Controllers()
        # Cross-thread marshalling: connect with QueuedConnection so emits
        # from worker threads (QgsTask.run) are queued for the main thread.
        self._internal.connect(self._on_internal, Qt.QueuedConnection)
        # Forward QGIS log messages to the web tier as qgis.log events.
        self._wire_qgis_log()

        global _active_bridge
        _active_bridge = self

    def __del__(self) -> None:  # pragma: no cover
        global _active_bridge
        if _active_bridge is self:
            _active_bridge = None

    # ------------------------------------------------------------------ #
    # Inbound (web → Python)                                             #
    # ------------------------------------------------------------------ #
    @pyqtSlot(str, result=str)
    def invoke(self, raw: str) -> str:
        """Validate → dispatch → return JSON string.

        Errors are returned as ``{ok: False, error: "..."}`` rather than
        raised — Qt slots that raise Python exceptions in a release build
        can crash the host process.
        """
        try:
            msg = CommandMessage.model_validate_json(raw)
        except ValueError as exc:
            return CommandResult(ok=False, error=f"invalid message: {exc}").model_dump_json()
        result = self.controllers.dispatch(msg.action, msg.payload)
        return result.model_dump_json()

    # ------------------------------------------------------------------ #
    # Outbound (Python → web)                                            #
    # ------------------------------------------------------------------ #
    def push_event(self, payload: dict[str, Any]) -> None:
        """Send an event to the web tier.  Safe from any thread.

        Internally hops through ``_internal`` (Qt::QueuedConnection) so the
        actual ``event.emit`` always runs on the main thread, which is
        where QWebChannel forwards from.
        """
        import json

        self._internal.emit(json.dumps(payload))

    @pyqtSlot(str)
    def _on_internal(self, payload_str: str) -> None:
        """Always runs on the Bridge's owner thread (main)."""
        self.event.emit(payload_str)

    # ------------------------------------------------------------------ #
    # QGIS log forwarding                                                #
    # ------------------------------------------------------------------ #
    def _wire_qgis_log(self) -> None:
        """Subscribe to QgsApplication's message log; mirror to qgis.log events.

        Gives the React dock a live log tail.  We forward all messages,
        not just the TerraScope tag, so deep dependency failures
        (rasterio, pystac, etc.) also surface in the UI.
        """
        try:
            from qgis.core import QgsApplication
        except ImportError:  # pragma: no cover — headless tests
            return

        try:
            log = QgsApplication.messageLog()
        except Exception:  # noqa: BLE001
            return

        # messageReceived has different signatures across QGIS versions;
        # the (str, str, Qgis.MessageLevel) flavour has been stable since
        # 3.20.
        try:
            log.messageReceived.connect(self._on_qgis_log)
        except Exception:  # noqa: BLE001
            return

    def _on_qgis_log(self, message: str, tag: str, level: int) -> None:
        """Forward each QGIS log line to the web tier.

        Note: this runs in whatever thread emitted the log, so route it
        through ``push_event`` to get main-thread marshalling for free.
        """
        try:
            self.push_event(
                {
                    "type": "qgis.log",
                    "message": str(message),
                    "tag": str(tag),
                    "level": int(level),
                }
            )
        except Exception:  # noqa: BLE001 — never let logging crash anything
            pass
