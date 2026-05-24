"""Post-processing for classification rasters.

All functions take and return numpy arrays.  No QGIS dependency — the QGIS
adapters live in :mod:`terrascope.processing.postprocess_algs`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np


def majority_filter(
    labels: "np.ndarray", *, size: int = 3, nodata: int = 0
) -> "np.ndarray":
    """Replace each pixel with the majority class in its ``size x size`` window.

    Uses :func:`scipy.ndimage.generic_filter` with a numba-free majority kernel.
    ``size`` must be odd.  Nodata pixels are preserved and excluded from
    majority counts.
    """
    import numpy as np
    from scipy.ndimage import generic_filter

    if size % 2 == 0:
        raise ValueError(f"size must be odd; got {size}")

    def _majority(window: np.ndarray) -> float:
        # window is a 1-D view into the size*size neighbourhood
        win = window.astype(np.int64)
        win = win[win != nodata]
        if win.size == 0:
            return float(nodata)
        # np.bincount is fastest when class ids are small non-negative ints.
        vals, counts = np.unique(win, return_counts=True)
        return float(vals[counts.argmax()])

    out = generic_filter(
        labels.astype(np.int64),
        _majority,
        size=size,
        mode="constant",
        cval=nodata,
    ).astype(labels.dtype, copy=False)
    # Preserve nodata where the original was nodata.
    out[labels == nodata] = nodata
    return out


def sieve(
    labels: "np.ndarray",
    *,
    min_pixels: int = 4,
    connectivity: int = 4,
    nodata: int = 0,
) -> "np.ndarray":
    """Remove connected components smaller than ``min_pixels``.

    Reassigns swept pixels to the most common neighbouring class.  This is
    the classic GDAL ``gdal_sieve.py`` behaviour, recoded here so we have it
    in pure Python and can run it without GDAL command-line tools.
    """
    import numpy as np
    from scipy.ndimage import label

    if connectivity not in (4, 8):
        raise ValueError(f"connectivity must be 4 or 8; got {connectivity}")

    structure = np.ones((3, 3), dtype=bool) if connectivity == 8 else np.array(
        [[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=bool
    )

    out = labels.copy()
    # Process each class separately so we don't merge unrelated components.
    for cls in np.unique(out):
        if cls == nodata:
            continue
        mask = out == cls
        cc, n = label(mask, structure=structure)
        if n == 0:
            continue
        sizes = np.bincount(cc.ravel())
        small_components = np.where(sizes < min_pixels)[0]
        small_components = small_components[small_components > 0]  # 0 is background
        for comp_id in small_components:
            comp_mask = cc == comp_id
            # Find the dominant non-target, non-nodata class in the 1-pixel halo.
            from scipy.ndimage import binary_dilation

            halo = binary_dilation(comp_mask, structure=structure) & ~comp_mask
            neighbour_labels = out[halo]
            neighbour_labels = neighbour_labels[
                (neighbour_labels != cls) & (neighbour_labels != nodata)
            ]
            if neighbour_labels.size == 0:
                continue
            vals, counts = np.unique(neighbour_labels, return_counts=True)
            replacement = vals[counts.argmax()]
            out[comp_mask] = replacement
    return out


def reclassify(labels: "np.ndarray", mapping: dict[int, int]) -> "np.ndarray":
    """Apply an explicit ``old_class → new_class`` lookup.  Unmapped classes pass through."""
    import numpy as np

    if not mapping:
        return labels.copy()
    out = labels.copy()
    max_class = max(int(labels.max()), max(mapping.keys()))
    lut = np.arange(max_class + 1, dtype=labels.dtype)
    for old, new in mapping.items():
        lut[old] = new
    # Mask out values outside the LUT to avoid IndexError.
    safe = labels.clip(0, max_class).astype(np.intp)
    out = lut[safe]
    return out
