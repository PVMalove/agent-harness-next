import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const repo = fileURLToPath(new URL("../../..", import.meta.url));

// Tests live in <repo>/tests/web: Node resolution from there never reaches this package's
// node_modules, so every bare package a test imports is resolved from this root (dedupe).
export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  esbuild: { jsx: "automatic" },
  resolve: {
    dedupe: [
      "react",
      "react-dom",
      "react-router",
      "@testing-library/react",
      "@testing-library/dom",
      "json-schema-to-typescript",
    ],
  },
  server: { fs: { allow: [repo] } },
  test: {
    dir: `${repo}/tests/web`,
    include: ["**/*.test.{ts,tsx}"],
    environment: "happy-dom",
    setupFiles: [`${repo}/tests/web/setup.ts`],
    restoreMocks: true,
  },
});
