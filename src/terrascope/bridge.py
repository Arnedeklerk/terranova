"""QWebChannel host — Python ↔ embedded React panel.

Sits between :class:`QWebEngineView` (web tier) and :class:`Controllers`
(domain dispatch).  Two channels:

- ``invoke(action, payload)`` — sync request/response (returns JSON string)
- ``event`` (signal) — Python pushes events the web tier subscribes to

For long-running operations, controllers return a ``{job_id: ...}`` from a
sync ``invoke`` and stream progress via :func:`push_event` from a QgsTask.
The React side filters events by ``job_id``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot

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

    Safe to call from the GUI thread.  Qt queues signal emissions across
    threads, so calling from a QgsTask worker is also safe — the React side
    receives the event on its event loop.  Logs (rather than silently
    dropping) if no bridge is active, so a closed-mid-task dock leaves a
    visible breadcrumb in the QGIS log.
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

    event = pyqtSignal(str)  # JSON-encoded message → web

    def __init__(self, controllers: Controllers | None = None) -> None:
        super().__init__()
        self.controllers = controllers or Controllers()
        global _active_bridge
        _active_bridge = self

    def __del__(self) -> None:  # pragma: no cover
        global _active_bridge
        if _active_bridge is self:
            _active_bridge = None

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

    def push_event(self, payload: dict[str, Any]) -> None:
        """Send an event to the web tier.  Safe to call from the GUI thread."""
        import json

        self.event.emit(json.dumps(payload))
