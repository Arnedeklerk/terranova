"""Pydantic v2 models for cross-layer state and message validation.

These models are deliberately small and self-contained — they form the wire
format between the UI tiers, the controllers, and the domain layer.
"""

from __future__ import annotations

from datetime import datetime as _dt
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Geographic primitives                                                       #
# --------------------------------------------------------------------------- #
class BBox(BaseModel):
    """A WGS84 axis-aligned bounding box (west, south, east, north)."""

    model_config = ConfigDict(frozen=True)

    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)

    @field_validator("east")
    @classmethod
    def _east_gt_west(cls, v: float, info) -> float:  # type: ignore[no-untyped-def]
        west = info.data.get("west")
        if west is not None and v <= west:
            raise ValueError("east must be > west")
        return v

    @field_validator("north")
    @classmethod
    def _north_gt_south(cls, v: float, info) -> float:  # type: ignore[no-untyped-def]
        south = info.data.get("south")
        if south is not None and v <= south:
            raise ValueError("north must be > south")
        return v

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


class DateRange(BaseModel):
    """Inclusive date range used by STAC ``datetime`` parameter."""

    start: _dt
    end: _dt

    def as_stac(self) -> str:
        return f"{self.start.date().isoformat()}/{self.end.date().isoformat()}"


# --------------------------------------------------------------------------- #
# Catalogue & search                                                          #
# --------------------------------------------------------------------------- #
class STACEndpoint(str, Enum):
    PLANETARY_COMPUTER = "planetary_computer"
    EARTH_SEARCH = "earth_search"
    CDSE = "cdse"


class CatalogSearch(BaseModel):
    """Parameters for a STAC search."""

    endpoint: STACEndpoint = STACEndpoint.PLANETARY_COMPUTER
    collection: str = "sentinel-2-l2a"
    bbox: BBox
    datetime: DateRange
    max_cloud: int = Field(default=30, ge=0, le=100)
    limit: int = Field(default=50, ge=1, le=1000)


# --------------------------------------------------------------------------- #
# Classification                                                              #
# --------------------------------------------------------------------------- #
class ClassifierKind(str, Enum):
    RANDOM_FOREST = "random_forest"
    EXTRA_TREES = "extra_trees"
    GRADIENT_BOOSTING = "gradient_boosting"
    LIGHTGBM = "lightgbm"
    XGBOOST = "xgboost"
    KNN = "knn"
    LOGISTIC_REGRESSION = "logistic_regression"
    MLP = "mlp"
    # Foundation-model variants.
    PRITHVI_EO_V2_300 = "prithvi_eo_v2_300"
    PRITHVI_EO_V2_600 = "prithvi_eo_v2_600"
    CLAY_V1_5 = "clay_v1_5"
    TERRAMIND = "terramind"


class TrainingInput(BaseModel):
    """Labelled training data sourced from a vector layer or drawn ROIs."""

    vector_path: Path
    class_field: str
    feature_bands: list[str] = Field(default_factory=list)


class ClassifierConfig(BaseModel):
    kind: ClassifierKind = ClassifierKind.RANDOM_FOREST
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    cross_validation_folds: int = Field(default=5, ge=2, le=20)
    test_size: float = Field(default=0.2, ge=0.05, le=0.5)
    random_state: int | None = 42


# --------------------------------------------------------------------------- #
# Project state                                                               #
# --------------------------------------------------------------------------- #
class LedgerEntry(BaseModel):
    """One reversible action recorded in the project ledger."""

    id: UUID = Field(default_factory=uuid4)
    timestamp: _dt = Field(default_factory=_dt.utcnow)
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class TelemetryEvent(BaseModel):
    """The exact, minimal shape sent to the telemetry endpoint when opt-in."""

    event_name: str
    plugin_version: str
    qgis_version: str
    os: str
    installation_id: UUID
    timestamp: _dt = Field(default_factory=_dt.utcnow)


# --------------------------------------------------------------------------- #
# UI bridge                                                                   #
# --------------------------------------------------------------------------- #
class CommandMessage(BaseModel):
    """JSON envelope flowing UI → Python via QWebChannel.

    The web tier sends ``{"action": "...", "payload": {...}}``; the controller
    dispatch table picks a handler by ``action`` and validates ``payload``.
    """

    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class CommandResult(BaseModel):
    """JSON envelope flowing Python → UI via QWebChannel."""

    ok: bool
    result: Any = None
    error: str | None = None
    kind: Literal["sync", "async", "stream"] = "sync"
