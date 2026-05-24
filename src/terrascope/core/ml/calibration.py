"""Probability calibration for tree-based classifiers.

Tree ensembles produce probabilities that are biased toward 0 and 1 (over-
confident).  Calibration via Platt scaling (sigmoid) or isotonic regression
restores well-calibrated probabilities — important when downstream code
makes decisions at non-default thresholds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np
    from sklearn.base import BaseEstimator

Method = Literal["sigmoid", "isotonic"]


def calibrate(
    estimator: "BaseEstimator",
    X: "np.ndarray",
    y: "np.ndarray",
    *,
    method: Method = "isotonic",
    cv: int = 5,
) -> "BaseEstimator":
    """Wrap ``estimator`` in :class:`sklearn.calibration.CalibratedClassifierCV`.

    Returns a fitted calibrated estimator with the same ``predict`` / ``predict_proba``
    surface — caller code shouldn't notice the difference.
    """
    from sklearn.calibration import CalibratedClassifierCV

    cal = CalibratedClassifierCV(estimator, method=method, cv=cv)
    cal.fit(X, y)
    return cal


def brier_score(y_true: "np.ndarray", proba: "np.ndarray") -> float:
    """Multi-class Brier score (lower = better-calibrated probabilities)."""
    import numpy as np
    from sklearn.preprocessing import label_binarize

    classes = np.unique(y_true)
    onehot = label_binarize(y_true, classes=classes).astype(np.float32)
    if onehot.shape[1] == 1:  # binary
        onehot = np.hstack([1.0 - onehot, onehot])
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))
