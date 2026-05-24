import { useEffect } from "react";

/**
 * Bind a list of keyboard shortcuts to a single handler.
 *
 * Combos are described as "Modifier+Key", e.g. "Meta+k", "Control+k",
 * "Alt+Shift+p".  Matching is case-insensitive on the final key.
 */
export function useHotkey(combos: string[], handler: (e: KeyboardEvent) => void) {
  useEffect(() => {
    const parsed = combos.map(parseCombo);
    const onKey = (e: KeyboardEvent) => {
      for (const c of parsed) {
        if (matches(c, e)) {
          e.preventDefault();
          handler(e);
          return;
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [combos, handler]);
}

interface Combo {
  meta: boolean;
  ctrl: boolean;
  alt: boolean;
  shift: boolean;
  key: string;
}

function parseCombo(s: string): Combo {
  const parts = s.split("+").map((p) => p.trim().toLowerCase());
  return {
    meta: parts.includes("meta") || parts.includes("cmd"),
    ctrl: parts.includes("control") || parts.includes("ctrl"),
    alt: parts.includes("alt") || parts.includes("option"),
    shift: parts.includes("shift"),
    key: parts[parts.length - 1],
  };
}

function matches(c: Combo, e: KeyboardEvent): boolean {
  return (
    e.metaKey === c.meta &&
    e.ctrlKey === c.ctrl &&
    e.altKey === c.alt &&
    e.shiftKey === c.shift &&
    e.key.toLowerCase() === c.key
  );
}
