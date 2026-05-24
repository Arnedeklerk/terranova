import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

/**
 * Embedded Earth-Explorer-style map for picking an AOI and previewing
 * scene footprints inside the catalog panel itself.
 *
 * Why this exists instead of pushing overlays to the QGIS canvas: the
 * QGIS-canvas approach depended on a lot of state lining up (project
 * CRS valid, layer panel not in a weird state, in-memory layer renderer
 * applying correctly).  An embedded map sidesteps all of that and gives
 * the user instant visual feedback regardless of what QGIS is doing.
 *
 * Props are the controlled bbox + an optional scene footprint polygon
 * to highlight; the parent owns state.  We never call back into the
 * bridge from here.
 */

export interface Bbox {
  west: number;
  south: number;
  east: number;
  north: number;
}

// Available basemaps.  Both are free without an API key; both require
// attribution which is set in the tile layer options.  Keep them outside
// the component so swap-on-toggle doesn't re-create the L.tileLayer
// options object every render.
type BasemapKey = "street" | "satellite";
const BASEMAPS: Record<
  BasemapKey,
  { url: string; options: L.TileLayerOptions }
> = {
  street: {
    url: "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    options: {
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> · © <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: "abcd",
      maxZoom: 20,
      keepBuffer: 4,
      // Defer tile-grid rebuilds until the pan/zoom gesture stops.
      // Makes the gesture itself glassy at the cost of a brief
      // blank-edge while tiles load; combined with keepBuffer: 4 the
      // blank-edge is minimal because tiles are preloaded.
      updateWhenIdle: true,
    },
  },
  satellite: {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: {
      attribution:
        "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
      maxZoom: 19,
      keepBuffer: 4,
      updateWhenIdle: true,
    },
  },
};

export interface FootprintSpec {
  id: string;
  geometry: { type: string; coordinates: unknown };
  /** Hex outline colour, e.g. ``#FFD43B``.  Fill is the same colour at ~15% alpha. */
  color: string;
  /** If true, draw thicker stroke — used for the currently-previewed row. */
  active?: boolean;
}

interface Props {
  /** Current AOI, drawn as an orange dashed rectangle.  `null` = none. */
  aoi: Bbox | null;
  /**
   * Footprints to draw with semi-transparent fills.  Overlapping regions
   * appear naturally darker because alpha compounds — the Earth-Explorer
   * "which scenes cover my AOI" effect.  Pass an empty array for none.
   */
  footprints: FootprintSpec[];
  /** Called when the user finishes drawing a new rectangle. */
  onAoiChange(b: Bbox): void;
  /** Whether downloads should clip the scene raster to the AOI. */
  maskToAoi: boolean;
  /** Toggle handler for the "Mask to AOI" checkbox in the header. */
  onMaskToAoiChange(v: boolean): void;
}

