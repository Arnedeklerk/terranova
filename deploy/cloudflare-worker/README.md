# TerraScope telemetry — Cloudflare Worker

Single endpoint `POST /v1/events` that receives opt-in telemetry from the
QGIS plugin.  Stores events to a Workers KV namespace with 30-day raw
retention (per [PRIVACY.md](../../PRIVACY.md)).

## Schema

Exactly the six fields documented in `PRIVACY.md`:

| Field             | Validation             |
|-------------------|------------------------|
| `event_name`      | `[a-z][a-z0-9_.]{0,63}` |
| `plugin_version`  | semver-ish              |
| `qgis_version`    | `[\w.-]{1,32}`          |
| `os`              | `[A-Za-z][A-Za-z0-9 ._-]{0,63}` |
| `installation_id` | UUID v4                 |
| `timestamp`       | ISO 8601 with timezone  |

Any other field → 400.  Body that isn't a plain object → 400.

## Deploy

```bash
npm install
wrangler login
# 1. Create the KV namespace
wrangler kv namespace create EVENTS
# 2. Paste the returned `id` into wrangler.toml
# 3. Repeat for preview
wrangler kv namespace create EVENTS --preview

# Then:
npm run typecheck
npm test
npm run deploy
```

## Custom domain

Configure `t.terrascope.app` to point at this worker via the Cloudflare
dashboard:

1. Workers & Pages → `terrascope-telemetry` → Triggers → Custom Domains.
2. Add `t.terrascope.app`.  Cloudflare provisions the TLS certificate.

## Rate limiting

Per-IP token bucket via KV.  Defaults: 30 events / 60 s.  Tune via
`wrangler secret put` or the env vars in `wrangler.toml`.

## What we deliberately do NOT do

- Log IP addresses.  Cloudflare adds `CF-Connecting-IP` at edge; we use it
  for the rate-limit key bucket but never persist it.
- Set cookies.
- Echo client headers back in responses.
- Accept any field outside the documented six.
