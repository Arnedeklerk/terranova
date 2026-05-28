# Terranova — web UI tier

The contents of this directory are bundled as static files inside the QGIS
plugin and loaded into a `QWebEngineView` at runtime.  In development you can
preview the panel in a regular browser via `serve.bat` (or `make ui-dev` from
the repo root); the `bridge.ts` falls back to a stub that logs invocations to
the console so the UI still functions without QGIS in the loop.

## Stack

- React 18 + TypeScript
- Vite 5
- Tailwind CSS 3
- Radix UI primitives (Dialog, Tooltip)
- Plotly.js (spectral / time-series charts)
- MapLibre GL JS (before/after slider)

## Build

```bash
npm install
npm run build           # writes ./dist
```

The QGIS plugin loads `dist/index.html` via `file://`; assets must therefore be
referenced with the relative `./` base (configured in `vite.config.ts`).

## Bridge

UI ↔ Python communication runs over QWebChannel.  See `src/bridge.ts` and
`src/terranova/bridge.py` for the matched pair.  Every message is validated
on the Python side with Pydantic before reaching a controller.
