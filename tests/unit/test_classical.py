"""Tests for ``core.ml.classical.build_estimator`` and related helpers.

We pin only the public surface — exact hyperparameter defaults can shift
with sklearn versions and that's fine.
"""

from __future__ import annotations

import pytest

sklearn = pytest.importorskip("sklearn")

from terranova.core.ml.classical import build_estimator  # noqa: E402
from terranova.core.models import ClassifierConfig, ClassifierKind  # noqa: E402

pytestmark = pytest.mark.unit


def test_random_forest_is_a_classifier() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.RANDOM_FOREST))
    assert type(est).__name__ == "RandomForestClassifier"


def test_extra_trees() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.EXTRA_TREES))
    assert type(est).__name__ == "ExtraTreesClassifier"


def test_gradient_boosting() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.GRADIENT_BOOSTING))
    assert type(est).__name__ == "HistGradientBoostingClassifier"


def test_knn() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.KNN))
    assert type(est).__name__ == "KNeighborsClassifier"


def test_logistic_regression() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.LOGISTIC_REGRESSION))
    assert type(est).__name__ == "LogisticRegression"


def test_mlp() -> None:
    est = build_estimator(ClassifierConfig(kind=ClassifierKind.MLP))
    assert type(est).__name__ == "MLPClassifier"


def test_random_state_passed_through() -> None:
    cfg = ClassifierConfig(kind=ClassifierKind.RANDOM_FOREST, random_state=123)
    est = build_estimator(cfg)
    assert getattr(est, "random_state", None) == 123


def test_hyperparameters_passed_through() -> None:
    cfg = ClassifierConfig(
        kind=ClassifierKind.RANDOM_FOREST,
        hyperparameters={"n_estimators": 42, "min_samples_leaf": 3},
    )
    est = build_estimator(cfg)
    assert est.n_estimators == 42
    assert est.min_samples_leaf == 3


def test_deep_kind_rejected() -> None:
    """Foundation-model kinds aren't classical — should error out clearly."""
    cfg = ClassifierConfig(kind=ClassifierKind.PRITHVI_EO_V2_300)
    with pytest.raises(ValueError, match="classical"):
        build_estimator(cfg)


def test_train_predict_round_trip() -> None:
    """Smoke test: tiny dataset, fit, predict, accuracy >= 0.5."""
    import numpy as np

    from terranova.core.ml.classical import train

    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3)).astype(np.float32)
    y = (X[:, 0] > 0).astype(int)  # learnable

    cfg = ClassifierConfig(kind=ClassifierKind.RANDOM_FOREST)
    est = train(build_estimator(cfg), X, y)
    pred = est.predict(X)
    assert (pred == y).mean() > 0.8
