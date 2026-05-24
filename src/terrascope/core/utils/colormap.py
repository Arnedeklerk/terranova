"""Cartographic colormap helpers.

TerraScope defaults to Crameri's perceptually-uniform, CVD-friendly ramps
(Crameri et al. 2020, Nature Communications 11, 5444).  Never default to
jet/rainbow.  When ``cmcrameri`` is unavailable, fall back to a sensible
matplotlib built-in.
"""

from __future__ import annotations

from typing import Literal

RampKind = Literal["sequential", "diverging", "cyclic", "categorical"]

# Crameri ramp names (cmcrameri); matplotlib fallback if not installed.
_CRAMERI = {
    "sequential": "cmc.batlow",
    "diverging": "cmc.vik",
    "cyclic": "cmc.romaO",
    "categorical": "cmc.batlowS",
}
_FALLBACK = {
    "sequential": "viridis",
    "diverging": "RdBu_r",
    "cyclic": "twilight",
    "categorical": "tab20",
}


def get_cmap(kind: RampKind = "sequential"):  # type: ignore[no-untyped-def]
    """Return a matplotlib Colormap, preferring Crameri ramps."""
    import matplotlib.pyplot as plt

    try:
        import cmcrameri  # noqa: F401

        return plt.get_cmap(_CRAMERI[kind])
    except ImportError:
        return plt.get_cmap(_FALLBACK[kind])


def name_for(kind: RampKind = "sequential") -> str:
    """Just the string name (for QGIS layer styling / matplotlib look-up)."""
    try:
        import cmcrameri  # noqa: F401

        return _CRAMERI[kind]
    except ImportError:
        return _FALLBACK[kind]


def sample_ramp(
    kind: RampKind = "sequential", n_stops: int = 8
) -> list[tuple[float, float, float, float]]:
    """Sample a colormap at ``n_stops`` positions across [0, 1].

    Returns a list of ``(position, r, g, b)`` tuples — pure-Python core API.
    The QGIS-flavoured factory that turns this into a ``QgsGradientColorRamp``
    lives in :mod:`terrascope.ui.colormap_qgis` so the core layer stays
    framework-free.
    """
    import numpy as np

    cmap = get_cmap(kind)
    out: list[tuple[float, float, float, float]] = []
    for x in np.linspace(0.0, 1.0, n_stops):
        r, g, b, _a = cmap(float(x))
        out.append((float(x), float(r), float(g), float(b)))
    return out
