# HANDOFF — TerraScope

**Last update:** 2026-05-23
**Phase:** 0 — prototype skeleton (heavily fleshed out toward Phase 1)

**Repo size:** 83 Python source files, 37 test files, 13 web-tier files,
16 docs pages, 2 recipes, 7 Processing algorithms, 5 GitHub workflows,
CLI with 5 subcommands.

## What landed in this session

### Repo + tooling
- `src/` layout, hatchling pyproject, ruff, mypy strict, pytest, pre-commit.
- Editorconfig + gitattributes (LF everywhere, linguist-generated for `dist/`).
- CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, NOTICE.md, AGENTS.md.
- GitHub issue templates (bug + feature), PR template, dependabot config.
- `.qgis-plugin-ci` config for the release workflow.
- `scripts/sync_version.py` keeps `version.py`, `metadata.txt`, and `pyproject.toml` in sync.

### Plugin lifecycle
- `classFactory`, `TerraScopePlugin`, dock toggle, Processing-provider registration + unregister.
- `terrascope.config` per-user settings module.
- `terrascope.version` single source of truth.

### Pure-Python domain (`core/*`) — 14 sub-packages, ~50 modules
- Pydantic v2 state models: `BBox`, `DateRange`, `CatalogSearch`, `ClassifierConfig`, `LedgerEntry`, `TelemetryEvent`, `CommandMessage`, `CommandResult`.
- `core.catalog.stac` — Planetary Computer, Earth Search, CDSE clients; S2 + Landsat search; `lazy_stack` via odc-stac.
- `core.catalog.cdse` — full device-code OAuth flow + token cache.
- `core.stacking.lazy` — median / mean / p25 / p75 / first_valid / least_cloudy composites; spatial_clip; harmonise_bands.
- `core.stacking.cog` — `write_cog` + `validate`.
- `core.stacking.cloudmask` — SCL implementation; OmniCloudMask hook (Phase 1).
- `core.stacking.bandset` — auto-detect bands from a raster.
- `core.sensors` — band registry for Sentinel-2 / Landsat 8-9 / Landsat 4-7.
- `core.timeseries.indices` — NDVI, NDWI, NDMI, NBR, NDSI, EVI, SAVI; spyndex hook.
- `core.timeseries.{bfast,cube,landtrendr,ccdc}` stubs with public signatures.
- `core.ml.classical` — sklearn / LightGBM / XGBoost estimators; `train`, `predict_to_cog` (real, block-wise rasterio + COG translate), `cross_validate`, `extract_training_samples`, `tune_hyperparameters` (Optuna TPE).
- `core.ml.training_eval` — nested K-fold CV.
- `core.ml.calibration` — Platt / isotonic + Brier score.
- `core.ml.foundation` — TerraTorch wrapper for Prithvi (Phase 2 path).
- `core.ml.inference` — ORT session cache; `export_onnx` for sklearn / LightGBM / XGBoost.
- `core.ml.sam` — segment-geospatial wrappers (Phase 2 stubs).
- `core.ml.explain` — SHAP TreeExplainer wrapper.
- `core.ml.postprocess` — majority filter + sieve + reclassify.
- `core.roi.region_grow` — pure-numpy flood-fill, euclidean or spectral-angle.
- `core.accuracy.metrics` — confusion matrix, OA, kappa, user's/producer's, F1; McNemar paired test.
- `core.accuracy.report` — reportlab + matplotlib PDF report with confusion-matrix heatmap.
- `core.project.state` — `ProjectState` with stepwise migration framework + `record(...)` for ledger.
- `core.telemetry` — opt-in only; payload limited to six fields by privacy policy; `emit`, `inspect_next_payload`, settings round-trip.
- `core.utils.bbox` — buffer, intersect, intersection, to_crs.
- `core.utils.colormap` — Crameri-preferring colormap helpers + `qgis_colour_ramp`.
- `core.io.reproject` — match-to-template reprojection.
- `core.recipes.loader` — Pydantic-validated YAML recipe loader.
- `core.viz.figures` — matplotlib confusion-matrix + spectral-signatures plot.
- `core.errors` — `TerraScopeError` exception hierarchy.
- `core.timeseries.landtrendr` — numpy-only piecewise-linear segmentation.
- `core.timeseries.bfast.detect_breaks_cusum` — dependency-free CuSum fallback.

