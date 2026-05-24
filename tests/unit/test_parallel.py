"""Parallel-map helper tests."""

from __future__ import annotations

import pytest

from terrascope.core.utils.parallel import map_chunks

pytestmark = pytest.mark.unit


def test_preserves_order() -> None:
    items = list(range(20))
    out = map_chunks(lambda x: x * 2, items, max_workers=4, use_dask=False)
    assert out == [x * 2 for x in items]


def test_executes_every_item() -> None:
    counter = {"n": 0}

    def fn(x: int) -> int:
        counter["n"] += 1
        return x

    map_chunks(fn, range(50), max_workers=4, use_dask=False)
    assert counter["n"] == 50


def test_empty_input() -> None:
    out = map_chunks(lambda x: x, [], use_dask=False)
    assert out == []
