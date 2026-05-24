import { useState } from "react";
import { invoke } from "../bridge";

/**
 * STAC catalogue search panel.
 *
 * Phase 1 implementation: collects AOI bbox + date range + cloud-cover ceiling
 * and dispatches `catalog.search`.  The Python controller resolves the bbox
 * (AOI from canvas, current layer, drawn polygon) before calling pystac.
 */
export function CatalogSearch() {
  const [endpoint, setEndpoint] = useState("planetary_computer");
  const [collection, setCollection] = useState("sentinel-2-l2a");
  const [west, setWest] = useState<string>("");
  const [south, setSouth] = useState<string>("");
  const [east, setEast] = useState<string>("");
  const [north, setNorth] = useState<string>("");
  const [start, setStart] = useState("2024-06-01");
  const [end, setEnd] = useState("2024-09-30");
  const [maxCloud, setMaxCloud] = useState(20);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState<unknown[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await invoke<{ items: unknown[] }>("catalog.search", {
        endpoint,
        collection,
        bbox: {
          west: parseFloat(west),
          south: parseFloat(south),
          east: parseFloat(east),
          north: parseFloat(north),
        },
        datetime: { start, end },
        max_cloud: maxCloud,
      });
      if (res.ok && res.result) {
        setResults(res.result.items ?? []);
      } else {
        setErr(res.error ?? "search failed");
      }
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const useCanvasBbox = async () => {
    const res = await invoke<{ bbox: [number, number, number, number] }>("canvas.bbox");
    if (res.ok && res.result?.bbox) {
      const [w, s, e, n] = res.result.bbox;
      setWest(String(w));
      setSouth(String(s));
      setEast(String(e));
      setNorth(String(n));
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

        <Field label="West">
          <NumInput value={west} onChange={setWest} />
        </Field>
        <Field label="South">
          <NumInput value={south} onChange={setSouth} />
        </Field>
        <Field label="East">
          <NumInput value={east} onChange={setEast} />
        </Field>
        <Field label="North">
          <NumInput value={north} onChange={setNorth} />
        </Field>

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
          onClick={useCanvasBbox}
          className="px-3 py-1.5 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm"
        >
          Use canvas extent
        </button>
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

interface NumInputProps {
  value: string;
  onChange(v: string): void;
}
function NumInput({ value, onChange }: NumInputProps) {
  return (
    <input
      type="number"
      step="any"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
    />
  );
}
