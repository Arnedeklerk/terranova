import { useEffect, useState } from "react";
import { onEvent } from "../bridge";

/**
 * Inspector panel — shows the value(s) under the most recent map click.
 *
 * Python pushes `inspector.update` events with `{x, y, crs, values: [...]}`.
 * Each value is `{band: "B04", value: 1234, label?: "red"}`.
 */
interface InspectorValue {
  band: string;
  value: number | null;
  label?: string;
}

interface InspectorPayload {
  type: "inspector.update";
  x: number;
  y: number;
  crs: string;
  values: InspectorValue[];
}

export function Inspector() {
  const [payload, setPayload] = useState<InspectorPayload | null>(null);

  useEffect(() => {
    return onEvent((p) => {
      const msg = p as { type?: string };
      if (msg?.type === "inspector.update") setPayload(p as InspectorPayload);
    });
  }, []);

  if (!payload) {
    return (
      <div className="text-fg-muted text-xs p-3">
        Click the map to inspect pixel values.
      </div>
    );
  }

  return (
    <div className="p-3 text-xs">
      <div className="text-fg-muted mb-2">
        <span className="font-mono">
          {payload.x.toFixed(4)}, {payload.y.toFixed(4)}
        </span>{" "}
        ({payload.crs})
      </div>
      <table className="w-full">
        <thead>
          <tr className="text-fg-muted">
            <th className="text-left font-normal">Band</th>
            <th className="text-right font-normal">Value</th>
          </tr>
        </thead>
        <tbody>
          {payload.values.map((v, i) => (
            <tr key={i} className="border-t border-bg-2">
              <td className="py-1">
                {v.band}
                {v.label && <span className="text-fg-muted ml-1">({v.label})</span>}
              </td>
              <td className="py-1 text-right font-mono">
                {v.value === null ? "—" : v.value.toFixed(4)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
