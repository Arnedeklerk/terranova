"""Command dispatch — maps action strings from the bridge to controller methods.

The dispatch table is the single source of truth for everything the web tier
can ask Python to do.  Adding a new action means:

1. Add a handler method to a controller.
2. Register ``"action.name" → controller.method`` in :meth:`Controllers._register`.
3. Add the corresponding ``invoke("action.name", ...)`` call site in TS.

Every handler must return a JSON-serialisable value; raising ``ValueError``
becomes a ``CommandResult(ok=False, error=...)``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..core.models import CommandResult
from ..version import __version__


class Controllers:
    """Container for all controllers + the dispatch table."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {}
        self._register()

    def _register(self) -> None:
        from . import accuracy as _accuracy
        from . import canvas as _canvas
        from . import catalog as _catalog
        from . import classify as _classify
        from . import dialogs as _dialogs
        from . import layers as _layers

        self._handlers["app.ping"] = self._ping
        self._handlers["app.version"] = self._version
        self._handlers["app.telemetry.status"] = self._telemetry_status
        self._handlers["app.telemetry.set"] = self._telemetry_set
        self._handlers["app.telemetry.inspect"] = self._telemetry_inspect

        # Catalogue + canvas (Phase 1).
        self._handlers["catalog.search"] = _catalog.search
        self._handlers["catalog.download"] = _catalog.download
        self._handlers["catalog.preview_footprint"] = _canvas.preview_footprint
        self._handlers["catalog.clear_preview"] = _canvas.clear_preview
        self._handlers["catalog.pick_aoi.start"] = _canvas.start_aoi_pick
        self._handlers["catalog.pick_aoi.stop"] = _canvas.stop_aoi_pick
        self._handlers["catalog.show_aoi"] = _canvas.show_aoi
        self._handlers["catalog.clear_aoi"] = _canvas.clear_aoi
        self._handlers["canvas.bbox"] = _canvas.bbox

        # Layer + dialog helpers (used by every panel that picks a layer or path).
        self._handlers["layers.list_rasters"] = _layers.list_rasters
        self._handlers["layers.list_vectors"] = _layers.list_vectors
        self._handlers["layers.fields"] = _layers.fields
        self._handlers["dialog.save_file"] = _dialogs.save_file
        self._handlers["dialog.open_file"] = _dialogs.open_file
        self._handlers["dialog.open_directory"] = _dialogs.open_directory

        # Workflow runners — start a QgsTask and return {job_id}, then stream
        # progress via bridge.push_event.
        from . import cdse as _cdse
        from . import foundation as _foundation
        from . import sam as _sam
        from . import timeseries as _timeseries

        self._handlers["classify.run"] = _classify.run
        self._handlers["accuracy.run"] = _accuracy.run
        self._handlers["timeseries.run"] = _timeseries.run
        self._handlers["cdse.signin"] = _cdse.signin
        self._handlers["cdse.status"] = _cdse.status
        self._handlers["cdse.signout"] = _cdse.signout
        self._handlers["sam.run"] = _sam.run
        self._handlers["sam.pick_points.start"] = _sam.start_pick_points
        self._handlers["sam.pick_points.stop"] = _sam.stop_pick_points
        self._handlers["foundation.run"] = _foundation.run

        # Web-sourced training-vector fetchers — long-running, emit
        # task.progress/complete/failed on a job_id.  Used by the
        # Classify panel's 'Find from OSM' / 'Find from WorldCover'
        # buttons.
        from . import training as _training

        self._handlers["training.from_osm"] = _training.from_osm
        self._handlers["training.from_worldcover"] = _training.from_worldcover

    def dispatch(self, action: str, payload: dict[str, Any]) -> CommandResult:
        handler = self._handlers.get(action)
        if handler is None:
            return CommandResult(ok=False, error=f"unknown action: {action!r}")
        try:
            return CommandResult(ok=True, result=handler(payload))
        except Exception as exc:
            return CommandResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ #
    # Handlers                                                           #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _ping(payload: dict[str, Any]) -> dict[str, Any]:
        """Round-trip smoke test for the QWebChannel bridge."""
        return {"pong": True, "echo": payload}

    @staticmethod
    def _version(_payload: dict[str, Any]) -> dict[str, Any]:
        return {"version": __version__}

    @staticmethod
    def _telemetry_status(_payload: dict[str, Any]) -> dict[str, Any]:
        from ..core.telemetry import load_settings

        s = load_settings()
        return {"decision": s.decision.value, "endpoint": s.endpoint}

    @staticmethod
    def _telemetry_set(payload: dict[str, Any]) -> dict[str, Any]:
        from ..core.telemetry import load_settings, save_settings
        from ..core.telemetry.settings import TelemetryDecision

        decision_value = payload.get("decision")
        if decision_value not in {d.value for d in TelemetryDecision}:
            raise ValueError(f"invalid decision: {decision_value!r}")
        s = load_settings()
        s.decision = TelemetryDecision(decision_value)
        save_settings(s)
        return {"decision": s.decision.value}

    @staticmethod
    def _telemetry_inspect(payload: dict[str, Any]) -> dict[str, Any]:
        from ..core.telemetry import inspect_next_payload

        return inspect_next_payload(payload.get("event_name", "preview"))
