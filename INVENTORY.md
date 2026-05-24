# TerraScope — module inventory

A one-page map of what exists, where, and how complete it is.
Status legend: **DONE** real implementation + tests · **STUB** signature only · **PARTIAL** real for the common path, edge cases TBD.

## Plugin lifecycle (`src/terrascope/`)

| File | What | Status |
|------|------|--------|
| `__init__.py` | `classFactory` entry point | DONE |
| `plugin.py` | `TerraScopePlugin` (dock, processing provider) | DONE |
| `version.py` | Single-source-of-truth version | DONE |
| `bridge.py` | QWebChannel host + Pydantic validation | DONE |
| `api.py` | Stable public Python surface | DONE |
| `config.py` | Per-user settings (JSON) | DONE |

## CLI (`src/terrascope/cli/`)

| Command | Status |
|---------|--------|
| `ndvi` | DONE |
| `index <kind>` (ndwi/ndmi/nbr/ndsi) | DONE |
| `search-s2` | DONE |
| `accuracy-report` | DONE |
| `validate-cog` | DONE |

## Domain (`src/terrascope/core/`)

| Sub-package | Modules | Status |
|-------------|---------|--------|
| `catalog/` | `stac` (PC + ES + CDSE), `cdse` (device-code OAuth) | DONE |
| `stacking/` | `lazy` (composites), `cog` (write + validate), `cloudmask` (SCL + OmniCloudMask), `bandset` (auto-detect) | DONE |
| `ml/` | `classical` (sklearn/LGBM/XGB + predict_to_cog + Optuna), `foundation` (TerraTorch wrapper), `inference` (ORT cache + ONNX export), `sam` (SAM 3 wrappers), `explain` (SHAP), `postprocess` (majority/sieve/reclassify), `calibration` (Platt/isotonic), `training_eval` (nested CV) | PARTIAL (foundation+sam are Phase 2) |
| `timeseries/` | `indices` (NDVI/NDWI/NDMI/NBR/NDSI/EVI/SAVI), `bfast` (bfast lib + CuSum fallback), `landtrendr` (numpy port), `ccdc` (stub), `cube` (Zarr I/O) | PARTIAL |
| `accuracy/` | `metrics` (OA/kappa/UA/PA/F1/McNemar), `report` (PDF) | DONE |
| `roi/` | `region_grow` (euclidean + SAM) | DONE |
| `project/` | `state` (Pydantic + migrations + ledger), `ledger` | DONE |
| `telemetry/` | `client` (emit + inspect), `settings` (decision tristate) | DONE |
| `recipes/` | `loader` (YAML → Pydantic) | DONE |
| `viz/` | `figures` (CM, signatures, MP4 animation) | DONE |
| `io/` | `reproject` (match-to-template), `read_window` (raw + centred) | DONE |
| `utils/` | `bbox`, `colormap`, `hashing`, `logging`, `naming`, `parallel`, `progress`, `feature_flags` | DONE |
| `sensors.py` | S2 / Landsat 4-9 band registry | DONE |
| `models.py` | Cross-layer Pydantic models | DONE |
| `errors.py` | TerraScopeError hierarchy | DONE |

## Controllers + tasks + processing

| File | Status |
|------|--------|
| `controllers/dispatch.py` | `app.*` + `catalog.search` + `app.telemetry.*` |
| `controllers/catalog.py` | DONE |
| `tasks/classify_task.py` | DONE |
| `tasks/cube_task.py` | DONE (minimal body, Phase 3 expands) |
| `tasks/catalog_task.py` | DONE |
| `processing/ndvi_alg.py` | DONE |
| `processing/indices_algs.py` (NDWI / NDMI / NBR / NDSI) | DONE |
| `processing/postprocess_algs.py` (majority filter + sieve) | DONE |

## UI

### Native Qt (`src/terrascope/ui/`)

