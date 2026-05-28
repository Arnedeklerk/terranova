"""Model explainability: SHAP for tree models, MC-Dropout uncertainty for MLPs.

Currently ships SHAP for sklearn-tree estimators.  Future versions can add SHAP
GradientExplainer for foundation-model heads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np
    from sklearn.base import BaseEstimator


def shap_tree(estimator: "BaseEstimator", X: "np.ndarray", *, max_samples: int = 1000) -> Any:
    """Return a SHAP TreeExplainer output for ``estimator`` on ``X``.

    Tree estimators (RF, ExtraTrees, GBM, LightGBM, XGBoost) support exact
    SHAP via TreeExplainer in O(LD^2) time per sample.  We cap the explanation
    set to ``max_samples`` rows to keep the UI responsive.
    """
    import numpy as np
    import shap

    explainer = shap.TreeExplainer(estimator)
    if X.shape[0] > max_samples:
        rng = np.random.default_rng(0)
        idx = rng.choice(X.shape[0], size=max_samples, replace=False)
        X = X[idx]
    return explainer(X)
