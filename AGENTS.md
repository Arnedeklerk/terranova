# AGENTS.md — instructions for AI coding agents working on TerraScope

This document is the source-of-truth for agents (Claude Code, Aider, etc.)
modifying this repo. Humans should also read it before contributing.

## Hard rules

1. **The domain layer is pure Python.**  Files under `src/terrascope/core/**`
   MUST NOT import from `qgis.*` or `PyQt*`.  Tests in `tests/unit/` must
   pass without any QGIS install.
2. **Long-running work runs on `QgsTask`.**  Never block the GUI thread.
   Pattern: controller copies inputs to plain Python, spawns a task,
   updates `setProgress`, and adds layers from `finished`.
3. **Every UI action emits a Pydantic-validated message.**  Add new actions
   by registering them in `controllers/dispatch.py`.  Never add an `eval`
   or `exec` path on the bridge.
4. **No new top-level `*.md` files** unless they are explicitly listed in
   the repo structure (README, PRIVACY, CHANGELOG, this file).
5. **No emojis in source or docs.**  Match the project's terse technical
   tone.
6. **Colour ramps default to `cmc.batlow` / `cmc.vik`.**  Never default
   to jet/rainbow.  See `src/terrascope/ui/styles/tokens.yaml`.

## Project layout

```
src/terrascope/
  __init__.py          classFactory entry point
  plugin.py            the only file that imports qgis.* + PyQt6.*
  api.py               stable public surface for scripting
  bridge.py            QWebChannel host
  core/                pure-Python domain (no qgis imports!)
  controllers/         thin adapters core <-> qgis/ui
  tasks/               QgsTask subclasses
  processing/          QgsProcessingAlgorithm subclasses
  ui/                  native Qt widgets, dialogs, styles, icons
  ui_web/              React/Vite source + built dist/
tests/
  unit/                core-layer tests, no QGIS required
  integration/         tests that need QGIS (marked @pytest.mark.qgis)
```

## Common commands

```bash
make install            # uv sync --all-extras --dev
make lint               # ruff check + format check
make type               # mypy --strict on src/terrascope
make test               # pytest -m "not gpu"
make ui-build           # bundle the React panel to ui_web/dist
make deploy             # symlink plugin into QGIS profile
make package            # build the .zip
```

## Adding a new feature

1. **Domain code** in `core/` with full type hints + a unit test.
2. **Pydantic models** for any new inputs/outputs in `core/models.py`.
3. **Controller method** in `controllers/` registered in `dispatch.py`.
4. **QgsTask** in `tasks/` if it is long-running.
5. **Processing algorithm** in `processing/` if it should appear in the
   Processing Toolbox.
6. **UI** in `ui/` (native) and/or `ui_web/src/panels/` (React).
7. **Docs page** in `docs/workflows/` or `docs/api/`.
8. **Recipe** in `recipes/` if it is a one-click workflow.

## Versioning

`metadata.txt`, `pyproject.toml`, and `src/terrascope/version.py` must all
match.  Bump via the release workflow, not by hand.

## Phase plan (where this work fits)

| Phase | Goal |
|-------|------|
| 0 | Skeleton, CI, web bridge, NDVI alg.  **<- you are here** |
| 1 | STAC search + classical classification |
| 2 | Foundation models + SAM |
| 3 | Time-series + change detection |
| 4 | Polish, i18n, public release |

See `HANDOFF.md` for the rolling status note.
