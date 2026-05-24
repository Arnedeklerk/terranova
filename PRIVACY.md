# TerraScope Privacy Policy

**Effective:** 23 May 2026

TerraScope is a QGIS plugin that processes raster and vector data locally on your machine. We do not collect, store, or transmit your imagery, your training data, your AOIs, your file paths, or any other content you process with the plugin.

## What we do not collect

- Imagery, scenes, COGs, Zarr cubes.
- Training polygons, points, or class labels.
- File paths, project file names, layer names.
- AOI coordinates, dates, or any other search parameters.
- Your Copernicus / Planetary Computer / Earth Search credentials.
- IP addresses (we discard them at the edge).

## Optional, opt-in telemetry

Telemetry is **off by default**. On first run, TerraScope asks once: "Help us improve TerraScope?" with options Yes / No / Decide later. If you opt in, the plugin sends one event per significant action with the following fields and **nothing else**:

| Field | Example | Purpose |
|-------|---------|---------|
| `event_name` | `classification.run` | Which feature you used |
| `plugin_version` | `0.1.0` | So we can correlate with releases |
| `qgis_version` | `3.40.1` | So we know which QGIS versions to support |
| `os` | `Windows 11` | Platform coverage |
| `installation_id` | `c4f1...` (random UUID v4, locally generated) | Distinguish unique installs without identifying you |
| `timestamp` | `2026-05-23T14:07:11Z` | When the event happened |

The `installation_id` is stored in `~/.config/terrascope/installation_id` (or the OS equivalent) and is reset on uninstall. It is not linked to any account, email, IP, or hardware identifier.

## Inspector

You can see the next outbound payload in **Settings → Privacy → Show next outbound payload**. You can disable telemetry at any time in the same panel.

## Endpoint

If enabled, events are sent over TLS to `https://t.terrascope.app/v1/events`, rate-limited to 1 event/sec. Logs are aggregated weekly and raw events older than 30 days are deleted.

## Third-party services

When you use TerraScope to search or download imagery, requests are made directly from your machine to the chosen catalogue (Planetary Computer, Earth Search, Copernicus Data Space). Those providers' privacy policies apply.

## Contact

Privacy questions: <arne@terrascope.app>.

## Changes

Material changes to this policy will be announced in [CHANGELOG.md](CHANGELOG.md) and on first launch after the update.
