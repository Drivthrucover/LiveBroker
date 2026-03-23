import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#101418",
        mist: "#edf1ec",
        olive: "#5d7a52",
        clay: "#bc754b",
        gold: "#d4a017",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "monospace"],
      },
      boxShadow: {
        panel: "0 14px 40px rgba(16, 20, 24, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
