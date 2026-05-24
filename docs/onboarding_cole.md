# Cole's first run — TerraScope

Step-by-step from "freshly cloned" to "exercising every dialog". Targeted at
your install:

- Repo: `C:\Users\coleb\OneDrive\Documents\GitHub\terrascope`
- QGIS: `C:\Program Files\QGIS 3.40.8` (LTR — perfect)
- Profile dir QGIS will look in: `C:\Users\coleb\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\terrascope`

The instructions assume you're on Windows with PowerShell. Where Bash-style
syntax differs I call it out.

---

## 0. Prereqs

1. **QGIS 3.40.8** — already installed.
2. **Node.js 20+** — needed once, to build the React panel embedded in the
   plugin dock. Download from <https://nodejs.org/> (LTS is fine).
3. **Git** — already installed (you cloned the repo).
4. **OSGeo4W Shell** — comes with QGIS. Start menu → "QGIS 3.40.8" group →
   "OSGeo4W Shell". This shell has QGIS's bundled Python on PATH. Use this
   shell for every `python -m pip install` step below — *not* a regular
   PowerShell or cmd.

---

## 1. Build the React panel (one-time)

The dock has an embedded web panel — we ship pre-built artefacts in the
release `.zip` but for a from-source clone you build them once.

Open **PowerShell** (regular, not OSGeo4W) and:

```powershell
cd "C:\Users\coleb\OneDrive\Documents\GitHub\terrascope\src\terrascope\ui_web"
npm install
npm run build
```

You should see `vite v5.x building for production... ✓ 105 modules
transformed... built in <2s`. After this the directory `dist/` exists with
the bundled HTML/JS/CSS.

If `npm install` is slow (~2-3 minutes the first time): that's normal,
Vite + React pull a few hundred packages.

---

## 2. Install Python deps into QGIS's Python

Open the **OSGeo4W Shell** (not PowerShell). Then:

```cmd
python -m pip install -e "C:/Users/coleb/OneDrive/Documents/GitHub/terrascope[timeseries]"
```

One line, no `--no-deps`. This:

- Installs the `terrascope` package editable (you can edit code and it picks
  up changes without reinstalling).
- Pulls every base dep from `pyproject.toml` — pystac-client,
  planetary-computer, odc-stac, rio-cogeo, scikit-learn, reportlab,
  matplotlib, rioxarray, spyndex, pyproj, fiona, etc.
- Adds the `[timeseries]` extras: zarr, dask, imageio-ffmpeg.

If you hit a **PROJ database error** (`DATABASE.LAYOUT.VERSION.MINOR = 2
whereas a number >= 4 is expected`) at any later step:

```cmd
python -m pip install --force-reinstall --no-deps pyproj
```

Optional extras (skip unless you specifically want them):

- For Phase 2 SAM: `python -m pip install segment-geospatial`
- For Phase 2 foundation models: `python -m pip install torch terratorch lightning` — heavy (multi-GB), only worth it if you have a CUDA GPU.

---

## 3. Deploy the plugin into your QGIS profile

Back in **regular PowerShell**:

```powershell
$src  = "C:\Users\coleb\OneDrive\Documents\GitHub\terrascope"
$dest = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\terrascope"

# Wipe any previous install
Remove-Item -Recurse -Force $dest -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null

# Copy the source tree + metadata
Copy-Item -Recurse "$src\src\terrascope" $dest
Copy-Item        "$src\metadata.txt"     "$dest\metadata.txt" -Force
```

Note the path uses `QGIS3` not `QGIS4` (because you're on the 3.40 LTR).

---

## 4. Enable the plugin

1. Launch QGIS.
2. **Plugins → Manage and Install Plugins → Installed**.
3. Tick **TerraScope**.

If it doesn't show:

- Settings tab in the same dialog → tick **"Show also experimental
  plugins"** (the metadata flag has been flipped to False but cached state
  can stick).
- Restart QGIS.

If TerraScope still doesn't appear, open **Plugins → Python Console**
(`Ctrl+Alt+P`) and paste this one-liner:

```python
exec("import qgis.utils, terrascope; print('terrascope', terrascope.__version__, 'in available:', 'terrascope' in qgis.utils.available_plugins)")
```

Expected: `terrascope 0.1.0 in available: True`. If you get an import error
instead, paste me the traceback.

---

## 5. Sanity check — Processing Toolbox

`Ctrl+Alt+T` to open the Processing Toolbox. Expand the **TerraScope**
provider. You should see two groups:

