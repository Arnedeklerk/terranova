"""Shared pytest configuration.

We register custom markers so ``pytest -m unit`` / ``-m integration`` work
without warnings, and we add a ``--runqgis`` opt-in flag so QGIS-host tests
are skipped by default (CI on the matrix-builders runs them with the flag).
"""

from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: pure-Python core tests; no QGIS required")
    config.addinivalue_line("markers", "integration: tests that touch external resources")
    config.addinivalue_line("markers", "qgis: tests that need a QGIS host (pytest-qgis)")
    config.addinivalue_line("markers", "gpu: tests that need a CUDA GPU")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--runqgis",
        action="store_true",
        default=False,
        help="Run tests marked with @pytest.mark.qgis",
    )
    parser.addoption(
        "--rungpu",
        action="store_true",
        default=False,
        help="Run tests marked with @pytest.mark.gpu",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_qgis = pytest.mark.skip(reason="needs --runqgis")
    skip_gpu = pytest.mark.skip(reason="needs --rungpu")
    if not config.getoption("--runqgis"):
        for item in items:
            if "qgis" in item.keywords:
                item.add_marker(skip_qgis)
    if not config.getoption("--rungpu"):
        for item in items:
            if "gpu" in item.keywords:
                item.add_marker(skip_gpu)
