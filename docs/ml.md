# ML stack

Terranova's ML stack is deliberately split into a **classical** layer (sklearn / LightGBM / XGBoost) and a **foundation-model** layer (TerraTorch wrappers around Prithvi, Clay, TerraMind, SAM 3). Both feed into the same inference path that writes a Cloud-Optimised GeoTIFF.

## Default install (no GPU)

The default `pip install terranova` gives you:

- scikit-learn — the full classical roster
- ONNX Runtime CPU — inference without PyTorch
- spyndex — spectral indices

This is enough for the SCP-equivalent workflow: train a RF on field labels, classify a Sentinel-2 scene, export an accuracy PDF.

## Opt-in `[ml]` install

```bash
pip install -e .[ml]
```

Adds:

- PyTorch + Lightning
- TerraTorch (foundation models)
- segment-geospatial (SAM 3)
- SHAP, Optuna, imbalanced-learn
- LightGBM, XGBoost

This pulls a multi-GB PyTorch wheel — keep it opt-in so casual SCP-replacement users aren't hit with it.

## Opt-in `[gpu]` install

```bash
pip install -e .[gpu]
```

Adds `onnxruntime-gpu` for CUDA inference. Foundation-model **fine-tuning** still uses PyTorch CUDA; ORT-GPU is for fast predict-time inference of exported ONNX models.

## Choosing a classifier

| If you have... | Use |
|----------------|-----|
| 30–500 labelled polygons, multi-spectral imagery | **Random Forest** (default) — robust, no tuning needed |
| 500–5k samples and want best accuracy | **LightGBM** or **XGBoost** — better calibration |
| Per-pixel time-series (Sentinel-2 cube) | **Prithvi-EO-2.0 300M** + LightGBM head |
| One-off interactive segmentation (buildings, fields) | **SAM 3** with text/point prompts |
| Sparse labels (~50 polygons) on a single scene | **Prithvi 300M** linear probe — uses the pre-trained representation |

## Reproducibility

Every training run records its full `ClassifierConfig` (random seed included) into the project ledger. Re-running the recipe with the same `terranova.json` reproduces the result bit-for-bit on the same machine.

## Exporting to ONNX

After fitting any sklearn / LightGBM / XGBoost classifier, calling `core.ml.inference.export_onnx(model, out_path)` writes an `.onnx` file that runs without PyTorch. The plugin caches one warm `InferenceSession` per model path; predictions on a 10,980 × 10,980 S2 tile finish in seconds on CPU.

## Memory rules of thumb

| Operation | RAM |
|-----------|-----|
| Train RF on 10k samples × 13 bands | < 1 GB |
| Fine-tune Prithvi 300M, batch 8, 256×256 patches | ~12 GB VRAM |
| Fine-tune Prithvi 600M, batch 4 | ~22 GB VRAM |
| SAM 3 base inference, 1k×1k tile | ~6 GB VRAM |

Users on integrated GPUs or older Macs will only be able to use the ONNX-CPU inference paths.
