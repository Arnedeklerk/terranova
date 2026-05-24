/**
 * Worker validation tests — driven by vitest with a fake KV.
 *
 * Run with `npm test`.  Doesn't exercise the actual worker runtime; the
 * pure validate() function is the meat anyway.
 */

import { describe, expect, it } from "vitest";

// Pull the validate function via a tiny re-export trick.
import worker, { Env } from "./index";

const validPayload = {
  event_name: "app.launch",
  plugin_version: "0.1.0",
  qgis_version: "3.40.1",
  os: "Windows 11",
  installation_id: "c4f1aaaa-1111-2222-3333-444455556666",
  timestamp: "2026-05-23T14:07:11Z",
};

class FakeKV {
  private store = new Map<string, string>();
  async get(k: string) {
    return this.store.get(k) ?? null;
  }
  async put(k: string, v: string) {
    this.store.set(k, v);
  }
}

function makeEnv(): Env {
  return {
    EVENTS: new FakeKV() as unknown as KVNamespace,
    RATE_LIMIT_WINDOW_S: "60",
    RATE_LIMIT_BURST: "30",
    RAW_RETENTION_DAYS: "30",
  };
}

function post(body: unknown): Request {
  return new Request("https://t.terrascope.app/v1/events", {
    method: "POST",
    headers: { "content-type": "application/json", "CF-Connecting-IP": "203.0.113.1" },
    body: JSON.stringify(body),
  });
}

describe("telemetry worker", () => {
  it("accepts a well-formed event", async () => {
    const r = await worker.fetch(post(validPayload), makeEnv(), {} as ExecutionContext);
    expect(r.status).toBe(200);
  });

  it("rejects unknown fields", async () => {
    const r = await worker.fetch(
      post({ ...validPayload, evil: "muahahaha" }),
      makeEnv(),
      {} as ExecutionContext,
    );
    expect(r.status).toBe(400);
  });

  it("rejects bad installation_id", async () => {
    const r = await worker.fetch(
      post({ ...validPayload, installation_id: "not-a-uuid" }),
      makeEnv(),
      {} as ExecutionContext,
    );
    expect(r.status).toBe(400);
  });

  it("rejects email-looking event_name", async () => {
    const r = await worker.fetch(
      post({ ...validPayload, event_name: "user@example.com" }),
      makeEnv(),
      {} as ExecutionContext,
    );
    expect(r.status).toBe(400);
  });

  it("404s on other paths", async () => {
    const r = await worker.fetch(
      new Request("https://t.terrascope.app/admin", { method: "POST" }),
      makeEnv(),
      {} as ExecutionContext,
    );
    expect(r.status).toBe(404);
  });

  it("healthz returns 200", async () => {
    const r = await worker.fetch(
      new Request("https://t.terrascope.app/healthz"),
      makeEnv(),
      {} as ExecutionContext,
    );
    expect(r.status).toBe(200);
  });
});
