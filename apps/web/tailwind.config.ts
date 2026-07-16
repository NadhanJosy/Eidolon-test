import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "var(--color-canvas)",
        panel: "var(--color-surface)",
        line: "var(--color-border)",
        paper: "var(--color-text)",
        ember: "var(--color-accent)",
        moss: "var(--color-success)",
        tide: "var(--color-accent-deep)"
      },
      boxShadow: {
        veil: "var(--shadow-overlay)",
        ember: "0 18px 56px rgba(122, 73, 50, 0.16)"
      },
      letterSpacing: {
        editorial: "0.18em"
      },
      maxWidth: {
        chat: "var(--measure-chat)",
        copy: "var(--measure-copy)"
      },
      transitionTimingFunction: {
        arrive: "var(--ease-arrive)"
      }
    }
  },
  plugins: []
};

export default config;
