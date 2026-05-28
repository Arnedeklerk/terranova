# Reviewer checklist

Run through this checklist when reviewing a Terranova PR.  Anything that doesn't fit a checkbox warrants a written comment.

## Hard rules — always check

- [ ] No new imports of `qgis.*` or `PyQt*` under `src/terranova/core/**`.  The `test_core_purity` test catches obvious cases; reviewers catch the cunning ones (e.g. hidden inside a function body).
- [ ] No new fields added to the telemetry payload without a matching PRIVACY.md change.  If the test `test_payload_contains_only_documented_fields` was edited, scrutinise why.
- [ ] No `eval` / `exec` / `subprocess.shell=True` introduced anywhere.
- [ ] Bridge actions registered in `controllers/dispatch.py` accept Pydantic-validated payloads.
- [ ] Long-running work runs through `QgsTask`.
- [ ] New colour ramps use `core.utils.colormap` helpers, not jet/rainbow.

## Quality

- [ ] Public functions have docstrings.
- [ ] Type hints on every function (mypy strict will catch).
- [ ] Tests added for new pure-Python code.
- [ ] No commented-out dead code.
- [ ] Imports are inside `if TYPE_CHECKING` when only used for type annotations.

## Backward compatibility

- [ ] `terranova.api.__all__` unchanged or extended — never reduced.
- [ ] `ProjectState` schema_version bumped if any breaking change to persisted state.
- [ ] `metadata.txt` `version` matches `version.py` (`scripts/sync_version.py --check`).

## UI

- [ ] Native dialogs respect dark + light QSS.
- [ ] Web panel responsive at 360px (the dock's min-width).
- [ ] No raw `console.error` calls without context; use the toast system.
- [ ] Keyboard navigation works (Tab order, Escape closes overlays).

## Performance

- [ ] No materialisation of full rasters when a windowed read would do.
- [ ] No `concurrent.futures.ThreadPoolExecutor` raw — use `QgsTask` or `dask`.
- [ ] No hidden 10× memory blow-ups (e.g. dense numpy arrays from sparse Zarr).

## Docs

- [ ] User-visible behaviour change documented in `docs/`.
- [ ] `CHANGELOG.md` updated.

## Security

- [ ] No new outbound URLs except the documented endpoints.
- [ ] No new file writes outside `tmp_path`, project dir, or user-config dir.
- [ ] No new dependencies with unclear licences.
