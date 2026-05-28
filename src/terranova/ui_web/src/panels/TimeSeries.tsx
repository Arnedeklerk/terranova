import { useState } from "react";
import { invoke } from "../bridge";
import { formatDMS, parseDMS } from "./dms";
import { JobProgress } from "./JobProgress";

/**
 * Time-series + change detection, parity with the Qt dialog.
 *
 * STAC search → cube → NDVI/NBR/NDMI → per-pixel change → break + magnitude
 * rasters + optional MP4 animation.
 */

type Format = "dd" | "dms";
interface CornerDD {
  lat: string;
  lon: string;
}

interface TimeseriesResult {
  break_path: string | null;
  magnitude_path: string | null;
  mp4_path: string | null;
}

export function TimeSeries() {
  const [format, setFormat] = useState<Format>("dd");
  const [nw, setNw] = useState<CornerDD>({ lat: "", lon: "" });
  const [se, setSe] = useState<CornerDD>({ lat: "", lon: "" });
  const [nwDms, setNwDms] = useState<CornerDD>({ lat: "", lon: "" });
  const [seDms, setSeDms] = useState<CornerDD>({ lat: "", lon: "" });

  const today = new Date().toISOString().slice(0, 10);
  const threeYrsAgo = new Date(new Date().setFullYear(new Date().getFullYear() - 3))
    .toISOString()
    .slice(0, 10);
  const oneYrAgo = new Date(new Date().setFullYear(new Date().getFullYear() - 1))
    .toISOString()
    .slice(0, 10);

  const [historyStart, setHistoryStart] = useState(threeYrsAgo);
  const [monitorStart, setMonitorStart] = useState(oneYrAgo);
  const [end, setEnd] = useState(today);

  const [endpoint, setEndpoint] = useState("planetary_computer");
  const [indexKind, setIndexKind] = useState("ndvi");
  const [maxCloud, setMaxCloud] = useState(20);
  const [resolution, setResolution] = useState(30);
  const [method, setMethod] = useState("cusum");
  const [threshold, setThreshold] = useState(2.0);
  const [exportMp4, setExportMp4] = useState(true);
  const [outDir, setOutDir] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<TimeseriesResult | null>(null);

  const currentBbox = () => {
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

  const useCanvasBbox = async () => {
    setErr(null);
    const r = await invoke<{ bbox: [number, number, number, number] }>("canvas.bbox");
    if (!r.ok || !r.result?.bbox) {
      setErr(r.error ?? "Could not read the canvas extent.");
      return;
    }
    const [west, south, east, north] = r.result.bbox;
    if (format === "dd") {
      setNw({ lat: String(north), lon: String(west) });
      setSe({ lat: String(south), lon: String(east) });
    } else {
      setNwDms({ lat: formatDMS(north, true), lon: formatDMS(west, false) });
      setSeDms({ lat: formatDMS(south, true), lon: formatDMS(east, false) });
    }
  };

  const pickOutDir = async () => {
    const r = await invoke<{ path: string }>("dialog.open_directory", {
      title: "Pick output directory",
    });
    if (r.ok && r.result?.path) setOutDir(r.result.path);
  };

  const run = async () => {
    setErr(null);
    setResult(null);
    if (!outDir) {
      setErr("Pick an output directory.");
      return;
    }
    try {
      const bbox = currentBbox();
      if (
        ![bbox.west, bbox.south, bbox.east, bbox.north].every(Number.isFinite) ||
        bbox.east <= bbox.west ||
        bbox.north <= bbox.south
      ) {
        throw new Error("Fill the AOI corners correctly (SE > NW on both axes).");
      }
      setBusy(true);
      const r = await invoke<{ job_id: string }>("timeseries.run", {
        bbox,
        history_start: historyStart,
        monitor_start: monitorStart,
        end,
        endpoint,
        index: indexKind,
        max_cloud: maxCloud,
        resolution,
        method,
        threshold,
        export_mp4: exportMp4,
        out_dir: outDir,
      });
      if (r.ok && r.result?.job_id) {
        setJobId(r.result.job_id);
      } else {
        setBusy(false);
        setErr(r.error ?? "timeseries.run failed");
      }
    } catch (e) {
      setErr((e as Error).message ?? String(e));
    }
  };

  return (
    <section className="max-w-2xl">
      <h2 className="text-lg font-semibold mb-2">Time-series + change detection</h2>
      <p className="text-fg-muted text-sm mb-4">
        Builds a Zarr cube from a STAC search, computes an index per time slice,
        and runs per-pixel change detection.  Writes break + magnitude rasters
        and an optional MP4 animation.
      </p>

      <div className="bg-bg-1 border border-bg-2 rounded-md p-3">
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <span className="text-xs text-fg-muted">AOI (WGS84)</span>
          <div className="flex items-center gap-2 text-xs">
            <button
              onClick={() => switchFormat("dd")}
              className={
                "px-2 py-1 rounded " +
                (format === "dd"
                  ? "bg-accent text-white"
                  : "bg-bg-2 hover:bg-bg-0 border border-bg-2")
              }
            >
              Decimal degrees
            </button>
            <button
              onClick={() => switchFormat("dms")}
              className={
                "px-2 py-1 rounded " +
                (format === "dms"
                  ? "bg-accent text-white"
                  : "bg-bg-2 hover:bg-bg-0 border border-bg-2")
              }
            >
              DMS
            </button>
            <button
              onClick={useCanvasBbox}
              className="ml-2 px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
            >
              Use canvas extent
            </button>
          </div>
        </div>
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

      <div className="grid grid-cols-3 gap-3 mt-4">
        <Field label="History start">
          <input
            type="date"
            value={historyStart}
            onChange={(e) => setHistoryStart(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          />
        </Field>
        <Field label="Monitoring start">
          <input
            type="date"
            value={monitorStart}
            onChange={(e) => setMonitorStart(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          />
        </Field>
        <Field label="End">
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <Field label="STAC endpoint">
          <select
            value={endpoint}
            onChange={(e) => setEndpoint(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="planetary_computer">Planetary Computer</option>
            <option value="earth_search">Earth Search</option>
          </select>
        </Field>
        <Field label="Index">
          <select
            value={indexKind}
            onChange={(e) => setIndexKind(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="ndvi">NDVI</option>
            <option value="nbr">NBR</option>
            <option value="ndmi">NDMI</option>
          </select>
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
        <Field label="Resolution (m)">
          <input
            type="number"
            value={resolution}
            min={10}
            max={300}
            onChange={(e) => setResolution(parseInt(e.target.value, 10) || 30)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
        <Field
          label="Method"
          hint="CuSum is the no-extra-deps default."
        >
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="cusum">CuSum (numpy)</option>
            <option value="bfast">BFAST Lite (extra deps)</option>
            <option value="landtrendr">LandTrendr-lite (numpy)</option>
          </select>
        </Field>
        <Field label="Threshold (σ)">
          <input
            type="number"
            step={0.5}
            min={0.5}
            max={10}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value) || 2.0)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
      </div>

      <label className="flex items-center gap-2 mt-4 text-sm text-fg-muted">
        <input
          type="checkbox"
          checked={exportMp4}
          onChange={(e) => setExportMp4(e.target.checked)}
        />
        Also export MP4 animation of the index cube
      </label>

      <Field label="Output directory">
        <div className="flex gap-2 mt-2">
          <input
            type="text"
            value={outDir}
            placeholder="(pick a folder…)"
            onChange={(e) => setOutDir(e.target.value)}
            className="flex-1 bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
          />
          <button
            onClick={pickOutDir}
            className="px-3 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm"
          >
            Browse…
          </button>
        </div>
      </Field>

      <div className="flex gap-2 mt-4">
        <button
          onClick={run}
          disabled={busy}
          className="px-3 py-1.5 bg-accent text-white rounded text-sm disabled:opacity-50"
        >
          {busy ? "Running…" : "Build cube + detect change"}
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}

      <JobProgress
        jobId={jobId}
        onComplete={(r) => {
          setBusy(false);
          setResult(r as TimeseriesResult);
        }}
        onFailed={(e) => {
          setBusy(false);
          setErr(e);
        }}
      />

      {result && (
        <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md p-4 text-sm space-y-1">
          {result.break_path && (
            <p className="text-fg-muted text-xs font-mono break-all">
              break-index: {result.break_path}
            </p>
          )}
          {result.magnitude_path && (
            <p className="text-fg-muted text-xs font-mono break-all">
              magnitude: {result.magnitude_path}
            </p>
          )}
          {result.mp4_path && (
            <p className="text-fg-muted text-xs font-mono break-all">
              MP4: {result.mp4_path}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

interface FieldProps {
  label: string;
  hint?: string;
  children: React.ReactNode;
}
function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-muted mt-2">
      <span>
        {label}
        {hint && <span className="ml-2 text-fg-muted/70">— {hint}</span>}
      </span>
      {children}
    </label>
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
        <input
          type="number"
          step="any"
          placeholder="Lat"
          value={dd.lat}
          onChange={(e) => onDd({ ...dd, lat: e.target.value })}
          className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
        />
        <input
          type="number"
          step="any"
          placeholder="Lon"
          value={dd.lon}
          onChange={(e) => onDd({ ...dd, lon: e.target.value })}
          className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
        />
      </div>
    );
  }
  return (
    <div className="grid grid-cols-[140px_1fr_1fr] gap-2 items-center mt-2">
      <span className="text-xs text-fg-muted">{name}</span>
      <input
        type="text"
        placeholder={`51° 30' 26" N`}
        value={dms.lat}
        onChange={(e) => onDms({ ...dms, lat: e.target.value })}
        className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
      />
      <input
        type="text"
        placeholder={`0° 7' 39" W`}
        value={dms.lon}
        onChange={(e) => onDms({ ...dms, lon: e.target.value })}
        className="w-full bg-bg-0 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
      />
    </div>
  );
}
