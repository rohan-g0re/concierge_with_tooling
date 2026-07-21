import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand tokens — Meridian Line / Compass
        navy: "#0C2340",
        gold: "#C8A45C",
        goldDark: "#B08F44",
        seaMist: "#E9ECEF",
        chatBg: "#F4F6F8",
        ink: "#22344B",
        slate: "#5A6B7E",
        mute: "#8A97A6",
        teal: "#4E7E86",
      },
      fontFamily: {
        // Playfair Display — headlines, brand name, cruise names
        display: ["var(--font-playfair)", "Georgia", "serif"],
        // Source Sans 3 — body, UI labels
        sans: ["var(--font-source-sans)", "system-ui", "sans-serif"],
      },
      letterSpacing: {
        widest2: "0.2em",
      },
    },
  },
  plugins: [],
};

export default config;
