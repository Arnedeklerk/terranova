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
  // Training-vector fetch state (separate from the main classify job
  // so the user can fetch a training set without overwriting the
  // classify run's progress display).
  const [trainingJobId, setTrainingJobId] = useState<string | null>(null);
  const [findingTraining, setFindingTraining] = useState(false);

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

  /**
   * Browse for a training vector file on disk without having to load it
   * as a QGIS layer first.  The picked path is added to the dropdown
   * with a "(file)" prefix so the user can see it's a one-shot pick,
   * and selected automatically.  Fields refresh via the existing
   * useEffect on vectorSrc.
   */
  const pickVectorFile = async () => {
    const r = await invoke<{ path: string }>("dialog.open_file", {
      title: "Pick a training vector file",
      filter:
        "Vector files (*.gpkg *.shp *.geojson *.json *.kml *.gpx);;All files (*.*)",
    });
    if (!r.ok || !r.result?.path) return;
    selectAsVector(r.result.path);
  };

  /** Add a freshly-discovered file path to the dropdown and select it. */
  const selectAsVector = (path: string) => {
    const name = path.split(/[/\\]/).pop() || path;
    setVectors((prev) =>
      prev.some((v) => v.source === path)
        ? prev
        : [...prev, { name: `(file) ${name}`, source: path }],
    );
    setVectorSrc(path);
  };

  /**
   * Kick off a server-side training-data fetch.  Both buttons funnel
   * through here; they only differ in which bridge action runs.
   *
   * - OSM (`training.from_osm`) pulls landuse / natural polygons from
   *   Overpass for the raster's WGS84 extent.
   * - WorldCover (`training.from_worldcover`) samples stratified
   *   random points from ESA WorldCover (10 m global LC) for the
   *   same extent via Planetary Computer's STAC.
   *
   * The QgsTask emits the usual task.progress/complete/failed events,
   * which our dedicated <JobProgress /> below listens for.  On
   * completion the result.output_path is auto-selected as the
   * training vector.
   */
  const findTraining = async (
    action: "training.from_osm" | "training.from_worldcover",
  ) => {
    if (!rasterSrc) {
      setErr("Pick an input raster first — its extent defines the search AOI.");
      return;
    }
    setErr(null);
    setFindingTraining(true);
    setTrainingJobId(null);
    const r = await invoke<{ job_id: string }>(action, {
      raster_path: rasterSrc,
    });
    if (r.ok && r.result?.job_id) {
      setTrainingJobId(r.result.job_id);
    } else {
      setFindingTraining(false);
      setErr(r.error ?? `${action} failed`);
    }
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

        <Field
          label="Training vector (polygons / points)"
          hint="Pick a loaded layer, Browse to a file on disk, or fetch one from the web for the raster's extent."
        >
          <div className="flex gap-2">
            <select
              value={vectorSrc}
              onChange={(e) => setVectorSrc(e.target.value)}
              className="flex-1 bg-bg-1 border border-bg-2 rounded px-2 py-1"
            >
              <option value="">— pick a vector layer —</option>
              {vectors.map((l) => (
                <option key={l.source} value={l.source}>
                  {l.name}
                </option>
              ))}
            </select>
            <button
              onClick={pickVectorFile}
              className="px-3 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm whitespace-nowrap"
              title="Pick a vector file from disk; no need to load it as a layer first"
            >
              Browse…
            </button>
          </div>
          {/* Web-sourced training set. Both buttons require an input
              raster to be picked first (the raster's extent defines the
              AOI we query against).  Disabled while a fetch is already
              running so the user can't double-tap. */}
          <div className="flex flex-wrap gap-2 mt-1.5 items-center">
            <span className="text-xs text-fg-muted/70">or fetch for the raster's extent:</span>
            <button
              onClick={() => findTraining("training.from_osm")}
              disabled={findingTraining || !rasterSrc}
              className="px-2.5 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              title="Fetch OpenStreetMap landuse / natural polygons via Overpass. Real polygons you can QA before training; coverage varies by region."
            >
              From OSM ↓
            </button>
            <button
              onClick={() => findTraining("training.from_worldcover")}
              disabled={findingTraining || !rasterSrc}
              className="px-2.5 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-xs disabled:opacity-50 disabled:cursor-not-allowed"
              title="Sample stratified random points from ESA WorldCover 10m global land cover. 11 classes, global coverage; points only."
            >
              From WorldCover ↓
            </button>
          </div>
        </Field>

        {/* Progress / completion for the training-data fetch.  Separate
            from the main classify-run JobProgress so finishing a fetch
            doesn't get confused with finishing a classification. */}
        <JobProgress
          jobId={trainingJobId}
          onComplete={(result) => {
            setFindingTraining(false);
            const r = result as { output_path?: string; feature_count?: number } | null;
            if (r?.output_path) selectAsVector(r.output_path);
          }}
          onFailed={(e) => {
            setFindingTraining(false);
            setErr(e);
          }}
        />

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
