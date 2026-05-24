"""Nested cross-validation — for trustworthy accuracy on tuned models.

The standard CV approach over-estimates accuracy when hyperparameters are
tuned on the same folds used to score the model.  Nested CV (Cawley &
Talbot 2010) cleanly separates tuning and scoring: the outer loop scores,
the inner loop tunes inside each outer fold.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..models import ClassifierConfig
from .classical import build_estimator

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


def nested_cross_validate(
    cfg: ClassifierConfig,
    X: "np.ndarray",
    y: "np.ndarray",
    *,
    outer_folds: int = 5,
    tune_fn: Callable[[ClassifierConfig, "np.ndarray", "np.ndarray"], dict[str, Any]] | None = None,
    random_state: int | None = 42,
) -> dict[str, Any]:
    """Outer K-fold around an inner ``tune_fn`` that returns best hyperparameters.

    If ``tune_fn`` is None, falls back to the config's hyperparameters as-is.
    Returns mean OA / F1-macro / balanced-accuracy across outer folds, plus
    the per-fold best hyperparameters (for inspection).
    """
    import numpy as np
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
    from sklearn.model_selection import StratifiedKFold

    outer = StratifiedKFold(n_splits=outer_folds, shuffle=True, random_state=random_state)
    accs: list[float] = []
    f1s: list[float] = []
    bal: list[float] = []
    chosen: list[dict[str, Any]] = []

    for train_idx, test_idx in outer.split(X, y):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        if tune_fn is not None:
            best_hp = tune_fn(cfg, X_tr, y_tr)
            fold_cfg = cfg.model_copy(update={"hyperparameters": best_hp})
        else:
            best_hp = dict(cfg.hyperparameters)
            fold_cfg = cfg

        est = build_estimator(fold_cfg)
        est.fit(X_tr, y_tr)
        pred = est.predict(X_te)

        accs.append(float(accuracy_score(y_te, pred)))
        f1s.append(float(f1_score(y_te, pred, average="macro", zero_division=0)))
        bal.append(float(balanced_accuracy_score(y_te, pred)))
        chosen.append(best_hp)

    return {
        "accuracy_mean": float(np.mean(accs)),
        "accuracy_std": float(np.std(accs)),
        "f1_macro_mean": float(np.mean(f1s)),
        "balanced_accuracy_mean": float(np.mean(bal)),
        "per_fold_hyperparameters": chosen,
    }
