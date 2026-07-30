import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/static/frontend/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "../src/lists/static/frontend",
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      input: {
        main: "src/main.tsx",
        "app-shell": "src/app/main.tsx",
      },
      output: {
        // Kept as two fully separate bundles (see the UI overhaul plan's
        // "separate SPA JS baseline" goal) -- the legacy per-page islands
        // and the new router-based shell have nothing to share yet.
        entryFileNames: (chunk) =>
          chunk.name === "app-shell" ? "app-shell.js" : "app.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: (assetInfo) =>
          assetInfo.names?.some((name) => name.endsWith(".css"))
            ? "app.css"
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
