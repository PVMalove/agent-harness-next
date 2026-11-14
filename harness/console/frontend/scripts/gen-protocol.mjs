// Renders harness/console/backend/api/ws-schema.json into src/ws/protocol.gen.ts (ADR 0029 §3).
// Run `npm run gen:protocol` after the schema changes; tests/web/protocol-types.test.ts fails on drift.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

// Paths from the module's own file path: tests import this module under a DOM URL global.
const HERE = dirname(fileURLToPath(import.meta.url));
export const SCHEMA_PATH = resolve(HERE, "../../backend/api/ws-schema.json");
export const OUTPUT_PATH = resolve(HERE, "../src/ws/protocol.gen.ts");
export const REGENERATE = "npm run gen:protocol";

const BANNER = `/* Generated from harness/console/backend/api/ws-schema.json by scripts/gen-protocol.mjs.
   Do not edit: run \`${REGENERATE}\` in harness/console/frontend. */`;

/** The TypeScript text of every definition in the schema. */
export async function renderProtocol(schemaText) {
  const schema = JSON.parse(schemaText);
  return compile(schema, "ConsoleProtocol", {
    bannerComment: BANNER,
    unreachableDefinitions: true,
    additionalProperties: false,
    strictIndexSignatures: true,
    format: true,
    cwd: dirname(SCHEMA_PATH),
  });
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  writeFileSync(OUTPUT_PATH, await renderProtocol(readFileSync(SCHEMA_PATH, "utf-8")));
}
