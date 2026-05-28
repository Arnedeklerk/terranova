# Recipes

A recipe is a YAML file that describes a one-click Terranova workflow.  Recipes appear on the welcome screen and in the command palette.  Anything done through a recipe is also reproducible from the QGIS Python console because every step is dispatched to the same controller actions the UI uses.

## Schema

```yaml
name: <human-readable name>
description: |
  Multi-line description.

inputs:
  <name>: { kind: <kind>, default: <value>, hint: "..." }
  ...

steps:
  - action: <dispatch-action>
    params:
      <key>: <value-or-expression>
    ...
```

## Supported input kinds

| Kind | Example default | Type in UI |
|------|-----------------|------------|
| `vector` | (none) | Layer picker, filtered to vector |
| `raster` | (none) | Layer picker, filtered to raster |
| `string` | `"class"` | Text input |
| `int`    | `30` | Number input (with min/max) |
| `float`  | `0.2` | Number input (with min/max) |
| `daterange` | `"2024-04-01/2024-09-30"` | Calendar pair |
| `date` | `"2024-01-01"` | Calendar |
| `bbox` | (none) | Pulled from canvas / drawn / layer extent |

## Variable substitution

Inside `params`, you can reference inputs as `${name}` and access nested fields with `${name.field}`.  A small handful of helper functions exist:

- `${aoi.bbox}` — bbox of the input named `aoi` (works for vector layers)
- `${end_of(now)}` — today's date in ISO 8601
- `${start_of(year)}` — Jan 1 of the current year

If your recipe needs more than these, prefer to build a Processing model or a Python script instead — recipes are deliberately limited so they remain reproducible and easy to understand.

## Available actions

The set of `action` values is the dispatch table in `terranova.controllers.dispatch.Controllers._register`.  Currently ships:

- `catalog.search` — STAC search returning items
- `app.ping` / `app.version` — smoke tests
- `app.telemetry.{status,set,inspect}` — telemetry consent flow

Future versions can add `stacking.composite`, `classify.train`, `classify.predict`, `accuracy.report`, `timeseries.cube`, `timeseries.bfast`.

## Worked example

```yaml
name: Crop classification (Sentinel-2)
description: |
  Median composite of cloud-masked Sentinel-2 L2A over a growing season,
  then RF on field polygons.

inputs:
  aoi: { kind: vector, hint: "Polygon AOI" }
  training: { kind: vector, hint: "Class field required" }
  class_field: { kind: string, default: "class" }
  date_range: { kind: daterange, default: "2024-04-01/2024-09-30" }
  max_cloud: { kind: int, default: 20, min: 0, max: 100 }

steps:
  - action: catalog.search
    params:
      endpoint: planetary_computer
      collection: sentinel-2-l2a
      bbox: "${aoi.bbox}"
      datetime: "${date_range}"
      max_cloud: "${max_cloud}"

  - action: stacking.composite
    params: { method: median, cloud_mask: omnicloudmask }

  - action: classify.train
    params:
      training: "${training}"
      class_field: "${class_field}"
      classifier: random_forest

  - action: classify.predict
    params: { output_name: "crops_${date_range}.tif" }

  - action: accuracy.report
    params: { output_name: "crops_${date_range}_accuracy.pdf" }
```

Recipes ship in `recipes/` and are also user-saveable via the "Save as recipe…" action in the command palette.
