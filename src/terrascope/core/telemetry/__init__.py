"""Opt-in telemetry — see PRIVACY.md.

Off by default.  On first run the dock asks the user, and if they consent a
random UUID is stored in ``platformdirs.user_config_dir("terrascope")``.
Events sent contain only ``event_name``, ``plugin_version``, ``qgis_version``,
``os``, ``installation_id``, and ``timestamp``.  Nothing else.
"""

from __future__ import annotations

from .client import emit, inspect_next_payload
from .settings import TelemetrySettings, load_settings, save_settings

__all__ = [
    "TelemetrySettings",
    "emit",
    "inspect_next_payload",
    "load_settings",
    "save_settings",
]
