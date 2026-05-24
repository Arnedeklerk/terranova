"""Per-user settings round-trip tests."""

from __future__ import annotations

import pytest

from terranova import config
from terranova.core.models import ClassifierKind, STACEndpoint

pytestmark = pytest.mark.unit


def test_defaults() -> None:
    s = config.Settings()
    assert s.default_endpoint is STACEndpoint.PLANETARY_COMPUTER
    assert s.default_classifier is ClassifierKind.RANDOM_FOREST
    assert s.max_parallel_tasks == 4


def test_round_trip(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(config, "_path", lambda: tmp_path / "settings.json")
    s = config.Settings(
        default_endpoint=STACEndpoint.EARTH_SEARCH,
        default_classifier=ClassifierKind.LIGHTGBM,
        max_parallel_tasks=8,
        onnx_prefer_gpu=True,
        theme="dark",
    )
    config.save(s)
    loaded = config.load()
    assert loaded.default_endpoint is STACEndpoint.EARTH_SEARCH
    assert loaded.default_classifier is ClassifierKind.LIGHTGBM
    assert loaded.max_parallel_tasks == 8
    assert loaded.onnx_prefer_gpu is True
    assert loaded.theme == "dark"


def test_load_missing_returns_defaults(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(config, "_path", lambda: tmp_path / "no_such.json")
    loaded = config.load()
    assert loaded.default_endpoint is STACEndpoint.PLANETARY_COMPUTER


def test_load_corrupt_returns_defaults(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / "settings.json"
    p.write_text("not json")
    monkeypatch.setattr(config, "_path", lambda: p)
    loaded = config.load()
    assert loaded.default_endpoint is STACEndpoint.PLANETARY_COMPUTER
