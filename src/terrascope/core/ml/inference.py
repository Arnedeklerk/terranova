"""ONNX Runtime inference helpers.

A single module-level cache keeps one warm ``InferenceSession`` per model
path.  ORT is thread-safe by design so a single session can be shared across
QgsTask threads.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import onnxruntime as ort

_SESSIONS: dict[str, "ort.InferenceSession"] = {}
_LOCK = Lock()


def get_session(model_path: Path, *, prefer_gpu: bool = False) -> "ort.InferenceSession":
    """Return a cached ORT session for ``model_path``.

    On first call, picks providers in this order: CUDA (if available and
    requested) → DirectML on Windows → CPU.  Subsequent calls return the
    cached session.
    """
    import onnxruntime as ort

    key = str(Path(model_path).resolve())
    with _LOCK:
        if key in _SESSIONS:
            return _SESSIONS[key]

        available = set(ort.get_available_providers())
        providers: list[str] = []
        if prefer_gpu and "CUDAExecutionProvider" in available:
            providers.append("CUDAExecutionProvider")
        if prefer_gpu and "DmlExecutionProvider" in available:
            providers.append("DmlExecutionProvider")
        providers.append("CPUExecutionProvider")

        session = ort.InferenceSession(key, providers=providers)
        _SESSIONS[key] = session
        return session


def clear_cache() -> None:
    """Drop all cached sessions (e.g. when the user reloads a model)."""
    with _LOCK:
        _SESSIONS.clear()


def export_onnx(
    estimator,  # type: ignore[no-untyped-def]  # BaseEstimator-ish
    n_features: int,
    out_path: Path,
    *,
    opset: int = 17,
) -> Path:
    """Export a sklearn / LightGBM / XGBoost estimator to ONNX.

    Picks the right ``skl2onnx`` / ``onnxmltools`` converter based on the
    estimator's module path.  Output models accept a single float tensor input
    of shape ``(N, n_features)`` and return class labels (and probabilities
    where available).
    """
    from pathlib import Path as _Path

    out_path = _Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    module = type(estimator).__module__
    if module.startswith("lightgbm"):
        import onnxmltools
        from onnxmltools.convert.common.data_types import FloatTensorType

        onx = onnxmltools.convert_lightgbm(
            estimator,
            initial_types=[("input", FloatTensorType([None, n_features]))],
            target_opset=opset,
        )
        out_path.write_bytes(onx.SerializeToString())
        return out_path

    if module.startswith("xgboost"):
        import onnxmltools
        from onnxmltools.convert.common.data_types import FloatTensorType

        onx = onnxmltools.convert_xgboost(
            estimator,
            initial_types=[("input", FloatTensorType([None, n_features]))],
            target_opset=opset,
        )
        out_path.write_bytes(onx.SerializeToString())
        return out_path

    # Default: scikit-learn family.
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType

    onx = convert_sklearn(
        estimator,
        initial_types=[("input", FloatTensorType([None, n_features]))],
        target_opset=opset,
    )
    out_path.write_bytes(onx.SerializeToString())
    return out_path
