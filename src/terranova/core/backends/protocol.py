"""Compute-backend protocol.

The local backend (default) is implicit — every classical operation runs
against a local odc-stac / xarray cube.  An alternative backend pushes the
same logical operations to a remote service.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ComputeBackend(Protocol):
    """The shape every backend must implement."""

    name: str

    def lazy_stack(
        self,
        bbox: tuple[float, float, float, float],
        datetime: str,
        bands: list[str],
        *,
        resolution: int,
    ):  # type: ignore[no-untyped-def]
        """Return a lazy data cube object (xarray-like)."""

    def composite(self, cube, *, method: str):  # type: ignore[no-untyped-def]
        """Reduce time → single scene."""

    def write_cog(self, cube, out_path: Path):  # type: ignore[no-untyped-def]
        """Materialise the lazy cube to a Cloud-Optimised GeoTIFF."""
