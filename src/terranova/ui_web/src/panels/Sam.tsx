import { useEffect, useState } from "react";
import { invoke, onEvent } from "../bridge";
import { JobProgress } from "./JobProgress";

/**
 * SAM segmentation panel.
 *
 * Two modes:
 *   - text: provide a Grounded-SAM text prompt ("buildings", "fields").
 *   - points: click points on the QGIS map canvas; each click is sent
 *     back as a `sam.point.added` event.
 */

interface LayerInfo {
  name: string;
  source: string;
}

type Mode = "text" | "points";

export function Sam() {
  const [rasters, setRasters] = useState<LayerInfo[]>([]);
  const [rasterSrc, setRasterSrc] = useState("");
  const [model, setModel] = useState("sam2_b");
  const [mode, setMode] = useState<Mode>("text");
  const [prompt, setPrompt] = useState("buildings");
  const [boxThreshold, setBoxThreshold] = useState(0.24);
  const [textThreshold, setTextThreshold] = useState(0.24);
  const [points, setPoints] = useState<Array<[number, number]>>([]);
  const [picking, setPicking] = useState(false);
  const [outPath, setOutPath] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const refresh = async () => {
    const r = await invoke<{ layers: LayerInfo[] }>("layers.list_rasters");
    if (r.ok && r.result) setRasters(r.result.layers);
  };
  useEffect(() => {
    refresh();
  }, []);

  // Subscribe to point-added events while picking.
  useEffect(() => {
    if (!picking) return;
    return onEvent((payload) => {
      const e = payload as { type?: string; x?: number; y?: number };
      if (
        e.type === "sam.point.added" &&
        typeof e.x === "number" &&
        typeof e.y === "number"
      ) {
        setPoints((prev) => [...prev, [e.x as number, e.y as number]]);
      }
    });
  }, [picking]);

  const startPicking = async () => {
    await invoke("sam.pick_points.start");
    setPicking(true);
  };
  const stopPicking = async () => {
    await invoke("sam.pick_points.stop");
    setPicking(false);
  };

  const pickOutput = async () => {
    const r = await invoke<{ path: string }>("dialog.save_file", {
      default: "terranova_sam.gpkg",
      title: "Save SAM polygon output",
      filter: "GeoPackage (*.gpkg)",
    });
    if (r.ok && r.result?.path) setOutPath(r.result.path);
  };

  const run = async () => {
    if (!rasterSrc || !outPath) {
      setErr("Pick an input raster and an output path.");
      return;
    }
    if (mode === "text" && !prompt.trim()) {
      setErr("Enter a text prompt.");
      return;
    }
    if (mode === "points" && !points.length) {
      setErr("Click at least one point on the map.");
      return;
    }
    setErr(null);
    setBusy(true);
    if (picking) await stopPicking();
    const r = await invoke<{ job_id: string }>("sam.run", {
      raster_path: rasterSrc,
      out_path: outPath,
      model,
      mode,
      prompt: mode === "text" ? prompt : null,
      points: mode === "points" ? points : null,
      box_threshold: boxThreshold,
      text_threshold: textThreshold,
    });
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "sam.run failed");
    }
  };

  return (
    <section className="max-w-2xl">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">Segment with SAM</h2>
        <button
          onClick={refresh}
          className="text-xs text-fg-muted hover:text-fg"
        >
          Refresh layers ↻
        </button>
      </div>
      <p className="text-fg-muted text-sm mb-4">
        Prompts SAM 2 / SAM 3 with a text query or map clicks; writes a
        GeoPackage of polygons.  First run downloads the model weights
        (hundreds of MB) — be patient.
      </p>

      <div className="grid grid-cols-1 gap-3">
        <Field label="Input raster">
          <select
            value={rasterSrc}
            onChange={(e) => setRasterSrc(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="">— pick a raster layer —</option>
            {rasters.map((l) => (
              <option key={l.source} value={l.source}>
                {l.name}
              </option>
            ))}
          </select>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Model">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
            >
              <option value="sam2_b">SAM 2 base</option>
              <option value="sam2_l">SAM 2 large</option>
              <option value="sam3">SAM 3</option>
            </select>
          </Field>
          <Field label="Mode">
            <div className="flex gap-2">
              <ModePill active={mode === "text"} onClick={() => setMode("text")}>
                Text prompt
              </ModePill>
              <ModePill
                active={mode === "points"}
                onClick={() => setMode("points")}
              >
                Point prompts
              </ModePill>
            </div>
          </Field>
        </div>

        {mode === "text" ? (
          <div className="grid grid-cols-2 gap-3">
            <Field label="Text prompt">
              <input
                type="text"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="buildings"
                className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
              />
            </Field>
            <Field label="Box threshold">
              <input
                type="number"
                step={0.05}
                min={0.05}
                max={0.95}
                value={boxThreshold}
                onChange={(e) => setBoxThreshold(parseFloat(e.target.value) || 0.24)}
                className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
              />
            </Field>
            <Field label="Text threshold">
              <input
                type="number"
                step={0.05}
                min={0.05}
                max={0.95}
                value={textThreshold}
                onChange={(e) => setTextThreshold(parseFloat(e.target.value) || 0.24)}
                className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
              />
            </Field>
          </div>
        ) : (
          <div className="bg-bg-1 border border-bg-2 rounded-md p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-fg-muted">
                {points.length} point{points.length === 1 ? "" : "s"}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={picking ? stopPicking : startPicking}
                  className={
                    "px-2.5 py-1 text-xs rounded " +
                    (picking
                      ? "bg-warn text-black"
                      : "bg-accent text-white")
                  }
                >
                  {picking ? "Stop picking" : "Pick points on map"}
                </button>
                <button
                  onClick={() => setPoints([])}
                  className="px-2.5 py-1 text-xs bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
                >
                  Clear
                </button>
              </div>
            </div>
            <ul className="text-xs font-mono text-fg-muted max-h-32 overflow-auto space-y-1">
              {points.map(([x, y], i) => (
                <li key={i}>
                  {i + 1}. {x.toFixed(3)}, {y.toFixed(3)}
                </li>
              ))}
            </ul>
          </div>
        )}

        <Field label="Output GeoPackage">
          <div className="flex gap-2">
            <input
              type="text"
              value={outPath}
              placeholder="(pick a path…)"
              onChange={(e) => setOutPath(e.target.value)}
              className="flex-1 bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
            />
            <button
              onClick={pickOutput}
              className="px-3 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm"
            >
              Browse…
            </button>
          </div>
        </Field>
      </div>

      <div className="flex gap-2 mt-4">
        <button
          onClick={run}
          disabled={busy}
          className="px-3 py-1.5 bg-accent text-white rounded text-sm disabled:opacity-50"
        >
          {busy ? "Segmenting…" : "Segment"}
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}

      <JobProgress
        jobId={jobId}
        onComplete={() => setBusy(false)}
        onFailed={(e) => {
          setBusy(false);
          setErr(e);
        }}
      />
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

interface ModePillProps {
  active: boolean;
  onClick(): void;
  children: React.ReactNode;
}
function ModePill({ active, onClick, children }: ModePillProps) {
  return (
    <button
      onClick={onClick}
      className={
        "flex-1 px-2 py-1 rounded text-xs " +
        (active
          ? "bg-accent text-white"
          : "bg-bg-1 hover:bg-bg-2 border border-bg-2")
      }
    >
      {children}
    </button>
  );
}
