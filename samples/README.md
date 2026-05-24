# Sample datasets

The bundled samples are used by the onboarding wizard and by recipe tutorials.
They are checked into the repo as small COG + GeoJSON triples (under a few MB
each) so the plugin is immediately useful with no network access.

## Phase 0

The sample dataset is intentionally not committed yet — Phase 1 adds:

- `khartoum_s2_2024.tif` — a 5 km clipping of a Sentinel-2 L2A scene over
  central Khartoum, ESA Copernicus open data
- `khartoum_classes.geojson` — 50 polygons across 5 land-cover classes
- `khartoum_validation.geojson` — 20 hold-out polygons

All samples sourced from open data only (ESA Copernicus, USGS public domain).
Provenance per file is recorded in `LICENSES.md` when the data lands.
