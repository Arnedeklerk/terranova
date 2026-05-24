# Contributing to TerraScope

Thanks for your interest in helping with TerraScope. This document covers what we need from contributors and how to set up a working dev environment.

## Before you start

- Read **AGENTS.md** — the hard rules apply to humans too.
- Check the [open issues](https://github.com/terrascope-rs/terrascope/issues) before opening a new one; small fixes and docs improvements can go straight to a pull request without an issue.
- Big changes (new module, new dependency, new UI panel) — open an issue first and let us bikeshed the design before you spend time on code.

## Dev setup

```bash
git clone https://github.com/terrascope-rs/terrascope
cd terrascope

# Install Python deps (uv is required for the lockfile but pip works too)
uv sync --all-extras --dev      # or: pip install -e .[dev,ml,gpu,timeseries]

# Install pre-commit hooks
pre-commit install

# Build the React panel
make ui-build

# Deploy into your QGIS profile
make deploy
```

## Code style

- Python: ruff (configured in `ruff.toml`) + mypy `--strict` on the `src/` tree.
- TypeScript: ESLint defaults + TypeScript strict mode.
- Tests for new pure-Python code go under `tests/unit/`; tests that need QGIS go under `tests/integration/` and are decorated with `@pytest.mark.qgis`.

Run `make lint type test` before opening a PR.

## Commit style

We follow Conventional Commits loosely:

```
feat(ml): add Optuna hyperparameter tuning
fix(stac): handle empty cloud-cover assets on Earth Search
docs(architecture): clarify QgsTask vs domain layer
test(roi): add region_grow boundary tests
```

Keep commits focused. Squash WIP commits before opening the PR.

## Architectural rules (the short version)

1. The domain layer (`src/terrascope/core/**`) MUST NOT import from `qgis.*` or `PyQt*`.
2. Long-running work runs through `QgsTask`. Never block the GUI thread.
3. Every UI action emits a Pydantic-validated message. No `eval` or `exec` on the bridge.
4. Telemetry payloads are the documented six fields. Adding a field requires a privacy-policy change.
5. Colour ramps default to `cmc.batlow` / `cmc.vik`. Never default to jet/rainbow.

## Licence

TerraScope is GPL-3-or-later. By contributing, you agree to license your contribution under the same terms.

## Reporting bugs

Please include:

- TerraScope version (Help → About, or `metadata.txt`).
- QGIS version and OS.
- Steps to reproduce.
- Relevant log output from the QGIS Log Messages panel (`TerraScope` tab).

For potential security issues, see [SECURITY.md](SECURITY.md) — please do not file a public issue.
