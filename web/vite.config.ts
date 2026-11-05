import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

/** Der Vorschau-Bau bekommt Titel, Manifest und Icons mit dem Zusatz. */
function previewHead(): Plugin {
  return {
    name: "vorschau-kopf",
    transformIndexHtml(html: string) {
      return html
        .replace(
          "<title>Trainings-Cockpit</title>",
          "<title>Trainings-Cockpit · Vorschau</title>",
        )
        .replace('content="Cockpit"', 'content="Cockpit Vorschau"')
        .replace('href="/manifest.webmanifest"', 'href="/manifest-vorschau.webmanifest"')
        .replace('href="/icons/favicon.svg"', 'href="/icons/vorschau.svg"')
        .replace(
          'href="/icons/apple-touch-icon.png"',
          'href="/icons/apple-touch-icon-vorschau.png"',
        );
    },
  };
}

export default defineConfig(({ mode }) => {
  const preview = loadEnv(mode, ".", "").VITE_APP_VARIANT === "preview";

  return {
    plugins: [react(), ...(preview ? [previewHead()] : [])],
    server: {
      port: 5173,
      proxy: {
        "/api": "http://127.0.0.1:8000",
      },
    },
    build: {
      outDir: "dist",
      sourcemap: false,
    },
  };
});
