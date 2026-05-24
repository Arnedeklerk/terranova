# Security Policy

## Supported versions

Until v1.0, only the latest released version is supported with security fixes.

## Reporting a vulnerability

Please email **security@terrascope.app** rather than filing a public issue. We aim to acknowledge within 72 hours and provide an initial assessment within 7 days.

Please include:

- A clear description of the issue.
- Reproduction steps and any proof-of-concept code.
- The version of TerraScope, QGIS, and Python you tested against.
- Any suggested mitigation.

We coordinate disclosure: typical timeline is a fix on a private branch, a release with the fix, and an advisory published within 90 days of the original report.

## Scope

In scope:

- The plugin's Python code under `src/terrascope/`.
- The embedded web tier under `src/terrascope/ui_web/src/`.
- The QWebChannel bridge between them.
- Recipes (`recipes/`) and sample data (`samples/`).

Out of scope:

- Vulnerabilities in upstream dependencies (please report to the upstream).
- Issues that require a malicious local user with write access to the QGIS profile directory.
- Issues in QGIS itself — please report to the [QGIS issue tracker](https://github.com/qgis/QGIS/issues).

## Known threat model

The plugin processes user-supplied raster and vector data and makes outbound requests to:

- Public STAC catalogues (Planetary Computer, Earth Search, CDSE) over HTTPS.
- The opt-in telemetry endpoint (see PRIVACY.md).
- A user-configured update-check endpoint (Phase 4).

The bridge between the embedded web view and Python validates every message with Pydantic before dispatch. The dispatch table is the only Python surface reachable from the web tier.