export function AoiMap({
  aoi,
  footprints,
  onAoiChange,
  maskToAoi,
  onMaskToAoiChange,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseLayerRef = useRef<L.TileLayer | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [basemap, setBasemap] = useState<BasemapKey>("street");
  // Layers we control — held in refs so we can replace cleanly on prop
  // changes without React tree churn.
  const aoiLayerRef = useRef<L.Rectangle | null>(null);
  // One L.GeoJSON per footprint id; diffed against the incoming prop on
  // every render so we don't tear-down/rebuild every layer each time.
  const footprintLayersRef = useRef<Map<string, L.GeoJSON>>(new Map());
  const drawingRef = useRef<{
    active: boolean;
    start: L.LatLng | null;
    rect: L.Rectangle | null;
  }>({ active: false, start: null, rect: null });
  // Latest onAoiChange — refs so the draw handlers don't have to be
  // re-registered on every parent re-render.
  const onAoiChangeRef = useRef(onAoiChange);
  onAoiChangeRef.current = onAoiChange;

  // ----------------------------------------------------------------- init
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      center: [20, 0],
      zoom: 2,
      worldCopyJump: true,
      zoomControl: true,
      scrollWheelZoom: true,
      wheelDebounceTime: 30,
      // Canvas renderer makes pan/drag MUCH smoother when several
      // semi-transparent footprints are visible — SVG alpha-blending
      // is the bottleneck with 4+ polygons on screen.
      preferCanvas: true,
      // No tile fade-in: shaves a frame off every pan + every tile
      // request and just makes the map feel snappier.
      fadeAnimation: false,
      // Don't request a new tile set on every zoom delta; wait until
      // the zoom-out finishes.  Smoother feeling zoom at the cost of
      // brief blurring at intermediate scales.
      zoomAnimation: true,
    });
    requestAnimationFrame(() => {
      map.invalidateSize();
    });
    // Initial tile layer is added by the basemap-effect below; we just
    // need the map instance ready first so the effect has something to
    // .addTo(...).
    mapRef.current = map;

    // Drawing handlers — registered once, gated by drawingRef.current.active
    // so the same map can be panned normally when draw mode is off.

    const abortDraw = () => {
      const d = drawingRef.current;
      if (d.rect) {
        d.rect.remove();
        d.rect = null;
      }
      d.start = null;
      d.active = false;
      map.dragging.enable();
      if (containerRef.current) {
        containerRef.current.style.cursor = "";
      }
    };

    const onMouseDown = (e: L.LeafletMouseEvent) => {
      const d = drawingRef.current;
      if (!d.active) return;
      d.start = e.latlng;
      d.rect = L.rectangle(L.latLngBounds(d.start, d.start), {
        color: "#FF9E2F",
        weight: 2,
        dashArray: "6 4",
        fill: false,
      }).addTo(map);
      map.dragging.disable();
    };
    const onMouseMove = (e: L.LeafletMouseEvent) => {
      const d = drawingRef.current;
      if (!d.active || !d.start || !d.rect) return;
      d.rect.setBounds(L.latLngBounds(d.start, e.latlng));
    };
    const onMouseUp = (e: L.LeafletMouseEvent) => {
      const d = drawingRef.current;
      if (!d.active || !d.start) return;
      const end = e.latlng;
      const south = Math.min(d.start.lat, end.lat);
      const north = Math.max(d.start.lat, end.lat);
      const west = Math.min(d.start.lng, end.lng);
      const east = Math.max(d.start.lng, end.lng);
      abortDraw();
      // Don't draw degenerate boxes (single-click without drag).
      if (north - south < 1e-5 || east - west < 1e-5) return;
      onAoiChangeRef.current({ west, south, east, north });
    };
    // Right-click during drag MUST cancel cleanly.  Leaflet fires
    // `contextmenu` instead of `mouseup` for the right button, so
    // without this the temporary rectangle leaks onto the map and
    // never gets cleared — every subsequent right-click stacks
    // another orphan polygon up.
    const onContextMenu = (e: L.LeafletMouseEvent) => {
      const d = drawingRef.current;
      if (!d.active && !d.rect) return;
      abortDraw();
      // Suppress the OS context menu so right-clicking on the map
      // can't accidentally pop up the page's right-click menu.
      e.originalEvent?.preventDefault?.();
    };
    // Esc also cancels — symmetrical with the Expand-modal Esc handler.
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && drawingRef.current.active) abortDraw();
    };

    map.on("mousedown", onMouseDown);
    map.on("mousemove", onMouseMove);
    map.on("mouseup", onMouseUp);
    map.on("contextmenu", onContextMenu);
    window.addEventListener("keydown", onEsc);

    return () => {
      map.off("mousedown", onMouseDown);
      map.off("mousemove", onMouseMove);
      map.off("mouseup", onMouseUp);
      map.off("contextmenu", onContextMenu);
      window.removeEventListener("keydown", onEsc);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Basemap layer — replaced wholesale when the user toggles between
  // street and satellite.  The new layer is added BEFORE the old one is
  // removed so there's no flash of empty grey while tiles load.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const cfg = BASEMAPS[basemap];
    const layer = L.tileLayer(cfg.url, cfg.options).addTo(map);
    // Keep base tiles below footprint/AOI overlays.
    layer.bringToBack();
    const prev = baseLayerRef.current;
    baseLayerRef.current = layer;
    if (prev) prev.remove();
  }, [basemap]);

  // Re-render the AOI rectangle when prop changes; fit view to it the
  // first time so the user sees their AOI without panning.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (aoiLayerRef.current) {
      aoiLayerRef.current.remove();
      aoiLayerRef.current = null;
    }
    if (!aoi) return;
    const bounds = L.latLngBounds(
      [aoi.south, aoi.west],
      [aoi.north, aoi.east],
    );
    aoiLayerRef.current = L.rectangle(bounds, {
      color: "#FF9E2F",
      weight: 2,
      dashArray: "6 4",
      fill: false,
    }).addTo(map);
    // Fit the bounds with a bit of padding, but only if the bounds are
    // outside the current view — don't yank the user's zoom for free.
    if (!map.getBounds().contains(bounds)) {
      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 12 });
    }
  }, [aoi]);

  // Footprints: one layer per id, diffed against the prop.  Overlapping
  // semi-transparent fills produce a natural Earth-Explorer-style
  // darkening where scenes overlap.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const current = footprintLayersRef.current;
    const incoming = new Map(footprints.map((f) => [f.id, f]));

    // Remove footprints that are no longer in the prop list.
    for (const [id, layer] of current) {
      if (!incoming.has(id)) {
        layer.remove();
        current.delete(id);
      }
    }
    // Add or restyle the rest.
    for (const spec of footprints) {
      const existing = current.get(spec.id);
      const style: L.PathOptions = {
        color: spec.color,
        weight: spec.active ? 3 : 1.5,
        fill: true,
        fillColor: spec.color,
        // ~15% fill so 2–3 overlapping scenes still let the basemap
        // through but stacked-up regions get visibly darker.
        fillOpacity: spec.active ? 0.25 : 0.15,
        opacity: spec.active ? 1.0 : 0.8,
      };
      if (existing) {
        existing.setStyle(style);
      } else {
        const layer = L.geoJSON(spec.geometry as never, { style }).addTo(map);
        current.set(spec.id, layer);
      }
    }
  }, [footprints]);

  // Leaflet caches the container size at every layout-affecting event.
  // Switching expanded mode resizes the container in one paint; tell
  // Leaflet to re-measure on the next frame so tiles + hit testing line
  // up with the new bounds.
  useEffect(() => {
    if (!mapRef.current) return;
    const t = setTimeout(() => mapRef.current?.invalidateSize(), 50);
    return () => clearTimeout(t);
  }, [expanded]);

  // Escape collapses the expanded view.  Only attach when expanded so
  // a stray Escape press in normal mode doesn't get swallowed.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  const startDrawing = () => {
    drawingRef.current.active = true;
    if (containerRef.current) {
      containerRef.current.style.cursor = "crosshair";
    }
  };
  // Drawing auto-disengages on mouseup; restore the cursor.
  useEffect(() => {
    if (!containerRef.current) return;
    const reset = () => {
      if (containerRef.current && !drawingRef.current.active) {
        containerRef.current.style.cursor = "";
      }
    };
    const t = setInterval(reset, 200);
    return () => clearInterval(t);
  }, []);

  return (
    <>
      {/* When expanded, dim everything behind the modal and let
          click-outside collapse it.  z-40 sits under the map wrapper's
          z-50 so the map stays clickable. */}
      {expanded && (
        <div
          className="fixed inset-0 bg-black/60 z-40"
          onClick={() => setExpanded(false)}
          aria-hidden="true"
        />
      )}
      <div
        className={
          "bg-bg-1 border border-bg-2 rounded-md overflow-hidden flex flex-col " +
          (expanded
            ? "fixed inset-3 z-50 shadow-2xl"
            : "mt-4")
        }
      >
        <div className="px-3 py-2 flex items-center justify-between border-b border-bg-2 text-xs">
          <span className="text-fg-muted">
            AOI map — draw a rectangle to set the search area.  Orange
            dashed = AOI, coloured fills = ticked scene footprints.
          </span>
          <div className="flex items-center gap-2">
            {/* AOI controls — Mask and Draw are visually grouped in a
                single segmented bar to signal that Mask is a modifier
                of the AOI workflow (it only matters if the AOI is set).
                Expand stays separate because it's a viewport concern,
                not an AOI concern. */}
            <div className="flex items-stretch bg-bg-2 border border-bg-2 rounded overflow-hidden">
              <label
                className="flex items-center gap-1.5 px-2.5 py-1 hover:bg-bg-0 cursor-pointer select-none border-r border-bg-2"
                title="Mask to AOI — when ON, downloaded scenes are cropped to the AOI rectangle. When OFF (default), the full scene tile is downloaded; much larger files, but you keep every pixel the scene covers."
              >
                <input
                  type="checkbox"
                  checked={maskToAoi}
                  onChange={(e) => onMaskToAoiChange(e.target.checked)}
                />
                Mask
              </label>
              <button
                onClick={startDrawing}
                className="px-2.5 py-1 hover:bg-bg-0"
                title="Click then drag on the map to draw an AOI rectangle"
              >
                Draw AOI
              </button>
            </div>
            {/* Basemap toggle — Map (Carto Voyager) vs Satellite (Esri).
                Single click switches; tiles swap without remounting the
                map, so AOI + footprints stay put. */}
            <div className="flex items-stretch bg-bg-2 border border-bg-2 rounded overflow-hidden">
              <button
                onClick={() => setBasemap("street")}
                className={
                  "px-2.5 py-1 border-r border-bg-2 " +
                  (basemap === "street"
                    ? "bg-accent text-white"
                    : "hover:bg-bg-0")
                }
                title="Street map basemap"
              >
                Map
              </button>
              <button
                onClick={() => setBasemap("satellite")}
                className={
                  "px-2.5 py-1 " +
                  (basemap === "satellite"
                    ? "bg-accent text-white"
                    : "hover:bg-bg-0")
                }
                title="Satellite imagery basemap (Esri World Imagery)"
              >
                Satellite
              </button>
            </div>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
              title={
                expanded
                  ? "Collapse map back into the panel (Esc)"
                  : "Expand map to fill the dock"
              }
            >
              {expanded ? "Collapse ↙" : "Expand ↗"}
            </button>
          </div>
        </div>
        {/* Map container.  In normal mode we use aspect-ratio so the map
            scales taller as the user drags the dock wider — no fixed
            pixel height.  In expanded mode flex-1 takes the remaining
            modal area.  Intentionally NO React onWheel handler — React
            adds passive listeners that fight Leaflet's native wheel
            handler. */}
        <div
          ref={containerRef}
          className="w-full"
          style={{
            // GPU compositing hints — promote the map container to its
            // own composited layer so pan/zoom blits are done on the
            // GPU instead of the CPU.  Single biggest source of
            // residual jank inside QtWebEngine embeds.
            willChange: "transform",
            transform: "translateZ(0)",
            backfaceVisibility: "hidden",
            ...(expanded
              ? { flex: "1 1 auto", minHeight: 0 }
              : { aspectRatio: "3 / 2", minHeight: 340 }),
          }}
        />
      </div>
    </>
  );
}