| File | Status |
|------|--------|
| `plugin_dock.py` (embedded `QWebEngineView` + fallbacks) | DONE |
| `widgets/{project_explorer, inspector, wizard}.py` | STUB |
| `dialogs/{catalog_search, classifier_setup}.py` | STUB |
| `styles/{dark, light}.qss` + `tokens.yaml` | DONE |
| `resources/{icon.svg, classification.qml}` | DONE |

### Web (`src/terrascope/ui_web/`)

| Panel | Status |
|-------|--------|
| `Welcome` | DONE |
| `CatalogSearch` | DONE |
| `CommandPalette` (Ctrl/Cmd+K) | DONE |
| `Inspector` | DONE |
| `SpectralPlot` (Plotly) | DONE |
| `BeforeAfter` (MapLibre swipe) | DONE |
| `TelemetryConsent` (first-run) | DONE |

## Tests (`tests/unit/`)

| Test file | Targets |
|-----------|---------|
| `test_models.py` | Pydantic models incl. BBox, DateRange, CatalogSearch, ClassifierConfig, CommandMessage, CommandResult |
| `test_indices.py` + `test_indices_properties.py` | NDVI/NDWI/NDMI/NBR/NDSI/EVI/SAVI (concrete + Hypothesis) |
| `test_accuracy.py` + `test_accuracy_report.py` | metrics + PDF rendering |
| `test_project_state.py` | save/load/migrate/ledger |
| `test_dispatch.py` + `test_catalog_controller.py` | dispatch + catalog handler |
| `test_cli.py` | argparse surface |
| `test_telemetry.py` | privacy-policy enforcement |
| `test_lazy_composite.py` | composites (median/mean/p25/p75/first_valid) |
| `test_region_grow.py` | numpy ROI |
| `test_postprocess.py` | majority/sieve/reclassify |
| `test_sensors.py` | S2 + Landsat band registry |
| `test_bbox.py` | BBox utility helpers |
| `test_config.py` | per-user settings round-trip |
| `test_metadata_txt.py` | metadata.txt parseable + version in sync |
| `test_cdse.py` | token cache + flow dataclasses |
| `test_inference.py` | ORT session cache |
| `test_bandset.py` | auto band detection |
| `test_bfast_cusum.py` | CuSum break detection |
| `test_landtrendr.py` | piecewise-linear segmentation |
| `test_viz.py` | matplotlib figure builders |
| `test_progress.py` | hierarchical progress |
| `test_logging.py` | sink + level routing |
| `test_hashing.py` | short_hash / file_hash |
| `test_naming.py` | safe filenames, unique_path |
| `test_recipes.py` | YAML → Pydantic |
| `test_errors.py` | exception hierarchy |
| `test_parallel.py` | map_chunks |
| `test_feature_flags.py` | env-driven flags |
| `test_pyproject.py` | pyproject.toml integrity |
| `test_read_window.py` | windowed reads |
| `test_classical.py` | build_estimator across kinds + smoke fit/predict |
| `test_api.py` | public surface doesn't regress |
| `test_core_purity.py` | **architectural guard** — no `qgis.*`/`PyQt*` in core/ |
| `test_lazy_composite.py` | composites (median / mean / p25 / p75 / first_valid) |

Plus `tests/integration/test_plugin_loads.py` — pytest-qgis class-factory smoke.

## CI / Workflows

| File | What |
|------|------|
| `ci.yml` | lint + type + unit matrix + web build + QGIS integration |
| `release.yml` | tag → `.zip` → GitHub Release |
| `docs.yml` | MkDocs Material → GitHub Pages |
| `security.yml` | pip-audit + npm-audit + CodeQL |
| `dependabot.yml` | weekly grouped updates |

## Where to look first

- New to the repo? Start with `README.md` then `docs/architecture.md`.
- Coming from SCP? `docs/scp_migration.md`.
- Want to write code? `AGENTS.md` + `docs/development.md`.
- Reviewing a PR? `docs/reviewer.md`.
- Shipping a release? `docs/phase4_deployment.md`.
