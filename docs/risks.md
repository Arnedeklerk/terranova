# Risk register

Per §10 of the build brief. Re-evaluate every Monday review.

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| R1 | QGIS 4.x API churn | M | H | Pin to QGIS 3.40 LTR; maintain 4.x branch; CI against both. |
| R2 | QtWebEngine unavailable in some QGIS bundles (older Linux) | M | M | Graceful degradation in `plugin_dock._build_fallback`: if `QWebEngineView` import fails, hide web-tier panels and fall back to native widgets. |
| R3 | PyTorch/CUDA install pain on Windows | H | H | One-click installer calls `pip install torch --index-url https://download.pytorch.org/whl/cu121`; default to ONNX Runtime CPU so the plugin works without Torch. |
| R4 | CDSE quota exhaustion | M | M | Prefer Planetary Computer by default; surface remaining CDSE quota when logged in. |
| R5 | Foundation-model VRAM | H | M | CPU-only ONNX paths for inference; document min specs (≥ 16 GB for Prithvi 600M, ≥ 8 GB for Clay v1.5). |
| R6 | Sample-data licensing | L | M | Only ESA Copernicus or US-Government public domain; per-file provenance in `samples/LICENSES.md`. |
| R7 | User confusion vs SCP | L | M | Onboarding wizard says explicitly "Coming from SCP? Here's the equivalent…" + the cheat-sheet at `docs/scp_migration.md`. |
| R8 | Single-maintainer bus factor | M | H | Strong tests; thorough docs; modular core; encourage community contribution from v1.0. |
| R9 | OmniCloudMask GPU-only path | M | L | Default SCL mask is pure rasterio; OmniCloudMask is opt-in for GPU users. |
| R10 | pip-installed deps clash with QGIS bundled Python | M | M | `docs/installation.md` documents the OSGeo4W route and warns against Anaconda mixing. |
| R11 | Telemetry endpoint outage breaks plugin | L | H | Network calls are best-effort daemon threads; failures are swallowed. Confirmed by `test_telemetry`. |
| R12 | Privacy-sensitive field leaked into telemetry | L | H | `test_payload_contains_only_documented_fields` enforces six-field shape; any expansion requires a PRIVACY.md PR. |
| R13 | Pydantic v3 breaking change | L | M | Pin `pydantic>=2.7,<3` in `pyproject.toml` once v3 ships. Until then, ride v2.7+. |
| R14 | rio-cogeo `cog_translate` slow on large rasters | M | L | Block-wise predict path keeps memory bounded; cogify happens once per write. |
| R15 | scikit-learn API rename | L | L | Sticky to documented public surface; CI matrix catches early. |

## Closed

_None yet — anything closed will move here with date + resolution._
