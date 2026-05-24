"""BFAST Lite per-pixel break detection, plus a dependency-free CuSum
fallback so the change-detection workflow has *something* to run before the
optional ``bfast`` GPU package is installed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import xarray as xr


def detect_breaks(  # pragma: no cover
    ndvi: "xr.DataArray",
    *,
    start_monitor: str,
    freq: int = 365,
    k: int = 3,
    hfrac: float = 0.25,
    trend: bool = True,
    level: float = 0.05,
    backend: str = "opencl",
) -> "xr.Dataset":
    """Run BFAST Monitor per pixel.

    Returns a Dataset with ``break_date`` and ``magnitude`` rasters.
    """
    import numpy as np
    import xarray as xr
    from bfast import BFASTMonitor

    model = BFASTMonitor(
        start_monitor=np.datetime64(start_monitor),
        freq=freq,
        k=k,
        hfrac=hfrac,
        trend=trend,
        level=level,
        backend=backend,
    )
    model.fit(ndvi.values, dates=ndvi.time.values.astype("datetime64[D]"))
    return xr.Dataset(
        dict(
            break_date=(("y", "x"), model.breaks),
            magnitude=(("y", "x"), model.magnitudes),
        ),
        coords=dict(y=ndvi.y, x=ndvi.x),
    )


# --------------------------------------------------------------------------- #
# Numpy CuSum fallback                                                        #
# --------------------------------------------------------------------------- #
def detect_breaks_cusum(
    series: "xr.DataArray",
    *,
    threshold: float = 2.0,
    monitor_start_index: int = 0,
) -> "xr.Dataset":
    """Lightweight per-pixel cumulative-sum break detector.

    Computes the residual against the per-pixel mean over the history window
    (everything before ``monitor_start_index``), then sums it forward; the
    first time the absolute CuSum crosses ``threshold * sigma`` is recorded as
    the break date.  Returns ``break_index`` (int, -1 if no break),
    ``break_time`` (datetime64), and ``magnitude`` (float) rasters.

    Suitable as a fast first-pass; for proper inference use the full BFAST.
    """
    import numpy as np
    import xarray as xr

    if "time" not in series.dims:
        raise ValueError("CuSum requires a `time` dim")

    values = series.values  # (T, y, x) — float
    if values.ndim != 3:
        raise ValueError(f"series must be (time, y, x); got {values.shape}")

    history = values[:monitor_start_index] if monitor_start_index > 0 else values
    mean = np.nanmean(history, axis=0)
    std = np.nanstd(history, axis=0)
    # Avoid division by zero on uniform pixels.
    std = np.where(std == 0, np.nan, std)

    # Standard CuSum-Lite monitoring: residuals taken across the full series,
    # but the cumulative sum *resets* at ``monitor_start_index`` so noise from
    # the history doesn't leak into the monitoring period as a false break.
    # Threshold scales as sqrt(N) * sigma where N is steps since reset — the
    # cumsum of mean-zero noise grows that fast under H0.
    residuals = values - mean[None, :, :]
    n_time = values.shape[0]
    monitor_start = max(0, min(monitor_start_index, n_time))
    # Zero out the history portion of residuals so the cumsum starts at 0
    # at monitor_start.  We could also slice + cumsum just the monitoring
    # tail and pad with zeros — same effect, this is simpler.
    monitored = residuals.copy()
    if monitor_start > 0:
        monitored[:monitor_start] = 0.0
    cusum = np.nancumsum(monitored, axis=0)
    abs_cusum = np.abs(cusum)

    # CuSum of N mean-zero observations with std σ has expected std σ·√N.
    # Scale the threshold accordingly so it's stable as the monitoring window
    # gets longer.
    steps_since_reset = np.arange(n_time, dtype=np.float32) - monitor_start + 1
    steps_since_reset = np.maximum(steps_since_reset, 1.0)  # avoid sqrt(<=0)
    scale = np.sqrt(steps_since_reset)[:, None, None]
    crossed = abs_cusum > (threshold * scale * std[None, :, :])
    # Only count crossings in the monitoring period itself.
    if monitor_start > 0:
        crossed[:monitor_start] = False

    # First index where any cross occurs (along the time axis).
    break_idx = np.where(
        crossed.any(axis=0),
        crossed.argmax(axis=0),
        -1,
    )

    # Magnitude = signed CuSum value at break.
    break_idx_safe = np.clip(break_idx, 0, values.shape[0] - 1)
    magnitude = np.take_along_axis(
        cusum, break_idx_safe[None, :, :], axis=0
    )[0]
    magnitude = np.where(break_idx >= 0, magnitude, np.nan)

    times = series.time.values
    break_time = np.where(
        break_idx >= 0,
        times[break_idx_safe],
        np.datetime64("NaT"),
    )

    return xr.Dataset(
        dict(
            break_index=(("y", "x"), break_idx.astype(np.int32)),
            break_time=(("y", "x"), break_time),
            magnitude=(("y", "x"), magnitude.astype(np.float32)),
        ),
        coords=dict(y=series.y, x=series.x),
    )
