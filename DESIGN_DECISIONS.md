# Design decisions — Phase 0

This is a Decision Log (ADR-lite). Every meaningful trade-off below was made
during the Phase-0 build and is recorded so we don't litigate it twice.

## D-1: `src/` layout

**Chosen:** `src/terrascope/` not flat `terrascope/`.
**Why:** prevents the "you can import the package without installing it" foot-gun that masks dependency errors; matches modern hatchling / uv defaults; encourages clean test runs.

## D-2: Three-layer architecture with a pure domain

**Chosen:** UI ↔ Controllers ↔ Core (no `qgis.*` in core).
**Why:** lets the core ship as a standalone PyPI library later; lets CI exercise 80%+ of the codebase without a QGIS install; matches the brief.
**Enforcement:** `tests/unit/test_core_purity.py` walks the AST of every file under `core/` and fails the build if any banned top-level module name appears.

## D-3: PyQt6 over PySide6

**Chosen:** PyQt6.
**Why:** QGIS 4.x bundles PyQt6; mixing bindings within a single Python process is hazardous; consistency with the host wins.

## D-4: qfluentwidgets *named*, not *vendored*

**Chosen:** Mention qfluentwidgets in the design tokens / docstrings as the intended look, but do not introduce a hard dependency until Phase 1.
**Why:** keeps Phase-0 install footprint minimal so the smoke test on three OSes is fast; the dock renders fine with native QtWidgets in the meantime.

## D-5: Hybrid UI tier (Qt + embedded React)

**Chosen:** Two-tier UI — native QtWidgets for the heavy plumbing, React-in-QWebEngineView for everything that benefits from modern web stack (palette, charts, swipe, welcome screen).
**Why:** safe since QGIS 3.36; the brief's UX-debt-elimination story needs it; falls back to native widgets when `QWebEngineView` import fails (issue qgis#59027 mitigation).

## D-6: Pydantic v2 for everything cross-layer

**Chosen:** Pydantic v2 models for project state, bridge messages, recipe schema, telemetry payload.
**Why:** one schema language across persistence, IPC, and validation; cheap to JSON-schema for the TS side via `scripts/dump_schemas.py`.

## D-7: Pinned `pydantic>=2.7`

**Chosen:** Floor is 2.7, no ceiling yet.
**Why:** 2.7 introduced the `model_validate_json` / `model_dump_json` patterns we use; the `ValidationInfo.data` field arrived earlier. Will pin `<3` when v3 ships.

## D-8: ORT inference singleton per model path

**Chosen:** Module-level `dict[path → InferenceSession]` cache in `core/ml/inference.py`.
**Why:** ORT is thread-safe by design; the warm-session pattern matches the brief's "live preview" expectation; the cache is keyed by absolute path so cross-project reloads are safe.

## D-9: Crameri colormaps by default; matplotlib viridis fallback

**Chosen:** `cmcrameri.batlow` / `cmc.vik` when installed, `viridis` / `RdBu_r` otherwise.
**Why:** Crameri ramps are perceptually uniform and CVD-friendly; the fallback degrades gracefully on minimal installs without surprising users.

## D-10: Telemetry — six fields exactly, opt-in, test-enforced

**Chosen:** Exactly six fields documented in PRIVACY.md; opt-in by default; `tests/unit/test_telemetry.py::test_payload_contains_only_documented_fields` makes adding a field a public PR.
**Why:** the brief is unambiguous; the test makes "we forgot to update the policy" impossible.

## D-11: Block-wise predict_to_cog (no full materialisation)

**Chosen:** `predict_to_cog` reads rasterio windows, predicts only on valid pixels, writes blocks, then `cog_translate`s the result.
**Why:** scales to S2 full-tiles (10980×10980); avoids the 1 GB+ RAM blow-up of "load whole image into memory and predict".

## D-12: GPL-3-or-later

**Chosen:** GPL-3-or-later.
**Why:** mandated for plugins.qgis.org; compatible with qfluentwidgets; copy-left protects derivative works as the brief positions us against SCP-derived forks.

## D-13: TerraScope (name)

**Chosen:** TerraScope.
**Why:** the brief's preferred option; no apparent trademark conflicts in the QGIS plugin space; clean to pronounce in any of en/fr/es/pt/de/it (the six launch locales).

## D-14: Recipes as YAML, not Python

**Chosen:** YAML recipes that map to a tightly-scoped subset of controller actions.
**Why:** non-developers can author recipes; the limited DSL is deliberately too small to need a sandbox; full-power scripting still uses Python via `terrascope.api`.

## D-15: Optional dependency groups

**Chosen:** `[ml]`, `[gpu]`, `[timeseries]`, `[dev]`.
**Why:** keeps the default install footprint small (no PyTorch by default — that's a multi-GB wheel); GPU users opt in to `onnxruntime-gpu` explicitly; the time-series cube path doesn't pull bfast unless asked.

## D-16: BFAST CuSum fallback

**Chosen:** ship a numpy-only CuSum break detector alongside the optional `bfast` GPU package.
**Why:** the brief flags `bfast`'s OpenCL backend as a fragile dependency on Windows; the fallback gives "something runs without GPU" guarantee for the change-detection workflow.

## D-17: Migration framework with stepwise registrations

**Chosen:** `ProjectState.load` calls `migrate(raw)` which steps `version → version+1` via a registered table.
**Why:** schemas change; we want a migration to be reviewable as one named function per version; raising on an unknown future version is safer than silently dropping fields.

## D-18: Architectural-guard tests

**Chosen:** Tests that enforce architectural invariants (`test_core_purity`, `test_payload_contains_only_documented_fields`, `test_version_matches_version_py`).
**Why:** invariants in CI are the only ones that survive; comments at the top of a file aren't enforced.

## D-19: PII-scrubbing in the package logger

**Chosen:** A `logging.Filter` on `getLogger("terrascope")` runs `scrub(message)` on every record.
**Why:** even with opt-in telemetry, a careless `logger.info(user_email)` could end up in a screenshot or a support attachment. Scrub at the source.

## D-20: Block default Phase 0 from any foundation-model checkpoint

**Chosen:** No checkpoint bundled in the plugin .zip; users download Prithvi / Clay / TerraMind themselves via TerraTorch.
**Why:** model weights are hundreds of MB to GB; cloning a 1.5 GB plugin .zip is a non-starter; the brief's Phase 2 launch criterion already assumes a CUDA laptop.

## D-21: STAC-first download — no scene-by-scene UI

**Chosen:** Catalogue search returns a STAC `ItemCollection`; users compose with `lazy_stack` rather than downloading every scene.
**Why:** the single biggest UX win over SCP (§Key Findings of the brief).

## D-22: Sample data deferred

**Chosen:** Phase 0 ships a `samples/README.md` describing the planned data; the actual Khartoum demo lands in Phase 1.
**Why:** licensing review takes a beat; we'd rather miss a smoke test than ship data with an unclear redistribution licence.

## D-23: Conventional Commits (loose)

**Chosen:** Conventional Commits for messages, but not enforced.
**Why:** good signal for changelog generation later; not so strict that it blocks contributors.
