"""ProgressReporter composition tests."""

from __future__ import annotations

import pytest

from terrascope.core.utils.progress import ProgressReporter

pytestmark = pytest.mark.unit


def test_top_level_passes_through() -> None:
    captured: list[float] = []
    r = ProgressReporter(sink=captured.append)
    r(0.0)
    r(0.5)
    r(1.0)
    assert captured == [0.0, 0.5, 1.0]


def test_clamps_to_unit_interval() -> None:
    captured: list[float] = []
    r = ProgressReporter(sink=captured.append)
    r(-0.5)
    r(1.5)
    assert captured == [0.0, 1.0]


def test_substep_scopes_progress() -> None:
    captured: list[float] = []
    r = ProgressReporter(sink=captured.append)

    with r.substep(0.5) as p:
        # The substep occupies [0.0, 0.5) of the parent.
        p(0.0)
        p(0.5)
        p(1.0)
    # Final value emitted on context exit should be at 0.5.
    assert captured[-1] == 0.5
    # Intermediate values are within [0, 0.5].
    assert captured[0] == 0.0
    assert captured[1] == 0.25
    assert captured[2] == 0.5


def test_substeps_compose() -> None:
    captured: list[float] = []
    r = ProgressReporter(sink=captured.append)
    with r.substep(0.4) as p:
        p(1.0)  # fills 0..0.4
    with r.substep(0.6) as p:
        p(1.0)  # fills 0.4..1.0
    assert captured[-1] == pytest.approx(1.0)


def test_invalid_fraction_raises() -> None:
    captured: list[float] = []
    r = ProgressReporter(sink=captured.append)
    with pytest.raises(ValueError), r.substep(1.5):
        pass


def test_invalid_start_raises() -> None:
    with pytest.raises(ValueError):
        ProgressReporter(sink=lambda _: None, start=2.0, extent=0.1)
