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
  output_xlsx?: string | null;
  overall_accuracy: number;
  kappa: number;
  n_samples: number;
}

type SamplingStrategy = "random" | "stratified" | "equalized_stratified";

const STRATEGY_LABELS: Record<SamplingStrategy, string> = {
  random: "Random",
  stratified: "Stratified random (proportional)",
  equalized_stratified: "Equalized stratified random",
};
const STRATEGY_HINTS: Record<SamplingStrategy, string> = {
  random:
    "Uniformly random points across all valid pixels.  Easy to reason about; large classes dominate the sample, rare classes can be missed entirely.",
  stratified:
    "Points per class are proportional to that class's pixel count, with a floor so rare classes still get tested.  Standard Olofsson-style design for OA estimation.",
  equalized_stratified:
    "Same N points per class regardless of class size.  Best for evaluating rare classes — gives every class equal evidence in the confusion matrix.",
};

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

  // Excel output toggle (default ON — most users want it).
  const [emitXlsx, setEmitXlsx] = useState(true);
  // Random-point generator state.
  const [strategy, setStrategy] = useState<SamplingStrategy>("stratified");
  const [nTotal, setNTotal] = useState(300);
  const [pointsPerClass, setPointsPerClass] = useState(30);
  const [generating, setGenerating] = useState(false);
  const [genMsg, setGenMsg] = useState<string | null>(null);

  // Labelling-mode state.  Driven by accuracy.label.start which returns
  // every point's coords + predicted/truth + the available class codes.
  // The CRS comes back too so accuracy.label.pan_to can project to the
  // canvas CRS for the marker.
  interface LabelFeature {
    fid: number;
    x: number;
    y: number;
    predicted: number;
    truth: number;
    note: string;
  }
  const [labelFile, setLabelFile] = useState<string>("");
  const [labelFeatures, setLabelFeatures] = useState<LabelFeature[]>([]);
  const [labelClasses, setLabelClasses] = useState<number[]>([]);
  const [labelCrs, setLabelCrs] = useState<string>("EPSG:4326");
  const [labelIdx, setLabelIdx] = useState<number>(0);
  const [labelActive, setLabelActive] = useState<boolean>(false);
  const [labelNote, setLabelNote] = useState<string>("");

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

  // Clear the canvas highlight marker when the panel unmounts (user
  // navigates away).  Otherwise the red cross hangs around forever.
  useEffect(() => {
    return () => {
      void invoke("accuracy.label.clear");
    };
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
      default: "terranova_accuracy.pdf",
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

    // Auto-derive an .xlsx path next to the PDF when the user opted in.
    const xlsxPath = emitXlsx
      ? outputPdf.replace(/\.pdf$/i, "") + ".xlsx"
      : null;

    const r = await invoke<{ job_id: string }>("accuracy.run", {
      raster_path: rasterSrc,
      vector_path: vectorSrc,
      class_field: classField,
      output_pdf: outputPdf,
      output_xlsx: xlsxPath,
    });
    if (r.ok && r.result?.job_id) {
      setJobId(r.result.job_id);
    } else {
      setBusy(false);
      setErr(r.error ?? "accuracy.run failed");
    }
  };

  /**
   * Sample validation points from a classified raster.  The classified
   * raster is whatever the user has picked above — the point file gets
   * dropped in and loaded as a layer, ready to edit `truth` on each
   * feature.  Synchronous in the backend (sub-second for typical
   * raster sizes), no QgsTask plumbing needed.
   */
  const generatePoints = async () => {
    if (!rasterSrc) {
      setErr("Pick a classified raster first.");
      return;
    }
    const r = await invoke<{ path: string }>("dialog.save_file", {
      default: `validation_points_${strategy}.gpkg`,
      title: "Save validation points",
      filter: "GeoPackage (*.gpkg)",
    });
    if (!r.ok || !r.result?.path) return;

    setErr(null);
    setGenerating(true);
    setGenMsg(null);
    const out = await invoke<{
      n_points: number;
      output_path: string;
      classes_sampled: number[];
    }>("accuracy.generate_points", {
      raster_path: rasterSrc,
      out_path: r.result.path,
      strategy,
      n_total: nTotal,
      points_per_class: pointsPerClass,
    });
    setGenerating(false);
    if (!out.ok || !out.result) {
      setErr(out.error ?? "accuracy.generate_points failed");
      return;
    }
    setGenMsg(
      `Wrote ${out.result.n_points} points across ${out.result.classes_sampled.length} classes — ` +
        "start the point-by-point labelling below, or edit truth manually in QGIS.",
    );
    // Auto-fill the labelling file picker with the freshly-generated
    // path so the user can jump straight into labelling without finding
    // the file again.
    setLabelFile(out.result.output_path);
  };

  // ----------------- labelling mode --------------------------------------
  const pickLabelFile = async () => {
    const r = await invoke<{ path: string }>("dialog.open_file", {
      title: "Pick a validation-points GeoPackage",
      filter: "GeoPackage (*.gpkg);;All files (*.*)",
    });
    if (r.ok && r.result?.path) setLabelFile(r.result.path);
  };

  const startLabelling = async () => {
    if (!labelFile) {
      setErr("Pick a validation-points file first (or generate one above).");
      return;
    }
    setErr(null);
    const r = await invoke<{
      features: LabelFeature[];
      classes: number[];
      src_crs: string;
    }>("accuracy.label.start", {
      path: labelFile,
      raster_path: rasterSrc || null,
    });
    if (!r.ok || !r.result) {
      setErr(r.error ?? "could not load validation points");
      return;
    }
    setLabelFeatures(r.result.features);
    setLabelClasses(r.result.classes);
    setLabelCrs(r.result.src_crs);
    // Jump to the first unlabelled point (truth == 0); fall back to 0
    // if every point already has a label (resume / re-check).
    const first = r.result.features.findIndex((f) => !f.truth);
    const idx = first >= 0 ? first : 0;
    setLabelIdx(idx);
    setLabelActive(true);
    setLabelNote(r.result.features[idx]?.note ?? "");
    panToIdx(idx, r.result.features, r.result.src_crs);
  };

  /**
   * Pan the canvas to the point at `i` and refresh the highlight marker.
   * Accepts the features + crs as args so it can be called during
   * startLabelling before the state setters have settled.
   */
  const panToIdx = (
    i: number,
    feats: LabelFeature[] = labelFeatures,
    crs: string = labelCrs,
  ) => {
    const f = feats[i];
    if (!f) return;
    void invoke("accuracy.label.pan_to", { x: f.x, y: f.y, crs });
  };

  /** Persist truth for the current point and step to a delta (+1, -1). */
  const labelStep = async (delta: number, picked: number | null) => {
    const cur = labelFeatures[labelIdx];
    if (!cur) return;
    if (picked !== null) {
      const r = await invoke("accuracy.label.update", {
        path: labelFile,
        fid: cur.fid,
        truth: picked,
        note: labelNote,
      });
      if (!r.ok) {
        setErr(r.error ?? "could not write truth");
        return;
      }
      // Reflect the change locally so the progress counter and the
      // 'first unlabelled' resume logic stay accurate.
      setLabelFeatures((prev) =>
        prev.map((p, i) =>
          i === labelIdx ? { ...p, truth: picked, note: labelNote } : p,
        ),
      );
    }
    const next = Math.max(0, Math.min(labelFeatures.length - 1, labelIdx + delta));
    if (next === labelIdx && delta !== 0) return;
    setLabelIdx(next);
    setLabelNote(labelFeatures[next]?.note ?? "");
    panToIdx(next);
  };

  const stopLabelling = () => {
    setLabelActive(false);
    void invoke("accuracy.label.clear");
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
        renders a one-page PDF (and optionally an Excel workbook).
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
          <label className="flex items-center gap-2 mt-1.5 text-xs text-fg-muted cursor-pointer">
            <input
              type="checkbox"
              checked={emitXlsx}
              onChange={(e) => setEmitXlsx(e.target.checked)}
            />
            Also export an Excel workbook (same path, .xlsx suffix)
          </label>
        </Field>
      </div>

      {/* Generate validation points -------------------------------------- */}
      <div className="mt-5 bg-bg-1 border border-bg-2 rounded-md p-3">
        <h3 className="text-sm font-semibold mb-1">
          Generate validation points
        </h3>
        <p className="text-xs text-fg-muted mb-3">
          Sample points from the classified raster to use as a validation
          vector. The output .gpkg has a <code>predicted</code> column already
          filled in from the raster — edit the <code>truth</code> column in
          QGIS, then point this panel at it.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Strategy" hint={STRATEGY_HINTS[strategy]}>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as SamplingStrategy)}
              className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
            >
              {(Object.keys(STRATEGY_LABELS) as SamplingStrategy[]).map(
                (k) => (
                  <option key={k} value={k}>
                    {STRATEGY_LABELS[k]}
                  </option>
                ),
              )}
            </select>
          </Field>
          {strategy === "equalized_stratified" ? (
            <Field label="Points per class">
              <input
                type="number"
                value={pointsPerClass}
                min={2}
                max={500}
                onChange={(e) =>
                  setPointsPerClass(parseInt(e.target.value, 10) || 0)
                }
                className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
              />
            </Field>
          ) : (
            <Field label="Total points">
              <input
                type="number"
                value={nTotal}
                min={10}
                max={5000}
                step={50}
                onChange={(e) => setNTotal(parseInt(e.target.value, 10) || 0)}
                className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono"
              />
            </Field>
          )}
        </div>
        <div className="flex gap-2 mt-3 items-center">
          <button
            onClick={generatePoints}
            disabled={!rasterSrc || generating}
            className="px-3 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded text-xs disabled:opacity-50"
          >
            {generating ? "Sampling…" : "Generate points"}
          </button>
          {genMsg && <span className="text-xs text-fg-muted">{genMsg}</span>}
        </div>
      </div>

      {/* Label points (interactive step-through) ------------------------- */}
      <div className="mt-5 bg-bg-1 border border-bg-2 rounded-md p-3">
        <h3 className="text-sm font-semibold mb-1">Label points</h3>
        <p className="text-xs text-fg-muted mb-3">
          Step through each validation point — the QGIS canvas pans to it,
          a red cross marks it, and you pick the actual ground-truth class.
          Saves to the file after every pick, so you can stop and resume.
        </p>

        {!labelActive && (
          <>
            <Field label="Validation points file">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={labelFile}
                  placeholder="(pick a .gpkg from disk, or generate one above)"
                  onChange={(e) => setLabelFile(e.target.value)}
                  className="flex-1 bg-bg-1 border border-bg-2 rounded px-2 py-1 font-mono text-xs"
                />
                <button
                  onClick={pickLabelFile}
                  className="px-3 py-1 bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded text-sm"
                >
                  Browse…
                </button>
              </div>
            </Field>
            <button
              onClick={startLabelling}
              disabled={!labelFile}
              className="mt-3 px-3 py-1 bg-accent text-white rounded text-xs disabled:opacity-50"
            >
              Start labelling
            </button>
          </>
        )}

        {labelActive && labelFeatures[labelIdx] && (
          <LabellingPad
            features={labelFeatures}
            idx={labelIdx}
            classes={labelClasses}
            note={labelNote}
            setNote={setLabelNote}
            onStep={(d, picked) => labelStep(d, picked)}
            onExit={stopLabelling}
          />
        )}
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
          {result.output_xlsx && (
            <p className="text-fg-muted text-xs mt-1 font-mono break-all">
              {result.output_xlsx}
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
  // Same rule as the Classify panel's Field: short hints inline next to
  // the label, long ones (>=80 chars) wrap as a block below the input.
  const longHint = !!hint && hint.length >= 80;
  return (
    <label className="flex flex-col gap-1 text-xs text-fg-muted">
      <span>
        {label}
        {hint && !longHint && (
          <span className="ml-2 text-fg-muted/70">— {hint}</span>
        )}
      </span>
      {children}
      {hint && longHint && (
        <span className="text-fg-muted/70 leading-snug mt-0.5">{hint}</span>
      )}
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

/* -------------------------------------------------------------------- */
/* Point-by-point labelling pad                                         */
/* -------------------------------------------------------------------- */

interface LabellingPadProps {
  features: Array<{ fid: number; predicted: number; truth: number }>;
  idx: number;
  classes: number[];
  note: string;
  setNote(s: string): void;
  /** delta is +1/-1/0 ; picked is the chosen class code, or null to skip. */
  onStep(delta: number, picked: number | null): void;
  onExit(): void;
}

function LabellingPad({
  features,
  idx,
  classes,
  note,
  setNote,
  onStep,
  onExit,
}: LabellingPadProps) {
  const cur = features[idx];
  const labelled = features.filter((f) => f.truth).length;
  const pct = features.length
    ? Math.round((labelled / features.length) * 100)
    : 0;

  // Pre-fill the "true class" picker with the existing truth (resume)
  // or the predicted class (first pass) so a confirmed-correct pixel is
  // one Enter away from being labelled.
  const initialPick = cur.truth || cur.predicted;
  const [picked, setPicked] = useState<number>(initialPick);
  // Re-sync when idx changes — useState only initialises once.
  useEffect(() => {
    setPicked(cur.truth || cur.predicted);
  }, [idx, cur.truth, cur.predicted]);

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-sm">
          <span className="font-semibold">
            Point {idx + 1} / {features.length}
          </span>
          <span className="text-fg-muted ml-2">
            · {labelled} labelled ({pct}%)
          </span>
        </div>
        <button
          onClick={onExit}
          className="text-xs text-fg-muted hover:text-fg"
          title="Stop labelling.  Progress is already saved to the file."
        >
          Exit ✕
        </button>
      </div>

      <div className="h-1 bg-bg-2 rounded overflow-hidden mb-3">
        <div className="h-full bg-accent transition-all" style={{ width: `${pct}%` }} />
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-fg-muted">Predicted class</div>
          <div className="font-mono text-lg font-semibold">{cur.predicted}</div>
        </div>
        <div>
          <div className="text-fg-muted">Existing truth</div>
          <div className="font-mono text-lg font-semibold">
            {cur.truth || <span className="text-fg-muted/60">—</span>}
          </div>
        </div>
      </div>

      <div className="mt-3">
        <div className="text-xs text-fg-muted mb-1">True class</div>
        {/* If <=10 classes, render as a row of clickable chips.  More
            classes → fall back to a dropdown.  Chips are faster for the
            common case. */}
        {classes.length <= 10 ? (
          <div className="flex flex-wrap gap-1.5">
            {classes.map((c) => {
              const active = c === picked;
              return (
                <button
                  key={c}
                  onClick={() => setPicked(c)}
                  className={
                    "px-2.5 py-1 rounded text-xs border " +
                    (active
                      ? "bg-accent text-white border-accent"
                      : "bg-bg-2 hover:bg-bg-0 border-bg-2")
                  }
                >
                  {c}
                </button>
              );
            })}
          </div>
        ) : (
          <select
            value={picked}
            onChange={(e) => setPicked(parseInt(e.target.value, 10) || 0)}
            className="w-full bg-bg-1 border border-bg-2 rounded px-2 py-1"
          >
            {classes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </div>

      <label className="flex flex-col gap-1 text-xs text-fg-muted mt-3">
        Note (optional)
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="e.g. 'cloud shadow', 'mixed pixel', etc."
          className="bg-bg-1 border border-bg-2 rounded px-2 py-1"
        />
      </label>

      <div className="flex gap-2 mt-4">
        <button
          onClick={() => onStep(-1, null)}
          disabled={idx === 0}
          className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded text-xs disabled:opacity-40"
        >
          ← Previous
        </button>
        <button
          onClick={() => onStep(+1, null)}
          disabled={idx >= features.length - 1}
          className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded text-xs disabled:opacity-40"
          title="Skip without saving"
        >
          Skip →
        </button>
        <button
          onClick={() => onStep(+1, picked)}
          disabled={idx >= features.length - 1}
          className="ml-auto px-3 py-1 bg-accent text-white rounded text-xs disabled:opacity-50"
        >
          Save & next →
        </button>
        <button
          onClick={() => onStep(0, picked)}
          className="px-2.5 py-1 bg-bg-2 hover:bg-bg-0 border border-bg-2 rounded text-xs"
          title="Save without advancing (useful on the last point)"
        >
          Save
        </button>
      </div>
    </div>
  );
}
