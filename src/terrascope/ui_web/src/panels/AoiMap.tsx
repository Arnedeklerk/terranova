import { useEffect, useRef } from "react";
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

interface Props {
  /** Current AOI, drawn as an orange dashed rectangle.  `null` = none. */
  aoi: Bbox | null;
  /** Currently-previewed scene footprint, drawn as a cyan polygon. */
  footprint: { type: string; coordinates: unknown } | null;
  /** Called when the user finishes drawing a new rectangle. */
  onAoiChange(b: Bbox): void;
  /** Optional fixed height — defaults to 280px. */
  height?: number;
}

export function AoiMap({ aoi, footprint, onAoiChange, height = 280 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  // Layers we control — held in refs so we can replace cleanly on prop
  // changes without React tree churn.
  const aoiLayerRef = useRef<L.Rectangle | null>(null);
  const footprintLayerRef = useRef<L.GeoJSON | null>(null);
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

  // Footprint preview (cyan solid).
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (footprintLayerRef.current) {
      footprintLayerRef.current.remove();
      footprintLayerRef.current = null;
    }
    if (!footprint) return;
    footprintLayerRef.current = L.geoJSON(footprint as never, {
      style: {
        color: "#40C4FF",
        weight: 2,
        fill: true,
        fillColor: "#40C4FF",
        fillOpacity: 0.1,
      },
    }).addTo(map);
  }, [footprint]);

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
    <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md overflow-hidden">
      <div className="px-3 py-2 flex items-center justify-between border-b border-bg-2 text-xs">
        <span className="text-fg-muted">
          AOI map — draw a rectangle to set the search area.  Orange
          dashed = AOI, cyan = scene footprint.
        </span>
        <button
          onClick={startDrawing}
          className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
          title="Click then drag on the map to draw a rectangle"
        >
          Draw AOI
        </button>
      </div>
      <div
        ref={containerRef}
        style={{ height }}
        className="w-full"
        // Intentionally NO React onWheel handler — React adds passive
        // listeners that interfere with Leaflet's native non-passive
        // wheel handler.  Let Leaflet own the event.
      />
    </div>
  );
}
