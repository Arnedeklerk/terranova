/// <reference types="vite/client" />

// CSS side-effect imports — Vite handles them, TS just needs to know they exist.
declare module "*.css";

// plotly.js-dist-min has no official @types package; the bundle exposes the
// usual Plotly factory functions.  We type it as `any`-ish to unblock the
// build; tighten when we actually consume more of its API.
declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot: (...args: unknown[]) => Promise<unknown>;
    purge: (el: HTMLElement) => void;
    [key: string]: any;
  };
  export default Plotly;
  export const newPlot: (...args: unknown[]) => Promise<unknown>;
  export const purge: (el: HTMLElement) => void;
}
