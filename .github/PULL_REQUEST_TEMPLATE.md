<!--
Thanks for opening a PR.  Please tick the relevant checkboxes and remove
any sections that don't apply.
-->

## Summary

<!-- 1-3 bullets summarising the change. -->

## Motivation

<!-- Why is this change worth making?  Link any related issues. -->

## Changes

<!-- A short list of what's actually touched. -->

## Test plan

- [ ] Added or updated unit tests under `tests/unit/`
- [ ] `make lint type test` passes
- [ ] Verified in-QGIS (if UI / plugin-lifecycle code is touched)

## Architectural rules (ticked = followed)

- [ ] No `qgis.*` / `PyQt*` imports added under `src/terrascope/core/**`
- [ ] Long-running work uses `QgsTask`
- [ ] Bridge actions validated by Pydantic
- [ ] Telemetry payload (if touched) still matches PRIVACY.md
- [ ] No jet/rainbow colormaps introduced

## Screenshots / GIFs

<!-- For UI changes. -->
