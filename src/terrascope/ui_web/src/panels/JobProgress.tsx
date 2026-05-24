import { useEffect, useRef, useState } from "react";
import { onEvent } from "../bridge";

/**
 * Subscribes to bridge events for a given job_id and renders a progress bar
 * + status line.  Used by every workflow that runs as a QgsTask.
 *
 *   {type: "task.progress", job_id, percent, status}
 *   {type: "task.complete", job_id, result}
 *   {type: "task.failed",   job_id, error}
 *
 * Shows a "no events received yet — likely silent failure" warning if no
 * progress event arrives within :data:`STALL_WARN_MS`.
 */

const STALL_WARN_MS = 15_000;

export interface JobProgressProps {
  jobId: string | null;
  onComplete?: (result: unknown) => void;
  onFailed?: (error: string) => void;
}

interface TaskEvent {
  type?: "task.progress" | "task.complete" | "task.failed";
  job_id?: string;
  percent?: number;
  status?: string;
  result?: unknown;
  error?: string;
}

export function JobProgress({ jobId, onComplete, onFailed }: JobProgressProps) {
  const [percent, setPercent] = useState(0);
  const [status, setStatus] = useState<string>("");
  const [done, setDone] = useState<"running" | "ok" | "fail">("running");
  const [stalled, setStalled] = useState(false);
  const stallTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!jobId) return;
    setPercent(0);
    setStatus("");
    setDone("running");
    setStalled(false);

    // Stall watchdog: if no progress event in 15s, warn the user.
    if (stallTimer.current) clearTimeout(stallTimer.current);
    stallTimer.current = setTimeout(() => setStalled(true), STALL_WARN_MS);

    const unsubscribe = onEvent((payload) => {
      const e = payload as TaskEvent;
      if (e.job_id !== jobId) return;

      // Any event resets the stall watchdog.
      if (stallTimer.current) clearTimeout(stallTimer.current);
      setStalled(false);

      if (e.type === "task.progress") {
        if (typeof e.percent === "number") setPercent(e.percent);
        if (e.status) setStatus(e.status);
        // Re-arm watchdog after every progress emit.
        stallTimer.current = setTimeout(() => setStalled(true), STALL_WARN_MS);
      } else if (e.type === "task.complete") {
        setPercent(100);
        setDone("ok");
        setStatus("Done.");
        onComplete?.(e.result);
      } else if (e.type === "task.failed") {
        setDone("fail");
        setStatus(e.error ?? "Failed.");
        onFailed?.(e.error ?? "Failed.");
      }
    });

    return () => {
      unsubscribe();
      if (stallTimer.current) clearTimeout(stallTimer.current);
    };
  }, [jobId, onComplete, onFailed]);

  if (!jobId) return null;
  return (
    <div className="mt-3">
      <div className="h-1.5 bg-bg-1 rounded overflow-hidden">
        <div
          className={
            "h-full transition-all duration-200 " +
            (done === "fail" ? "bg-danger" : "bg-accent")
          }
          style={{ width: `${Math.round(percent)}%` }}
        />
      </div>
      <p
        className={
          "text-xs mt-1 " + (done === "fail" ? "text-danger" : "text-fg-muted")
        }
      >
        {Math.round(percent)}% — {status || (done === "running" ? "Starting…" : "")}
      </p>
      {stalled && done === "running" && (
        <p className="text-warn text-xs mt-1">
          No progress event in {STALL_WARN_MS / 1000} s. The task may be hung,
          the underlying dependency may be missing, or the bridge may have
          stopped forwarding events. Check the QGIS Log Messages panel
          (View → Panels → Log Messages → TerraScope tab) for the real
          last-known status.
        </p>
      )}
    </div>
  );
}
