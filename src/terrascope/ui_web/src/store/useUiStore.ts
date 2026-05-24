import { create } from "zustand";

/**
 * Global UI state for the embedded panel.
 *
 * Kept minimal — anything that needs to outlast a Welcome → CatalogSearch
 * navigation lives here.  Long-term project state lives Python-side in
 * `ProjectState` (terrascope.json).
 */
export type View = "welcome" | "catalog" | "classify" | "timeseries" | "sam";

interface ToastMessage {
  id: string;
  kind: "info" | "success" | "warn" | "danger";
  text: string;
}

interface UiState {
  view: View;
  setView(v: View): void;

  toasts: ToastMessage[];
  pushToast(t: Omit<ToastMessage, "id">): void;
  clearToast(id: string): void;

  busy: number; // counter for in-flight long tasks; > 0 means show spinner
  beginBusy(): void;
  endBusy(): void;
}

export const useUiStore = create<UiState>((set) => ({
  view: "welcome",
  setView: (v) => set({ view: v }),

  toasts: [],
  pushToast: (t) =>
    set((s) => ({
      toasts: [...s.toasts, { ...t, id: crypto.randomUUID() }],
    })),
  clearToast: (id) =>
    set((s) => ({
      toasts: s.toasts.filter((x) => x.id !== id),
    })),

  busy: 0,
  beginBusy: () => set((s) => ({ busy: s.busy + 1 })),
  endBusy: () => set((s) => ({ busy: Math.max(0, s.busy - 1) })),
}));
