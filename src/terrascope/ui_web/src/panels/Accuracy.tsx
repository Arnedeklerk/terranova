import { useEffect, useState } from "react";
import { invoke } from "../bridge";
import { JobProgress } from "./JobProgress";

/**
 * Accuracy report — Phase 1, parity with the Qt dialog.
 *
 * Compares a classified raster to a labelled validation vector, computes
 * OA / kappa / per-class / F1, and writes a one-page PDF report.
 */

interface LayerInfo {
  name: string;
  source: string;
}

interface AccuracyResult {
  output_path: string;
  overall_accuracy: number;
  kappa: number;
  n_samples: number;
}

export function Accuracy() {
  const [rasters, setRasters] = useState<LayerInfo[]>([]);
  const [vectors, setVectors] = useState<LayerInfo[]>([]);
  const [fields, setFields] = useState<string[]>([]);

  const [rasterSrc, setRasterSrc] = useState("");
  const [vectorSrc, setVectorSrc] = useState("");
  const [classField, setClassField] = useState("");
  const [outputPdf, setOutputPdf] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<AccuracyResult | null>(null);

  const refreshLayers = async () => {
    const [r, v] = await Promise.all([
      invoke<{ layers: LayerInfo[] }>("layers.list_rasters"),
      invoke<{ layers: LayerInfo[] }>("layers.list_vectors"),
    ]);
    if (r.ok && r.result) setRasters(r.result.layers);
    if (v.ok && v.result) setVectors(v.result.layers);
  };
  useEffect(() => {
    refreshLayers();
  }, []);

  useEffect(() => {
    if (!vectorSrc) {
      setFields([]);
      return;
    }
    invoke<{ fields: string[] }>("layers.fields", { path: vectorSrc }).then((r) => {
      if (r.ok && r.result) {
        const fs = r.result.fields;
        setFields(fs);
        const guess = fs.find((n) =>
          ["class", "Class", "CLASS", "label", "category"].includes(n),
        );
        if (guess) setClassField(guess);
        else if (fs.length > 0) setClassField(fs[0]);
      }
    });
  }, [vectorSrc]);

  const pickOutput = async () => {
    const r = await invoke<{ path: string }>("dialog.save_file", {
      default: "terrascope_accuracy.pdf",
      title: "Save accuracy report",
      filter: "PDF (*.pdf)",
    });
    if (r.ok && r.result?.path) setOutputPdf(r.result.path);
  };

  const run = async () => {
    if (!rasterSrc || !vectorSrc || !classField || !outputPdf) {
      setErr("Pick raster, vector, class field, and PDF path.");
      return;
    }
    setErr(null);
    setResult(null);
    setBusy(true);
    const r = await invoke<{ job_id: string }>("accuracy.run", {
      raster_path: rasterSrc,
      vector_path: vectorSrc,
      class_field: classField,
      output_pdf: outputPdf,
    });
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "accuracy.run failed");
    }
  };

  return (
    <section className="max-w-2xl">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">Accuracy report</h2>
        <button
          onClick={refreshLayers}
          className="text-xs text-fg-muted hover:text-fg"
        >
          Refresh layers ↻
        </button>
      </div>
      <p className="text-fg-muted text-sm mb-4">
        Samples the classified raster at every pixel covered by a validation
        vector, computes confusion matrix / OA / κ / per-class metrics, and
        renders a one-page PDF.
      </p>

      <div className="grid grid-cols-1 gap-3">
        <Field label="Classified raster">
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

        <Field label="Validation vector (held-out polygons / points)">
          <select
            value={vectorSrc}
            onChange={(e) => setVectorSrc(e.target.value)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            <option value="">— pick a vector layer —</option>
            {vectors.map((l) => (
              <option key={l.source} value={l.source}>
                {l.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Class field on the validation layer">
          <select
            value={classField}
            onChange={(e) => setClassField(e.target.value)}
            disabled={!fields.length}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 disabled:opacity-50"
          >
            {!fields.length && <option value="">— pick a vector first —</option>}
            {fields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Output PDF">
          <div className="flex gap-2">
            <input
              type="text"
              value={outputPdf}
              placeholder="(pick a path…)"
              onChange={(e) => setOutputPdf(e.target.value)}
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
          {busy ? "Running…" : "Generate report"}
        </button>
      </div>

      {err && <p className="text-danger text-sm mt-3">{err}</p>}

      <JobProgress
        jobId={jobId}
        onComplete={(r) => {
          setBusy(false);
          setResult(r as AccuracyResult);
        }}
        onFailed={(e) => {
          setBusy(false);
          setErr(e);
        }}
      />

      {result && (
        <div className="mt-4 bg-bg-1 border border-bg-2 rounded-md p-4 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Overall accuracy" value={result.overall_accuracy.toFixed(3)} />
            <Stat label="Kappa (κ)" value={result.kappa.toFixed(3)} />
            <Stat label="N samples" value={String(result.n_samples)} />
          </div>
          <p className="text-fg-muted text-xs mt-3 font-mono break-all">
            {result.output_path}
          </p>
        </div>
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

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-fg-muted">{label}</div>
      <div className="text-lg font-semibold text-fg font-mono">{value}</div>
    </div>
  );
}
