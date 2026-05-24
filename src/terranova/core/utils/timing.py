"""Light timing helpers — useful for in-task progress estimates."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(slots=True)
class TimedResult:
    """Outcome of a ``timed`` context — ``elapsed`` in seconds."""

    elapsed: float


@contextmanager
def timed() -> Iterator[TimedResult]:
    """Measure wall time of a block.

    >>> with timed() as t:
    ...     do_work()
    >>> print(t.elapsed)

    Uses ``time.perf_counter`` so it captures the actual stopwatch time even
    when the GIL is contended.
    """
    result = TimedResult(elapsed=0.0)
    start = time.perf_counter()
    try:
        yield result
    finally:
        result.elapsed = time.perf_counter() - start


def humanise_duration(seconds: float) -> str:
    """Format ``seconds`` as a short human-readable string.

    Examples: ``0.4s``, ``3.7s``, ``1m12s``, ``2h05m``.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m{s:02d}s"
    h, rem = divmod(int(seconds), 3600)
    m, _ = divmod(rem, 60)
    return f"{h}h{m:02d}m"
