import { useEffect, useState } from "react";
import { invoke } from "../bridge";
import { JobProgress } from "./JobProgress";

/**
 * Classify scene — Phase 1, parity with the Qt dialog.
 *
 * Picks: input raster (from currently-loaded raster layers), training vector
 * (from loaded vector layers) and its class field, classifier kind, ensemble
 * size, CV folds, output path.  Kicks off classify.run on Python, then
 * streams progress + completion via the JobProgress component.
 */

interface LayerInfo {
  name: string;
  source: string;
}

const CLASSIFIERS: Array<{ label: string; value: string }> = [
  { label: "Random Forest", value: "random_forest" },
  { label: "Extra Trees", value: "extra_trees" },
  { label: "Gradient Boosting", value: "gradient_boosting" },
  { label: "LightGBM", value: "lightgbm" },
  { label: "XGBoost", value: "xgboost" },
  { label: "K-Nearest Neighbours", value: "knn" },
  { label: "Logistic Regression", value: "logistic_regression" },
  { label: "Multi-layer Perceptron", value: "mlp" },
];

export function Classify() {
  const [rasters, setRasters] = useState<LayerInfo[]>([]);
  const [vectors, setVectors] = useState<LayerInfo[]>([]);
  const [fields, setFields] = useState<string[]>([]);

  const [rasterSrc, setRasterSrc] = useState<string>("");
  const [vectorSrc, setVectorSrc] = useState<string>("");
  const [classField, setClassField] = useState<string>("");
  const [classifier, setClassifier] = useState("random_forest");
  const [nEstimators, setNEstimators] = useState(300);
  const [cvFolds, setCvFolds] = useState(5);
  const [outputPath, setOutputPath] = useState<string>("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Initial + refresh of layer lists.
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

  // Refresh field list when the vector layer changes.
  useEffect(() => {
    if (!vectorSrc) {
      setFields([]);
      return;
    }
    invoke<{ fields: string[] }>("layers.fields", { path: vectorSrc }).then((r) => {
      if (r.ok && r.result) {
        const fs = r.result.fields;
        setFields(fs);
        // Best-guess default.
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
      default: "terranova_classification.tif",
      title: "Save classified COG",
      filter: "Cloud-Optimised GeoTIFF (*.tif)",
    });
    if (r.ok && r.result?.path) setOutputPath(r.result.path);
  };

  const run = async () => {
    if (!rasterSrc || !vectorSrc || !classField || !outputPath) {
      setErr("Pick raster, vector, class field, and output path.");
      return;
    }
    setErr(null);
    setBusy(true);
    setJobId(null);
    const r = await invoke<{ job_id: string }>("classify.run", {
      raster_path: rasterSrc,
      vector_path: vectorSrc,
      class_field: classField,
      classifier,
      n_estimators: nEstimators,
      cv_folds: cvFolds,
      output_path: outputPath,
    });
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "classify.run failed");
    }
  };

  return (
    <section className="max-w-2xl">
      <div className="flex items-baseline justify-between mb-3">
        <h2 className="text-lg font-semibold">Classify scene</h2>
        <button
          onClick={refreshLayers}
          className="text-xs text-fg-muted hover:text-fg"
        >
          Refresh layers ↻
        </button>
      </div>
      <p className="text-fg-muted text-sm mb-4">
        Trains a classifier on every pixel covered by your training polygons
        and applies it to the input raster.  Open the Log Messages panel for
        training-set diagnostics as the task runs.
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

        <Field label="Training vector (polygons / points)">
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

        <Field label="Class field on the vector layer">
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

        <div className="grid grid-cols-2 gap-3">
          <Field label="Classifier">
            <select
              value={classifier}
              onChange={(e) => setClassifier(e.target.value)}
              className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
            >
              {CLASSIFIERS.map((c) => (
                <option key={c.value} value={c.value}>
                  {c.label}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Trees / boosting rounds"
            hint="Ensemble size — not the training-sample count.  100–500 is the sweet spot."
          >
            <input
              type="number"
              value={nEstimators}
              min={10}
              max={2000}
              step={50}
              onChange={(e) => setNEstimators(parseInt(e.target.value, 10) || 0)}
              className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
            />
          </Field>

          <Field label="Cross-validation folds">
            <input
              type="number"
              value={cvFolds}
              min={2}
              max={10}
              onChange={(e) => setCvFolds(parseInt(e.target.value, 10) || 0)}
              className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
            />
          </Field>
        </div>

        <Field label="Output COG">
          <div className="flex gap-2">
            <input
              type="text"
              value={outputPath}
              placeholder="(pick a path…)"
              onChange={(e) => setOutputPath(e.target.value)}
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
          {busy ? "Running…" : "Train + classify"}
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
  hint?: string;
  children: React.ReactNode;
}
function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-muted">
      <span>
        {label}
        {hint && <span className="ml-2 text-fg-muted/70">— {hint}</span>}
      </span>
      {children}
    </label>
  );
}
