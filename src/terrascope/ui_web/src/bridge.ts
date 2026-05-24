/**
 * QWebChannel client for the TerraScope embedded React panel.
 *
 * In the QGIS host, QtWebEngine injects `qrc:///qtwebchannel/qwebchannel.js`
 * on page load and exposes `qt.webChannelTransport`.  In dev (`vite dev` in
 * a normal browser), neither is available — `initBridge()` falls back to a
 * stub that logs invocations to the console so the UI is still usable.
 */

type Json = unknown;

export interface CommandResult<T = Json> {
  ok: boolean;
  result?: T;
  error?: string;
  kind?: "sync" | "async" | "stream";
}

interface BridgeObject {
  invoke(raw: string): Promise<string> | string;
  // Renamed from `event` because that name shadows QObject.event() and
  // PyQt6 QWebChannel silently failed to expose it to JS.
  payload: { connect(cb: (raw: string) => void): void };
}

let bridge: BridgeObject | null = null;
const eventListeners: Array<(payload: unknown) => void> = [];

export async function initBridge(): Promise<void> {
  const qt = (window as unknown as { qt?: { webChannelTransport?: unknown } }).qt;
  if (!qt?.webChannelTransport) {
    bridge = stubBridge();
    return;
  }

  // Load qwebchannel.js from the QtWebEngine-injected qrc:// URL.
  await loadScript("qrc:///qtwebchannel/qwebchannel.js").catch(() => {
    /* swallow — stub will take over */
  });

  const QWebChannel = (window as unknown as { QWebChannel?: new (transport: unknown, cb: (ch: { objects: Record<string, BridgeObject> }) => void) => void }).QWebChannel;
  if (!QWebChannel) {
    bridge = stubBridge();
    return;
  }

  await new Promise<void>((res) => {
    new QWebChannel(qt.webChannelTransport, (channel) => {
      bridge = channel.objects.bridge ?? null;
      if (!bridge) {
        console.error("bridge: object 'bridge' missing from QWebChannel");
        res();
        return;
      }
      if (!bridge.payload || typeof bridge.payload.connect !== "function") {
        console.error(
          "bridge: 'payload' signal missing from bridge object — " +
            "events from Python will not reach the UI",
          Object.keys(bridge),
        );
        res();
        return;
      }
      bridge.payload.connect((raw) => {
        try {
          const payload = JSON.parse(raw);
          eventListeners.forEach((l) => l(payload));
        } catch (e) {
          console.error("bridge: bad event payload", e, raw);
        }
      });
      res();
    });
  });
}

export async function invoke<T = Json>(action: string, payload: Json = {}): Promise<CommandResult<T>> {
  if (!bridge) throw new Error("bridge not initialised");
  const raw = await bridge.invoke(JSON.stringify({ action, payload }));
  return JSON.parse(raw) as CommandResult<T>;
}

export function onEvent(cb: (payload: unknown) => void): () => void {
  eventListeners.push(cb);
  return () => {
    const i = eventListeners.indexOf(cb);
    if (i >= 0) eventListeners.splice(i, 1);
  };
}

// ----------------------------------------------------------------- helpers
function loadScript(src: string): Promise<void> {
  return new Promise((res, rej) => {
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => res();
    s.onerror = () => rej(new Error(`failed to load ${src}`));
    document.head.appendChild(s);
  });
}

function stubBridge(): BridgeObject {
  console.warn("TerraScope bridge: running in stub mode (no QGIS host detected)");
  return {
    invoke(raw: string): string {
      console.log("[stub bridge] invoke", raw);
      const { action, payload } = JSON.parse(raw);
      if (action === "app.ping") {
        return JSON.stringify({ ok: true, result: { pong: true, echo: payload } });
      }
      if (action === "app.version") {
        return JSON.stringify({ ok: true, result: { version: "dev" } });
      }
      return JSON.stringify({ ok: false, error: `stub bridge: unknown action ${action}` });
    },
    payload: { connect: () => {} },
  };
}
