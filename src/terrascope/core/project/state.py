"""``ProjectState`` — the JSON-serialisable, Pydantic-validated bag of state
that TerraScope persists alongside the QGIS project file as ``terrascope.json``.

The state schema is versioned via a literal ``schema_version`` field so future
migrations can be detected on load.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from ..models import CatalogSearch, ClassifierConfig, LedgerEntry

SCHEMA_VERSION = 1


class BandSet(BaseModel):
    """A named subset of bands from a raster — the SCP "Band set" concept."""

    name: str
    raster_paths: list[Path]
    band_names: list[str] = Field(default_factory=list)
    central_wavelengths_nm: list[float] = Field(default_factory=list)


class TrainingDataset(BaseModel):
    """Reference to a training vector layer registered with the project."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    vector_path: Path
    class_field: str
    n_samples: int = 0


class ModelArtefact(BaseModel):
    """A saved classifier — joblib for sklearn, .onnx for inference, .ckpt for Lightning."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    kind: str  # ClassifierKind value
    artefact_path: Path
    onnx_path: Path | None = None
    accuracy: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClassificationResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    raster_path: Path
    model_id: UUID | None = None
    overall_accuracy: float | None = None
    kappa: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectState(BaseModel):
    """The whole TerraScope project, persisted as ``terrascope.json``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION  # type: ignore[assignment]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    last_search: CatalogSearch | None = None
    band_sets: list[BandSet] = Field(default_factory=list)
    training: list[TrainingDataset] = Field(default_factory=list)
    classifiers: list[ClassifierConfig] = Field(default_factory=list)
    models: list[ModelArtefact] = Field(default_factory=list)
    results: list[ClassificationResult] = Field(default_factory=list)
    ledger: list[LedgerEntry] = Field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Persistence                                                        #
    # ------------------------------------------------------------------ #
    @classmethod
    def load(cls, path: Path) -> "ProjectState":
        """Load + validate a ``terrascope.json``.  Returns a fresh state if absent.

        Older schema versions are migrated in-place via :func:`migrate` before
        validation.  Unknown future versions raise rather than silently drop
        fields.
        """
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw = migrate(raw)
        return cls.model_validate(raw)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")

    def record(self, action: str, payload: dict | None = None) -> LedgerEntry:
        """Append a ledger entry and return it (for undo)."""
        entry = LedgerEntry(action=action, payload=payload or {})
        self.ledger.append(entry)
        return entry


# --------------------------------------------------------------------------- #
# Migrations                                                                  #
# --------------------------------------------------------------------------- #
class ProjectStateMigrationError(RuntimeError):
    """Raised when a ``terrascope.json`` from an unknown future version is loaded."""


def migrate(raw: dict) -> dict:
    """Migrate a raw project-state dict to the current :data:`SCHEMA_VERSION`.

    Migrations are stepwise functions registered in :data:`_MIGRATIONS`.
    Loading a state whose ``schema_version`` is *greater than* the current
    code-side version raises — never silently downgrade.
    """
    version = int(raw.get("schema_version", 1))
    if version == SCHEMA_VERSION:
        return raw
    if version > SCHEMA_VERSION:
        raise ProjectStateMigrationError(
            f"terrascope.json schema_version={version} is newer than this "
            f"plugin supports (max {SCHEMA_VERSION}).  Please upgrade TerraScope."
        )
    while version < SCHEMA_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            raise ProjectStateMigrationError(
                f"no migration from schema_version={version} to {version + 1}"
            )
        raw = step(raw)
        version += 1
        raw["schema_version"] = version
    return raw


# {from_version: callable(raw) -> raw_at_next_version}
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {}
