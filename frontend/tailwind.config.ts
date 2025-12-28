import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Biosecurity-themed dark palette
        background: "#0a0a0f",
        foreground: "#e4e4e7",
        card: "#111116",
        "card-foreground": "#e4e4e7",
        muted: "#1c1c24",
        "muted-foreground": "#71717a",
        border: "#27272a",
        primary: "#22c55e",
        "primary-foreground": "#0a0a0f",
        secondary: "#18181b",
        "secondary-foreground": "#e4e4e7",
        accent: "#f59e0b",
        "accent-foreground": "#0a0a0f",
        destructive: "#ef4444",
        "destructive-foreground": "#fafafa",
        // Risk grade colors
        "grade-a": "#22c55e",
        "grade-b": "#84cc16",
        "grade-c": "#eab308",
        "grade-d": "#f97316",
        "grade-f": "#ef4444",
      },
      fontFamily: {
        sans: ["JetBrains Mono", "monospace"],
        mono: ["JetBrains Mono", "monospace"],
      },
      backgroundImage: {
        "grid-pattern": "linear-gradient(to right, #1c1c24 1px, transparent 1px), linear-gradient(to bottom, #1c1c24 1px, transparent 1px)",
      },
      backgroundSize: {
        grid: "20px 20px",
      },
    },
  },
  plugins: [],
};

export default config;

