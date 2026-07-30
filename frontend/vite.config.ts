import path from "node:path";

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "/static/frontend/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "../src/lists/static/frontend",
    emptyOutDir: true,
    // Each entry needs its own CSS output now that "tokens" is a
    // CSS-only entry shared by Django templates directly, separate from
    // the legacy per-page CSS bundled with "main".
    cssCodeSplit: true,
    rollupOptions: {
      // "app" (not "main") so its associated CSS asset, named from the
      // entry key below, comes out as app.css rather than main.css.
      input: {
        app: "src/main.tsx",
        "app-shell": "src/app/main.tsx",
        tokens: "src/app/tailwind.css",
      },
      output: {
        // Kept as separate bundles (see the UI overhaul plan's "separate
        // SPA JS baseline" goal) -- the legacy per-page islands and the
        // new router-based shell have nothing to share yet.
        entryFileNames: (chunk) => {
          if (chunk.name === "app-shell") return "app-shell.js";
          // Vite still emits a facade JS module for a CSS-only entry;
          // nothing references it, it just needs a name that doesn't
          // collide with the "app" entry's own app.js.
          if (chunk.name === "tokens") return "tokens-entry.js";
          return "app.js";
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        // CSS assets take their name from the entry ([name] resolves to
        // the input key above, e.g. "app" -> app.css, "tokens" -> tokens.css)
        // so Django's {% static %} references stay fixed and predictable.
        assetFileNames: (assetInfo) =>
          assetInfo.names?.some((name) => name.endsWith(".css"))
            ? "[name][extname]"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    globals: true,
  },
});
