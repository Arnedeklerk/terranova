"""Tests for the ONNX Runtime session cache."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from terrascope.core.ml import inference

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_cache():  # type: ignore[no-untyped-def]
    inference.clear_cache()
    yield
    inference.clear_cache()


def test_session_is_cached_by_path(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A second call with the same path returns the same session object."""
    model_path = tmp_path / "fake.onnx"
    model_path.write_bytes(b"fake-onnx")

    fake_module = MagicMock()
    fake_module.get_available_providers.return_value = ["CPUExecutionProvider"]
    calls = []

    def fake_session(path: str, providers: list[str]) -> MagicMock:
        calls.append((path, providers))
        return MagicMock(name=f"session({path})")

    fake_module.InferenceSession = fake_session
    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", fake_module)

    a = inference.get_session(model_path)
    b = inference.get_session(model_path)
    assert a is b
    assert len(calls) == 1


def test_prefer_gpu_adds_provider(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    model_path = tmp_path / "fake.onnx"
    model_path.write_bytes(b"fake-onnx")
    captured: list[list[str]] = []

    fake_module = MagicMock()
    fake_module.get_available_providers.return_value = [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    fake_module.InferenceSession = lambda path, providers: captured.append(providers) or MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", fake_module)

    inference.get_session(model_path, prefer_gpu=True)
    assert captured == [["CUDAExecutionProvider", "CPUExecutionProvider"]]


def test_clear_cache_forgets_sessions(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    model_path = tmp_path / "fake.onnx"
    model_path.write_bytes(b"fake-onnx")
    fake_module = MagicMock()
    fake_module.get_available_providers.return_value = ["CPUExecutionProvider"]
    n_calls = [0]

    def fake_session(path: str, providers: list[str]) -> MagicMock:
        n_calls[0] += 1
        return MagicMock()

    fake_module.InferenceSession = fake_session
    monkeypatch.setitem(__import__("sys").modules, "onnxruntime", fake_module)

    inference.get_session(model_path)
    assert n_calls[0] == 1
    inference.clear_cache()
    inference.get_session(model_path)
    assert n_calls[0] == 2
