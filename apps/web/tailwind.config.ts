import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#090908",
        panel: "#121210",
        line: "#302d28",
        paper: "#f3eee5",
        ember: "#c68c5b",
        moss: "#9b9b78",
        tide: "#a97a62"
      },
      boxShadow: {
        veil: "0 28px 80px rgba(0, 0, 0, 0.42)",
        ember: "0 18px 56px rgba(122, 73, 50, 0.16)"
      },
      letterSpacing: {
        editorial: "0.18em"
      }
    }
  },
  plugins: []
};

export default config;
