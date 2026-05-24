"""Matplotlib figure builders used by the report and the API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..utils.colormap import get_cmap

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


def plot_confusion_matrix(
    cm: "np.ndarray",
    *,
    class_labels: list[str] | None = None,
    title: str | None = None,
):  # type: ignore[no-untyped-def]
    """Render a confusion-matrix heatmap with cell-value annotations.

    Uses the Crameri batlow ramp when available; never jet/rainbow.  Returns
    the :class:`matplotlib.figure.Figure` so the caller can save / show.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = cm.shape[0]
    fig, ax = plt.subplots(figsize=(5.5, 4.5), dpi=150)
    im = ax.imshow(cm, cmap=get_cmap("sequential"), aspect="auto")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pixels")
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Reference")
    if title:
        ax.set_title(title)

    labels = class_labels or [str(i) for i in range(n)]
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_yticklabels(labels)

    if cm.max() > 0:
        thresh = cm.max() / 2.0
        for i in range(n):
            for j in range(n):
                ax.text(
                    j,
                    i,
                    f"{cm[i, j]}",
                    ha="center",
                    va="center",
                    color="white" if cm[i, j] > thresh else "black",
                    fontsize=8,
                )
    fig.tight_layout()
    return fig


def export_animation(
    cube,  # type: ignore[no-untyped-def]  # xr.DataArray (time, y, x)
    out_path,  # type: ignore[no-untyped-def]
    *,
    cmap_kind: str = "sequential",
    vmin: float | None = None,
    vmax: float | None = None,
    fps: int = 4,
):  # type: ignore[no-untyped-def]
    """Render an MP4 animation of a per-pixel time-series raster.

    Uses imageio-ffmpeg under the hood.  The time axis becomes frames; each
    frame is a colourmapped image with a timestamp overlay.  Useful for
    presenting NDVI / NBR / disturbance evolution.
    """
    import imageio.v3 as iio
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    if "time" not in cube.dims:
        raise ValueError("export_animation expects a `time` dim")
    times = cube.time.values
    cmap = get_cmap(cmap_kind)
    vmin = vmin if vmin is not None else float(np.nanpercentile(cube.values, 2))
    vmax = vmax if vmax is not None else float(np.nanpercentile(cube.values, 98))

    frames = []
    for ts in times:
        slice_t = cube.sel(time=ts).values
        fig, ax = plt.subplots(figsize=(6, 6), dpi=100)
        ax.imshow(slice_t, cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_axis_off()
        ax.text(
            0.02, 0.98, str(np.datetime64(ts, "D")),
            transform=ax.transAxes, ha="left", va="top",
            color="white",
            bbox=dict(facecolor="black", alpha=0.5, boxstyle="round,pad=0.3"),
            fontsize=10, family="monospace",
        )
        fig.canvas.draw()
        # `tostring_rgb` was removed in matplotlib 3.10; use buffer_rgba.
        buf = np.asarray(fig.canvas.buffer_rgba())
        img = buf[..., :3]  # drop alpha
        frames.append(img)
        plt.close(fig)

    iio.imwrite(str(out_path), frames, fps=fps, codec="libx264", quality=8)
    return out_path


def plot_spectral_signatures(
    signatures: dict[str, tuple["np.ndarray", "np.ndarray"]],
    *,
    title: str | None = None,
):  # type: ignore[no-untyped-def]
    """Plot one line per class — wavelength on x, reflectance on y.

    Parameters
    ----------
    signatures
        ``{class_name: (wavelengths_nm, reflectances)}``.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    for cls, (wl, refl) in signatures.items():
        ax.plot(wl, refl, marker="o", linewidth=1, markersize=3, label=str(cls))
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Reflectance")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", frameon=False, fontsize=8)
    if title:
        ax.set_title(title)
    fig.tight_layout()
    return fig
