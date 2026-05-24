import type { Config } from "tailwindcss";

// Mirrors src/terranova/ui/styles/tokens.yaml.  When updating one, update the other.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          0: "#0B0D10",
          1: "#14171C",
          2: "#1C2027",
        },
        fg: {
          DEFAULT: "#E8ECF1",
          muted: "#8A93A0",
        },
        accent: "#4F8AF7",
        success: "#3FB57E",
        warn: "#E6B450",
        danger: "#E5484D",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI Variable", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
} satisfies Config;
