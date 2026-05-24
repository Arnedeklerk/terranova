# Development guide

This page assumes you have read [installation.md](installation.md) and have a working dev environment. It covers the parts you only learn by working on the plugin.

## Architectural rules

1. **The domain layer is pure Python.**  Files under `src/terrascope/core/**` MUST NOT import from `qgis.*` or any Qt binding. Enforced by `tests/unit/test_core_purity.py`.
2. **Long-running work runs through `QgsTask`.**  Never block the GUI thread.
3. **Bridge messages are Pydantic-validated.**  Add new actions in `controllers/dispatch.py`.
4. **Telemetry stays at six fields.**  Adding a field is a privacy-policy change and a public PR — `tests/unit/test_telemetry.py::test_payload_contains_only_documented_fields` enforces.
5. **Colour ramps default to Crameri ramps.**  Never jet/rainbow.

## Layout cheat sheet

```
src/terrascope/
  __init__.py          classFactory entry point
  plugin.py            the only file that imports qgis.* / PyQt*
  api.py               stable public scripting surface
  config.py            per-user settings
  bridge.py            QWebChannel host
  cli/                 CLI entry point (no QGIS)
  core/                pure-Python domain (no qgis imports)
    catalog/           STAC + CDSE OAuth
    stacking/          composites, COG, cloud mask, band sets
    ml/                classical + foundation + SAM + post-process + ONNX
    timeseries/        cube + indices + BFAST + CCDC + LandTrendr
    accuracy/          metrics + PDF report
    roi/               region-growing
    project/           Pydantic state with migrations
    telemetry/         opt-in only; six-field payload
    utils/             bbox, colormap, hashing, progress, logging, naming
    io/                reproject + window read
    viz/               matplotlib figures
    sensors.py         band registries
    models.py          shared Pydantic models
  controllers/         thin adapters core <-> qgis/ui
  tasks/               QgsTask subclasses
  processing/          QgsProcessingAlgorithm subclasses
  ui/                  native Qt UI
  ui_web/              React/Vite source + built dist/
tests/
  unit/                core-layer tests; no QGIS required
  integration/         needs QGIS (marked @pytest.mark.qgis)
docs/                  MkDocs Material site
recipes/               one-click workflow YAML
samples/               bundled COGs + GeoJSON labels
scripts/               release helpers, sample fetchers
```

## Common commands

```bash
make install          # uv sync --all-extras --dev
make lint             # ruff check + format check
make type             # mypy --strict on src/terrascope
make test             # pytest -m "not gpu"
make ui-build         # bundle the React panel
make ui-dev           # Vite dev server (in-browser)
make deploy           # symlink into QGIS profile
make package          # build the .zip
python scripts/sync_version.py            # check
python scripts/sync_version.py --bump x.y.z
```

## Adding a feature

1. Pure-Python work in `core/` first.  Write the unit tests in the same PR.
2. Add a Pydantic model to `core/models.py` for any new payload shapes.
3. Wire a controller in `controllers/` and register its action in `dispatch.py`.
4. If long-running, make a `QgsTask` in `tasks/`.
5. If it should appear in the Processing Toolbox, write a `QgsProcessingAlgorithm` in `processing/`.
6. Wire the UI (native Qt in `ui/`, React in `ui_web/src/panels/`).
7. Add a docs page in `docs/workflows/` or `docs/api/`.
8. Update `CHANGELOG.md`.

## Conventional commits

```
feat(ml): add Optuna hyperparameter tuning
fix(stac): handle empty cloud-cover assets on Earth Search
docs(architecture): clarify QgsTask vs domain layer
test(roi): add region_grow boundary tests
```

## Testing patterns

- Pure domain tests go in `tests/unit/`.  Hypothesis is fair game for property-based tests on indices and accuracy metrics.
- QGIS-dependent tests go in `tests/integration/` with `@pytest.mark.qgis` and run only with `pytest --runqgis`.
- Mock pystac + rasterio when you can — they're heavy.
- Skip tests that depend on optional installs via `pytest.importorskip(...)`.

## Web tier

The React panel is bundled into `src/terrascope/ui_web/dist/` and loaded by QtWebEngine via `file://`.  In dev, run `npm run dev` (or `serve.bat`/`serve.ps1`) for in-browser iteration; the bridge falls back to a stub that logs calls to the console.

State management: Zustand for UI-only state, Python's `ProjectState` for everything that should outlive a panel.

## Release flow

1. `python scripts/sync_version.py --bump x.y.z`
2. Update `CHANGELOG.md`.
3. `git commit -m "release: vX.Y.Z"`
4. `git tag vX.Y.Z`
5. `git push origin main vX.Y.Z`
6. The Release workflow builds the `.zip` and uploads to a GitHub Release.  Phase 4 adds the plugins.qgis.org upload.

## Where to look first when something breaks

- Plugin won't load — `Plugins → Plugin Manager → Show Errors`, plus the `TerraScope` tab in the Log Messages panel.
- Web bundle missing — run `make ui-build`.
- `QtWebEngineView` import fails — install `python3-pyqtwebengine` (Linux only).
- Tests pass locally but CI fails — check the matrix.  Most often a `pytest.importorskip` is missing or a Linux-only path was used.
