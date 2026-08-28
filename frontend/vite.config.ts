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
      // The "app" entry (src/main.tsx) was removed on August 15, 2026. It
      // mounted the per-page islands, and no template had referenced them
      // since the router shell took over -- so every deploy built and shipped
      // a bundle nothing loaded. The components it mounted are very much
      // alive; they are the SPA's routes now.
      input: {
        "app-shell": "src/app/main.tsx",
        tokens: "src/app/tailwind.css",
      },
      output: {
        entryFileNames: (chunk) => {
          // Vite still emits a facade JS module for a CSS-only entry;
          // nothing references it, it just needs a name of its own.
          if (chunk.name === "tokens") return "tokens-entry.js";
          return "app-shell.js";
        },
        chunkFileNames: "chunks/[name]-[hash].js",
        // CSS assets are named and hashed after their entry, so without this
        // the shell's stylesheet emits as "app-shell-<hash>.css" and misses
        // the fixed frontend/app.css that lists.templatetags.frontend_tags
        // hardcodes. Only "tokens" (never shared, Django-owned) gets its own
        // name; everything else collapses into one predictable app.css.
        //
        // This said until August 28, 2026 that route components are "lazily
        // split", so their CSS would take the *chunk's* name. They are not:
        // there is no React.lazy, no dynamic import and no Suspense anywhere
        // in src/, and the build emits no chunks/ directory at all despite
        // chunkFileNames above being configured for one. The rule is still
        // needed for the entry-name reason above, and would cover lazy chunks
        // too if they ever appear -- but they do not exist today.
        assetFileNames: (assetInfo) =>
          assetInfo.names?.some((name) => name.endsWith(".css"))
            ? assetInfo.names[0]?.startsWith("tokens")
              ? "tokens.css"
              : "app.css"
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
