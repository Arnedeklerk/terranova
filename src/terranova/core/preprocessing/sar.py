"""SAR preprocessing via SNAP + pyroSAR planning surface.

The standard SAR-for-classification recipe is:
  1. Apply-orbit-file
  2. Radiometric calibration → sigma_0
  3. Speckle filter (Refined Lee or Lee Sigma)
  4. Terrain flattening (gamma_0)
  5. Range-Doppler terrain correction → geocoded output
  6. Convert linear → dB scaling

This module records the shape; we'll wire it up only once 5+ users ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SpeckleFilter = Literal["refined_lee", "lee_sigma", "frost", "gamma_map"]


@dataclass(slots=True, frozen=True)
class SarConfig:
    speckle_filter: SpeckleFilter = "refined_lee"
    polarisations: tuple[str, ...] = ("VV", "VH")
    output_dB: bool = True
    target_resolution: int = 10


def process_sentinel1_grd(
    src_safe_path: Path,
    out_path: Path,
    *,
    cfg: SarConfig | None = None,
) -> Path:
    """Run the standard S1 GRD → analysis-ready stack via pyroSAR + SNAP.

    Requires SNAP installed locally and discoverable on PATH, plus pyroSAR
    in the Python env.  Future implementation; raises a clear error if the
    deps aren't present.
    """
    try:
        from pyroSAR.snap import geocode
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "pyroSAR is required for SAR preprocessing.  Install SNAP first, "
            "then `pip install pyroSAR`."
        ) from exc

    cfg = cfg or SarConfig()
    geocode(
        infile=str(src_safe_path),
        outdir=str(out_path.parent),
        tr=cfg.target_resolution,
        polarizations=list(cfg.polarisations),
        speckle_filter=cfg.speckle_filter,
        refarea=("gamma0", "sigma0"),
        terrain_flattening=True,
        scaling="dB" if cfg.output_dB else "linear",
    )
    return out_path
