# Telemetry

TerraScope's telemetry is **opt-in**, **minimal**, and **inspectable**. The summary on this page is the same one in [PRIVACY.md](../PRIVACY.md), elaborated for readers who want to dig into the implementation.

## What is sent

Exactly six fields per event:

| Field | Example | Notes |
|-------|---------|-------|
| `event_name` | `classification.run` | The action you performed |
| `plugin_version` | `0.1.0` | Correlate with releases |
| `qgis_version` | `3.40.1` | Platform support |
| `os` | `Windows 11` | Coarse OS string from `platform.system()` + `platform.release()` |
| `installation_id` | random UUID v4 | Distinguishes installs without identifying you |
| `timestamp` | `2026-05-23T14:07:11Z` | UTC ISO 8601 |

**No** imagery, file paths, layer names, AOIs, dates, search parameters, model paths, credentials, IP addresses, or anything else. This is enforced by `tests/unit/test_telemetry.py::test_payload_contains_only_documented_fields` — adding a seventh field would fail CI.

## When telemetry runs

Only if you opt in. On first launch, the welcome panel shows a one-time dialog with three buttons:

- **No thanks** — sets `decision = opted_out`. Telemetry never runs again.
- **Yes, help out** — sets `decision = opted_in`.
- Closing the dialog leaves `decision = not_asked` and you'll be asked again on the next launch.

The `decision` is persisted in `~/.config/terrascope/telemetry.json` (or the platform-equivalent location).

## Inspecting the payload

Settings → Privacy → **Show next outbound payload** runs `terrascope.core.telemetry.client.inspect_next_payload(...)` and renders the resulting JSON in the dialog. The inspector path is guaranteed never to touch the network — there's a test for that too (`test_inspect_does_not_send`).

## Transport and retention

If enabled:

- Events are POSTed to `https://t.terrascope.app/v1/events` over TLS.
- A daemon thread sends — telemetry never blocks the UI thread.
- Network errors are silently swallowed; telemetry must never break the plugin.
- Rate-limited to 1 event per second by the client (further rate-limiting at the edge).
- Logs are aggregated weekly; raw events older than 30 days are deleted.

## Opting out later

Settings → Privacy → toggle **Send anonymous usage data**. The change applies immediately; the installation id is preserved (no rotation) but no further events are sent.

## Forgetting

Uninstall removes the telemetry settings file and the installation id with it. There is no per-user record on the server linked to anything outside the plugin install.

## Code references

- Implementation: `src/terrascope/core/telemetry/`.
- Privacy policy (authoritative): `PRIVACY.md`.
- Tests that enforce the privacy policy: `tests/unit/test_telemetry.py`.
- Dispatch handlers (`app.telemetry.{status,set,inspect}`): `src/terrascope/controllers/dispatch.py`.
- First-run UI: `src/terrascope/ui_web/src/panels/TelemetryConsent.tsx`.
