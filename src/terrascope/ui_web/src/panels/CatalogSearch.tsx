import { useState } from "react";
import { invoke } from "../bridge";
import { formatDMS, parseDMS } from "./dms";

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
  const [results, setResults] = useState<unknown[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

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
      const res = await invoke<{ items: unknown[] }>("catalog.search", {
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
        <p className="text-fg-muted text-sm mt-3">
          {results.length} item{results.length === 1 ? "" : "s"} found.
        </p>
      )}
    </section>
  );
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
