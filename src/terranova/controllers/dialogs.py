"""Bridge actions wrapping native Qt file/folder dialogs.

React inputs can't open OS-native file pickers, so we shell out to QFileDialog
on the Python side via the bridge.  Used by the dock panels to let users
pick output paths or input folders that aren't already loaded as layers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def save_file(payload: dict[str, Any]) -> dict[str, Any]:
    """Open a native 'save as' dialog.  Returns ``{"path": "..."}`` or empty."""
    from qgis.PyQt.QtWidgets import QFileDialog

    default = payload.get("default", str(Path.home()))
    title = payload.get("title", "Save")
    filt = payload.get("filter", "All files (*.*)")
    path, _ = QFileDialog.getSaveFileName(None, title, default, filt)
    return {"path": path or ""}


def open_file(payload: dict[str, Any]) -> dict[str, Any]:
    """Open a native 'open' dialog.  Returns ``{"path": "..."}`` or empty."""
    from qgis.PyQt.QtWidgets import QFileDialog

    default = payload.get("default", str(Path.home()))
    title = payload.get("title", "Open")
    filt = payload.get("filter", "All files (*.*)")
    path, _ = QFileDialog.getOpenFileName(None, title, default, filt)
    return {"path": path or ""}


def open_directory(payload: dict[str, Any]) -> dict[str, Any]:
    """Open a native 'pick a folder' dialog.  Returns ``{"path": "..."}`` or empty."""
    from qgis.PyQt.QtWidgets import QFileDialog

    default = payload.get("default", str(Path.home()))
    title = payload.get("title", "Pick a folder")
    path = QFileDialog.getExistingDirectory(None, title, default)
    return {"path": path or ""}
