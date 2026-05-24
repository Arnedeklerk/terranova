"""COG export and validation helpers built on :mod:`rio_cogeo`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr


def write_cog(
    data: "xr.DataArray",
    dst: Path,
    *,
    profile: str = "deflate",
    overview_resampling: str = "nearest",
    nodata: float | int | None = None,
) -> Path:
    """Write a DataArray to a Cloud-Optimised GeoTIFF.

    Uses ``rio_cogeo.cog_profiles`` for the output profile.  Common picks:

    - ``"deflate"`` — lossless, default
    - ``"zstd"``    — lossless, faster
    - ``"jpeg"``    — lossy, 8-bit RGB only

    Parameters
    ----------
    data
        A 2-D or 3-D DataArray with rio coordinates (``x``, ``y``, optionally
        ``band``) and a CRS set via ``rio.write_crs``.
    dst
        Output path.  Parent directory must exist.
    """
    import rioxarray  # noqa: F401  (registers ``.rio`` accessor)
    from rio_cogeo import cog_profiles
    from rio_cogeo.cogeo import cog_translate

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp GeoTIFF first; cog_translate then rewrites with overviews
    # in a single pass.  rioxarray handles the CRS + transform plumbing.
    tmp = dst.with_suffix(".tmp.tif")
    data.rio.to_raster(tmp, nodata=nodata, compress=None)

    output_profile = cog_profiles.get(profile)
    cog_translate(
        str(tmp),
        str(dst),
        output_profile,
        overview_resampling=overview_resampling,
        in_memory=False,
        quiet=True,
    )
    tmp.unlink(missing_ok=True)
    return dst


def validate(path: Path) -> tuple[bool, list[str], list[str]]:
    """Check whether ``path`` is a valid Cloud-Optimised GeoTIFF.

    Wraps :func:`rio_cogeo.cogeo.cog_validate`.  Returns ``(is_cog, errors, warnings)``.
    """
    from rio_cogeo.cogeo import cog_validate

    is_cog, errors, warnings = cog_validate(str(path))
    return bool(is_cog), list(errors), list(warnings)
