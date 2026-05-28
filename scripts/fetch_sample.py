#!/usr/bin/env python3
"""Fetch the Phase-1 demo dataset: a 5 km Sentinel-2 clip + class polygons.

Currently ships only the script.  A future version wires it into the welcome screen.
Run manually for now:

    python scripts/fetch_sample.py samples/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def fetch_khartoum(out_dir: Path) -> int:
    """Pull a Sentinel-2 L2A scene over central Khartoum + bundled labels.

    Hits Microsoft Planetary Computer.  No CDSE OAuth required.
    """
    try:
        import planetary_computer
        import pystac_client
        import rioxarray  # noqa: F401  (registers .rio)
        import xarray as xr
    except ImportError as exc:
        print(f"missing dep: {exc.name}.  pip install -e .[dev]", file=sys.stderr)
        return 1

    bbox = (32.470, 15.560, 32.560, 15.650)
    print(f"Searching Sentinel-2 L2A over {bbox} …")

    client = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = list(
        client.search(
            collections=["sentinel-2-l2a"],
            bbox=bbox,
            datetime="2024-01-01/2024-12-31",
            query={"eo:cloud_cover": {"lt": 5}},
            max_items=1,
        ).item_collection()
    )
    if not items:
        print("no item found — try widening the date range", file=sys.stderr)
        return 2

    item = items[0]
    print(f"Picked {item.id} (cloud {item.properties.get('eo:cloud_cover'):.1f}%)")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "khartoum_s2_2024.tif"

    # Stack a sensible 4-band RGBNIR composite.
    bands = ["red", "green", "blue", "nir"]
    import odc.stac

    da = odc.stac.load([item], bands=bands, resolution=10).isel(time=0)
    # Clip to the AOI to keep the file small.
    da = da.rio.clip_box(*bbox, crs="EPSG:4326")
    da.rio.to_raster(out_path, compress="deflate", tiled=True)
    print(f"Wrote {out_path}  ({out_path.stat().st_size / 1e6:.1f} MB)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out_dir", type=Path, nargs="?", default=Path("samples"))
    args = p.parse_args()
    return fetch_khartoum(args.out_dir)


if __name__ == "__main__":
    sys.exit(main())
