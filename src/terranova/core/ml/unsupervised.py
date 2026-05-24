"""Unsupervised pixel-clustering for the Classify panel.

Two algorithms exposed:

- **K-Means.**  ``sklearn.cluster.MiniBatchKMeans`` — memory-friendly,
  fast, the classic centroid-based clustering.  Pixels go to the
  cluster with the nearest centroid.

- **ISODATA.**  Iterative Self-Organising Data Analysis.  A long-time
  remote-sensing staple: starts with K clusters, then dynamically
  splits high-variance clusters (along the band of max stdev) and
  merges clusters whose centroids are too close, so the final cluster
  count adapts to the data.

Both fit on a random subsample of raster pixels for memory bounds
(default 100 k pixels) and return an estimator with a sklearn-shaped
``.predict(X)`` method so the existing :func:`predict_to_cog` writes
out the result identically to a supervised classifier.

Pure-Python — no qgis imports — so the unit tests can exercise these
without QGIS installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

import numpy as np

UnsupervisedKind = Literal["kmeans", "isodata"]


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #
def fit_unsupervised(
    kind: UnsupervisedKind,
    raster_path: Path,
    *,
    n_clusters: int = 5,
    max_iter: int = 50,
    sample_size: int = 100_000,
    isodata_min_size: int | None = None,
    isodata_max_std: float | None = None,
    isodata_min_distance: float | None = None,
    random_state: int = 42,
    progress_cb: Callable[[float], None] | None = None,
) -> object:
    """Subsample, fit the chosen algorithm, return a `.predict`-able estimator.

    The estimator is then handed to
    :func:`terranova.core.ml.classical.predict_to_cog` which writes the
    full raster as a labelled COG block-by-block.
    """
    sample, _ = _sample_raster_pixels(raster_path, sample_size, random_state)
    if progress_cb:
        progress_cb(0.35)

    if kind == "kmeans":
        from sklearn.cluster import MiniBatchKMeans

        est = MiniBatchKMeans(
            n_clusters=max(2, n_clusters),
            max_iter=max_iter,
            random_state=random_state,
            batch_size=min(10_000, max(1000, sample.shape[0] // 10)),
            n_init=5,
        )
        est.fit(sample)
        if progress_cb:
            progress_cb(0.95)
        return est

    if kind == "isodata":
        return _fit_isodata(
            sample,
            n_target=n_clusters,
            max_iter=max_iter,
            min_size=isodata_min_size,
            max_std=isodata_max_std,
            min_distance=isodata_min_distance,
            random_state=random_state,
            progress_cb=progress_cb,
        )

    raise ValueError(f"unknown unsupervised kind: {kind!r}")


# --------------------------------------------------------------------------- #
# Sampling                                                                    #
# --------------------------------------------------------------------------- #
def _sample_raster_pixels(
    raster_path: Path, sample_size: int, random_state: int
) -> tuple[np.ndarray, int]:
    """Return ``(samples, n_bands)``, dropping any pixel with NaN bands.

    We materialise the whole raster in memory for the read, then subsample.
    That's fine for the ~GB-class rasters this UI is aimed at; for larger
    rasters we'd want windowed sampling.  TODO when it bites.
    """
    import rasterio

    with rasterio.open(str(raster_path)) as src:
        arr = src.read()
    bands = arr.shape[0]
    feats = arr.reshape(bands, -1).T.astype(np.float32, copy=False)
    valid = ~np.isnan(feats).any(axis=1)
    feats = feats[valid]
    if feats.shape[0] == 0:
        raise RuntimeError(
            "Raster has no valid pixels after NaN filtering — check the band "
            "data."
        )
    if feats.shape[0] > sample_size:
        rng = np.random.default_rng(random_state)
        idx = rng.choice(feats.shape[0], size=sample_size, replace=False)
        feats = feats[idx]
    return feats, bands


# --------------------------------------------------------------------------- #
# ISODATA                                                                     #
# --------------------------------------------------------------------------- #
class _IsodataEstimator:
    """Sklearn-shaped wrapper exposing ``.predict`` against fixed centroids.

    Implements predict in chunks to keep peak memory bounded — naive
    broadcast subtraction (``X[:, None] - centers[None, :]``) is O(N×K×B)
    in memory and would blow up on a multi-gigabyte raster.
    """

    def __init__(self, cluster_centers: np.ndarray) -> None:
        self.cluster_centers_ = np.asarray(cluster_centers, dtype=np.float32)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return _nearest_centroid(np.asarray(X, dtype=np.float32),
                                 self.cluster_centers_)

    @property
    def n_clusters(self) -> int:
        return int(self.cluster_centers_.shape[0])


def _fit_isodata(
    X: np.ndarray,
    *,
    n_target: int,
    max_iter: int,
    min_size: int | None,
    max_std: float | None,
    min_distance: float | None,
    random_state: int,
    progress_cb: Callable[[float], None] | None,
) -> _IsodataEstimator:
    """Run ISODATA on ``X``.  ``n_target`` is the initial / target cluster count.

    Sensible defaults derived from the data spread when the caller leaves
    the three ISODATA-specific thresholds at ``None``:

    - ``min_size``: drop clusters with fewer than 0.5 % of samples.
    - ``max_std``: split clusters whose max per-band stdev exceeds 70 % of
      the overall feature stdev.
    - ``min_distance``: merge cluster pairs whose centroid distance is below
      10 % of the overall feature spread.
    """
    from sklearn.cluster import MiniBatchKMeans

    n_features = X.shape[1]
    n_sample = X.shape[0]

    if min_size is None:
        min_size = max(50, n_sample // 200)
    if max_std is None:
        max_std = float(X.std(axis=0).max()) * 0.7
    if min_distance is None:
        min_distance = float(np.linalg.norm(X.std(axis=0))) * 0.1
    # Cap final cluster count so an unstable run can't explode.
    n_max = max(2, n_target * 2)

    # Initial centres via K-Means at the target count.
    init = MiniBatchKMeans(
        n_clusters=max(2, n_target),
        max_iter=10,
        random_state=random_state,
        n_init=3,
        batch_size=min(10_000, max(1000, n_sample // 10)),
    )
    init.fit(X)
    centers = init.cluster_centers_.astype(np.float32, copy=True)

    for it in range(max_iter):
        labels = _nearest_centroid(X, centers)
        survivors: list[tuple[int, np.ndarray, np.ndarray]] = []
        for i in range(centers.shape[0]):
            mask = labels == i
            sz = int(mask.sum())
            if sz < min_size:
                continue
            cent = X[mask].mean(axis=0)
            std = X[mask].std(axis=0)
            survivors.append((sz, cent.astype(np.float32), std.astype(np.float32)))
        if not survivors:
            # Pathological — re-seed.
            init = MiniBatchKMeans(
                n_clusters=max(2, n_target),
                max_iter=10,
                random_state=random_state + it + 1,
                n_init=1,
                batch_size=min(10_000, max(1000, n_sample // 10)),
            )
            init.fit(X)
            centers = init.cluster_centers_.astype(np.float32, copy=True)
            continue

        # Build the new centre list from survivors, then apply splits and
        # merges in two passes.
        new_centers = [c for _, c, _ in survivors]

        # Split high-variance clusters.
        for _, cent, std in survivors:
            if len(new_centers) >= n_max:
                break
            band = int(std.argmax())
            if std[band] > max_std:
                delta = np.zeros(n_features, dtype=np.float32)
                delta[band] = std[band] * 0.5
                new_centers.append(cent + delta)
                new_centers.append(cent - delta)

        # Merge close centroids — single pass, greedy.  Cluster pairs
        # within min_distance get averaged into one.
        merged_ok = [True] * len(new_centers)
        for i in range(len(new_centers)):
            if not merged_ok[i]:
                continue
            for j in range(i + 1, len(new_centers)):
                if not merged_ok[j]:
                    continue
                if (
                    np.linalg.norm(new_centers[i] - new_centers[j])
                    < min_distance
                ):
                    new_centers[i] = (new_centers[i] + new_centers[j]) / 2.0
                    merged_ok[j] = False
        new_centers = [
            c for c, ok in zip(new_centers, merged_ok, strict=False) if ok
        ]

        # Floor: never collapse below 2 clusters.
        if len(new_centers) < 2:
            new_centers = list(centers[:2])

        centers = np.asarray(new_centers, dtype=np.float32)
        if progress_cb:
            progress_cb(0.35 + 0.6 * (it + 1) / max_iter)

    return _IsodataEstimator(centers)


def _nearest_centroid(X: np.ndarray, centers: np.ndarray) -> np.ndarray:
    """Assign each row of ``X`` to its nearest centroid index, chunked."""
    n = X.shape[0]
    out = np.empty(n, dtype=np.int64)
    chunk = 10_000
    for s in range(0, n, chunk):
        e = min(s + chunk, n)
        diffs = X[s:e, None, :] - centers[None, :, :]
        d2 = (diffs * diffs).sum(axis=2)
        out[s:e] = d2.argmin(axis=1)
    return out
