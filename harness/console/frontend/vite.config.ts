import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import type { Plugin } from "vite";

/** The accepted mockup stylesheet, shipped byte for byte (tests/web/dist.test.ts compares it). */
export const MOCKUP_CSS = fileURLToPath(
  new URL("../../../docs/design/web-console-mockups/execution-console.css", import.meta.url),
);
const CSS_NAME = "execution-console.css";

function mockupStylesheet(): Plugin {
  return {
    name: "harness-mockup-stylesheet",
    configureServer(server) {
      server.middlewares.use(`/${CSS_NAME}`, (_request, response) => {
        response.setHeader("Content-Type", "text/css; charset=utf-8");
        response.end(readFileSync(MOCKUP_CSS));
      });
    },
    generateBundle() {
      this.emitFile({ type: "asset", fileName: CSS_NAME, source: readFileSync(MOCKUP_CSS) });
    },
  };
}

export default defineConfig({
  base: "/",
  esbuild: { jsx: "automatic" },
  plugins: [mockupStylesheet()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Fonts and icons stay files: data: URLs would break font-src 'self'.
    assetsInlineLimit: 0,
    sourcemap: false,
  },
});
