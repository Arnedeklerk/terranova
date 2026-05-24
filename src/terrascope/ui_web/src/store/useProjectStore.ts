import { create } from "zustand";

/**
 * Project-state slice mirroring a subset of Python's `ProjectState`.
 *
 * The Python side is authoritative — this store caches a snapshot for the
 * web UI to render against.  Updates flow Python → web via `onEvent`
 * subscriptions or explicit `invoke("project.state.get")` calls.
 */
export interface CatalogItemSummary {
  id: string;
  datetime: string;
  cloud: number | null;
  platform: string | null;
}

interface ProjectStateSlice {
  lastSearchResults: CatalogItemSummary[];
  setSearchResults(items: CatalogItemSummary[]): void;

  activeAoi: { west: number; south: number; east: number; north: number } | null;
  setActiveAoi(bbox: { west: number; south: number; east: number; north: number } | null): void;

  recipeName: string | null;
  setRecipeName(name: string | null): void;
}

export const useProjectStore = create<ProjectStateSlice>((set) => ({
  lastSearchResults: [],
  setSearchResults: (items) => set({ lastSearchResults: items }),

  activeAoi: null,
  setActiveAoi: (bbox) => set({ activeAoi: bbox }),

  recipeName: null,
  setRecipeName: (name) => set({ recipeName: name }),
}));
