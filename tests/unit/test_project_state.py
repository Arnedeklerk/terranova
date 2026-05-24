"""Project state round-trip tests."""

from __future__ import annotations

from datetime import datetime

import pytest

from terranova.core.models import (
    BBox,
    CatalogSearch,
    DateRange,
)
from terranova.core.project.state import ProjectState

pytestmark = pytest.mark.unit


def test_round_trip_empty(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "terranova.json"
    state = ProjectState()
    state.save(p)
    loaded = ProjectState.load(p)
    assert loaded.schema_version == 1
    assert loaded.band_sets == []


def test_record_appends_to_ledger() -> None:
    state = ProjectState()
    state.record("test.action", {"k": "v"})
    state.record("test.action.2")
    assert len(state.ledger) == 2
    assert state.ledger[0].action == "test.action"
    assert state.ledger[0].payload == {"k": "v"}


def test_round_trip_with_search(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "terranova.json"
    state = ProjectState(
        last_search=CatalogSearch(
            bbox=BBox(west=0, south=0, east=1, north=1),
            datetime=DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 12, 31)),
            max_cloud=15,
        )
    )
    state.save(p)
    loaded = ProjectState.load(p)
    assert loaded.last_search is not None
    assert loaded.last_search.max_cloud == 15


def test_load_missing_returns_default(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = ProjectState.load(tmp_path / "does-not-exist.json")
    assert state.schema_version == 1
    assert state.band_sets == []


def test_future_schema_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Loading a file from a future plugin version must NOT silently work."""
    import json

    from terranova.core.project.state import ProjectStateMigrationError

    p = tmp_path / "terranova.json"
    p.write_text(json.dumps({"schema_version": 99}), encoding="utf-8")
    with pytest.raises(ProjectStateMigrationError):
        ProjectState.load(p)
