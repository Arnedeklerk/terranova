# API reference

`terrascope.api` is the stable public surface for scripting TerraScope from notebooks or the QGIS Python console. Everything reachable from this module is covered by semantic versioning.

## Quickstart

```python
from terrascope import api

# Search Sentinel-2 over a bbox + date range
items = api.search_sentinel2(
    bbox=(-0.5, 51.3, 0.3, 51.7),
    datetime="2024-06-01/2024-09-30",
    max_cloud=20,
)

# Build a lazy xarray cube
stack = api.lazy_stack(items, bands=("red", "green", "blue", "nir"))
```

## Surface

| Symbol | Description |
|--------|-------------|
| `api.__version__` | Current TerraScope version. |
| `api.ProjectState` | Pydantic model for the project state file (`terrascope.json`). |
| `api.search_sentinel2(...)` | Convenience over `core.catalog.stac.search_s2_l2a` against Planetary Computer. |
| `api.open_planetary_computer()` | Pre-configured `pystac_client.Client` with auto-signing. |
| `api.lazy_stack(items, ...)` | Build a dask-chunked `xarray.DataArray` from a STAC ItemCollection. |

Internal modules (`terrascope.core.*`, `terrascope.controllers.*`) may change between minor versions; `terrascope.api` may not.
