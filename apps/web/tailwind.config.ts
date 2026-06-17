import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0d0d0f",
        panel: "#171719",
        line: "#2d2d32",
        paper: "#f4f4f5",
        ember: "#f59e0b",
        moss: "#65a30d",
        tide: "#0891b2"
      }
    }
  },
  plugins: []
};

export default config;

