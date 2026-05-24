import { useEffect, useRef, useState } from "react";
import { onEvent } from "../bridge";

/**
 * Live tail of QGIS log messages, scoped to a tag (default "Terranova").
 *
 * Subscribes to `qgis.log` events forwarded by the Bridge.  Each entry
 * shows level (info / warn / critical), a relative timestamp, and the
 * message.  Auto-scrolls to the bottom on new entries.
 *
 * Used inside JobProgress as a "what is actually happening right now"
 * fallback when the headline progress bar isn't enough.
 */

interface LogEntry {
  message: string;
  tag: string;
  level: number;
  ts: number;
}

interface QgisLogEvent {
  type?: string;
  message?: string;
  tag?: string;
  level?: number;
}

const LEVEL_NAME: Record<number, "info" | "warn" | "critical"> = {
  0: "info",
  1: "warn",
  2: "critical",
  3: "critical",
};

interface Props {
  /** Only show messages with this QGIS-log tag.  Empty = all tags. */
  tag?: string;
  /** Max lines kept in memory.  Older lines drop off the top. */
  bufferSize?: number;
  /** Start expanded vs collapsed.  Default collapsed. */
  startOpen?: boolean;
}

export function LogTail({ tag = "Terranova", bufferSize = 200, startOpen = false }: Props) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [open, setOpen] = useState(startOpen);
  const scrollerRef = useRef<HTMLDivElement>(null);
  const newCount = useRef(0);

  useEffect(() => {
    return onEvent((payload) => {
      const e = payload as QgisLogEvent;
      if (e.type !== "qgis.log") return;
      if (tag && e.tag !== tag) return;
      const entry: LogEntry = {
        message: e.message ?? "",
        tag: e.tag ?? "",
        level: e.level ?? 0,
        ts: Date.now(),
      };
      setEntries((prev) => {
        const next = [...prev, entry];
        return next.length > bufferSize ? next.slice(-bufferSize) : next;
      });
      if (!open) newCount.current += 1;
    });
  }, [tag, bufferSize, open]);

  useEffect(() => {
    if (open && scrollerRef.current) {
      scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }
  }, [entries, open]);

  // Worst level still in the visible buffer — used to tint the toggle when
  // collapsed so a critical message doesn't go unnoticed.
  const worstLevel = entries.reduce((m, e) => Math.max(m, e.level), 0);
  const worstName = LEVEL_NAME[worstLevel] ?? "info";

  return (
    <div className="mt-2">
      <button
        onClick={() => {
          setOpen((v) => !v);
          newCount.current = 0;
        }}
        className="text-xs text-fg-muted hover:text-fg flex items-center gap-2"
      >
        <span>{open ? "▾" : "▸"} Log</span>
        <span className="text-fg-muted/70">
          ({entries.length} line{entries.length === 1 ? "" : "s"}
          {tag ? ` from ${tag}` : ""})
        </span>
        {!open && newCount.current > 0 && (
          <span
            className={
              "px-1.5 rounded text-xs " +
              (worstName === "critical"
                ? "bg-danger text-white"
                : worstName === "warn"
                  ? "bg-warn text-black"
                  : "bg-bg-2")
            }
          >
            {newCount.current} new
          </span>
        )}
      </button>
      {open && (
        <div
          ref={scrollerRef}
          className="mt-2 max-h-48 overflow-auto bg-bg-0 border border-bg-2 rounded p-2 font-mono text-xs leading-relaxed"
        >
          {entries.length === 0 && (
            <p className="text-fg-muted">No log messages yet.</p>
          )}
          {entries.map((e, i) => (
            <div
              key={i}
              className={
                "whitespace-pre-wrap " +
                (LEVEL_NAME[e.level] === "critical"
                  ? "text-danger"
                  : LEVEL_NAME[e.level] === "warn"
                    ? "text-warn"
                    : "text-fg")
              }
            >
              <span className="text-fg-muted">
                [{new Date(e.ts).toLocaleTimeString()}]
              </span>{" "}
              {e.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
