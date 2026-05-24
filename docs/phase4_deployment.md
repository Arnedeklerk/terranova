# Phase 4 — deployment plan

This page is the engineering checklist for getting TerraScope from "feature-complete in CI" to "v1.0.0 published on plugins.qgis.org". It is intentionally specific so a single engineer can work through it without surprises.

## Pre-flight

- [ ] All Phase 0-3 features implemented and tested on Linux, Windows, macOS.
- [ ] CI green on the latest commits, including QGIS-container integration.
- [ ] `pytest -m unit` covers ≥ 80% of `src/terrascope/core/`.
- [ ] Architectural guard (`test_no_qgis_or_qt_imports_in_core`) passes.
- [ ] Architectural guard: telemetry payload still six fields (`test_payload_contains_only_documented_fields`).

## Infrastructure

- [ ] Reserve `terrascope.app` (Cloudflare Registrar).
- [ ] DNS:
  - [ ] `terrascope.app` → Cloudflare Pages (landing page).
  - [ ] `docs.terrascope.app` → GitHub Pages (MkDocs).
  - [ ] `t.terrascope.app` → Cloudflare Worker (telemetry endpoint).
  - [ ] MX → Cloudflare Email Routing (forwarding `*@terrascope.app`).
- [ ] Cloudflare Workers KV for telemetry events; retention policy 30 days raw / aggregated weekly.
- [ ] GitHub Org `terrascope-rs` created with `terrascope`, `terrascope-core` (Phase 4+), `terrascope-docs` repos.
- [ ] plugins.qgis.org account; verify ownership email.

## Plugin metadata

- [ ] `metadata.txt` final values: name, description, about, icon, tags, license.
- [ ] `metadata.txt` `experimental=False`.
- [ ] `version=1.0.0` (and matching in pyproject.toml + version.py).
- [ ] Screenshots: 3 to 5 at 1280×720, JPG, < 200 kB each.
- [ ] Icon: 256×256 PNG export of `icon.svg`.

## Release workflow

- [ ] Tag `v1.0.0` on `main`.
- [ ] `qgis-plugin-ci release` uploads to plugins.qgis.org.
- [ ] GitHub Release with the same `.zip` and auto-generated notes.
- [ ] Docs deploy.

## Launch

- [ ] Post to QGIS user mailing list (https://lists.osgeo.org/mailman/listinfo/qgis-user).
- [ ] Post on GIS Stack Exchange feature-announcement thread.
- [ ] Post to r/QGIS.
- [ ] LinkedIn announcement.
- [ ] Email Luca Congedo (SCP maintainer) as a courtesy — same ecosystem.

## Watch-list (first month)

- [ ] Track plugins.qgis.org install count via the analytics dashboard.
- [ ] Monitor GitHub issues; aim for 24h first-touch.
- [ ] Triage telemetry-derived crash signals (if any opted in users hit errors).
- [ ] **Go/no-go gate** (per the brief): ≥ 500 unique installs in the first month. If we miss, write the post-mortem and decide whether to continue.

## Post-1.0

- [ ] Publish `terrascope-core` to PyPI for non-QGIS use of the domain layer.
- [ ] Crowdin integration for community translations.
- [ ] First `1.1` planning issue with the prioritised post-launch backlog.

## Rollback

If a published `.zip` breaks QGIS for users:

1. Mark the version as deprecated on plugins.qgis.org.
2. Push a `1.0.1` patch within 24h.
3. If 24h is unrealistic, file an issue on plugins.qgis.org to delist `1.0.0` entirely so the Plugins Manager surfaces only the previous version.
