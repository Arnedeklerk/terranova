# NOTICE — Third-party software used by TerraScope

TerraScope is released under GPL-3-or-later (see [LICENSE](LICENSE)).  It depends on, and is grateful to, the following projects:

## Direct Python dependencies

| Project | Licence | Used for |
|---------|---------|----------|
| pydantic | MIT | State validation + bridge schema |
| pystac-client | Apache-2 | STAC search |
| planetary-computer | MIT | Auto-signing Planetary Computer asset URLs |
| odc-stac | Apache-2 | Lazy xarray stack building |
| stackstac | MIT | Alternative lazy stack |
| rioxarray | Apache-2 | rio + xarray glue |
| rasterio | BSD-3-Clause | Raster I/O |
| rio-cogeo | BSD-3-Clause | COG profiles + validation |
| scikit-learn | BSD-3-Clause | Classical classifiers |
| spyndex | MIT | Spectral indices catalogue |
| reportlab | BSD-3-Clause | PDF accuracy report |
| matplotlib | BSD-style | Confusion-matrix heatmap |

## Optional Python dependencies (`[ml]`, `[gpu]`, `[timeseries]`)

| Project | Licence | Used for |
|---------|---------|----------|
| PyTorch | BSD-3-Clause | Foundation-model training |
| Lightning | Apache-2 | Trainer wrapper |
| TerraTorch | Apache-2 | Prithvi, Clay, TerraMind, DOFA wrappers |
| segment-geospatial | Apache-2 | SAM 3 in QGIS |
| onnxruntime | MIT | ONNX inference (CPU + CUDA + DML) |
| shap | MIT | Tree explainability |
| optuna | MIT | Hyperparameter tuning |
| imbalanced-learn | MIT | Class imbalance handling |
| LightGBM | MIT | Gradient boosting |
| XGBoost | Apache-2 | Gradient boosting |
| bfast | LGPL-3 | Time-series change detection |
| zarr | MIT | Time-series cube storage |
| dask | BSD-3-Clause | Lazy compute |

## Web tier dependencies

| Project | Licence | Used for |
|---------|---------|----------|
| React | MIT | Embedded UI panel |
| Vite | MIT | Bundler |
| Tailwind CSS | MIT | Styling |
| Radix UI | MIT | Dialog, Tooltip primitives |
| Zustand | MIT | UI state |
| Plotly.js | MIT | Spectral / time-series charts |
| MapLibre GL JS | BSD-3-Clause | Before/after slider |

## Foundation model checkpoints

| Model | Licence | Source |
|-------|---------|--------|
| Prithvi-EO-2.0 (300M / 600M) | Apache-2 | IBM / NASA — HuggingFace `ibm-nasa-geospatial` |
| Clay v1.5 | OpenRAIL | `made-with-clay/clay-foundation-model` |
| TerraMind | Apache-2 | IBM Research |
| SAM 3 | Apache-2 | Meta AI Research |

## Sample data

Sample datasets bundled in `samples/` are derived from open data — ESA Copernicus and US Government public domain.  Per-file provenance and licence is recorded in `samples/LICENSES.md`.

## Imagery in screenshots / docs

Screenshots in documentation use ESA Copernicus Sentinel-2 imagery, available under the Copernicus open data policy.
