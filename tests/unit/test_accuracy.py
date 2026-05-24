"""Accuracy assessment metrics tests."""

from __future__ import annotations

import numpy as np
import pytest

from terranova.core.accuracy.metrics import assess

pytestmark = pytest.mark.unit


def test_perfect_classification() -> None:
    y_true = np.array([0, 1, 2, 0, 1, 2, 0, 1, 2])
    y_pred = y_true.copy()
    r = assess(y_true, y_pred)
    assert r.overall_accuracy == pytest.approx(1.0)
    assert r.kappa == pytest.approx(1.0)
    np.testing.assert_allclose(r.users_accuracy, [1.0, 1.0, 1.0])
    np.testing.assert_allclose(r.producers_accuracy, [1.0, 1.0, 1.0])


def test_random_classification_kappa_near_zero() -> None:
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 4, size=1000)
    y_pred = rng.integers(0, 4, size=1000)
    r = assess(y_true, y_pred)
    assert abs(r.kappa) < 0.1


def test_class_labels_sorted() -> None:
    y_true = np.array([3, 1, 5, 1, 3, 5])
    y_pred = np.array([1, 1, 5, 3, 3, 5])
    r = assess(y_true, y_pred)
    assert r.class_labels == [1, 3, 5]
    assert r.confusion_matrix.shape == (3, 3)
    assert r.n_samples == 6
