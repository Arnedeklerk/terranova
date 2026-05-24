"""SAM-prompted segmentation via segment-geospatial.

We wrap :mod:`samgeo` (segment-geospatial, opengeos) which itself wraps
Meta's SAM 2 / SAM 3 weights with geospatial-aware tiling, CRS handling,
and polygon export.

Two prompt types in Phase 2:

- **point / box prompts** — interactive (one click → instant mask)
- **text prompts** — Grounded-SAM style ("buildings", "agricultural field")

Embeddings are cached per raster + model in :data:`embedding_cache_dir`.
The cache key is the SHA-256 of the raster contents + the model name, so
two different rasters never collide even with the same filename, and a
re-saved raster invalidates its own cache.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from ..utils.hashing import file_hash, short_hash

if TYPE_CHECKING:  # pragma: no cover
    pass

SamModel = Literal["sam2_b", "sam2_l", "sam3"]


# --------------------------------------------------------------------------- #
# Embedding cache                                                             #
# --------------------------------------------------------------------------- #
def embedding_cache_dir(project_dir: Path) -> Path:
    """Where embeddings live for a given project."""
    d = Path(project_dir) / "embeddings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _embedding_path(project_dir: Path, raster_path: Path, model: str) -> Path:
    raster_h = file_hash(raster_path, length=12)
    model_h = short_hash(model, length=6)
    return embedding_cache_dir(project_dir) / f"{raster_path.stem}__{raster_h}__{model_h}.npz"


# --------------------------------------------------------------------------- #
# Prompt-based segmentation                                                   #
# --------------------------------------------------------------------------- #
def segment_from_points(
    raster_path: Path,
    out_geopackage: Path,
    *,
    points: list[tuple[float, float]],
    labels: list[int] | None = None,
    model: SamModel = "sam2_b",
    project_dir: Path | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> Path:
    """Segment ``raster_path`` using foreground/background point prompts.

    Parameters
    ----------
    points
        List of ``(x, y)`` map coordinates in the raster CRS.
    labels
        Per-point label: ``1`` = foreground (include), ``0`` = background
        (exclude).  Defaults to all foreground.
    model
        Which SAM checkpoint to use (``"sam2_b"``, ``"sam2_l"``, or ``"sam3"``).
    project_dir
        Where to cache embeddings; defaults to ``raster_path.parent``.

    Writes a GeoPackage containing one polygon per segment.  Returns its path.
    """
    import samgeo

    if labels is None:
        labels = [1] * len(points)
    if len(labels) != len(points):
        raise ValueError("points and labels must be the same length")
    if project_dir is None:
        project_dir = Path(raster_path).parent

    out_geopackage = Path(out_geopackage)
    out_geopackage.parent.mkdir(parents=True, exist_ok=True)

    sam = samgeo.SamGeo(
        model_type=_to_samgeo_model(model),
        sam_kwargs=None,
    )
    if progress_cb:
        progress_cb(0.1)
    sam.set_image(str(raster_path))
    if progress_cb:
        progress_cb(0.5)
    sam.predict(
        point_coords=points,
        point_labels=labels,
        point_crs=None,  # samgeo reads from set_image
        output=str(out_geopackage),
    )
    if progress_cb:
        progress_cb(1.0)
    return out_geopackage


def segment_from_text(
    raster_path: Path,
    out_geopackage: Path,
    *,
    prompt: str,
    box_threshold: float = 0.24,
    text_threshold: float = 0.24,
    model: SamModel = "sam3",
    project_dir: Path | None = None,
    progress_cb: Callable[[float], None] | None = None,
) -> Path:
    """Text-prompted segmentation (Grounded-SAM-style).

    Example prompts: ``"buildings"``, ``"agricultural field"``, ``"river"``.

    Requires the ``langsam`` flavour of segment-geospatial — the wrapper
    pulls Grounding-DINO for the text→box step and SAM 3 for masks.
    """
    from samgeo.text_sam import LangSAM

    if project_dir is None:
        project_dir = Path(raster_path).parent

    out_geopackage = Path(out_geopackage)
    out_geopackage.parent.mkdir(parents=True, exist_ok=True)

    sam = LangSAM(model_type=_to_samgeo_model(model))
    if progress_cb:
        progress_cb(0.1)
    sam.predict(
        str(raster_path),
        prompt,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
    )
    if progress_cb:
        progress_cb(0.8)
    # `sam.show_anns` writes mask raster + polygon GPKG.
    sam.raster_to_vector(
        sam.prediction_path if hasattr(sam, "prediction_path") else None,
        str(out_geopackage),
    )
    if progress_cb:
        progress_cb(1.0)
    return out_geopackage


def encode_image(
    raster_path: Path,
    *,
    project_dir: Path | None = None,
    model: SamModel = "sam2_b",
) -> Path:
    """Pre-compute and cache SAM embeddings for ``raster_path``.

    Returns the path to the cached embedding.  Subsequent prompts on the same
    raster + model skip the encode step, which is the expensive one.
    """
    import samgeo

    if project_dir is None:
        project_dir = Path(raster_path).parent
    cache = _embedding_path(Path(project_dir), Path(raster_path), model)
    if cache.exists():
        return cache

    sam = samgeo.SamGeo(model_type=_to_samgeo_model(model))
    sam.set_image(str(raster_path))
    sam.save_image_embeddings(str(cache))
    return cache


# --------------------------------------------------------------------------- #
def _to_samgeo_model(model: SamModel) -> str:
    """Map our enum onto samgeo's strings."""
    mapping = {
        "sam2_b": "sam2-hiera-base-plus",
        "sam2_l": "sam2-hiera-large",
        "sam3": "sam3",
    }
    return mapping[model]
