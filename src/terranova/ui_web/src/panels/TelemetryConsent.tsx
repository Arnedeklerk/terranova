import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { invoke } from "../bridge";

interface TelemetryStatus {
  decision: "not_asked" | "opted_in" | "opted_out";
  endpoint: string;
}

/**
 * One-time telemetry-consent prompt — appears on first launch if the user
 * has neither opted in nor out.  Honest and reversible:  the inspector shows
 * exactly the JSON that would be sent.
 */
export function TelemetryConsent() {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<unknown>(null);

  useEffect(() => {
    invoke<TelemetryStatus>("app.telemetry.status").then((r) => {
      if (r.ok && r.result?.decision === "not_asked") {
        setOpen(true);
        invoke("app.telemetry.inspect", { event_name: "app.launch" }).then((p) => {
          if (p.ok) setPreview(p.result);
        });
      }
    });
  }, []);

  const decide = (decision: "opted_in" | "opted_out") =>
    invoke("app.telemetry.set", { decision }).finally(() => setOpen(false));

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60" />
        <Dialog.Content
          className="fixed top-[20%] left-1/2 -translate-x-1/2 w-[min(540px,92vw)] bg-bg-1 border border-bg-2 rounded-md p-5 shadow-2xl"
          aria-label="Telemetry consent"
        >
          <Dialog.Title className="text-lg font-semibold mb-2">
            Help us improve Terranova?
          </Dialog.Title>
          <Dialog.Description asChild>
            <div className="text-sm text-fg-muted">
              <p>
                Telemetry is <strong>off by default</strong>. If you opt in we send only
                one event per significant action with these fields and{" "}
                <strong>nothing else</strong>: event name, plugin version, QGIS version,
                operating system, an opaque installation id, and a timestamp.
              </p>
              <p className="mt-2">
                Imagery, file paths, AOIs, credentials, and IP addresses are never sent.
                You can change this anytime in Settings → Privacy.
              </p>
            </div>
          </Dialog.Description>

          {preview != null && (
            <details className="mt-3 text-xs">
              <summary className="cursor-pointer text-fg-muted">
                Show next outbound payload
              </summary>
              <pre className="mt-1 p-2 bg-bg-0 rounded font-mono overflow-auto">
                {JSON.stringify(preview, null, 2)}
              </pre>
            </details>
          )}

          <div className="flex gap-2 mt-5 justify-end">
            <button
              onClick={() => decide("opted_out")}
              className="px-3 py-1.5 bg-bg-2 hover:bg-bg-1 border border-bg-2 rounded text-sm"
            >
              No thanks
            </button>
            <button
              onClick={() => decide("opted_in")}
              className="px-3 py-1.5 bg-accent text-white rounded text-sm"
            >
              Yes, help out
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
