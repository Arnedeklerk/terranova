"""BBox utility helpers — buffer, expand-to-pixel-grid, intersect, reproject."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass

from ..models import BBox


def buffer(bbox: BBox, *, degrees: float) -> BBox:
    """Expand a WGS84 bbox by ``degrees`` on every side, clipped to global extent."""
    return BBox(
        west=max(-180.0, bbox.west - degrees),
        south=max(-90.0, bbox.south - degrees),
        east=min(180.0, bbox.east + degrees),
        north=min(90.0, bbox.north + degrees),
    )


def intersects(a: BBox, b: BBox) -> bool:
    """True if the two WGS84 bboxes overlap (not just touch)."""
    return not (
        a.east <= b.west or a.west >= b.east or a.north <= b.south or a.south >= b.north
    )


def intersection(a: BBox, b: BBox) -> BBox | None:
    """Return the intersection of two bboxes, or None if they don't overlap."""
    if not intersects(a, b):
        return None
    return BBox(
        west=max(a.west, b.west),
        south=max(a.south, b.south),
        east=min(a.east, b.east),
        north=min(a.north, b.north),
    )


def width(bbox: BBox) -> float:
    return bbox.east - bbox.west


def height(bbox: BBox) -> float:
    return bbox.north - bbox.south


def area_deg2(bbox: BBox) -> float:
    """Area in *degrees squared* — useful for rough size sanity checks, not science."""
    return width(bbox) * height(bbox)


def to_crs(
    bbox: BBox, src_crs: str = "EPSG:4326", dst_crs: str = "EPSG:3857"
) -> tuple[float, float, float, float]:
    """Reproject a bbox into ``dst_crs``.  Returns a plain tuple in the new CRS units."""
    from pyproj import Transformer

    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    west, south = transformer.transform(bbox.west, bbox.south)
    east, north = transformer.transform(bbox.east, bbox.north)
    return (west, south, east, north)
