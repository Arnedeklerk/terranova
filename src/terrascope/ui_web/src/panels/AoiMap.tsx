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
  const [expanded, setExpanded] = useState(false);
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
      // Explicit even though it's the default — QtWebEngine embeds can
      // be subtle about wheel-event delivery; making sure Leaflet has
      // its scroll-zoom handler wired regardless.
      scrollWheelZoom: true,
      wheelDebounceTime: 30,
    });
    // If the dock was mounted while collapsed (size 0x0) then later
    // expanded, Leaflet's initial measurement is wrong — schedule a
    // resize on the next frame so tiles + interactions line up with the
    // visible container.
    requestAnimationFrame(() => {
      map.invalidateSize();
    });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(map);
    mapRef.current = map;

    // Drawing handlers — registered once, gated by drawingRef.current.active
    // so the same map can be panned normally when draw mode is off.
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
      if (d.rect) {
        d.rect.remove();
        d.rect = null;
      }
      d.start = null;
      d.active = false;
      map.dragging.enable();
      // Don't draw degenerate boxes (single-click without drag).
      if (north - south < 1e-5 || east - west < 1e-5) return;
      onAoiChangeRef.current({ west, south, east, north });
    };
    map.on("mousedown", onMouseDown);
    map.on("mousemove", onMouseMove);
    map.on("mouseup", onMouseUp);

    return () => {
      map.off("mousedown", onMouseDown);
      map.off("mousemove", onMouseMove);
      map.off("mouseup", onMouseUp);
      map.remove();
      mapRef.current = null;
    };
  }, []);

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
            <label
              className="flex items-center gap-1.5 px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded cursor-pointer select-none"
              title="When ON, downloaded scenes are cropped to your AOI rectangle. When OFF (default), the full scene tile is downloaded — much larger files, but you keep all pixels."
            >
              <input
                type="checkbox"
                checked={maskToAoi}
                onChange={(e) => onMaskToAoiChange(e.target.checked)}
              />
              Mask to AOI
            </label>
            <button
              onClick={startDrawing}
              className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
              title="Click then drag on the map to draw a rectangle"
            >
              Draw AOI
            </button>
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
          style={
            expanded
              ? { flex: "1 1 auto", minHeight: 0 }
              : { aspectRatio: "3 / 2", minHeight: 340 }
          }
        />
      </div>
    </>
  );
}
