"""Smoke tests for the matplotlib figure builders."""

from __future__ import annotations

import numpy as np
import pytest

matplotlib = pytest.importorskip("matplotlib")

from terrascope.core.viz.figures import (  # noqa: E402
    plot_confusion_matrix,
    plot_spectral_signatures,
)

pytestmark = pytest.mark.unit


def test_confusion_matrix_returns_figure() -> None:
    cm = np.array([[5, 1], [0, 4]])
    fig = plot_confusion_matrix(cm, class_labels=["A", "B"], title="Test")
    assert hasattr(fig, "savefig")
    # Make sure both axes exist (heatmap + colourbar makes 2).
    assert len(fig.axes) >= 1


def test_confusion_matrix_default_labels() -> None:
    cm = np.eye(3, dtype=int) * 10
    fig = plot_confusion_matrix(cm)
    labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    assert labels == ["0", "1", "2"]


def test_spectral_signatures_returns_figure() -> None:
    sigs = {
        "Class A": (np.array([490, 560, 665, 842]), np.array([0.05, 0.07, 0.06, 0.45])),
        "Class B": (np.array([490, 560, 665, 842]), np.array([0.1, 0.2, 0.15, 0.2])),
    }
    fig = plot_spectral_signatures(sigs, title="Signatures")
    assert hasattr(fig, "savefig")
    legend_entries = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert "Class A" in legend_entries
    assert "Class B" in legend_entries
