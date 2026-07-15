import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Eidolon",
    short_name: "Eidolon",
    description: "A private, text-only companion built around continuity.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    display_override: ["standalone", "minimal-ui"],
    background_color: "#0d0d0f",
    theme_color: "#0d0d0f",
    orientation: "any",
    lang: "en",
    dir: "ltr",
    categories: ["lifestyle", "utilities"],
    prefer_related_applications: false,
    launch_handler: {
      client_mode: "navigate-existing"
    },
    icons: [
      {
        src: "/eidolon-mark.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any"
      },
      {
        src: "/eidolon-mark.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "maskable"
      }
    ]
  };
}
