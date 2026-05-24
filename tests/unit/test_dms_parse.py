"""DMS ↔ DD round-trip tests for the catalogue search coordinate parser.

Imports through a tiny shim so we don't need PyQt5/PyQt6 / qgis available
during unit tests — we only exercise the pure-python helpers.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def _load_helpers():  # type: ignore[no-untyped-def]
    """Pull just the two pure-python helpers out of the dialog module.

    The dialog file pulls in qgis.* at import time, which isn't available
    in pure-python CI.  We side-step that by reading the source and
    exec'ing only the helpers at the bottom of the file.
    """
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "terrascope"
        / "ui"
        / "dialogs"
        / "catalog_search.py"
    )
    src = path.read_text(encoding="utf-8")
    start = src.find("def _parse_dms")
    end = src.find("\n# ", start + 1)  # next divider comment, or EOF
    if end == -1:
        snippet = src[start:]
    else:
        snippet = src[start:end]
    # Bring re into the exec namespace (the snippet uses `_re`).
    ns: dict = {"_re": __import__("re")}
    exec(snippet, ns)  # noqa: S102 — we wrote this code
    return ns["_parse_dms"], ns["_format_dms"]


parse_dms, format_dms = _load_helpers()


# ---------------------- parse ----------------------
@pytest.mark.parametrize(
    "text,expected",
    [
        ("51.50722", 51.50722),
        ("51 30 26 N", 51.50722222),
        ("51° 30' 26\" N", 51.50722222),
        ("51 30 26", 51.50722222),
        ("-51 30 26", -51.50722222),
        ("51 30.5 N", 51.508333),  # DDM
        ("0 7 39 W", -0.1275),
        ("0° 7' 39\" W", -0.1275),
        ("51,5 N", 51.5),  # comma decimal
        ("90 S", -90.0),
        ("180 E", 180.0),
        ("0", 0.0),
    ],
)
def test_parse_dms(text, expected) -> None:  # type: ignore[no-untyped-def]
    assert parse_dms(text) == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize("bad", ["", "   ", "junk", "1 2 3 4", "abc N"])
def test_parse_dms_rejects_garbage(bad) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        parse_dms(bad)


# ---------------------- format ----------------------
def test_format_dms_positive_lat() -> None:
    assert format_dms(51.50722, is_lat=True).endswith("N")


def test_format_dms_negative_lat() -> None:
    assert format_dms(-1.5, is_lat=True).endswith("S")


def test_format_dms_positive_lon() -> None:
    assert format_dms(2.3, is_lat=False).endswith("E")


def test_format_dms_negative_lon() -> None:
    assert format_dms(-0.127, is_lat=False).endswith("W")


# ---------------------- round-trip ----------------------
@pytest.mark.parametrize("value", [0.0, 51.50722, -0.127, 180.0, -90.0, 45.5])
def test_round_trip(value) -> None:  # type: ignore[no-untyped-def]
    """Format → parse must recover the original to within rounding."""
    formatted = format_dms(value, is_lat=True)
    recovered = parse_dms(formatted)
    assert recovered == pytest.approx(value, abs=1e-4)
