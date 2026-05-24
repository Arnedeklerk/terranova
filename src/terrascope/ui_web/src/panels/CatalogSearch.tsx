import { useEffect, useState } from "react";
import { invoke, onEvent } from "../bridge";
import { formatDMS, parseDMS } from "./dms";
import { JobProgress } from "./JobProgress";

interface CatalogItem {
  id: string;
  datetime: string;
  cloud: number | null;
  platform: string | null;
  bbox: [number, number, number, number] | null;
  // GeoJSON Polygon / MultiPolygon — typed loosely to avoid pulling in
  // @types/geojson just for this.
  geometry: { type: string; coordinates: unknown } | null;
}

/**
 * STAC catalogue search panel.
 *
 * AOI is given as two corners — NW (top-left) and SE (bottom-right) — with
 * a switch between Decimal Degrees and DMS for typing.  "Use canvas extent"
 * dispatches `canvas.bbox` to Python; the Python controller reads the QGIS
 * map canvas, projects to WGS84, and returns the bbox.
 */

type Format = "dd" | "dms";

interface CornerDD {
  lat: string;
  lon: string;
}

export function CatalogSearch() {
  const [endpoint, setEndpoint] = useState("planetary_computer");
  const [collection, setCollection] = useState("sentinel-2-l2a");
  const [format, setFormat] = useState<Format>("dd");

  // Decimal-degrees state — north/west = NW corner; south/east = SE corner.
  const [nw, setNw] = useState<CornerDD>({ lat: "", lon: "" });
  const [se, setSe] = useState<CornerDD>({ lat: "", lon: "" });

  // DMS state (parallel — we convert on toggle).
  const [nwDms, setNwDms] = useState<CornerDD>({ lat: "", lon: "" });
  const [seDms, setSeDms] = useState<CornerDD>({ lat: "", lon: "" });

  const [start, setStart] = useState("2024-06-01");
  const [end, setEnd] = useState("2024-09-30");
  const [maxCloud, setMaxCloud] = useState(20);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<CatalogItem[] | null>(null);
  // Multi-select: set of item IDs the user has ticked.
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  // The item currently previewed on the QGIS map (last row clicked, not
  // necessarily ticked).  Separated from selectedIds because previewing
  // one footprint to inspect coverage shouldn't force a download.
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [downloadJobId, setDownloadJobId] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [picking, setPicking] = useState(false);
  // Per-item download status while a batch is running.
  const [batchProgress, setBatchProgress] = useState<{
    done: number;
    total: number;
    failed: string[];
  } | null>(null);
  // Batch driver state: queue of items left, shared output dir, currently
  // running item id.  These have to live up here at the top of the
  // component because all useState calls must run before the first
  // conditional return / JSX block.
  const [pendingQueue, setPendingQueue] = useState<CatalogItem[]>([]);
  const [batchOutDir, setBatchOutDir] = useState<string | null>(null);
  const [currentItemId, setCurrentItemId] = useState<string | null>(null);

  // Clean up the map preview + any active AOI picker when the panel
  // unmounts (user navigates away).
  useEffect(() => {
    return () => {
      void invoke("catalog.clear_preview");
      void invoke("catalog.pick_aoi.stop");
    };
  }, []);

  // Listen for the "user finished drawing the AOI rectangle" event the
  // canvas-side tool emits when they release the mouse.
  useEffect(() => {
    return onEvent((payload) => {
      const p = payload as {
        type?: string;
        bbox?: [number, number, number, number];
      };
      if (p.type !== "catalog.aoi.picked" || !p.bbox) return;
      const [west, south, east, north] = p.bbox;
      if (format === "dd") {
        setNw({ lat: String(north), lon: String(west) });
        setSe({ lat: String(south), lon: String(east) });
      } else {
        setNwDms({
          lat: formatDMS(north, true),
          lon: formatDMS(west, false),
        });
        setSeDms({
          lat: formatDMS(south, true),
          lon: formatDMS(east, false),
        });
      }
      setPicking(false);
    });
  }, [format]);

  const currentBbox = (): {
    west: number;
    south: number;
    east: number;
    north: number;
  } => {
    if (format === "dd") {
      return {
        north: parseFloat(nw.lat),
        west: parseFloat(nw.lon),
        south: parseFloat(se.lat),
        east: parseFloat(se.lon),
      };
    }
    return {
      north: parseDMS(nwDms.lat),
      west: parseDMS(nwDms.lon),
      south: parseDMS(seDms.lat),
      east: parseDMS(seDms.lon),
    };
  };

  const switchFormat = (next: Format) => {
    if (next === format) return;
    if (next === "dms") {
      const toDms = (s: string, isLat: boolean) => {
        const v = parseFloat(s);
        return Number.isFinite(v) ? formatDMS(v, isLat) : "";
      };
      setNwDms({ lat: toDms(nw.lat, true), lon: toDms(nw.lon, false) });
      setSeDms({ lat: toDms(se.lat, true), lon: toDms(se.lon, false) });
    } else {
      const toDd = (s: string) => {
        try {
          return String(parseDMS(s));
        } catch {
          return "";
        }
      };
      setNw({ lat: toDd(nwDms.lat), lon: toDd(nwDms.lon) });
      setSe({ lat: toDd(seDms.lat), lon: toDd(seDms.lon) });
    }
    setFormat(next);
  };

  const submit = async () => {
    setBusy(true);
    setErr(null);
    setResults(null);
    setSelectedIds(new Set());
    setPreviewId(null);
    void invoke("catalog.clear_preview");
    try {
      const bbox = currentBbox();
      if (
        !Number.isFinite(bbox.west) ||
        !Number.isFinite(bbox.east) ||
        !Number.isFinite(bbox.south) ||
        !Number.isFinite(bbox.north)
      ) {
        throw new Error("Fill in all four corner coordinates.");
      }
      if (bbox.east <= bbox.west) {
        throw new Error("SE longitude must be greater than NW longitude.");
      }
      if (bbox.north <= bbox.south) {
        throw new Error("NW latitude must be greater than SE latitude.");
      }
      const res = await invoke<{ items: CatalogItem[] }>("catalog.search", {
        endpoint,
        collection,
        bbox,
        datetime: { start, end },
        max_cloud: maxCloud,
      });
      if (res.ok && res.result) {
        setResults(res.result.items ?? []);
      } else {
        setErr(res.error ?? "search failed");
      }
    } catch (e) {
      setErr((e as Error).message ?? String(e));
    } finally {
      setBusy(false);
    }
  };

  const pickOnMap = async () => {
    setErr(null);
    if (picking) {
      // Toggle off — user clicked the active button.
      await invoke("catalog.pick_aoi.stop");
      setPicking(false);
      return;
    }
    const r = await invoke("catalog.pick_aoi.start");
    if (!r.ok) {
      setErr(r.error ?? "Could not start the map picker.");
      return;
    }
    setPicking(true);
  };

  const useCanvasBbox = async () => {
    setErr(null);
    const res = await invoke<{ bbox: [number, number, number, number] }>(
      "canvas.bbox",
    );
    if (!res.ok || !res.result?.bbox) {
      setErr(res.error ?? "Could not read the canvas extent.");
      return;
    }
    const [west, south, east, north] = res.result.bbox;
    if (format === "dd") {
      setNw({ lat: String(north), lon: String(west) });
      setSe({ lat: String(south), lon: String(east) });
    } else {
      setNwDms({ lat: formatDMS(north, true), lon: formatDMS(west, false) });
      setSeDms({ lat: formatDMS(south, true), lon: formatDMS(east, false) });
    }
  };

  return (
    <section className="max-w-2xl">
      <h2 className="text-lg font-semibold mb-2">Catalogue search</h2>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Endpoint">
          <select
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="planetary_computer">Planetary Computer</option>
            <option value="earth_search">Earth Search</option>
            <option value="cdse">Copernicus Data Space</option>
          </select>
        </Field>
        <Field label="Collection">
          <select
            value={collection}
            onChange={(e) => setCollection(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="sentinel-2-l2a">Sentinel-2 L2A</option>
            <option value="landsat-c2-l2">Landsat C2 L2</option>
            <option value="sentinel-1-rtc">Sentinel-1 RTC</option>
          </select>
        </Field>
      </div>

      {/* AOI block ----------------------------------------------------- */}
      <div className="mt-5 bg-bg-1 border border-bg-2 rounded-md p-3">
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <span className="text-xs text-fg-muted">AOI (WGS84)</span>
          <div className="flex items-center gap-2 text-xs">
            <FormatPill active={format === "dd"} onClick={() => switchFormat("dd")}>
              Decimal degrees
            </FormatPill>
            <FormatPill active={format === "dms"} onClick={() => switchFormat("dms")}>
              DMS
            </FormatPill>
            <button
              onClick={useCanvasBbox}
              className="ml-2 px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
            >
              Use canvas extent
            </button>
            <button
              onClick={pickOnMap}
              className={
                "px-2.5 py-1 border border-bg-2 rounded " +
                (picking
                  ? "bg-accent text-white"
                  : "bg-bg-2 hover:bg-bg-0")
              }
              title="Drag a rectangle on the QGIS canvas"
            >
              {picking ? "Draw on map…" : "Pick on map"}
            </button>
          </div>
        </div>
        {picking && (
          <p className="text-xs text-fg-muted mb-2">
            Click and drag on the map to outline your AOI; release to confirm.
            Click "Pick on map" again to cancel.
          </p>
        )}

        <CornerRow
          name="Top-left (NW)"
          format={format}
          dd={nw}
          dms={nwDms}
          onDd={setNw}
          onDms={setNwDms}
        />
        <CornerRow
          name="Bottom-right (SE)"
          format={format}
          dd={se}
          dms={seDms}
          onDd={setSe}
          onDms={setSeDms}
        />
      </div>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <Field label="Start date">
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          />
        </Field>
        <Field label="End date">
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          />
        </Field>
        <Field label={`Max cloud cover (${maxCloud}%)`}>
          <input
            type="range"
            min={0}
            max={100}
            value={maxCloud}
            onChange={(e) => setMaxCloud(parseInt(e.target.value, 10))}
            className="w-full"
          />
        </Field>
      </div>

      <div className="flex gap-2 mt-4">
        <button
          onClick={submit}
          disabled={busy}
          className="px-3 py-1.5 bg-accent text-white rounded text-sm disabled:opacity-50"
        >
          {busy ? "Searching…" : "Search"}
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}

      {results && (
        <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md overflow-hidden">
          <div className="px-3 py-2 flex items-center justify-between border-b border-bg-2">
            <span className="text-xs text-fg-muted">
              {results.length} item{results.length === 1 ? "" : "s"} found
              {selectedIds.size > 0 && (
                <span className="ml-2 text-accent">
                  — {selectedIds.size} selected
                </span>
              )}
              {previewId && (
                <span className="ml-2 text-fg-muted/70">
                  · previewing on map
                </span>
              )}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => toggleAll()}
                className="px-2 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded text-xs"
              >
                {selectedIds.size === results.length && results.length > 0
                  ? "Clear all"
                  : "Select all"}
              </button>
              <button
                onClick={() => downloadBatch()}
                disabled={selectedIds.size === 0 || downloading}
                className="px-3 py-1 bg-accent text-white rounded text-xs disabled:opacity-50"
              >
                {downloading
                  ? "Downloading…"
                  : `Download ${selectedIds.size || ""} as COG${
                      selectedIds.size > 1 ? "s" : ""
                    }…`}
              </button>
            </div>
          </div>
          <div className="max-h-72 overflow-auto">
            <table className="w-full text-xs">
              <thead className="bg-bg-2 sticky top-0">
                <tr className="text-fg-muted">
                  <th className="w-8 px-2 py-1.5"></th>
                  <th className="text-left font-normal px-3 py-1.5">ID</th>
                  <th className="text-left font-normal px-3 py-1.5">Datetime</th>
                  <th className="text-right font-normal px-3 py-1.5">Cloud %</th>
                  <th className="text-left font-normal px-3 py-1.5">Platform</th>
                </tr>
              </thead>
              <tbody>
                {results.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="text-center text-fg-muted py-4"
                    >
                      No items matched.  Widen the date range or cloud cap.
                    </td>
                  </tr>
                )}
                {results.map((it) => {
                  const checked = selectedIds.has(it.id);
                  const active = previewId === it.id;
                  return (
                    <tr
                      key={it.id}
                      onClick={() => previewItem(it)}
                      className={
                        "cursor-pointer border-t border-bg-2 " +
                        (active ? "bg-accent/20 text-fg" : "hover:bg-bg-2")
                      }
                    >
                      <td
                        className="px-2 py-1.5 text-center"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelect(it.id)}
                          aria-label={`select ${it.id}`}
                        />
                      </td>
                      <td className="px-3 py-1.5 font-mono truncate max-w-[16rem]">
                        {it.id}
                      </td>
                      <td className="px-3 py-1.5 font-mono">
                        {String(it.datetime).slice(0, 19).replace("T", " ")}
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono">
                        {it.cloud == null ? "—" : it.cloud.toFixed(1)}
                      </td>
                      <td className="px-3 py-1.5">
                        {it.platform ?? "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="px-3 py-1.5 border-t border-bg-2 text-fg-muted text-xs">
            Tick the checkbox to queue for download.  Click a row to preview
            its actual footprint on the map (cyan outline) — useful for
            spotting scenes whose coverage barely overlaps your AOI.
          </p>
        </div>
      )}

      {batchProgress && (
        <div className="mt-3 text-xs text-fg-muted">
          Batch: {batchProgress.done}/{batchProgress.total} done
          {batchProgress.failed.length > 0 && (
            <span className="text-danger ml-2">
              · {batchProgress.failed.length} failed
            </span>
          )}
        </div>
      )}

      <JobProgress
        jobId={downloadJobId}
        onComplete={() => onItemComplete(true)}
        onFailed={(e) => onItemComplete(false, e)}
      />
    </section>
  );

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelectedIds((prev) =>
      prev.size === (results?.length ?? 0)
        ? new Set()
        : new Set((results ?? []).map((it) => it.id)),
    );
  }

  async function previewItem(it: CatalogItem) {
    setPreviewId(it.id);
    if (!it.geometry && !it.bbox) return;
    const r = await invoke("catalog.preview_footprint", {
      item_id: it.id,
      geometry: it.geometry ?? null,
      bbox: it.bbox ?? null,
    });
    if (!r.ok) {
      // Non-fatal — log but don't block download flow.
      console.warn("[catalog] preview_footprint failed:", r.error);
    }
  }

  async function downloadBatch() {
    if (selectedIds.size === 0 || !results) return;
    setErr(null);
    const queue = results.filter((it) => selectedIds.has(it.id));
    if (queue.length === 0) return;

    // For batch downloads, ask once for an output FOLDER and auto-name
    // files by item_id.  Single-item downloads keep the old save-file
    // dialog so users can choose a specific filename.
    let out_dir: string | null = null;
    if (queue.length > 1) {
      const r = await invoke<{ path: string }>("dialog.open_directory", {
        title: "Save downloads to folder",
      });
      if (!r.ok || !r.result?.path) return;
      out_dir = r.result.path;
    }

    setDownloading(true);
    setBatchProgress({ done: 0, total: queue.length, failed: [] });
    setBatchOutDir(out_dir);
    setPendingQueue(queue.slice(1));
    await startDownload(queue[0], out_dir);
  }

  async function startDownload(it: CatalogItem, outDir: string | null) {
    let bbox;
    try {
      bbox = currentBbox();
    } catch (e) {
      finishBatch();
      setErr((e as Error).message);
      return;
    }

    let out_path: string;
    if (outDir) {
      out_path = `${outDir.replace(/[/\\]+$/, "")}/${it.id}.tif`;
    } else {
      const r = await invoke<{ path: string }>("dialog.save_file", {
        default: `${it.id}.tif`,
        title: "Save as COG",
        filter: "Cloud-Optimised GeoTIFF (*.tif)",
      });
      if (!r.ok || !r.result?.path) {
        finishBatch();
        return;
      }
      out_path = r.result.path;
    }

    setCurrentItemId(it.id);
    const dl = await invoke<{ job_id: string }>("catalog.download", {
      endpoint,
      collection,
      item_id: it.id,
      bbox,
      out_path,
    });
    if (dl.ok && dl.result?.job_id) {
      setDownloadJobId(dl.result.job_id);
    } else {
      onItemComplete(false, dl.error ?? "catalog.download failed");
    }
  }

  function onItemComplete(ok: boolean, error?: string) {
    setDownloadJobId(null);
    setBatchProgress((p) =>
      p
        ? {
            done: p.done + 1,
            total: p.total,
            failed: ok && currentItemId ? p.failed : [...p.failed, currentItemId ?? "?"],
          }
        : null,
    );
    if (!ok && error) setErr(error);

    if (pendingQueue.length === 0) {
      finishBatch();
      return;
    }
    const [next, ...rest] = pendingQueue;
    setPendingQueue(rest);
    void startDownload(next, batchOutDir);
  }

  function finishBatch() {
    setDownloading(false);
    setCurrentItemId(null);
    setPendingQueue([]);
    setBatchOutDir(null);
  }
}

/* ------------------------------------------------------------------ */

interface FormatPillProps {
  active: boolean;
  onClick(): void;
  children: React.ReactNode;
}
function FormatPill({ active, onClick, children }: FormatPillProps) {
  return (
    <button
      onClick={onClick}
      className={
        "px-2 py-1 rounded text-xs " +
        (active
          ? "bg-accent text-white"
          : "bg-bg-2 hover:bg-bg-0 border border-bg-2")
      }
    >
      {children}
    </button>
  );
}

interface CornerRowProps {
  name: string;
  format: Format;
  dd: CornerDD;
  dms: CornerDD;
  onDd(v: CornerDD): void;
  onDms(v: CornerDD): void;
}
function CornerRow({ name, format, dd, dms, onDd, onDms }: CornerRowProps) {
  if (format === "dd") {
    return (
      <div className="grid grid-cols-[140px_1fr_1fr] gap-2 items-center mt-2">
        <span className="text-xs text-fg-muted">{name}</span>
        <Field label="Lat">
          <input
            type="number"
            step="any"
            value={dd.lat}
            onChange={(e) => onDd({ ...dd, lat: e.target.value })}
            className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
        <Field label="Lon">
          <input
            type="number"
            step="any"
            value={dd.lon}
            onChange={(e) => onDd({ ...dd, lon: e.target.value })}
            className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
      </div>
    );
  }
  return (
    <div className="grid grid-cols-[140px_1fr_1fr] gap-2 items-center mt-2">
      <span className="text-xs text-fg-muted">{name}</span>
      <Field label="Lat">
        <input
          type="text"
          value={dms.lat}
          placeholder={`51° 30' 26" N`}
          onChange={(e) => onDms({ ...dms, lat: e.target.value })}
          className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono"
        />
      </Field>
      <Field label="Lon">
        <input
          type="text"
          value={dms.lon}
          placeholder={`0° 7' 39" W`}
          onChange={(e) => onDms({ ...dms, lon: e.target.value })}
          className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono"
        />
      </Field>
    </div>
  );
}

interface FieldProps {
  label: string;
  children: React.ReactNode;
}
function Field({ label, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-muted">
      {label}
      {children}
    </label>
  );
}
