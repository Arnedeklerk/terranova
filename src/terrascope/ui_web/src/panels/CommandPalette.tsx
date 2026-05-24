import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { invoke } from "../bridge";
import { useUiStore, type View } from "../store/useUiStore";

/**
 * Cmd-K command palette.
 *
 * Two command shapes:
 *   - `view`   navigates the dock to the given tab
 *   - `action` dispatches a single bridge action (used for the smoke test)
 *
 * Anything more complex than "go there" belongs inside the destination panel,
 * not as a one-shot command — that's why this list is short.
 */

interface Command {
  id: string;
  title: string;
  hint?: string;
  view?: View;
  action?: string;
}

const COMMANDS: Command[] = [
  // Navigation
  { id: "go.catalog", title: "Catalogue search", view: "catalog", hint: "go to" },
  { id: "go.classify", title: "Classify scene", view: "classify", hint: "go to" },
  { id: "go.accuracy", title: "Accuracy report", view: "accuracy", hint: "go to" },
  {
    id: "go.timeseries",
    title: "Time-series + change detection",
    view: "timeseries",
    hint: "go to",
  },
  { id: "go.sam", title: "Segment with SAM", view: "sam", hint: "go to" },
  {
    id: "go.foundation",
    title: "Fine-tune foundation model",
    view: "foundation",
    hint: "go to",
  },
  { id: "go.cdse", title: "Sign in to CDSE", view: "cdse", hint: "go to" },
  { id: "go.welcome", title: "Welcome", view: "welcome", hint: "go to" },

  // Diagnostics
  { id: "app.ping", title: "Bridge: ping", action: "app.ping", hint: "smoke test" },
  { id: "app.version", title: "Show plugin version", action: "app.version", hint: "diagnostic" },
];

interface Props {
  open: boolean;
  onOpenChange(open: boolean): void;
}

export function CommandPalette({ open, onOpenChange }: Props) {
  const [q, setQ] = useState("");
  const setView = useUiStore((s) => s.setView);

  const filtered = useMemo(() => {
    const needle = q.toLowerCase().trim();
    if (!needle) return COMMANDS;
    return COMMANDS.filter((c) => c.title.toLowerCase().includes(needle));
  }, [q]);

  const run = (cmd: Command) => {
    if (cmd.view) {
      setView(cmd.view);
    } else if (cmd.action) {
      invoke(cmd.action)
        .then((r) => {
          // Surface bridge replies in the browser console so smoke tests are visible.
          console.log("[palette]", cmd.action, r);
        })
        .catch(console.error);
    }
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
