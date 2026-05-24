# Terranova

> Classify Earth, gracefully.

A modern QGIS 3.40+ / 4.x plugin for semi-automatic classification, foundation-model inference, and time-series change detection.

## Why Terranova

The Semi-Automatic Classification Plugin (SCP) has been the de-facto QGIS plugin for supervised classification for over a decade. Its scope is unmatched, but its UX has not been redesigned since 2016 and its classifier stack is sklearn-era. Terranova keeps SCP's surface area and adds:

- **STAC + COG everywhere.** Search Planetary Computer, Earth Search, and CDSE; build lazy xarray cubes without scene-by-scene download.
- **Foundation models.** Prithvi-EO-2.0, Clay v1.5, TerraMind, SAM 3.
- **Time-series.** BFAST, LandTrendr, CCDC running per-pixel on Zarr cubes.
- **Modern UI.** Command palette, wizards, dark mode, embedded React via QtWebEngine.

## Get started

- [Quickstart](quickstart.md) — install and run the smoke test.
- [Architecture](architecture.md) — how the three layers fit together.
- Workflows: [Classification](workflows/classification.md) · [Time-series](workflows/timeseries.md) · [SAM segmentation](workflows/sam.md).

## Status

| Phase | Scope | State |
|-------|-------|-------|
| 0 | Skeleton, CI, web bridge, NDVI alg | In progress |
| 1 | STAC search + classical classification | Planned |
| 2 | Foundation models + SAM | Planned |
| 3 | Time-series + change detection | Planned |
| 4 | Polish, i18n, public release | Planned |

## Licence

[GPL-3.0-or-later](https://www.gnu.org/licenses/gpl-3.0.html).