- **Indices**: Compute NDVI, NDWI, NDMI, NBR, NDSI
- **Post-processing**: Majority filter, Sieve filter

That alone confirms the plugin loaded and the Processing provider
registered correctly. **Don't run anything yet** — we'll exercise them in
the test plan below.

---

# Test plan by phase

Each item below tells you what to click, what to expect, and which build
phase it belongs to (so you know whether you're testing my code or someone
else's).

## Phase 0 — Plugin lifecycle & scaffolding

**Owner**: Phase 0 work. The foundation.

### T0.1 — Toolbar dock opens

Click the **TerraScope icon** in the QGIS toolbar (the icon at the top of
the QGIS window, blue planet-ish glyph). The right-side dock opens with a
welcome screen showing four cards (Classify a scene, Detect change,
Download imagery, Segment with AI) plus tabs at the top.

**Expected**: dock loads, no errors in the **View → Panels → Log
Messages → TerraScope** tab.

**Phase**: 0. If this fails, the React panel isn't bundled (run `npm run
build` again) or QtWebEngine isn't available (unlikely on Windows).

### T0.2 — Command palette

Anywhere in QGIS press `Ctrl+K`. The palette overlay appears. Type "ping"
→ pick "Bridge: ping". The Log Messages panel should show a successful
round-trip through the QWebChannel bridge.

**Phase**: 0. Exercises the Python ↔ React message bus.

### T0.3 — Telemetry consent dialog

First time you open the dock, you should see a dialog "Help us improve
TerraScope?" with Yes / No options and an expandable "Show next outbound
payload" preview. **Pick No** unless you want to test the network round-trip.

**Phase**: 0. Exercises the privacy-policy-enforced six-field payload.

---

## Phase 1 — Catalogue search + classification + accuracy

**Owner**: Phase 1 work. The SCP-killer flow.

### T1.1 — Catalogue search (Planetary Computer)

**Raster → TerraScope → Catalogue search…**

1. Zoom QGIS to anywhere with land — Cambridge UK is easy (paste
   `52.205,0.119` into the bottom-bar coordinate box, hit Enter).
2. In the dialog, click **Use canvas extent**. The W/S/E/N fields fill
   from your current view.
3. Default date range (last 4 months) and 20% cloud cap are fine.
4. Click **Search**.

**Expected**: within 5-10 seconds, the results table populates with ~25
Sentinel-2 scenes — id, date, cloud %, platform.

**Phase**: 1. The search runs in a background `QgsTask` so QGIS stays
responsive. If you get an SSL error, your corporate proxy is in the way —
otherwise this should just work.

### T1.2 — Download a scene as COG

Same dialog. Pick a row with low cloud %. Click **Download selected as
COG…**. Pick a path on disk.

**Expected**: a few seconds later (depends on AOI size), a 4-band COG
(R/G/B/NIR @ 10 m) appears as a new layer in the project. The Log
Messages panel logs the path.

**Phase**: 1. Uses `odc-stac` to materialise a lazy xarray cube clipped to
your AOI.

### T1.3 — Classify the scene

You need a vector layer with training polygons + a class field. Two
options:

**Option A — quick & dirty**: digitise 10-20 polygons yourself. Layer →
Create Layer → New Shapefile. Set type=Polygon, add an integer field
called `class`. Use the digitising tools to draw polygons covering
distinct land covers (e.g. 1=water, 2=urban, 3=vegetation, 4=bare). Set
the class value as you draw each polygon.

**Option B**: import an existing labelled set you trust.

Then **Raster → TerraScope → Classify scene…**

1. Input raster: the COG you downloaded.
2. Training vector: your polygons.
3. Class field: `class` (or whatever you named it).
4. Classifier: leave as Random Forest.
5. Output path: pick somewhere.
6. **Train + classify**.

**Expected**: 30-90 seconds of work depending on raster size. Status
updates as it goes through "extracting samples", "training",
"applying". When done, a new classified raster appears in the project.
Class IDs in single-band uint8 GeoTIFF (COG).

**Phase**: 1. End-to-end `extract_training_samples → train → predict_to_cog`.

### T1.4 — Accuracy report (PDF)

For this you need a *separate* set of validation polygons (held out from
training). If you only have one set, just reuse it — the accuracy will
look unrealistically perfect, but the PDF will still render correctly.

**Raster → TerraScope → Accuracy report…**

1. Classified raster: the output from T1.3.
2. Validation vector: your held-out polygons.
3. Class field: `class`.
4. Output PDF: pick a path.
5. **Generate report**.

**Expected**: a one-page A4 PDF with confusion matrix heatmap, overall
accuracy, kappa, per-class user's & producer's accuracy. Crameri batlow
colormap (perceptually uniform, CVD-friendly).

**Phase**: 1. Exercises `core.accuracy.metrics.assess` +
`core.accuracy.report.render_pdf` (reportlab + matplotlib).

### T1.5 — Processing-toolbox NDVI

Quick standalone test if T1.3 is too much:

**Processing Toolbox → TerraScope → Indices → Compute NDVI**

Input: any multi-band raster (the COG from T1.2 works). Red band = 3,
NIR band = 4 (or 1 and 4 for some rasters). Run.

**Expected**: float32 GeoTIFF with NDVI in `[-1, 1]`, NaN where R+NIR == 0.

**Phase**: 0/1. Pure-numpy implementation tested with property-based
Hypothesis tests in CI.

### T1.6 — Other indices

Same flow as T1.5 but pick **NDWI / NDMI / NBR / NDSI** under Indices.
Band-pair semantics differ — read the help string at the bottom of each
dialog for which bands to assign.

**Phase**: 0/1.

### T1.7 — Sieve / majority filter (post-processing)

Take a classified raster (T1.3 output) → **Processing → TerraScope →
Post-processing → Sieve filter**. Set min component size to e.g. 8. Run.
You should see salt-and-pepper noise cleaned up.

**Phase**: 0/1. Pure-numpy port of GDAL's sieve.

### T1.8 — CDSE sign-in (optional)

If you have a Copernicus Data Space account: **Raster → TerraScope →
Sign in to CDSE…** → Start sign-in → browser opens with a 6-character
code → type the code → close browser → status flips to "Signed in".

**Expected**: a token cached locally for future CDSE searches.

**Phase**: 1. Skip if you don't have a CDSE account.

---

## Phase 2 — Foundation models + SAM

**Owner**: Phase 2. The "things SCP can't do" pitch.

### T2.1 — SAM segmentation (text prompt)

Requires `segment-geospatial` installed. Run in the OSGeo4W shell:

```cmd
python -m pip install segment-geospatial
```

Then in QGIS:

**Raster → TerraScope → Segment with SAM…**

1. Input raster: any raster (the T1.2 download works, or aerial imagery).
2. Model: SAM 2 base (smallest, fastest first time).
3. Mode: Text prompt.
4. Text prompt: `buildings` (or `agricultural fields`, `water bodies`).
5. Output: pick a .gpkg path.
6. **Segment**.

**Expected**: first run downloads model weights (~700 MB for SAM 2 base) —
takes a few minutes the first time. Then segmentation runs and writes a
GeoPackage of polygons that get added to the project.

**Phase**: 2. Wraps `segment-geospatial`'s LangSAM. Heavy first-time download.

### T2.2 — SAM segmentation (point prompts)

Same dialog, switch Mode to **Point prompts**. Click **Pick points on
map** — your cursor becomes a crosshair. Click foreground points on the
features you want segmented. Press Escape (or just click Segment in the
dialog) when done.

**Phase**: 2. Same backend, different prompt route.

### T2.3 — Fine-tune a foundation model

Only attempt this if you have a CUDA GPU. Otherwise it'll work on CPU
but take an hour+ per epoch.

**Raster → TerraScope → Fine-tune foundation model…**

You need paired scene + mask rasters. The mask is a single-band raster
where each pixel is the class id (0 = background/nodata). Mask must align
georeferentially with the scene.

Pick Prithvi-EO-2.0 300M, add at least one pair, pick an output
directory, hit Fine-tune.

**Expected**: model downloads on first run, then trains. End state: a
`best.ckpt` Lightning checkpoint + a `model.onnx` exported for fast
inference.

**Phase**: 2. Wraps TerraTorch. Heavy on disk, RAM, and VRAM.

---

## Phase 3 — Time-series + change detection

**Owner**: Phase 3. The "what changed over time" pitch.

### T3.1 — Build a time-series cube + run CuSum

**Raster → TerraScope → Time-series + change detection…**

1. **Use canvas extent** — keep it small (5×5 km) for a first test;
   bigger AOIs take longer.
2. History start: 3 years before today.
3. Monitoring start: 1 year before today.
4. End: today.
5. Endpoint: Planetary Computer.
6. Index: NDVI.
7. Method: **CuSum** (no extra deps, works out of the box).
8. Tick "Export MP4 animation".
9. Pick an output directory.
10. **Build cube + detect change**.

**Expected**: 1-5 minutes for a small AOI. Output directory ends up with:

- `ndvi_break_index.tif` — int raster, index of the time step where each
  pixel first crossed the change threshold (-1 = no break).
- `ndvi_magnitude.tif` — float raster, signed magnitude of the change.
- `ndvi_timeseries.mp4` — animation of NDVI over time.

The break-index raster is also added to the project automatically.

**Phase**: 3. End-to-end STAC search → Zarr cube → per-pixel CuSum →
COG + MP4.

### T3.2 — LandTrendr-lite

Same dialog, change Method to **LandTrendr-lite**. Run again with a
narrower AOI (LandTrendr is slower than CuSum — it's a per-pixel
piecewise-linear segmentation in Python).

**Expected**: similar outputs but with an additional `n_segments` raster
(trajectory complexity).

**Phase**: 3. Pure-numpy port of Kennedy et al. 2010 LandTrendr core.

### T3.3 — BFAST (skip — Windows pain)

The full BFAST Lite has OpenCL deps and a broken `setup.py` that doesn't
install cleanly on Windows. The CuSum method covers the common "did
something break?" case. Skip BFAST unless you specifically need its
statistical apparatus and want to wrestle OpenCL drivers.

**Phase**: 3.

---

## Phase 4 — Distribution (mostly server-side)

**Owner**: Phase 4. Nothing for you to test locally.

This phase covers: Cloudflare Worker for telemetry, landing page at
`terrascope.app`, auto-update check, Crowdin i18n sync, release-to-
plugins.qgis.org via `qgis-plugin-ci`. None of these run on the
end-user's machine.

The one client-side bit is the auto-update check — open the Python
console and:

```python
from terrascope.core.update_check import check_for_updates
print(check_for_updates())
```

It pings `https://terrascope.app/latest.json`. Until that endpoint exists,
this returns `None` (the function gracefully handles network errors).

**Phase**: 4. Not user-testable until the domain is registered and the
Cloudflare Worker is deployed.

---

## Phase 5 — Speculative

**Owner**: Phase 5. Stubs only.

These exist in `core/preprocessing/` and `core/backends/` but aren't
wired to any dialog. They're API surface for future work:

- `core/preprocessing/sen2cor.py` — Sen2Cor L1C → L2A atmospheric
  correction wrapper. Needs ESA's Sen2Cor installed separately.
- `core/preprocessing/sar.py` — Sentinel-1 GRD preprocessing via pyroSAR
  + SNAP. Needs SNAP installed.
- `core/backends/openeo_backend.py` — alternative compute backend that
  pushes work to an openEO endpoint instead of computing locally.

Nothing to click-test in Phase 5. If you want to exercise these you'll
need to be quite hands-on with the underlying tools.

**Phase**: 5.

---

## When things break

1. **First place to look**: `View → Panels → Log Messages → TerraScope`
   tab in QGIS. Almost every error gets logged there with a stack trace.

2. **Python Console** (`Ctrl+Alt+P`): try importing the failing module
   directly to see the real traceback.

3. **TerraScope's testing harness** can be re-run from outside QGIS
   to isolate domain-layer bugs from QGIS-layer bugs:

```cmd
cd "C:\Users\coleb\OneDrive\Documents\GitHub\terrascope"
python -m pytest tests/unit -v -m unit
```

199 tests should pass. If something fails locally that passed in CI,
it's probably a PROJ database mismatch — see the `pip install
--force-reinstall --no-deps pyproj` fix in section 2.

4. **Catch-all**: send Arné the contents of the Log Messages panel and
   what you clicked to get there.

---

## What to prioritise testing

If you only have time for an hour:

1. T1.1 + T1.2 (catalogue search + COG download) — confirms the Planetary
   Computer integration works end-to-end. Most demoable feature.
2. T1.5 (NDVI in Processing Toolbox) — confirms the plugin loaded
   cleanly into Processing.
3. T1.3 + T1.4 (classify + accuracy PDF) — the SCP-replacement flow.

If you have a half-day:

4. T3.1 (time-series + change detection with CuSum) — the most visually
   rewarding output.
5. T2.1 (SAM with a text prompt) — high "wow" factor; downloads model
   on first run.

Things to skip on a first pass: T2.3 (foundation-model fine-tune, GPU
required), T3.3 (BFAST install pain), T1.8 (CDSE only if you have an
account).
