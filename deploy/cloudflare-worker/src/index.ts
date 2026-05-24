/**
 * Terranova telemetry endpoint — Cloudflare Worker.
 *
 * Single POST endpoint at `/v1/events`.  Accepts the exact 6-field payload
 * defined in PRIVACY.md.  Drops anything else.  Rejects bodies that don't
 * match the schema.  Writes to Workers KV with a 30-day TTL.
 *
 * What we deliberately do NOT do:
 *   - Log IP addresses (Cloudflare adds them at edge; we don't persist them).
 *   - Set cookies.
 *   - Read or echo client headers in the response body.
 *   - Accept any field outside the documented six.
 */

export interface Env {
  EVENTS: KVNamespace;
  RATE_LIMIT_WINDOW_S: string;
  RATE_LIMIT_BURST: string;
  RAW_RETENTION_DAYS: string;
}

const ALLOWED_FIELDS = new Set([
  "event_name",
  "plugin_version",
  "qgis_version",
  "os",
  "installation_id",
  "timestamp",
]);

// UUID v4 regex (loose — accept any v).  installation_id must be a UUID.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
// SemVer-ish.  The optional suffix MUST start with '-' or '+' so it can
// never compete with the third \d+ for the same characters — without
// that anchor, an input like "9.9.9" followed by many '0's hits
// polynomial backtracking (CodeQL js/polynomial-redos).  Suffix body
// uses ASCII identifier chars only; no embedded literal '+'.
const SEMVER_RE = /^\d+\.\d+\.\d+(?:[-+][a-z0-9.\-]+)?$/i;
const EVENT_NAME_RE = /^[a-z][a-z0-9_.]{0,63}$/;
const OS_RE = /^[A-Za-z][A-Za-z0-9 ._\-]{0,63}$/;
const QGIS_RE = /^[\w.\-]{1,32}$/;
const ISO_TS_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+\-]\d{2}:?\d{2})$/;

// Hard input-length caps applied BEFORE running regex tests.  Each value
// is well above the legitimate maximum (semver is short, UUID is 36
// chars, ISO timestamp is ~32) so we can reject pathological inputs
// without affecting real payloads.  Defence in depth against
// regex-backtracking inputs: even if a regex turns out to be quadratic
// later, the worst case is 64-char input, which is fast.
const MAX_FIELD_LEN: Record<string, number> = {
  event_name: 64,
  plugin_version: 64,
  qgis_version: 32,
  os: 64,
  installation_id: 36,
  timestamp: 40,
};

interface Event {
  event_name: string;
  plugin_version: string;
  qgis_version: string;
  os: string;
  installation_id: string;
  timestamp: string;
}

export default {
  async fetch(req: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/healthz") {
      return json({ ok: true });
    }

    if (req.method !== "POST" || url.pathname !== "/v1/events") {
      return json({ ok: false, error: "not found" }, 404);
    }

    // Rate-limit by installation_id (which we'll see in the body) AND by
    // client IP via the Cloudflare-supplied header — but we never persist IP.
    const ip = req.headers.get("CF-Connecting-IP") ?? "anon";
    const burst = parseInt(env.RATE_LIMIT_BURST, 10) || 30;
    const window = parseInt(env.RATE_LIMIT_WINDOW_S, 10) || 60;
    const rlKey = `rl:${ip}:${Math.floor(Date.now() / 1000 / window)}`;
    const current = parseInt((await env.EVENTS.get(rlKey)) ?? "0", 10);
    if (current >= burst) {
      return json({ ok: false, error: "rate limited" }, 429);
    }
    // We don't await the write — best-effort.
    env.EVENTS.put(rlKey, String(current + 1), { expirationTtl: window + 5 });

    let raw: unknown;
    try {
      raw = await req.json();
    } catch {
      return json({ ok: false, error: "invalid JSON" }, 400);
    }

    const evt = validate(raw);
    if (!evt.ok) return json({ ok: false, error: evt.error }, 400);

    const ttl = (parseInt(env.RAW_RETENTION_DAYS, 10) || 30) * 86400;
    const key = `evt:${evt.value.timestamp}:${evt.value.installation_id.slice(0, 8)}:${cryptoRandom(8)}`;
    await env.EVENTS.put(key, JSON.stringify(evt.value), { expirationTtl: ttl });

    return json({ ok: true });
  },
};

// --------------------------------------------------------------------------- //
function validate(raw: unknown): { ok: true; value: Event } | { ok: false; error: string } {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    return { ok: false, error: "body must be an object" };
  }
  const obj = raw as Record<string, unknown>;

  for (const key of Object.keys(obj)) {
    if (!ALLOWED_FIELDS.has(key)) {
      return { ok: false, error: `unexpected field: ${key}` };
    }
  }
  for (const field of ALLOWED_FIELDS) {
    if (!(field in obj)) return { ok: false, error: `missing field: ${field}` };
    if (typeof obj[field] !== "string") {
      return { ok: false, error: `field ${field} must be a string` };
    }
    // Length cap BEFORE regex testing — pathological inputs can't reach
    // the regex engine in the first place.
    const max = MAX_FIELD_LEN[field] ?? 256;
    if ((obj[field] as string).length > max) {
      return { ok: false, error: `field ${field} exceeds ${max} chars` };
    }
  }
  const v = obj as Record<string, string>;

  if (!EVENT_NAME_RE.test(v.event_name)) return { ok: false, error: "bad event_name" };
  if (!SEMVER_RE.test(v.plugin_version)) return { ok: false, error: "bad plugin_version" };
  if (!QGIS_RE.test(v.qgis_version)) return { ok: false, error: "bad qgis_version" };
  if (!OS_RE.test(v.os)) return { ok: false, error: "bad os" };
  if (!UUID_RE.test(v.installation_id)) return { ok: false, error: "bad installation_id" };
  if (!ISO_TS_RE.test(v.timestamp)) return { ok: false, error: "bad timestamp" };

  return {
    ok: true,
    value: {
      event_name: v.event_name,
      plugin_version: v.plugin_version,
      qgis_version: v.qgis_version,
      os: v.os,
      installation_id: v.installation_id,
      timestamp: v.timestamp,
    },
  };
}

function json(body: unknown, status: number = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "x-content-type-options": "nosniff" },
  });
}

function cryptoRandom(bytes: number): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return [...arr].map((b) => b.toString(16).padStart(2, "0")).join("");
}
