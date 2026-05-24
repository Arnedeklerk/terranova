import { useEffect, useState } from "react";
import { invoke } from "../bridge";
import { useUiStore, type View } from "../store/useUiStore";

interface Card {
  id: string;
  title: string;
  sub: string;
  /** Navigate to this view; falls back to invoking the action over the bridge. */
  view?: View;
  action?: string;
}

const CARDS: Card[] = [
  {
    id: "classify",
    title: "Classify a scene",
    sub: "Train a model on field labels and apply it to Sentinel or Landsat imagery.",
    view: "classify",
  },
  {
    id: "change",
    title: "Detect change over time",
    sub: "Build a time-series cube and run BFAST, LandTrendr, or CCDC per pixel.",
    view: "timeseries",
  },
  {
    id: "download",
    title: "Download imagery",
    sub: "Search Planetary Computer, Earth Search, or CDSE — lazy or full download.",
    view: "catalog",
  },
  {
    id: "sam",
    title: "Segment with AI",
    sub: "Use SAM 3 with text or point prompts to extract features instantly.",
    view: "sam",
  },
];

export function Welcome() {
  const [version, setVersion] = useState<string>("");
  const setView = useUiStore((s) => s.setView);

  useEffect(() => {
    invoke<{ version: string }>("app.version")
      .then((r) => r.ok && r.result && setVersion(r.result.version))
      .catch(() => setVersion("?"));
  }, []);

  const onCardClick = (c: Card) => {
    if (c.view) setView(c.view);
    else if (c.action) invoke(c.action).catch(console.error);
  };

  return (
    <section className="max-w-3xl mx-auto">
      <h2 className="text-xl font-semibold mb-1">Welcome to TerraScope</h2>
      <p className="text-fg-muted mb-6 text-sm">
        Phase 0 prototype{version ? ` — v${version}` : ""}. Pick a starting point.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {CARDS.map((c) => (
          <button
            key={c.id}
            onClick={() => onCardClick(c)}
            className="text-left bg-bg-1 hover:bg-bg-2 border border-bg-2 rounded-md p-4 transition"
          >
            <div className="font-medium mb-1">{c.title}</div>
            <div className="text-fg-muted text-xs leading-relaxed">{c.sub}</div>
          </button>
        ))}
      </div>

      <p className="text-fg-muted text-xs mt-8">
        Coming from SCP? Open the command palette (Ctrl K) and search for
        &quot;SCP equivalent&quot; to find the matching TerraScope action.
      </p>
    </section>
  );
}
