import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 402Pilot interactive explainer — static SPA for GitHub Pages.
// Set base to "/402Pilot/" so asset paths resolve under
// https://<org>.github.io/402Pilot/.
export default defineConfig({
  plugins: [react()],
  base: "/402Pilot/",
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    // Bind-mounted directories (e.g. macOS Finder folders surfaced into a
    // Linux sandbox) sometimes refuse `unlink`, which makes Vite's default
    // empty-on-build crash. Skip the cleanup; stale chunk hashes are
    // harmless and `npm run deploy` does its own clean.
    emptyOutDir: false,
  },
});
