"""Architectural guard — ``src/terranova/core/**`` must not import QGIS or Qt.

The domain layer's whole point is to be headlessly testable.  This test scans
every ``.py`` file under ``core/`` and fails if any of them mention the
banned import paths.  Adding a deliberate exception requires editing this
test, which makes the violation impossible to slip in by accident.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

CORE_DIR = Path(__file__).resolve().parents[2] / "src" / "terranova" / "core"
BANNED_TOP_LEVELS = {"qgis", "PyQt5", "PyQt6", "PySide2", "PySide6"}


def _walk_imports(tree: ast.AST):  # type: ignore[no-untyped-def]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


def test_no_qgis_or_qt_imports_in_core() -> None:
    offenders: list[tuple[Path, str]] = []
    for path in CORE_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for module in _walk_imports(tree):
            top = module.split(".")[0]
            if top in BANNED_TOP_LEVELS:
                offenders.append((path, module))
    assert not offenders, (
        "core/ must not import qgis.* or Qt bindings — found:\n"
        + "\n".join(f"  {p.relative_to(CORE_DIR.parent.parent.parent)}: {m}" for p, m in offenders)
    )
