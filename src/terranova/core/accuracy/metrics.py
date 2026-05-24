"""Accuracy assessment metrics: confusion matrix, kappa, per-class metrics.

Pure NumPy + scikit-learn; no QGIS, no plotting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


@dataclass(slots=True)
class AccuracyReport:
    """Output of :func:`assess`.

    All arrays are indexed in the order of ``class_labels``.
    """

    class_labels: list[int]
    confusion_matrix: "np.ndarray"   # shape (n_classes, n_classes), int
    overall_accuracy: float
    kappa: float
    producers_accuracy: "np.ndarray"  # 1-D, per class
    users_accuracy: "np.ndarray"      # 1-D, per class
    f1_per_class: "np.ndarray"        # 1-D, per class
    n_samples: int


def assess(y_true: "np.ndarray", y_pred: "np.ndarray") -> AccuracyReport:
    """Compute overall accuracy, kappa, and per-class user's & producer's accuracy.

    Definitions follow Congalton 1991:

    - **User's accuracy** of class *i* is the diagonal cell ``C[i, i]`` divided
      by the row total — the probability that a pixel predicted as *i* truly
      is *i* (commission error complement).
    - **Producer's accuracy** of class *i* is the diagonal divided by the
      column total — the probability that a true-class-*i* pixel is correctly
      labelled (omission error complement).
    """
    import numpy as np
    from sklearn.metrics import (
        cohen_kappa_score,
        confusion_matrix,
        f1_score,
    )

    classes = sorted(set(np.unique(y_true)) | set(np.unique(y_pred)))
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    n = int(cm.sum())
    overall = float(np.trace(cm) / n) if n else 0.0
    kappa = float(cohen_kappa_score(y_true, y_pred, labels=classes))
    row_totals = cm.sum(axis=1)
    col_totals = cm.sum(axis=0)
    diag = np.diag(cm)
    with np.errstate(invalid="ignore", divide="ignore"):
        users = np.where(row_totals > 0, diag / row_totals, np.nan)
        producers = np.where(col_totals > 0, diag / col_totals, np.nan)
    f1 = f1_score(y_true, y_pred, labels=classes, average=None, zero_division=0)
    return AccuracyReport(
        class_labels=[int(c) for c in classes],
        confusion_matrix=cm,
        overall_accuracy=overall,
        kappa=kappa,
        producers_accuracy=np.asarray(producers, dtype=float),
        users_accuracy=np.asarray(users, dtype=float),
        f1_per_class=np.asarray(f1, dtype=float),
        n_samples=n,
    )


def mcnemar_paired(
    y_true: "np.ndarray", y_a: "np.ndarray", y_b: "np.ndarray"
) -> tuple[float, float]:
    """McNemar's test on two classifications of the same pixels.

    Returns ``(statistic, p_value)``.  Useful for "is model A significantly
    better than model B on this scene?".
    """
    import numpy as np
    from statsmodels.stats.contingency_tables import mcnemar

    a_correct = y_a == y_true
    b_correct = y_b == y_true
    n01 = int(np.sum(a_correct & ~b_correct))
    n10 = int(np.sum(~a_correct & b_correct))
    table = np.array([[0, n01], [n10, 0]])
    result = mcnemar(table, exact=False, correction=True)
    return float(result.statistic), float(result.pvalue)
