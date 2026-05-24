import { useState } from "react";
import { Welcome } from "./panels/Welcome";
import { CatalogSearch } from "./panels/CatalogSearch";
import { Classify } from "./panels/Classify";
import { CommandPalette } from "./panels/CommandPalette";
import { TelemetryConsent } from "./panels/TelemetryConsent";
import { useHotkey } from "./hooks/useHotkey";
import { useUiStore } from "./store/useUiStore";

/**
 * Root of the embedded React panel.
 *
 * View-switching is local (Zustand store).  The Cmd/Ctrl+K palette overlays
 * regardless of which view is mounted.
 */
export function App() {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const view = useUiStore((s) => s.view);
  const setView = useUiStore((s) => s.setView);

  useHotkey(["Meta+k", "Control+k"], () => setPaletteOpen((v) => !v));
  useHotkey(["Escape"], () => setPaletteOpen(false));

  return (
    <div className="min-h-screen flex flex-col">
      <header className="px-6 py-4 border-b border-bg-2 flex items-baseline gap-3">
        <h1 className="text-lg font-semibold tracking-tight">TerraScope</h1>
        <span className="text-fg-muted text-xs">Classify Earth, gracefully.</span>

        <nav className="ml-6 flex gap-1 text-xs">
          {(["welcome", "catalog", "classify", "timeseries", "sam"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={
                "px-2.5 py-1 rounded " +
                (view === v
                  ? "bg-bg-2 text-fg"
                  : "text-fg-muted hover:text-fg hover:bg-bg-1")
              }
            >
              {v}
            </button>
          ))}
        </nav>

        <div className="ml-auto text-fg-muted text-xs">
          <kbd className="px-1.5 py-0.5 bg-bg-1 rounded">Ctrl K</kbd>
          <span className="ml-2">commands</span>
        </div>
      </header>

      <main className="flex-1 p-6 overflow-auto">
        {view === "welcome" && <Welcome />}
        {view === "catalog" && <CatalogSearch />}
        {view === "classify" && <Classify />}
        {view === "timeseries" && (
          <PointerToMenu
            name="Time-series + change detection"
            menuPath="Raster → TerraScope → Time-series + change detection…"
            description="Build a Zarr cube from a STAC search, compute NDVI / NBR / NDMI, run CuSum / BFAST / LandTrendr per pixel, write break rasters and an MP4 animation. The dialog opens from the main QGIS menu."
          />
        )}
        {view === "sam" && (
          <PointerToMenu
            name="SAM segmentation"
            menuPath="Raster → TerraScope → Segment with SAM…"
            description="Segment features using SAM 2 / SAM 3 with text or point prompts. The dialog opens from the main QGIS menu."
          />
        )}
      </main>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <TelemetryConsent />
    </div>
  );
}

interface PointerProps {
  name: string;
  menuPath: string;
  description: string;
}

function PointerToMenu({ name, menuPath, description }: PointerProps) {
  return (
    <div className="max-w-xl">
      <h2 className="text-lg font-semibold mb-2">{name}</h2>
      <p className="text-fg-muted text-sm mb-4 leading-relaxed">{description}</p>
      <div className="bg-bg-1 border border-bg-2 rounded-md p-4 text-sm">
        <div className="text-fg-muted mb-1 text-xs uppercase tracking-wide">
          Where to find it
        </div>
        <code className="text-fg font-mono">{menuPath}</code>
      </div>
    </div>
  );
}
