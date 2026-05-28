"""Classical (sklearn-family) classifiers and the predict-to-COG path.

Currently ships ``build_estimator`` (which picks a sklearn / LightGBM / XGBoost
estimator from a :class:`ClassifierConfig`) and the shapes of ``train`` and
``predict_to_cog``.  A future version fleshes out the inference loop over dask blocks.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..models import ClassifierConfig, ClassifierKind

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np
    from sklearn.base import BaseEstimator


def build_estimator(cfg: ClassifierConfig) -> "BaseEstimator":
    """Return an unfitted estimator chosen by ``cfg.kind`` with sane defaults.

    LightGBM and XGBoost are imported lazily so a default install does not
    require them.
    """
    hp = dict(cfg.hyperparameters)
    rs = cfg.random_state

    if cfg.kind is ClassifierKind.RANDOM_FOREST:
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=hp.get("n_estimators", 300),
            min_samples_leaf=hp.get("min_samples_leaf", 2),
            n_jobs=-1,
            random_state=rs,
        )
    if cfg.kind is ClassifierKind.EXTRA_TREES:
        from sklearn.ensemble import ExtraTreesClassifier

        return ExtraTreesClassifier(
            n_estimators=hp.get("n_estimators", 400),
            n_jobs=-1,
            random_state=rs,
        )
    if cfg.kind is ClassifierKind.GRADIENT_BOOSTING:
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(random_state=rs, **hp)
    if cfg.kind is ClassifierKind.LIGHTGBM:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(random_state=rs, **hp)
    if cfg.kind is ClassifierKind.XGBOOST:
        from xgboost import XGBClassifier

        return XGBClassifier(
            tree_method="hist",
            n_jobs=-1,
            random_state=rs,
            **hp,
        )
    if cfg.kind is ClassifierKind.KNN:
        from sklearn.neighbors import KNeighborsClassifier

        return KNeighborsClassifier(n_jobs=-1, **hp)
    if cfg.kind is ClassifierKind.LOGISTIC_REGRESSION:
        from sklearn.linear_model import LogisticRegression

        return LogisticRegression(max_iter=1000, n_jobs=-1, random_state=rs, **hp)
    if cfg.kind is ClassifierKind.MLP:
        from sklearn.neural_network import MLPClassifier

        return MLPClassifier(random_state=rs, **hp)
    raise ValueError(f"Not a classical classifier: {cfg.kind!r}")


def train(
    estimator: "BaseEstimator",
    X: "np.ndarray",
    y: "np.ndarray",
    *,
    progress_cb: Callable[[float], None] | None = None,
) -> "BaseEstimator":
    """Fit ``estimator``.  ``progress_cb`` receives a float in [0, 1]."""
    if progress_cb:
        progress_cb(0.0)
    estimator.fit(X, y)
    if progress_cb:
        progress_cb(1.0)
    return estimator


def predict_to_cog(
    estimator: "BaseEstimator",
    raster_path: Path,
    out_path: Path,
    *,
    progress_cb: Callable[[float], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    block_size: int = 1024,
    nodata_input: float | int | None = None,
    nodata_output: int = 0,
    dtype: str = "uint8",
) -> Path:
    """Apply ``estimator`` to ``raster_path`` block-by-block and write a COG.

    The estimator must have been ``fit`` on a feature matrix shaped
    ``(n_samples, n_bands)`` where ``n_bands`` matches the input raster band
    count.  Class codes are written as ``dtype`` (default ``uint8`` — supports
    up to 255 classes).  Pixels with any NaN / nodata value across bands are
    written as ``nodata_output``.

    The output COG uses DEFLATE compression and nearest-neighbour overviews
    (correct for categorical rasters — never use bilinear/cubic on class maps).
    """
    import numpy as np
    import rasterio
    from rio_cogeo import cog_profiles
    from rio_cogeo.cogeo import cog_translate

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = out_path.with_suffix(".tmp.tif")

    with rasterio.open(raster_path) as src:
        profile = src.profile.copy()
        profile.update(
            count=1,
            dtype=dtype,
            nodata=nodata_output,
            compress="deflate",
            tiled=True,
            blockxsize=min(block_size, 512),
            blockysize=min(block_size, 512),
        )
        n_bands = src.count
        height, width = src.height, src.width
        windows = list(_iter_windows(height, width, block_size))
        n_blocks = len(windows)

        with rasterio.open(tmp_path, "w", **profile) as dst:
            for i, win in enumerate(windows):
                if cancel_cb is not None and cancel_cb():
                    raise RuntimeError("classification cancelled by user")

                block = src.read(window=win)  # (n_bands, h, w)
                features = block.reshape(n_bands, -1).T.astype(np.float32, copy=False)

                # Build a mask of pixels with any invalid input band.
                if nodata_input is not None:
                    invalid = (block == nodata_input).any(axis=0).reshape(-1)
                else:
                    invalid = np.isnan(features).any(axis=1)

                # Predict only on valid pixels to save work.
                preds = np.full(features.shape[0], nodata_output, dtype=dtype)
                if (~invalid).any():
                    preds[~invalid] = estimator.predict(features[~invalid]).astype(dtype)

                dst.write(
                    preds.reshape(int(win.height), int(win.width)),
                    1,
                    window=win,
                )

                if progress_cb is not None:
                    progress_cb((i + 1) / n_blocks * 0.9)  # leave 10% for COG

    # Re-write as a proper COG with overviews + LERC/deflate.
    output_profile = cog_profiles.get("deflate")
    cog_translate(
        str(tmp_path),
        str(out_path),
        output_profile,
        overview_resampling="nearest",  # categorical raster — never bilinear
        in_memory=False,
        quiet=True,
    )
    tmp_path.unlink(missing_ok=True)

    if progress_cb is not None:
        progress_cb(1.0)
    return out_path


def _iter_windows(height: int, width: int, block_size: int):  # type: ignore[no-untyped-def]
    """Yield rasterio :class:`Window` covers of an (h, w) raster."""
    from rasterio.windows import Window

    for y0 in range(0, height, block_size):
        h = min(block_size, height - y0)
        for x0 in range(0, width, block_size):
            w = min(block_size, width - x0)
            yield Window(x0, y0, w, h)


def extract_training_samples(
    raster_path: Path,
    vector_path: Path,
    class_field: str,
    *,
    nodata: float | int | None = None,
) -> tuple["np.ndarray", "np.ndarray"]:
    """Sample raster band values at vector training geometries.

    Polygons are densely sampled at every covered pixel; points are sampled at
    the nearest pixel.  Returns ``(X, y)`` where ``X`` is float32 with shape
    ``(n_samples, n_bands)`` and ``y`` is int.  Rows with any nodata value are
    dropped.
    """
    import fiona
    import numpy as np
    import rasterio
    from rasterio import features

    with fiona.open(vector_path) as src, rasterio.open(raster_path) as ras:
        # Reproject vector geoms to raster CRS if needed.
        if src.crs and ras.crs and src.crs != ras.crs:
            from fiona.transform import transform_geom

            geoms = [
                (transform_geom(src.crs, ras.crs, f["geometry"]), f["properties"][class_field])
                for f in src
            ]
        else:
            geoms = [(f["geometry"], f["properties"][class_field]) for f in src]

        # Rasterise the training polygons/points to a class-id raster.
        out_shape = (ras.height, ras.width)
        transform = ras.transform
        shapes_iter = ((g, int(c)) for g, c in geoms if g is not None)
        class_raster = features.rasterize(
            shapes_iter,
            out_shape=out_shape,
            transform=transform,
            fill=0,
            dtype="int32",
        )

        bands = ras.read()  # (n_bands, h, w)

    mask = class_raster > 0
    y = class_raster[mask]
    X = bands[:, mask].T.astype(np.float32, copy=False)

    if nodata is not None:
        keep = (nodata != X).all(axis=1)
        X = X[keep]
        y = y[keep]
    valid = ~np.isnan(X).any(axis=1)
    return X[valid], y[valid]


def tune_hyperparameters(
    cfg: ClassifierConfig,
    X: "np.ndarray",
    y: "np.ndarray",
    *,
    n_trials: int = 30,
    folds: int = 5,
    timeout_seconds: float | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Optuna TPE search for ``cfg.kind`` hyperparameters.

    Returns the best-found hyperparameter dict.  Search space depends on
    the classifier; only the common knobs are tuned here — for an exhaustive
    search, the user should pass overrides via ``cfg.hyperparameters``.
    """
    import optuna

    def objective(trial: "optuna.Trial") -> float:
        hp = _suggest_hp(trial, cfg.kind)
        sub_cfg = cfg.model_copy(update={"hyperparameters": hp})
        est = build_estimator(sub_cfg)
        scores = cross_validate(est, X, y, folds=folds, random_state=cfg.random_state)
        return float(scores["f1_macro_mean"])

    sampler = optuna.samplers.TPESampler(seed=cfg.random_state)
    study = optuna.create_study(direction="maximize", sampler=sampler)

    def _cb(_study: "optuna.Study", trial: "optuna.trial.FrozenTrial") -> None:
        if progress_cb is not None:
            progress_cb((trial.number + 1) / n_trials)

    study.optimize(objective, n_trials=n_trials, timeout=timeout_seconds, callbacks=[_cb])
    return dict(study.best_params)


