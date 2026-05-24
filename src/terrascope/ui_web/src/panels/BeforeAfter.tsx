import { useEffect, useRef } from "react";

interface Props {
  before: { url: string; bounds: [number, number, number, number] };
  after: { url: string; bounds: [number, number, number, number] };
  center?: [number, number];
  zoom?: number;
}

/**
 * Before/after raster swipe — MapLibre's `setStyle({sources: ...})` plus a
 * draggable vertical divider.  Useful for the change-detection workflow:
 * point the URLs at pre/post Sentinel-2 COG tile services.
 */
export function BeforeAfter({ before, after, center, zoom }: Props) {
  const mapNode = useRef<HTMLDivElement>(null);
  const sliderNode = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!mapNode.current) return;
    let map: any | null = null;
    let disposed = false;

    async function start() {
      const maplibre = await import("maplibre-gl");
      // CSS side-effect import — Vite handles the bundling.
      await import("maplibre-gl/dist/maplibre-gl.css");
      if (disposed || !mapNode.current) return;

      map = new maplibre.Map({
        container: mapNode.current,
        center: center ?? [
          (before.bounds[0] + before.bounds[2]) / 2,
          (before.bounds[1] + before.bounds[3]) / 2,
        ],
        zoom: zoom ?? 10,
        style: {
          version: 8,
          sources: {
            before: {
              type: "raster",
              tiles: [before.url],
              tileSize: 256,
              bounds: before.bounds,
            },
            after: {
              type: "raster",
              tiles: [after.url],
              tileSize: 256,
              bounds: after.bounds,
            },
          },
          layers: [
            { id: "before-layer", type: "raster", source: "before" },
            { id: "after-layer", type: "raster", source: "after", paint: { "raster-opacity": 1 } },
          ],
        },
      });

      const updateClip = (pct: number) => {
        const canvas = map?.getCanvas();
        if (!canvas) return;
        canvas.style.clipPath = `inset(0 0 0 ${pct}%)`;
        if (sliderNode.current) sliderNode.current.style.left = `${pct}%`;
      };
      updateClip(50);

      // Listen on the wrapper for slider drags.
      mapNode.current!.addEventListener("pointermove", (e: PointerEvent) => {
        if (e.buttons !== 1) return;
        const rect = mapNode.current!.getBoundingClientRect();
        const pct = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
        updateClip(pct);
      });
    }

    start().catch(console.error);
    return () => {
      disposed = true;
      if (map) map.remove();
    };
  }, [before, after, center, zoom]);

  return (
    <div className="relative w-full h-96 rounded-md overflow-hidden border border-bg-2">
      <div ref={mapNode} className="w-full h-full" />
      <div
        ref={sliderNode}
        className="absolute top-0 bottom-0 w-1 bg-accent pointer-events-none"
        style={{ left: "50%" }}
      />
    </div>
  );
}