### Controllers + bridge + tasks
- `controllers.Controllers` with dispatch table: `app.ping`, `app.version`, `app.telemetry.{status,set,inspect}`, `catalog.search`.
- `bridge.Bridge` — QWebChannel host with Pydantic-validated `invoke(...)`.
- `tasks.ClassifyTask` — wraps `predict_to_cog` in `QgsTask`.
- `tasks.cube_task.BuildCubeTask` — odc-stac → Zarr (real-but-minimal body, Phase 3 expands).

### Processing algorithms
- `terrascope:ndvi`, `terrascope:ndwi`, `terrascope:ndmi`, `terrascope:nbr`, `terrascope:ndsi`
- `terrascope:majority_filter`, `terrascope:sieve`

### Native Qt UI
- Dock with embedded React panel; graceful fallback when QtWebEngine absent or web bundle missing.
- Dark + light QSS generated from `tokens.yaml`.
- SVG icon + sample classification QML style.
- Project-explorer / inspector / wizard widget stubs.

### Web tier (React + Vite + TS + Tailwind)
- `Welcome`, `CatalogSearch`, `CommandPalette` (Ctrl/Cmd+K), `Inspector`, `SpectralPlot` (Plotly), `TelemetryConsent` panels.
- Zustand store for view + toasts + busy state.
- QWebChannel client with stub fallback for browser dev.
- Top-level navigation + Cmd-K shortcut + Escape-to-close.
- `serve.bat` + `serve.ps1` for in-browser dev.

### Tests
- 18+ unit-test files covering: models, indices (concrete + Hypothesis property tests), accuracy, project state + migration, dispatch, CLI, telemetry, lazy composite, region grow, post-process, sensors, bbox, config, metadata.txt parseability, catalog controller, CDSE token.
- `pytest-qgis` integration test for plugin import + `classFactory`.
- `conftest.py` registers `unit`, `integration`, `qgis`, `gpu` markers and `--runqgis` / `--rungpu` opt-in flags.

### CI
- GitHub Actions for ruff + mypy, unit tests on Ubuntu/Windows/macOS × py 3.10/3.11/3.12, web typecheck + build, QGIS container tests (advisory).
- Release workflow packages `.zip` and uploads to a GitHub Release.
- Docs workflow deploys MkDocs to GitHub Pages.

### Docs
- MkDocs Material with: home, quickstart, SCP migration cheat-sheet, architecture (incl. Mermaid module graph), ML stack, recipes DSL, workflow stubs, API reference, privacy.

### Recipes
- `crop_classification.yaml`, `deforestation_alert.yaml`.

### CLI
- `terrascope ndvi`, `terrascope index <kind>`, `terrascope search-s2`, `terrascope accuracy-report`, `terrascope validate-cog`.

## Open / next steps

- [ ] Spike the QWebEngine bridge as a 1-day proof-of-concept on QGIS 3.40 LTR on Linux + Windows + macOS.
- [ ] Reserve `terrascope.app` and create the `terrascope-rs` GitHub org; MX for `arne@terrascope.app`.
- [ ] Set up Cloudflare Pages + Workers KV store for telemetry endpoint.
- [ ] Phase 1: full Catalogue-Search Qt dialog wiring; classification workflow end-to-end; PDF report from a real classification.
- [ ] Phase 2: TerraTorch path for Prithvi fine-tune; SAM 3 prompts.
- [ ] Phase 3: Zarr cube + BFAST per-pixel.

## Decisions locked in

- PyQt6 (QGIS 4.x bundles PyQt6).
- GPL-3-or-later (plugins.qgis.org + qfluentwidgets compatible).
- Domain layer publishable separately later — possibly as `terrascope-core` on PyPI.
- Default colour ramps: cmcrameri `cmc.batlow` / `cmc.vik`.
- Telemetry: opt-in, six documented fields, nothing else. Test enforces.

## How to verify

```bash
cd C:\CODE\GIS\terrascope
uv sync --dev
ruff check .
mypy src/terrascope
pytest -m unit
```

For the in-QGIS smoke test, see `docs/quickstart.md`.
