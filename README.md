# Terranova

> Earth observation for QGIS.

A modern QGIS plugin (3.40+ / 4.x) for STAC search, classification, accuracy reporting, and time-series change detection. Built on a STAC-first, COG / xarray pipeline with native Qt dialogs *and* a React-in-QWebEngine dock with an embedded interactive Leaflet map for AOI picking and footprint inspection.

**Status:** experimental — usable end-to-end for catalogue search + classification + change detection, but expect rough edges.

## Authors

- Cole Battell
- Arné de Klerk — KnetMiner / Rothamsted Research

## Why

The Semi-Automatic Classification Plugin (SCP) is the de-facto QGIS plugin for supervised classification, with 1.15 M+ cumulative downloads and a decade of feature accretion. But its UX has not been redesigned since 2016, its install path is fragile, and its classifier stack is sklearn-era. Terranova replaces it with:

- **STAC + COG everywhere.** Search Planetary Computer, Earth Search, and CDSE; build lazy xarray cubes without scene-by-scene download.
- **Foundation models.** Prithvi-EO-2.0, Clay v1.5, TerraMind, SAM 3 — via [TerraTorch](https://github.com/IBM/terratorch) and segment-geospatial.
- **Time-series.** BFAST, LandTrendr, CCDC running per-pixel on Zarr cubes.
- **Modern UI.** Command palette, wizards, dark mode, embedded React via QtWebEngine (safe since QGIS 3.36).

## Architecture

Three layers, hard-separated:

```
UI (PyQt6 + qfluentwidgets  ↔  React 18 + Vite in QWebEngineView)
       │
Controllers (QgsTask, layer plumbing)
       │
Domain (pure Python — no qgis.* imports)
       │
Infra (rasterio, odc-stac, pystac-client, scikit-learn, onnxruntime, terratorch, ...)
```

See [docs/architecture.md](docs/architecture.md) for the full diagram.

## Quickstart (developer)

```bash
# Clone and install dev deps (Python 3.10–3.12)
git clone https://github.com/Arnedeklerk/terranova
cd terranova
uv sync --all-extras --dev

# Build the React panel
make ui-build

# Deploy into your QGIS profile and launch QGIS
make deploy
```

End-user installs go via Plugins → Manage and Install → Search "Terranova" (once published to plugins.qgis.org).

## Coming from SCP?

See [docs/scp_migration.md](docs/scp_migration.md) — one-page cheat-sheet mapping every SCP concept to its Terranova equivalent.

## Phase plan

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| 0 | Skeleton, CI, web bridge, NDVI alg | Plugin loads on three OSes |
| 1 | STAC search + classical classification | RF / LightGBM / XGBoost end-to-end |
| 2 | Foundation models + SAM | Prithvi fine-tune + SAM 3 prompts |
| 3 | Time-series + change detection | BFAST / LandTrendr / CCDC |
| 4 | Polish, i18n, public release | v1.0.0 on plugins.qgis.org |

## Licence

[GPL-3.0-or-later](LICENSE). Distributed via the official QGIS plugins page.

## Privacy

See [PRIVACY.md](PRIVACY.md). Telemetry is opt-in and minimal.
