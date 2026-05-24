"""CLI argument-parser smoke tests."""

from __future__ import annotations

import pytest

from terrascope.cli.main import build_parser

pytestmark = pytest.mark.unit


def test_help_does_not_crash(capsys) -> None:  # type: ignore[no-untyped-def]
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "terrascope" in captured.out
    assert "ndvi" in captured.out


def test_ndvi_subcommand_args() -> None:
    parser = build_parser()
    args = parser.parse_args(["ndvi", "in.tif", "out.tif", "--red", "4", "--nir", "8"])
    assert args.command == "ndvi"
    assert str(args.input) == "in.tif"
    assert args.red == 4
    assert args.nir == 8


def test_index_subcommand_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["index", "nbr", "in.tif", "out.tif", "--band-a", "4", "--band-b", "6"]
    )
    assert args.kind == "nbr"
    assert args.band_a == 4
    assert args.band_b == 6


def test_search_s2_subcommand_args() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["search-s2", "-0.5", "51.3", "0.3", "51.7", "2024-06-01/2024-09-30", "--max-cloud", "10"]
    )
    assert args.west == -0.5
    assert args.max_cloud == 10
    assert args.datetime == "2024-06-01/2024-09-30"


def test_missing_subcommand_exits(capsys) -> None:  # type: ignore[no-untyped-def]
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])
