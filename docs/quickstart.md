# Quickstart

## End-user install

Once published to plugins.qgis.org:

1. **Plugins → Manage and Install Plugins → All**
2. Search for **Terranova**, click **Install Plugin**
3. Toggle the toolbar icon to open the dock

## Developer install

```bash
git clone https://github.com/terranova-rs/terranova
cd terranova

# Python deps via uv
uv sync --all-extras --dev

# Build the React panel
make ui-build

# Symlink into your QGIS profile and launch QGIS
make deploy
```

On Windows substitute `make` with `nmake` or run the Makefile via Git Bash.

## Smoke test

After installing:

1. Open a multi-band raster (a Sentinel-2 L2A scene is fine).
2. **Processing Toolbox → Terranova → Indices → Compute NDVI**.
3. Pick red and NIR bands; run.
4. The output GeoTIFF should appear as a new layer with NDVI values in `[-1, 1]`.

The Terranova dock will show the welcome screen rendered in an embedded React panel. Press `Ctrl K` (or `Cmd K` on macOS) to open the command palette.

## Optional dependencies

| Group | Install | What it unlocks |
|-------|---------|-----------------|
| `[ml]` | `pip install -e .[ml]` | Foundation models (Prithvi, Clay), SAM 3, ONNX Runtime, SHAP, Optuna |
| `[gpu]` | `pip install -e .[gpu]` | CUDA `onnxruntime-gpu` |
| `[timeseries]` | `pip install -e .[timeseries]` | BFAST, Zarr, dask, MP4 export |

## Troubleshooting

- **Dock loads but shows "Web bundle not found"** — run `make ui-build` first.
- **Web panel says "QtWebEngine is not available"** — on Debian/Ubuntu: `sudo apt install python3-pyqtwebengine`.
- **`ModuleNotFoundError: rasterio`** — install into your QGIS Python: `python -m pip install rasterio` from the QGIS Python console.
