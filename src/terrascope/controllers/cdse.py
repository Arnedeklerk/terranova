"""CDSE sign-in controller — drives the device-code OAuth flow.

Three events emitted on the job channel:

- ``{"type": "task.cdse.challenge", "job_id": ..., "user_code": "...",
    "verification_uri": "https://..."}`` — when the device code is ready
  for the user to type in their browser.
- ``{"type": "task.progress", "job_id": ..., "status": "Waiting for browser sign-in… (12s)"}``
- ``{"type": "task.complete", "job_id": ...}``  /  ``{"type": "task.failed", ...}``

Plus ``cdse.status`` (synchronous) and ``cdse.signout`` (synchronous).
"""

from __future__ import annotations

import uuid
from typing import Any

from . import _keepalive


def status(_payload: dict[str, Any]) -> dict[str, Any]:
    from ..core.catalog.cdse import load_cached_token

    token = load_cached_token()
    if token is None:
        return {"signed_in": False}
    return {"signed_in": True, "expired": token.is_expired()}


def signout(_payload: dict[str, Any]) -> dict[str, Any]:
    from ..core.catalog.cdse import forget_token

    forget_token()
    return {"signed_in": False}


def signin(_payload: dict[str, Any]) -> dict[str, Any]:
    """Start the device-code flow.  Returns ``{job_id}`` immediately."""
    from qgis.core import QgsApplication

    job_id = str(uuid.uuid4())
    task = _build_task(job_id=job_id)
    _keepalive.hold(job_id, task)
    QgsApplication.taskManager().addTask(task)
    return {"job_id": job_id}


def _build_task(**kwargs: Any):  # type: ignore[no-untyped-def]
    from qgis.core import QgsTask

    class _CdseLoginJobTask(QgsTask):
        def __init__(self) -> None:
            super().__init__("TerraScope: CDSE sign-in", QgsTask.CanCancel)
            self.job_id: str = kwargs["job_id"]
            self.error_text: str | None = None

        def run(self) -> bool:
            return _do_signin(self)

        def finished(self, ok: bool) -> None:  # noqa: N802
            _on_finished(self, ok)

    return _CdseLoginJobTask()


def _do_signin(task: Any) -> bool:
    from qgis.core import Qgis, QgsMessageLog

    from ..bridge import push_event

    try:
        from ..core.catalog.cdse import begin_device_flow, poll_for_token, save_token

        _emit(task, 5, "Requesting device code…")
        challenge = begin_device_flow()
        push_event(
            {
                "type": "task.cdse.challenge",
                "job_id": task.job_id,
                "user_code": challenge.user_code,
                "verification_uri": challenge.verification_uri_complete,
            }
        )
        _emit(task, 15, "Waiting for browser sign-in…")
        token = poll_for_token(
            challenge,
            on_pending=lambda elapsed: _emit(
                task, 15, f"Waiting for browser sign-in… ({int(elapsed)}s)"
            ),
        )
        save_token(token)
        _emit(task, 100, "Signed in.")
        return True
    except Exception as exc:  # noqa: BLE001
        task.error_text = f"{type(exc).__name__}: {exc}"
        QgsMessageLog.logMessage(
            f"CDSE sign-in failed: {exc!r}",
            "TerraScope",
            Qgis.MessageLevel.Critical,
        )
        return False


def _on_finished(task: Any, ok: bool) -> None:
    from ..bridge import push_event

    try:
        push_event(
            {
                "type": "task.complete" if ok else "task.failed",
                "job_id": task.job_id,
                "result": {} if ok else None,
                "error": None if ok else (task.error_text or "Cancelled."),
            }
        )
    finally:
        _keepalive.release(task.job_id)


def _emit(task: Any, percent: float, status: str) -> None:
    from qgis.core import Qgis, QgsMessageLog

    from ..bridge import push_event

    task.setProgress(float(percent))
    push_event(
        {
            "type": "task.progress",
            "job_id": task.job_id,
            "percent": float(percent),
            "status": status,
        }
    )
    if status:
        QgsMessageLog.logMessage(status, "TerraScope", Qgis.MessageLevel.Info)
