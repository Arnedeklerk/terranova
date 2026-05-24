# Changelog

All notable changes to TerraScope are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Phase 1 (remainder) + Phase 2 + Phase 3 + Phase 4 + Phase 5
- **Phase 1**: `CdseLoginDialog` (device-code OAuth flow with browser handoff).
- **Phase 2**: `SamDialog` (text + click prompts via segment-geospatial),
  `FoundationDialog` (Prithvi / Clay / TerraMind fine-tune via TerraTorch),
  real `core/ml/sam.py` + `core/ml/foundation.py` + ONNX export.
- **Phase 3**: `TimeSeriesDialog` (STAC search → cube → NDVI/NBR/NDMI →
  CuSum/BFAST/LandTrendr per-pixel → break + magnitude rasters + MP4),
  `core/timeseries/change.py` unified driver, real `core/timeseries/cube.py`,
  numpy LandTrendr-lite, CuSum fallback.
- **Phase 4**: Cloudflare Worker telemetry endpoint at
  `deploy/cloudflare-worker/` with KV storage + 30-day retention + strict
  six-field validation + per-IP rate limit; landing page at `deploy/landing/`
  with `_headers` CSP, `latest.json` for the update-check;
  `core/update_check.py` with 24h cache + numeric semver compare;
  Crowdin config + i18n workflow; release workflow that builds the .zip,
  publishes to plugins.qgis.org via `qgis-plugin-ci`, and deploys landing +
  worker to Cloudflare.
- **Phase 5 (speculative)**: `core/preprocessing/sen2cor.py` subprocess
  wrapper, `core/preprocessing/sar.py` pyroSAR shape,
  `core/backends/openeo_backend.py` + `ComputeBackend` protocol.

### Fixed
- Architectural rule violation: `core/utils/colormap.py` imported `qgis.*`.
  Moved the QGIS factory to `ui/colormap_qgis.py`; `core` is pure again.
- `ProgressReporter.substep` composition was wrong (children took fraction
  of *remaining* extent, breaking sibling-sum-to-1.0).  Now siblings compose.
- Hypothesis tests for NDVI generated mismatched array shapes; consolidated
  via `@st.composite`.

### Verified
- AST parse of all 146 Python files in the repo — zero syntax errors.
- pytest with OSGeo4W Python 3.12 + `PROJ_DATA` pointed at pyproj's
  bundled data: **199 unit tests pass, 0 failures, 2 skipped**.
- ruff: 30 remaining stylistic nits (variable naming matching paper
  notation, deferred imports — all deliberate); 100 auto-fixes applied.
- mypy strict on core: optional-dep imports stubbed in `mypy.ini`;
  two real type fixes landed (matplotlib `tostring_rgb` → `buffer_rgba`
  for matplotlib 3.10+, modern `torch.onnx.export` tuple signature).
- Cloudflare Worker: `npm run typecheck` clean; **6 vitest tests pass**
  (incl. unknown-field-rejection enforcing the six-field privacy schema).
- Web UI tier: `vite build` clean (105 modules, 192 kB → 63 kB gzipped).
- CLI end-to-end smoke: `terrascope ndvi` synthesised a 4-band raster,
  ran NDVI, wrote a float32 GeoTIFF — output is 32×32, all 1024 pixels
  finite, range `[-0.85, +0.85]` matching the synthetic gradient.

## [0.1.0] — 2026-05-23

### Added

