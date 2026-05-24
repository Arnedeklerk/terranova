"""Parallel-map helper that respects user-configured parallelism.

Avoids `concurrent.futures.ThreadPoolExecutor`-as-a-stop-gap by routing
through dask when available and falling back to a sequential map otherwise.
QGIS-level concurrency stays under QgsTask; this helper is for CPU-heavy
batch operations *inside* a task.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


def map_chunks(
    fn: Callable[[T], R],
    items: Iterable[T],
    *,
    max_workers: int = 4,
    use_dask: bool = True,
) -> list[R]:
    """Map ``fn`` across ``items`` with bounded parallelism.

    Picks dask when installed (and ``use_dask`` is True), else uses a
    plain ``ThreadPoolExecutor`` with ``max_workers``.  Always returns a list
    in input order.
    """
    items = list(items)
    if use_dask:
        try:
            import dask

            tasks = [dask.delayed(fn)(it) for it in items]
            return list(dask.compute(*tasks, num_workers=max_workers))
        except ImportError:
            pass

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(fn, items))
