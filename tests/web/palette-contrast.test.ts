/* Owner decision 2026-11-11: error and warning text stay readable (WCAG 2.1 AA, 1.4.3) on every
 * surface of the mockup palette, and the active menu item is highlighted in the blue range. */
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const MOCKUP_CSS = readFileSync(
  join(resolve(__dirname, "../.."), "docs/design/web-console-mockups/execution-console.css"),
  "utf-8",
);

function rootTokens(css: string): Record<string, string> {
  const root = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? "";
  return Object.fromEntries(
    [...root.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((match) => [match[1], match[2].trim()]),
  );
}

function luminance(hex: string): number {
  const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const tokens = rootTokens(MOCKUP_CSS);
const SURFACES = ["bg", "surface", "panel", "row", "sel"];

describe("the mockup palette", () => {
  for (const tone of ["err", "warn"]) {
    for (const surface of SURFACES) {
      test(`--${tone} text reaches 4.5:1 on --${surface}`, () => {
        expect(contrast(tokens[tone], tokens[surface])).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  test("the active menu icon sits on a blue background, not the brown-red #4d352c", () => {
    const rule = /nav a\[aria-current="page"\] \.nav-icon \{([^}]*)\}/.exec(MOCKUP_CSS)?.[1] ?? "";
    const background = /background:\s*(#[0-9a-f]{6})/i.exec(rule)?.[1] ?? "";
    expect(background).not.toBe("");
    expect(background.toLowerCase()).not.toBe("#4d352c");
    const [r, g, b] = [1, 3, 5].map((start) => parseInt(background.slice(start, start + 2), 16));
    expect(b).toBeGreaterThan(r);
    expect(b).toBeGreaterThanOrEqual(g);
    expect(contrast(tokens.selfg, background)).toBeGreaterThanOrEqual(4.5);
  });
});

describe("the design system v3 palette", () => {
  const ds = rootTokens(readFileSync(join(resolve(__dirname, "../.."), "harness/console/frontend/src/styles/ds-tokens.css"), "utf-8"));
  for (const tone of ["ds-ok", "ds-warn", "ds-err", "ds-muted", "ds-faint", "ds-accent"]) {
    for (const surface of ["ds-bg", "ds-surface", "ds-raised", "ds-rail"]) {
      test(`--${tone} text reaches 4.5:1 on --${surface}`, () => {
        expect(contrast(ds[tone]!, ds[surface]!)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
  for (const [tone, surface] of [["ds-ok", "ds-ok-bg"], ["ds-warn", "ds-warn-bg"], ["ds-err", "ds-err-bg"], ["ds-accent", "ds-accent-bg"]] as const) {
    test(`--${tone} on its own tint --${surface} reaches 4.5:1`, () => {
      expect(contrast(ds[tone]!, ds[surface]!)).toBeGreaterThanOrEqual(4.5);
    });
  }
});