- Phase 0 prototype skeleton with Phase 1-shape extensions.
- `src/` layout repo with hatchling, ruff, mypy strict, pytest, pre-commit, editorconfig, gitattributes.
- `classFactory` + `TerraScopePlugin` lifecycle with dock toggle and Processing-provider registration.
- Embedded `QWebEngineView` with React 18 + TypeScript + Tailwind + Radix UI.
- `Bridge` QObject + QWebChannel with Pydantic-validated message round-trip.
- Pure-Python domain layer covering:
  - STAC catalogue access (Planetary Computer, Earth Search, CDSE) + CDSE OAuth device-code flow.
  - Lazy xarray cube building (odc-stac) with composites, spatial/temporal clipping, OmniCloudMask + SCL cloud masking.
  - Classical ML (sklearn / LightGBM / XGBoost) — `build_estimator`, `train`, `predict_to_cog`, `cross_validate`, `extract_training_samples`, `tune_hyperparameters` (Optuna TPE), nested CV, probability calibration, ONNX export, SHAP explainer, majority/sieve/reclassify post-processing.
  - Foundation-model stubs (TerraTorch Prithvi/Clay/TerraMind; segment-geospatial SAM 3 wrappers).
  - Time-series: BFAST + numpy CuSum fallback; Zarr cube I/O.
  - Accuracy: confusion matrix, OA/kappa, user's & producer's, F1, McNemar paired test, PDF report.
  - Sensor band registry for Sentinel-2 / Landsat 4-9.
  - Numpy region-grow ROI (euclidean + spectral-angle).
  - Project state with Pydantic v2 + stepwise migration framework + reversible ledger.
  - Opt-in telemetry (six-field payload, six-field test enforcement).
  - BBox / colormap (Crameri default) / hashing / progress / logging utilities.
  - Match-to-template raster reprojection.
- 7 Processing algorithms: NDVI, NDWI, NDMI, NBR, NDSI, majority filter, sieve.
- `terrascope` CLI: `ndvi`, `index`, `search-s2`, `accuracy-report`, `validate-cog`.
- Web tier panels: Welcome, CatalogSearch, CommandPalette (Ctrl/Cmd+K), Inspector, SpectralPlot (Plotly), BeforeAfter (MapLibre), TelemetryConsent.
- Zustand store; QWebChannel client with browser-dev stub.
- Native Qt UI: dock with graceful fallbacks, dark/light QSS from `tokens.yaml`, SVG icon, sample QML classification style.
- 25+ unit-test files covering models, indices (concrete + Hypothesis property), accuracy, state migration, dispatch, CLI, telemetry, composites, region grow, post-process, sensors, bbox, config, metadata.txt sync, catalog controller, CDSE, inference cache, band-set, BFAST CuSum, viz, progress, logging, hashing, and an architectural-guard test that blocks any `qgis.*`/`PyQt*` import under `core/`.
- GitHub Actions: lint + type + matrix unit tests (Ubuntu/Windows/macOS × py 3.10/3.11/3.12), web typecheck + build, QGIS-container integration (advisory), release workflow producing a plugin `.zip`, docs deploy to GitHub Pages.
- Documentation (MkDocs Material): home, quickstart, installation, SCP migration cheat sheet, architecture (with Mermaid module graph), ML stack, recipes DSL, CLI, telemetry, workflow stubs, API reference, privacy.
- Recipes: `crop_classification.yaml`, `deforestation_alert.yaml`.
- AGENTS.md (hard rules), CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, NOTICE.md, HANDOFF.md.
- GitHub issue templates (bug + feature), PR template, dependabot config (grouped updates).
- `scripts/sync_version.py`, `scripts/fetch_sample.py`.
- `core.utils.timing` + `core.utils.feature_flags` + `core.utils.parallel` + `core.utils.naming` + `core.utils.hashing` helpers.
- `core.recipes.loader` + `core.viz.figures` (matplotlib + MP4 animation export) + `core.errors`.
- `core.timeseries.landtrendr` numpy port + `core.timeseries.bfast.detect_breaks_cusum` fallback.
- `core.io.read_window` + `core.io.reproject_to_match`.
- `INVENTORY.md` — module-by-module status map.
- `docs/risks.md` + `docs/reviewer.md` + `docs/development.md` + `docs/installation.md` + `docs/cli.md` + `docs/telemetry.md` + `docs/recipes.md` + `docs/scp_migration.md` + `docs/phase4_deployment.md` + `docs/ml.md`.
- GitHub `CODEOWNERS`, issue templates, PR template, security workflow (pip-audit + npm-audit + CodeQL), dependabot config.

[Unreleased]: https://github.com/terrascope-rs/terrascope/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/terrascope-rs/terrascope/releases/tag/v0.1.0
