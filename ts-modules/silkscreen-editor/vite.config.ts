import { defineConfig } from "vite";
import { silkApiPlugin } from "./server/api";

// Dev-tool config: browser UI + /api middleware in one process.
// The middleware spawns a bun child (server/compile-worker.ts) for the actual
// tscircuit eval, so the vite process itself never loads tscircuit internals
// and the KiCad-font-patched ../node_modules stays the single source
// of truth for eval + rendering packages.
export default defineConfig({
  // .tsx sources use the automatic JSX runtime (no `import React` needed);
  // without this esbuild falls back to the classic `React.createElement`.
  esbuild: {
    jsx: "automatic",
  },
  plugins: [silkApiPlugin()],
  server: {
    port: 5175,
    strictPort: true,
    fs: {
      // allow serving the workspace root (underlay svg is injected as HTML)
      strict: false,
    },
  },
});
