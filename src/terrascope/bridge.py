"""QWebChannel host — Python ↔ embedded React panel.

Sits between :class:`QWebEngineView` (web tier) and :class:`Controllers`
(domain dispatch).  Two channels:

- ``invoke(action, payload)`` — sync request/response (returns JSON string)
- ``event`` (signal) — Python pushes events the web tier subscribes to
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot

from .controllers import Controllers
from .core.models import CommandMessage, CommandResult

if TYPE_CHECKING:  # pragma: no cover
    pass


class Bridge(QObject):
    """QObject exposed to the web tier over QWebChannel."""

    event = pyqtSignal(str)  # JSON-encoded message → web

    def __init__(self, controllers: Controllers | None = None) -> None:
        super().__init__()
        self.controllers = controllers or Controllers()

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

    def push_event(self, payload: dict) -> None:
        """Send an event to the web tier.  Safe to call from the GUI thread."""
        import json

        self.event.emit(json.dumps(payload))
