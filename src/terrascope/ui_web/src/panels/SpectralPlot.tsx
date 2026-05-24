import { useEffect, useRef } from "react";

interface SpectralSample {
  className: string;
  wavelengths_nm: number[];
  reflectances: number[];
}

interface Props {
  samples: SpectralSample[];
}

/**
 * Spectral-signature scatter/line chart for training samples.
 *
 * Uses Plotly (loaded async to avoid bloating the Vite vendor chunk when this
 * panel isn't open).  Hover reveals exact wavelength + reflectance.
 */
export function SpectralPlot({ samples }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let plot: any | null = null;
    let disposed = false;

    async function render() {
      if (!ref.current) return;
      const Plotly = await import("plotly.js-dist-min");
      if (disposed) return;

      const data = samples.map((s) => ({
        type: "scatter" as const,
        mode: "lines+markers" as const,
        name: s.className,
        x: s.wavelengths_nm,
        y: s.reflectances,
        hovertemplate: "%{x} nm<br>%{y:.3f}<extra>%{fullData.name}</extra>",
      }));

      const layout = {
        margin: { l: 50, r: 16, t: 8, b: 40 },
        xaxis: { title: "Wavelength (nm)", color: "#8A93A0", gridcolor: "#1C2027" },
        yaxis: { title: "Reflectance", color: "#8A93A0", gridcolor: "#1C2027" },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: "#E8ECF1", family: "Inter, system-ui, sans-serif" },
        legend: { orientation: "h" as const, y: -0.25 },
      };

      plot = await Plotly.newPlot(ref.current, data, layout, {
        responsive: true,
        displaylogo: false,
      });
    }

    render().catch(console.error);
    return () => {
      disposed = true;
      if (plot && ref.current) {
        import("plotly.js-dist-min").then((Plotly) => Plotly.purge(ref.current!));
      }
    };
  }, [samples]);

  return <div ref={ref} className="w-full h-64" />;
}
