#!/usr/bin/env python3
"""Dump JSON Schemas for Pydantic models so the TypeScript side can codegen.

Writes one ``.json`` file per top-level model into ``src/terranova/ui_web/src/schemas/``.
The web tier can then use a tool like ``json-schema-to-typescript`` to generate
matching ``.d.ts`` types — keeping the Python/TS boundary in sync.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from terranova.core.models import (  # noqa: E402
    BBox,
    CatalogSearch,
    ClassifierConfig,
    CommandMessage,
    CommandResult,
    DateRange,
    LedgerEntry,
    TelemetryEvent,
)

OUT_DIR = ROOT / "src" / "terranova" / "ui_web" / "src" / "schemas"

MODELS = {
    "BBox": BBox,
    "CatalogSearch": CatalogSearch,
    "ClassifierConfig": ClassifierConfig,
    "CommandMessage": CommandMessage,
    "CommandResult": CommandResult,
    "DateRange": DateRange,
    "LedgerEntry": LedgerEntry,
    "TelemetryEvent": TelemetryEvent,
}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
