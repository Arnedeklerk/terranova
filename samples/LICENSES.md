# Sample dataset licences

This file records the provenance and licence of every file under `samples/`.
Terranova only ships samples that are licensed for redistribution.

## Currently bundled

_None yet will add the Khartoum demo._

## Planned

| File | Source | Licence | Notes |
|------|--------|---------|-------|
| `khartoum_s2_2024.tif` | ESA Copernicus Sentinel-2 L2A via Microsoft Planetary Computer | [Copernicus open data](https://www.copernicus.eu/en/access-data/copyright-and-licences) | 5 km clip, 4 bands (R, G, B, NIR), 10 m |
| `khartoum_classes.geojson` | Hand-digitised by the Terranova team over the imagery above | CC0 | 50 polygons, 5 classes |
| `khartoum_validation.geojson` | Same | CC0 | 20 hold-out polygons |

## Adding new samples

Open a PR that adds:

1. The data file under `samples/`.
2. An entry in this file with **Source**, **Licence**, **Notes**.
3. (If imagery) the original asset URL or DOI in **Notes** for traceability.

We reject samples without a clear redistribution licence.
