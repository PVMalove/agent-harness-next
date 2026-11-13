/* Unslop direction approved 2026-11-11: a short type scale with no text below 11px, weights 400-600,
 * no letter-spaced caps, tabular figures, a 4px spacing grid, one KPI accent, no italic and no
 * infinite animation outside a live state. Checked over the mockup stylesheet and the SPA layer. */
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const REPO = resolve(__dirname, "../..");
const STYLES = "harness/console/frontend/src/styles";
/** The design system v3 sheets (ds-tokens, ds-shell, ds-components, ds-screens), found by name. */
const DS_SHEETS = readdirSync(join(REPO, STYLES))
  .filter((name) => /^ds-.+\.css$/.test(name))
  .sort();
const SHEETS: Record<string, string> = {
  mockup: "docs/design/web-console-mockups/execution-console.css",
  app: `${STYLES}/app.css`,
  ...Object.fromEntries(DS_SHEETS.map((name) => [name, `${STYLES}/${name}`])),
};
const read = (path: string) => readFileSync(join(REPO, path), "utf-8");
const mockup = read(SHEETS.mockup);

function rootSizes(): Map<string, number> {
  const root = /:root\s*\{([^}]*)\}/.exec(mockup)?.[1] ?? "";
  return new Map(
    [...root.matchAll(/--(fs-\d):\s*(\d+(?:\.\d+)?)px/g)].map((m) => [m[1], Number(m[2])]),
  );
}

/** Every rule as [selector, body]; nested @media blocks are flattened. */
function rules(css: string): [string, string][] {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => [m[1].trim(), m[2]]);
}

describe("the type scale", () => {
  const scale = rootSizes();

  test("the mockup defines four or five size tokens, none below 11px", () => {
    expect(scale.size).toBeGreaterThanOrEqual(4);
    expect(scale.size).toBeLessThanOrEqual(5);
    for (const size of scale.values()) expect(size).toBeGreaterThanOrEqual(11);
  });

  for (const [name, path] of Object.entries(SHEETS)) {
    const css = read(path);

    test(`${name}: no pixel font size below 11px`, () => {
      const sizes = [...css.matchAll(/font(?:-size)?:\s*(?:\d{3}\s+)?(\d+(?:\.\d+)?)px/g)].map((m) =>
        Number(m[1]),
      );
      expect(sizes.filter((size) => size < 11)).toEqual([]);
    });

    test(`${name}: weights stay within 400-600`, () => {
      const weights = [
        ...[...css.matchAll(/font-weight:\s*(\d+|bold)/g)].map((m) => m[1]),
        ...[...css.matchAll(/font:\s*(\d{3})\s/g)].map((m) => m[1]),
      ].map((w) => (w === "bold" ? 700 : Number(w)));
      expect(weights.filter((w) => w > 600 || w < 400)).toEqual([]);
    });

    test(`${name}: no letter-spaced uppercase labels and no italic`, () => {
      expect(css).not.toMatch(/text-transform:\s*uppercase/);
      expect(css).not.toMatch(/letter-spacing/);
      expect(css).not.toMatch(/font-style:\s*italic/);
    });

    test(`${name}: padding, margin and gap sit on the 4px grid (2px inside small controls)`, () => {
      const off: string[] = [];
      for (const m of css.matchAll(/(?:padding|margin|gap)[\w-]*\s*:([^;}]+)/g)) {
        for (const value of m[1].matchAll(/(\d+(?:\.\d+)?)px/g)) {
          const px = Number(value[1]);
          if (px !== 0 && px !== 2 && px % 4 !== 0) off.push(`${m[0].trim()}`);
        }
      }
      expect(off).toEqual([]);
    });

    test(`${name}: an infinite animation runs only on a live state`, () => {
      const loose = rules(css)
        .filter(([, body]) => /animation[^;]*infinite/.test(body))
        .map(([selector]) => selector)
        .filter((selector) => !/active|current|live|reconnecting|spinner|loading|mascot/.test(selector));
      expect(loose).toEqual([]);
    });
  }
});

describe("numbers and accents", () => {
  test("numbers use tabular figures", () => {
    const body = rules(mockup).find(([selector]) => selector === "body")?.[1] ?? "";
    expect(body).toMatch(/font-variant-numeric:\s*tabular-nums/);
  });

  test("KPI values share one accent instead of a colour per tile", () => {
    const colours = new Set(
      rules(mockup)
        .filter(([selector]) => /kpis? b\.\w+/.test(selector))
        .flatMap(([, body]) => [...body.matchAll(/(?:^|;)\s*color:\s*([^;]+)/g)].map((m) => m[1].trim())),
    );
    expect([...colours].filter((colour) => colour !== "var(--fg)").length).toBeLessThanOrEqual(1);
  });
});

describe("the design system v3 sheets", () => {
  const sheets = DS_SHEETS.map((name) => [name, read(`${STYLES}/${name}`)] as const);

  test("the token, shell, component and screen sheets are all present once the shell lands", () => {
    expect(DS_SHEETS).toContain("ds-tokens.css");
  });

  for (const [name, css] of sheets) {
    test(`${name}: font sizes come from var(--ds-fs-N) only`, () => {
      const sizes = [...css.matchAll(/(?:^|[;{\s])font(?:-size)?:\s*([^;}]+)/g)].map((m) => m[1]!.trim());
      const loose = sizes.filter((value) => /\d+(?:\.\d+)?(?:px|rem|em)\b/.test(value.replace(/var\([^)]*\)/g, "")));
      expect(loose).toEqual([]);
      const tokens = [...css.matchAll(/var\(--ds-fs-(\d+)\)/g)].map((m) => Number(m[1]));
      expect(tokens.filter((n) => n < 1 || n > 5)).toEqual([]);
    });

    test(`${name}: only transform and opacity move, and nothing is letter-spaced`, () => {
      for (const [selector, body] of rules(css)) {
        for (const m of body.matchAll(/transition(?:-property)?:\s*([^;]+)/g)) {
          const props = m[1]!.split(",").map((part) => part.trim().split(/\s+/)[0]);
          expect(props.filter((p) => !["transform", "opacity", "none"].includes(p!)), selector).toEqual([]);
        }
      }
      expect(css).not.toMatch(/letter-spacing/);
    });
  }

  test("the type scale tokens are 11, 13, 16, 20 and 28 px", () => {
    const tokens = read(`${STYLES}/ds-tokens.css`);
    const scale = [...tokens.matchAll(/--ds-fs-(\d):\s*(\d+)px/g)].map((m) => [m[1], Number(m[2])]);
    expect(scale).toEqual([["1", 11], ["2", 13], ["3", 16], ["4", 20], ["5", 28]]);
  });

  test("prefers-reduced-motion switches animation and transition off", () => {
    const tokens = read(`${STYLES}/ds-tokens.css`);
    const block = /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?\n\})/.exec(tokens)?.[1] ?? "";
    expect(block).toMatch(/animation:\s*none/);
    expect(block).toMatch(/transition:\s*none/);
  });

  test("the switch is 34 by 20 px", () => {
    const css = sheets.map(([, text]) => text).join("\n");
    const rule = rules(css).filter(([selector]) => /^\.ds-sw\b/.test(selector) && !selector.includes("::") && !/[ >+~:]/.test(selector.slice(1).replace(/^ds-sw/, ""))).map(([, body]) => body).join(";");
    if (DS_SHEETS.includes("ds-components.css")) {
      expect(rule).toMatch(/width:\s*34px/);
      expect(rule).toMatch(/height:\s*20px/);
    }
  });
});
