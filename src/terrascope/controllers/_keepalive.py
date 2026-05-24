"""Strong-reference registry for in-flight QgsTasks.

QgsTaskManager.addTask() takes ownership of the QObject on the C++ side
but does NOT keep a strong Python reference.  If our controller returns
without holding the QgsTask subclass somewhere Python can see, the
interpreter garbage-collects it before Qt has a chance to run it — the
job_id reaches the React panel, "Downloading…" lights up, and then
nothing ever happens because run() was never called.

Every controller that spawns a long-running task must:

    hold(job_id, task)
    QgsApplication.taskManager().addTask(task)

and release the reference from its `_on_finished` callback:

    release(task.job_id)

Importing this module from any controller is safe; it has no qgis.*
dependency so the architectural guard test still passes.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

_active: dict[str, Any] = {}
_lock = Lock()


def hold(job_id: str, task: Any) -> None:
    """Pin `task` in memory until :func:`release` is called."""
    with _lock:
        _active[job_id] = task


def release(job_id: str) -> None:
    """Drop the reference to a finished task.  Idempotent."""
    with _lock:
        _active.pop(job_id, None)


def active_count() -> int:
    """Diagnostic — number of tasks currently kept alive."""
    with _lock:
        return len(_active)
