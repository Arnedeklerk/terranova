"""Smoke test: an accuracy PDF is actually written and parses as a PDF."""

from __future__ import annotations

import numpy as np
import pytest

reportlab = pytest.importorskip("reportlab")
matplotlib = pytest.importorskip("matplotlib")

from terrascope.core.accuracy.metrics import AccuracyReport  # noqa: E402
from terrascope.core.accuracy.report import render_pdf  # noqa: E402

pytestmark = pytest.mark.unit


def _fake_report() -> AccuracyReport:
    cm = np.array([[40, 2, 1], [3, 35, 4], [0, 5, 30]])
    return AccuracyReport(
        class_labels=[1, 2, 3],
        confusion_matrix=cm,
        overall_accuracy=0.85,
        kappa=0.78,
        producers_accuracy=np.array([0.93, 0.83, 0.86]),
        users_accuracy=np.array([0.93, 0.83, 0.85]),
        f1_per_class=np.array([0.93, 0.83, 0.85]),
        n_samples=int(cm.sum()),
    )


def test_pdf_is_written(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "report.pdf"
    render_pdf(_fake_report(), out, title="Test Report")
    assert out.exists()
    assert out.stat().st_size > 1024  # some non-trivial content


def test_pdf_starts_with_magic_bytes(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "report.pdf"
    render_pdf(_fake_report(), out)
    assert out.read_bytes()[:5] == b"%PDF-"


def test_class_names_label_override(tmp_path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "report.pdf"
    render_pdf(
        _fake_report(),
        out,
        class_names={1: "Water", 2: "Crops", 3: "Forest"},
    )
    # Confidence check — the file is still a PDF.
    assert out.read_bytes()[:5] == b"%PDF-"
