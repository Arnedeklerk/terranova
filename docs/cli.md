# Command-line tool

Terranova installs a small CLI alongside the QGIS plugin so you can use the same core operations from a terminal, a notebook, or CI. It calls into `terranova.core` directly — no QGIS install required.

```bash
pip install -e .          # in a clone, or
pip install terranova    # once published
```

## Commands

### `terranova ndvi`

```bash
terranova ndvi input.tif out.tif --red 4 --nir 8
```

Computes NDVI from a multi-band raster. `--red` and `--nir` are 1-based band indices in the input file.

### `terranova index <kind>`

```bash
terranova index nbr scene.tif burn.tif --band-a 4 --band-b 6
```

Computes any two-band normalised-difference index. `<kind>` is one of `ndwi`, `ndmi`, `nbr`, `ndsi`. The semantics of `--band-a` and `--band-b` depend on the index; see [the indices module](api/index.md) or `terranova index <kind> --help`.

### `terranova search-s2`

```bash
terranova search-s2 -0.5 51.3 0.3 51.7 2024-06-01/2024-09-30 --max-cloud 20
```

STAC search Sentinel-2 L2A on Microsoft Planetary Computer. Returns the matching items as JSON to stdout — useful for piping into `jq`.

### `terranova accuracy-report`

```bash
terranova accuracy-report report.json report.pdf
```

Render a one-page PDF accuracy report from a JSON blob produced by `terranova.core.accuracy.metrics.assess(...)`.

### `terranova validate-cog`

```bash
terranova validate-cog candidate.tif
```

Validate whether a GeoTIFF is a proper Cloud-Optimised GeoTIFF. Exits 0 for valid, 2 for invalid.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generic error (printed to stderr) |
| 2 | `validate-cog` only — not a valid COG |
| 130 | Interrupted by Ctrl+C |

## In a notebook

Everything the CLI does is also available as a stable Python API:

```python
from terranova import api
items = api.search_sentinel2(
    bbox=(-0.5, 51.3, 0.3, 51.7),
    datetime="2024-06-01/2024-09-30",
    max_cloud=20,
)
stack = api.lazy_stack(items)
```
