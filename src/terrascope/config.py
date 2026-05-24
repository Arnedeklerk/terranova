"""Per-user TerraScope settings — distinct from per-project state and from
telemetry settings.  Things like default endpoint, default classifier, max
parallel tasks, etc.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .core.models import ClassifierKind, STACEndpoint


@dataclass(slots=True)
class Settings:
    """Global per-user TerraScope preferences."""

    default_endpoint: STACEndpoint = STACEndpoint.PLANETARY_COMPUTER
    default_classifier: ClassifierKind = ClassifierKind.RANDOM_FOREST
    max_parallel_tasks: int = 4
    onnx_prefer_gpu: bool = False
    theme: str = "auto"  # "auto" / "light" / "dark"


def _path() -> Path:
    try:
        import platformdirs

        return Path(platformdirs.user_config_dir("terrascope")) / "settings.json"
    except ImportError:  # pragma: no cover
        return Path.home() / ".config" / "terrascope" / "settings.json"


def load() -> Settings:
    p = _path()
    if not p.exists():
        return Settings()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return Settings(
            default_endpoint=STACEndpoint(raw.get("default_endpoint", "planetary_computer")),
            default_classifier=ClassifierKind(raw.get("default_classifier", "random_forest")),
            max_parallel_tasks=int(raw.get("max_parallel_tasks", 4)),
            onnx_prefer_gpu=bool(raw.get("onnx_prefer_gpu", False)),
            theme=str(raw.get("theme", "auto")),
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        return Settings()


def save(s: Settings) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    raw = asdict(s)
    raw["default_endpoint"] = s.default_endpoint.value
    raw["default_classifier"] = s.default_classifier.value
    p.write_text(json.dumps(raw, indent=2), encoding="utf-8")
