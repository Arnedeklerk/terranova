"""Sanity-check that pyproject.toml is parseable + has the keys we expect."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    tomllib = pytest.importorskip("tomli")

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "pyproject.toml"


def _data() -> dict:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)


def test_parseable() -> None:
    _data()  # must not raise


def test_project_metadata() -> None:
    d = _data()
    proj = d["project"]
    assert proj["name"] == "terranova"
    assert proj["version"]
    assert proj["requires-python"]
    assert proj["license"]["text"].startswith("GPL")
    assert "anthropic" not in str(d)  # silly canary — should be no leakage


def test_optional_dependency_groups_present() -> None:
    d = _data()
    opt = d["project"]["optional-dependencies"]
    for group in ("ml", "gpu", "timeseries", "dev"):
        assert group in opt, f"pyproject missing optional group: {group}"


def test_cli_entry_point_present() -> None:
    d = _data()
    assert d["project"]["scripts"]["terranova"] == "terranova.cli:main"


def test_version_matches_version_py() -> None:
    from terranova.version import __version__

    d = _data()
    assert d["project"]["version"] == __version__
