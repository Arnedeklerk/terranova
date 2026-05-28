"""Validation-point generation strategies for accuracy assessment.

Three strategies, all writing a GeoPackage with one Point feature per
sample and these fields:

- ``predicted`` (int): the class code sampled from the classified raster
  at the point.  Reserved 0 = nodata pixels are skipped.
- ``truth`` (int): empty / zero — the user fills these in by editing
  the layer in QGIS, then runs the accuracy job to get OA / kappa / etc.
- ``note`` (str): free-text scratch column for the user.

Strategies:

- ``"random"``                — N uniformly random valid pixels.
- ``"stratified"``            — counts per class proportional to that class's
                                pixel count in the raster (with a floor of
                                ``min_per_class`` so rare classes still get
                                tested).
- ``"equalized_stratified"``  — same N per class regardless of class size.
                                Best for accuracy-assessment of rare classes.

Pure-Python — no qgis imports — so the unit tests can drive this without
QGIS installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np

SamplingStrategy = Literal["random", "stratified", "equalized_stratified"]


def generate_validation_points(
    raster_path: Path,
    out_path: Path,
    *,
    strategy: SamplingStrategy,
    n_total: int = 300,
    points_per_class: int = 30,
    min_per_class: int = 5,
    random_state: int = 42,
) -> dict:
    """Sample validation points from a classified raster.

    Returns a small summary dict for the caller to log.  All file I/O
    goes through OGR (ships with QGIS, no extra dep).
    """
    import rasterio
    from osgeo import ogr, osr

    rng = np.random.default_rng(random_state)

    with rasterio.open(str(raster_path)) as src:
        arr = src.read(1)
        transform = src.transform
        crs_wkt = src.crs.to_wkt() if src.crs else None

    # Treat 0 as nodata (terranova's classification COGs reserve 0).
    # Also respect explicit src.nodata if it's something else.
    nodata_vals = {0}
    if src.nodata is not None:
        nodata_vals.add(int(src.nodata))
    valid_mask = ~np.isin(arr, list(nodata_vals))
    if not valid_mask.any():
        raise RuntimeError(
            "Raster has no valid pixels — every value is nodata. "
            "Check the raster you picked."
        )

    rows, cols = np.where(valid_mask)
    classes = arr[rows, cols]

    if strategy == "random":
        n = min(int(n_total), rows.size)
        idx = rng.choice(rows.size, size=n, replace=False)
        sel_rows, sel_cols, sel_classes = rows[idx], cols[idx], classes[idx]
    elif strategy in {"stratified", "equalized_stratified"}:
        unique, counts = np.unique(classes, return_counts=True)
        if strategy == "stratified":
            # Proportional split of n_total across classes, with a floor
            # so rare classes still get tested.
            shares = counts / counts.sum()
            per_class = np.maximum(
                (shares * n_total).round().astype(int),
                min_per_class,
            )
        else:  # equalized
            per_class = np.full(unique.shape, int(points_per_class), dtype=int)
        sel_rows_list: list[np.ndarray] = []
        sel_cols_list: list[np.ndarray] = []
        sel_classes_list: list[np.ndarray] = []
        for cls, want in zip(unique, per_class, strict=False):
            cls_mask = classes == cls
            n_avail = int(cls_mask.sum())
            n_take = min(int(want), n_avail)
            if n_take == 0:
                continue
            pool = np.where(cls_mask)[0]
            picked = rng.choice(pool, size=n_take, replace=False)
            sel_rows_list.append(rows[picked])
            sel_cols_list.append(cols[picked])
            sel_classes_list.append(classes[picked])
        if not sel_rows_list:
            raise RuntimeError("Stratified sampler picked zero points.")
        sel_rows = np.concatenate(sel_rows_list)
        sel_cols = np.concatenate(sel_cols_list)
        sel_classes = np.concatenate(sel_classes_list)
    else:
        raise ValueError(f"unknown sampling strategy: {strategy!r}")

    # Convert pixel (row, col) to map (x, y) — affine transform's
    # (a, b, c, d, e, f) gives x = a*col + b*row + c, y = d*col + e*row + f.
    xs = transform.a * (sel_cols + 0.5) + transform.b * (sel_rows + 0.5) + transform.c
    ys = transform.d * (sel_cols + 0.5) + transform.e * (sel_rows + 0.5) + transform.f

    # Write the GeoPackage via OGR — same pattern the catalog/preview
    # path uses, no fiona dependency required.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(out_path))
    srs = osr.SpatialReference()
    if crs_wkt:
        srs.ImportFromWkt(crs_wkt)
    else:
        srs.ImportFromEPSG(4326)
    layer = ds.CreateLayer(
        "terranova_validation", srs=srs, geom_type=ogr.wkbPoint
    )
    for name, ogr_type, width in (
        ("predicted", ogr.OFTInteger, None),
        ("truth", ogr.OFTInteger, None),
        ("note", ogr.OFTString, 120),
    ):
        f = ogr.FieldDefn(name, ogr_type)
        if width is not None:
            f.SetWidth(width)
        layer.CreateField(f)
    defn = layer.GetLayerDefn()
    for x, y, cls in zip(xs, ys, sel_classes, strict=False):
        feat = ogr.Feature(defn)
        feat.SetField("predicted", int(cls))
        feat.SetField("truth", 0)
        feat.SetField("note", "")
        geom = ogr.Geometry(ogr.wkbPoint)
        geom.AddPoint(float(x), float(y))
        feat.SetGeometry(geom)
        layer.CreateFeature(feat)
        feat = None  # release
    ds = None  # close + flush

    return {
        "output_path": str(out_path),
        "n_points": int(sel_rows.size),
        "strategy": strategy,
        "classes_sampled": [int(c) for c in np.unique(sel_classes)],
    }
