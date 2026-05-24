"""Background heartbeat ticker for in-flight QgsTasks.

Some workflow phases run for minutes between progress emits — writing
a full-scene COG, exporting an ONNX model, lazily fetching a huge cube
through odc.stac. The actual work isn't naturally chunked, so naive
progress callbacks would add complexity for little gain.

To keep the dock's stall watchdog from tripping during legitimate long
phases, this module runs a single main-thread :class:`QTimer` that
emits a ``task.heartbeat`` event for every active job in the keepalive
registry every :data:`HEARTBEAT_MS`. The React side's :class:`JobProgress`
resets its stall timer on any event with a matching job_id, so this
keeps the warning quiet without making the workflow code responsible
for periodic emits.

Lifecycle: ``_keepalive.hold()`` calls :func:`ensure_running` (idempotent);
``_keepalive.release()`` calls :func:`stop_if_idle`. The timer therefore
exists only while there's at least one task to heartbeat for.
"""

from __future__ import annotations

from typing import Any

from . import _keepalive

# 30 s — comfortably below the React-side stall threshold (currently
# 120 s, raise/lower without changing this) so even if one tick is
# delayed by main-thread contention, the next reset arrives well
# before the watchdog fires.
HEARTBEAT_MS = 30_000

_timer: Any = None


def ensure_running() -> None:
    """Start the heartbeat timer if it isn't already running.  Idempotent."""
    global _timer
    if _timer is not None:
        return
    try:
        from qgis.PyQt.QtCore import QTimer
    except ImportError:  # pragma: no cover — headless tests
        return
    _timer = QTimer()
    _timer.setInterval(HEARTBEAT_MS)
    _timer.timeout.connect(_emit_all)
    _timer.start()


def stop_if_idle() -> None:
    """Stop the timer if no tasks are being tracked."""
    global _timer
    if _timer is None:
        return
    if _keepalive.active_count() > 0:
        return
    try:
        _timer.stop()
    except Exception:  # noqa: BLE001
        pass
    _timer = None


def _emit_all() -> None:
    """Push a single heartbeat event for every tracked job_id.

    Runs on the main thread (QTimer.timeout); :func:`push_event` is
    thread-safe but we avoid any worker-thread races by emitting from
    the timer's thread directly.
    """
    try:
        from ..bridge import push_event
    except ImportError:  # pragma: no cover
        return

    for job_id in _keepalive.active_job_ids():
        try:
            push_event({"type": "task.heartbeat", "job_id": job_id})
        except Exception:  # noqa: BLE001 — never let heartbeat crash anything
            pass
