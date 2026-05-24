import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { invoke } from "../bridge";

interface Command {
  id: string;
  title: string;
  action: string;
  hint?: string;
}

const COMMANDS: Command[] = [
  { id: "catalog.open", title: "Open catalogue search", action: "catalog.open" },
  { id: "classify.start", title: "Start a classification", action: "classify.start" },
  { id: "ndvi.run", title: "Compute NDVI on the active raster", action: "ndvi.run" },
  { id: "timeseries.start", title: "Build a time-series cube", action: "timeseries.start" },
  { id: "sam.start", title: "Segment with SAM 3", action: "sam.start" },
  { id: "app.ping", title: "Bridge: ping", action: "app.ping", hint: "smoke test" },
];

interface Props {
  open: boolean;
  onOpenChange(open: boolean): void;
}

export function CommandPalette({ open, onOpenChange }: Props) {
  const [q, setQ] = useState("");
  const filtered = useMemo(() => {
    const needle = q.toLowerCase().trim();
    if (!needle) return COMMANDS;
    return COMMANDS.filter((c) => c.title.toLowerCase().includes(needle));
  }, [q]);

  const run = (cmd: Command) => {
    invoke(cmd.action).catch(console.error);
    onOpenChange(false);
    setQ("");
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/60" />
        <Dialog.Content
          className="fixed top-[15%] left-1/2 -translate-x-1/2 w-[min(560px,90vw)] bg-bg-1 border border-bg-2 rounded-md shadow-2xl"
          aria-label="Command palette"
        >
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filtered[0]) run(filtered[0]);
            }}
            placeholder="Search commands…"
            className="w-full px-4 py-3 bg-transparent text-fg outline-none border-b border-bg-2"
          />
          <ul className="max-h-72 overflow-auto">
            {filtered.length === 0 && (
              <li className="px-4 py-3 text-fg-muted text-sm">No matches.</li>
            )}
            {filtered.map((c) => (
              <li key={c.id}>
                <button
                  className="w-full text-left px-4 py-2.5 hover:bg-bg-2 flex items-center gap-3"
                  onClick={() => run(c)}
                >
                  <span className="flex-1">{c.title}</span>
                  {c.hint && <span className="text-fg-muted text-xs">{c.hint}</span>}
                </button>
              </li>
            ))}
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
