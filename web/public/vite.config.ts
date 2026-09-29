import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";

const directory = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: resolve(directory, "../.."),
  build: {
    emptyOutDir: true,
    lib: {
      entry: resolve(directory, "src/index.ts"),
      formats: ["es"],
      fileName: "ecodeling-experience",
    },
    outDir: resolve(directory, "dist"),
    rollupOptions: {
      external: [],
    },
  },
  server: {
    host: "127.0.0.1",
    port: 4173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
    },
  },
});
