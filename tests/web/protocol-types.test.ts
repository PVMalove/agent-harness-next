/* src/ws/protocol.gen.ts is generated from the server's WebSocket schema and must not drift. */
import { readFileSync } from "node:fs";
import { expect, test } from "vitest";

interface Generator {
  OUTPUT_PATH: string;
  REGENERATE: string;
  SCHEMA_PATH: string;
  renderProtocol(schemaText: string): Promise<string>;
}

// The generator is a plain .mjs script of the frontend package; its exports are typed here.
const GENERATOR = "../../harness/console/frontend/scripts/gen-protocol.mjs";
const { OUTPUT_PATH, REGENERATE, SCHEMA_PATH, renderProtocol } = (await import(
  /* @vite-ignore */ GENERATOR
)) as Generator;

test("the committed protocol types equal the rendered schema", async () => {
  const rendered = await renderProtocol(readFileSync(SCHEMA_PATH, "utf-8"));
  expect(
    readFileSync(OUTPUT_PATH, "utf-8") === rendered,
    `protocol.gen.ts is out of date: run \`${REGENERATE}\` in harness/console/frontend and commit it.`,
  ).toBe(true);
});

test("a changed schema changes the rendered types", async () => {
  const schema = JSON.parse(readFileSync(SCHEMA_PATH, "utf-8")) as {
    $defs: Record<string, { properties: Record<string, unknown> }>;
  };
  schema.$defs.ErrorBody!.properties.retry_after = { type: "integer" };
  const rendered = await renderProtocol(JSON.stringify(schema));
  expect(rendered).not.toBe(readFileSync(OUTPUT_PATH, "utf-8"));
});
