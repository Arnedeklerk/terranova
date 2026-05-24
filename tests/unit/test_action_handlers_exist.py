"""Architectural guard — every action invoked from the React tree must be
backed by a real Python dispatch handler.

This is the test that would have caught the CommandPalette / Welcome
'action does nothing' bugs before they ever hit a user.  When you add a
new ``invoke("foo.bar", ...)`` on the TS side you must also register it
in :class:`terranova.controllers.Controllers._register` or this test
fails.

Lives as a unit test (not in CI's TS jobs) because we want it to run
even on environments without Node, and the parsing is trivial.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO = Path(__file__).resolve().parents[2]
UI_WEB = REPO / "src" / "terranova" / "ui_web" / "src"
DISPATCH = REPO / "src" / "terranova" / "controllers" / "dispatch.py"

# Actions referenced in code comments / strings that aren't real calls.
KNOWN_NON_INVOCATIONS = {"project.state.get"}


def _ts_invocations() -> set[str]:
    """All actions any panel passes to ``invoke()`` in the React tree."""
    pattern = re.compile(r'invoke[^("]*\(\s*"([a-z][a-z0-9._]*)"')
    found: set[str] = set()
    for path in UI_WEB.rglob("*.ts"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    for path in UI_WEB.rglob("*.tsx"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    return found - KNOWN_NON_INVOCATIONS


def _registered_actions() -> set[str]:
    """All action names registered in the dispatch table."""
    pattern = re.compile(r'self\._handlers\["([a-z][a-z0-9._]*)"\]')
    src = DISPATCH.read_text(encoding="utf-8")
    return set(pattern.findall(src))


def test_every_ts_invocation_has_a_handler() -> None:
    invocations = _ts_invocations()
    registered = _registered_actions()
    missing = invocations - registered
    assert not missing, (
        f"React panels invoke actions that aren't registered in dispatch.py: "
        f"{sorted(missing)}.\n"
        "Either register the handler (controllers/dispatch.py) or remove the "
        "invoke() call.  See AGENTS.md → 'Long-running task pattern'."
    )


def test_at_least_the_baseline_actions_are_registered() -> None:
    """Sanity check — if dispatch parsing broke, the test above would
    silently say 'no missing actions because we found none at all'."""
    registered = _registered_actions()
    expected = {
        "app.ping",
        "app.version",
        "catalog.search",
        "canvas.bbox",
        "classify.run",
    }
    assert expected.issubset(registered), (
        f"Baseline actions missing from dispatch.py: {expected - registered}"
    )