def _suggest_hp(trial: Any, kind: ClassifierKind) -> dict[str, Any]:
    """Optuna search space per classifier kind."""
    if kind in (ClassifierKind.RANDOM_FOREST, ClassifierKind.EXTRA_TREES):
        return {
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=100),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 1, 8),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", "log2", None]),
        }
    if kind is ClassifierKind.GRADIENT_BOOSTING:
        return {
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "max_iter": trial.suggest_int("max_iter", 100, 600, step=100),
            "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 15, 127),
        }
    if kind is ClassifierKind.LIGHTGBM:
        return {
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 255),
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=100),
        }
    if kind is ClassifierKind.XGBOOST:
        return {
            "learning_rate": trial.suggest_float("learning_rate", 1e-3, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "n_estimators": trial.suggest_int("n_estimators", 100, 800, step=100),
        }
    if kind is ClassifierKind.KNN:
        return {
            "n_neighbors": trial.suggest_int("n_neighbors", 3, 25),
            "weights": trial.suggest_categorical("weights", ["uniform", "distance"]),
        }
    return {}


def cross_validate(
    estimator: "BaseEstimator",
    X: "np.ndarray",
    y: "np.ndarray",
    *,
    folds: int = 5,
    random_state: int | None = 42,
) -> dict[str, Any]:
    """K-fold stratified cross-validation; returns mean and per-fold metrics."""
    from sklearn.model_selection import StratifiedKFold
    from sklearn.model_selection import cross_validate as _cv

    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
    scores = _cv(
        estimator,
        X,
        y,
        cv=cv,
        scoring=["accuracy", "f1_macro", "balanced_accuracy"],
        n_jobs=-1,
        return_train_score=False,
    )
    return {
        "accuracy_mean": float(scores["test_accuracy"].mean()),
        "accuracy_std": float(scores["test_accuracy"].std()),
        "f1_macro_mean": float(scores["test_f1_macro"].mean()),
        "balanced_accuracy_mean": float(scores["test_balanced_accuracy"].mean()),
        "fit_time_mean": float(scores["fit_time"].mean()),
    }
