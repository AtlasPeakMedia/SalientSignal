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
        // SalientSignal palette - dark intelligence aesthetic
        bg: {
          base: "#0D0D0F",        // Near-black base surface
          ocean: "#0A0F1A",       // Globe ocean (barely lighter than base)
          card: "#161819",        // Elevated cards/surfaces
          divider: "#2A2D32",     // Hairline separators
        },
        country: {
          neutral: "#1A1D24",     // Quiet country polygon
        },
        deviation: {
          deepBlue: "#1A3A5C",    // Significant silence
          steelBlue: "#4A7FB5",   // Unusually quiet
          coolGray: "#2A3040",    // Slightly below normal
          neutral: "#1A1D24",     // Normal range
          amber: "#F5A623",       // Elevated
          orange: "#E8601C",      // Significant spike
          red: "#D93025",         // Anomalous surge
        },
        accent: {
          teal: "#00897B",        // Brand accent
          tealBright: "#00BFA5",  // Coordination arc medium
          tealMax: "#00E5CC",     // Coordination arc bright
        },
        text: {
          primary: "#FFFFFF",
          secondary: "#9E9E9E",
          body: "#E0E0E0",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      animation: {
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.5s ease-in-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
