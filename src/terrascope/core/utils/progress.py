"""Hierarchical progress reporting.

A :class:`ProgressReporter` is a small object that scopes a fraction of the
overall progress (0..1) to a child step.  Long pipelines compose them so the
"overall" progress on the QGIS task is the weighted sum of substep progress
without each substep needing to know its place in the larger workflow.

``substep(fraction)`` takes ``fraction`` of the parent's *total* extent
(not the remaining extent), so sibling substeps with fractions ``0.4`` and
``0.6`` together fill the parent exactly.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass(slots=True)
class ProgressReporter:
    """Reports progress in ``[start, start + extent)`` to ``sink``."""

    sink: Callable[[float], None]
    start: float = 0.0
    extent: float = 1.0
    _consumed: float = field(default=0.0, repr=False)

    def __post_init__(self) -> None:
        if not (0.0 <= self.start <= 1.0):
            raise ValueError(f"start must be in [0, 1], got {self.start}")
        if not (0.0 < self.extent <= 1.0 - self.start + 1e-9):
            raise ValueError(f"extent {self.extent} doesn't fit at start {self.start}")

    def __call__(self, fraction: float) -> None:
        fraction = max(0.0, min(1.0, fraction))
        self.sink(self.start + fraction * self.extent)

    @contextmanager
    def substep(self, fraction: float) -> Iterator["ProgressReporter"]:
        """Yield a child reporter occupying ``fraction`` of *this* extent.

        ``fraction`` is the share of the parent's full extent the child gets.
        Siblings' fractions should sum to ≤ 1.

        Usage::

            with reporter.substep(0.3) as p:  # take 30% of my budget
                heavy_work(progress_cb=p)
        """
        if not (0.0 < fraction <= 1.0):
            raise ValueError(f"fraction must be in (0, 1], got {fraction}")
        if self._consumed + fraction > 1.0 + 1e-9:
            raise ValueError(
                f"substep would over-fill parent: consumed {self._consumed} + {fraction} > 1.0"
            )
        child_start = self.start + self._consumed * self.extent
        child_extent = fraction * self.extent
        child = ProgressReporter(sink=self.sink, start=child_start, extent=child_extent)
        try:
            yield child
        finally:
            child(1.0)  # mark child as complete
            self._consumed += fraction
