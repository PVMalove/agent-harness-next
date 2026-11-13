/* The design system v3 shares a page with the stylesheet of the screens that are not moved yet, so
   every class its sheets define starts with ds-: a name that exists in both would silently restyle
   the old screens. */
import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const REPO = resolve(__dirname, "../..");
const STYLES = join(REPO, "harness/console/frontend/src/styles");
/** State classes the shell sets on <body> (`nav-open`, `nav-collapsed`): the sheets read them, the old
    stylesheet owns their names. */
const BODY_STATE = new Set(["nav-open", "nav-collapsed"]);
const SHEETS = readdirSync(STYLES).filter((name) => /^ds-.+\.css$/.test(name)).sort();

function selectors(css: string): string[] {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...clean.matchAll(/([^{}]+)\{[^{}]*\}/g)]
    .map((m) => m[1]!.trim())
    .filter((selector) => !selector.startsWith("@") && !/^[\d.]+%|^(from|to)$/.test(selector));
}

describe("ds-*.css", () => {
  test("the token sheet exists", () => {
    expect(SHEETS).toContain("ds-tokens.css");
  });

  for (const name of SHEETS) {
    test(`${name}: every class selector starts with ds-`, () => {
      const css = readFileSync(join(STYLES, name), "utf-8");
      const foreign = selectors(css)
        .flatMap((selector) => [...selector.replace(/\[[^\]]*\]/g, "").matchAll(/\.([A-Za-z_][\w-]*)/g)].map((m) => m[1]!))
        .filter((cls) => !cls.startsWith("ds-") && !BODY_STATE.has(cls));
      expect(foreign).toEqual([]);
    });

    test(`${name}: every custom property starts with --ds-`, () => {
      const css = readFileSync(join(STYLES, name), "utf-8");
      const foreign = [...css.matchAll(/(?:^|[;{\s])(--[\w-]+)\s*:/g)].map((m) => m[1]!).filter((p) => !p.startsWith("--ds-"));
      expect(foreign).toEqual([]);
    });
  }
});

test("docs/README.md links the web console RFC and the file exists", () => {
  const readme = readFileSync(join(REPO, "docs/README.md"), "utf-8");
  expect(readme).toContain("(./rfc/web-console-v3.md)");
  expect(existsSync(join(REPO, "docs/rfc/web-console-v3.md"))).toBe(true);
});
