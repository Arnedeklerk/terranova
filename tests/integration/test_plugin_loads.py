"""Smoke test — does ``import terranova`` and ``classFactory`` work in a QGIS host?

Marked ``@pytest.mark.qgis`` so it is opt-in via ``pytest --runqgis`` (CI on
the QGIS matrix runners passes the flag).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.qgis, pytest.mark.integration]


def test_import_module() -> None:
    import terranova

    assert terranova.__version__


def test_class_factory_returns_plugin() -> None:
    pytest.importorskip("qgis.core")
    from unittest.mock import MagicMock

    import terranova

    iface = MagicMock()
    plugin = terranova.classFactory(iface)
    assert plugin is not None
    # initGui / unload exist
    assert hasattr(plugin, "initGui")
    assert hasattr(plugin, "unload")
