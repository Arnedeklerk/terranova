import { useState } from "react";
import { invoke } from "../bridge";
import { JobProgress } from "./JobProgress";

/**
 * Foundation-model fine-tune panel — Phase 2, parity with the Qt dialog.
 *
 * Heavy workflow (GPU strongly recommended).  User picks paired scene + mask
 * rasters one at a time, sets backbone + epochs + batch size, kicks off the
 * QgsTask which downloads weights, fine-tunes via TerraTorch / Lightning,
 * then exports the checkpoint to ONNX.
 */

interface Pair {
  raster: string;
  mask: string;
}

interface FoundationResult {
  checkpoint_path: string | null;
  onnx_path: string | null;
}

const BACKBONES: Array<{ label: string; value: string }> = [
  { label: "Prithvi-EO-2.0 300M", value: "prithvi_eo_v2_300" },
  { label: "Prithvi-EO-2.0 600M", value: "prithvi_eo_v2_600" },
  { label: "Clay v1.5", value: "clay_v1_5" },
  { label: "TerraMind", value: "terramind" },
];

export function Foundation() {
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [backbone, setBackbone] = useState("prithvi_eo_v2_300");
  const [nClasses, setNClasses] = useState(5);
  const [maxEpochs, setMaxEpochs] = useState(20);
  const [batchSize, setBatchSize] = useState(8);
  const [learningRate, setLearningRate] = useState(1e-4);
  const [accelerator, setAccelerator] = useState("auto");
  const [outDir, setOutDir] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<FoundationResult | null>(null);

  const addPair = async () => {
    const r1 = await invoke<{ path: string }>("dialog.open_file", {
      title: "Pick a training raster",
      filter: "Rasters (*.tif *.tiff)",
    });
    if (!r1.ok || !r1.result?.path) return;
    const r2 = await invoke<{ path: string }>("dialog.open_file", {
      title: "Pick the matching mask raster (single-band class ids)",
      filter: "Rasters (*.tif *.tiff)",
    });
    if (!r2.ok || !r2.result?.path) return;
    setPairs((prev) => [...prev, { raster: r1.result!.path, mask: r2.result!.path }]);
  };

  const removePair = (i: number) =>
    setPairs((prev) => prev.filter((_, j) => j !== i));

  const pickOutDir = async () => {
    const r = await invoke<{ path: string }>("dialog.open_directory", {
      title: "Pick output directory",
    });
    if (r.ok && r.result?.path) setOutDir(r.result.path);
  };

  const run = async () => {
    if (!pairs.length) {
      setErr("Add at least one scene + mask pair.");
      return;
    }
    if (!outDir) {
      setErr("Pick an output directory.");
      return;
    }
    setErr(null);
    setResult(null);
    setBusy(true);
    const r = await invoke<{ job_id: string }>("foundation.run", {
      backbone,
      n_classes: nClasses,
      max_epochs: maxEpochs,
      batch_size: batchSize,
      learning_rate: learningRate,
      accelerator,
      pairs,
      out_dir: outDir,
    });
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "foundation.run failed");
    }
  };

  return (
    <section className="max-w-2xl">
      <h2 className="text-lg font-semibold mb-2">Fine-tune foundation model</h2>
      <p className="text-fg-muted text-sm mb-4 leading-relaxed">
        Heavy workflow: downloads multi-GB weights, fine-tunes on your scene/
        mask pairs, exports an ONNX for fast inference.  GPU strongly
        recommended (CPU works but slowly).  Requires the <code>[ml]</code>
        extras: <code>pip install terranova[ml]</code>.
      </p>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Backbone">
          <select
            value={backbone}
            onChange={(e) => setBackbone(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            {BACKBONES.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Accelerator">
          <select
            value={accelerator}
            onChange={(e) => setAccelerator(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="auto">Auto</option>
            <option value="gpu">GPU (CUDA)</option>
            <option value="cpu">CPU</option>
          </select>
        </Field>

        <Field label="Number of classes">
          <input
            type="number"
            min={2}
            max={50}
            value={nClasses}
            onChange={(e) => setNClasses(parseInt(e.target.value, 10) || 2)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
        <Field label="Max epochs">
          <input
            type="number"
            min={1}
            max={200}
            value={maxEpochs}
            onChange={(e) => setMaxEpochs(parseInt(e.target.value, 10) || 1)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
        <Field label="Batch size">
          <input
            type="number"
            min={1}
            max={64}
            value={batchSize}
            onChange={(e) => setBatchSize(parseInt(e.target.value, 10) || 1)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
        <Field label="Learning rate">
          <input
            type="number"
            step={1e-5}
            min={1e-6}
            max={1e-1}
            value={learningRate}
            onChange={(e) => setLearningRate(parseFloat(e.target.value) || 1e-4)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
          />
        </Field>
      </div>

      <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-fg-muted">
            Training scene + mask pairs ({pairs.length})
          </span>
          <button
            onClick={addPair}
            className="px-2.5 py-1 text-xs bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded"
          >
            Add pair…
          </button>
        </div>
        {pairs.length === 0 && (
          <p className="text-xs text-fg-muted">
            No pairs yet.  Each pair is a scene raster + a single-band mask
            where pixel values are class ids (0 = background / nodata).
          </p>
        )}
        <ul className="space-y-1 max-h-40 overflow-auto">
          {pairs.map((p, i) => (
            <li
              key={i}
              className="flex items-center justify-between gap-2 text-xs font-mono"
            >
              <span className="truncate flex-1" title={`${p.raster}  ↔  ${p.mask}`}>
                {basename(p.raster)} ↔ {basename(p.mask)}
              </span>
              <button
                onClick={() => removePair(i)}
                className="text-fg-muted hover:text-danger"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      </div>

      <Field label="Output directory (checkpoint + ONNX)">
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
          {busy ? "Fine-tuning…" : "Fine-tune"}
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}

      <JobProgress
        jobId={jobId}
        onComplete={(r) => {
          setBusy(false);
          setResult(r as FoundationResult);
        }}
        onFailed={(e) => {
          setBusy(false);
          setErr(e);
        }}
      />

      {result && (
        <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md p-4 text-sm space-y-1">
          {result.checkpoint_path && (
            <p className="text-fg-muted text-xs font-mono break-all">
              checkpoint: {result.checkpoint_path}
            </p>
          )}
          {result.onnx_path && (
            <p className="text-fg-muted text-xs font-mono break-all">
              ONNX: {result.onnx_path}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function basename(p: string): string {
  const m = p.match(/[^\\/]+$/);
  return m ? m[0] : p;
}

interface FieldProps {
  label: string;
  children: React.ReactNode;
}
function Field({ label, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-muted mt-2">
      {label}
      {children}
    </label>
  );
}
