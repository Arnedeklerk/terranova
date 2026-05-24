"""Per-user telemetry settings — persisted JSON next to the installation id."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from uuid import UUID, uuid4

DEFAULT_ENDPOINT = "https://t.terrascope.app/v1/events"


class TelemetryDecision(str, Enum):
    """Tristate consent — we explicitly distinguish "not asked" from "no"."""

    NOT_ASKED = "not_asked"
    OPTED_IN = "opted_in"
    OPTED_OUT = "opted_out"


@dataclass(slots=True)
class TelemetrySettings:
    decision: TelemetryDecision = TelemetryDecision.NOT_ASKED
    installation_id: UUID = field(default_factory=uuid4)
    endpoint: str = DEFAULT_ENDPOINT


def _settings_path() -> Path:
    try:
        import platformdirs

        return Path(platformdirs.user_config_dir("terrascope")) / "telemetry.json"
    except ImportError:  # pragma: no cover
        return Path.home() / ".config" / "terrascope" / "telemetry.json"


def load_settings() -> TelemetrySettings:
    p = _settings_path()
    if not p.exists():
        return TelemetrySettings()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return TelemetrySettings(
            decision=TelemetryDecision(raw["decision"]),
            installation_id=UUID(raw["installation_id"]),
            endpoint=raw.get("endpoint", DEFAULT_ENDPOINT),
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return TelemetrySettings()


def save_settings(s: TelemetrySettings) -> None:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = asdict(s)
    raw["decision"] = s.decision.value
    raw["installation_id"] = str(s.installation_id)
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
