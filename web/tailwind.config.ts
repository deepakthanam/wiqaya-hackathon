import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#F7F4F0",
        ink: "#2E2A26",
        teal: { DEFAULT: "#0E6B68", dark: "#0A4F4D", light: "#E3EFEE" },
        coral: { DEFAULT: "#B5543F", light: "#F6E6E1" },
        line: "#C9BEB1",
        muted: "#6B6259",
      },
      fontFamily: { sans: ["Inter", "system-ui", "Segoe UI", "Roboto", "Arial", "sans-serif"] },
    },
  },
  plugins: [],
};
export default config;
