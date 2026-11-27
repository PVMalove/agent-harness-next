/* Owner decision 2026-11-11: error and warning text stay readable (WCAG 2.1 AA, 1.4.3) on every
 * surface of the mockup palette, and the active menu item is highlighted in the blue range. Every
 * token is light-dark(light, dark): each contrast holds in both themes (web UX review of #1296). */
import { readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const MOCKUP_CSS = readFileSync(
  join(resolve(__dirname, "../.."), "harness/console/frontend/legacy/execution-console.css"),
  "utf-8",
);

type Theme = "light" | "dark";
const THEMES: readonly Theme[] = ["light", "dark"];

/** The colour of a value in one theme: light-dark(light, dark) picks its side, a hex stays. */
function inTheme(value: string, theme: Theme): string {
  const pair = /^light-dark\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)$/.exec(value.trim());
  return pair ? pair[theme === "light" ? 1 : 2] : value.trim();
}

function rootTokens(css: string, theme: Theme = "dark"): Record<string, string> {
  const root = /:root\s*\{([^}]*)\}/.exec(css.replace(/\/\*[\s\S]*?\*\//g, ""))?.[1] ?? "";
  return Object.fromEntries(
    [...root.matchAll(/--([\w-]+):\s*([^;]+);/g)].map((match) => [match[1], inTheme(match[2], theme)]),
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

const SURFACES = ["bg", "surface", "panel", "row", "sel"];
const DS_CSS = readFileSync(join(resolve(__dirname, "../.."), "harness/console/frontend/src/styles/ds-tokens.css"), "utf-8");

describe.each(THEMES)("the mockup palette, %s theme", (theme) => {
  const tokens = rootTokens(MOCKUP_CSS, theme);
  for (const tone of ["err", "warn", "ok", "primary", "muted"]) {
    for (const surface of SURFACES) {
      test(`--${tone} text reaches 4.5:1 on --${surface}`, () => {
        expect(contrast(tokens[tone]!, tokens[surface]!)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }

  test("the active menu icon sits on a blue background, not the brown-red #4d352c", () => {
    const rule = /nav a\[aria-current="page"\] \.nav-icon \{([^}]*)\}/.exec(MOCKUP_CSS)?.[1] ?? "";
    const value = /background:\s*([^;]+)/i.exec(rule)?.[1] ?? "";
    const side = inTheme(value, theme);
    const background = side.startsWith("var(--") ? tokens[side.slice(6, -1)]! : side;
    expect(background).toMatch(/^#[0-9a-f]{6}$/i);
    expect(background.toLowerCase()).not.toBe("#4d352c");
    const [r, g, b] = [1, 3, 5].map((start) => parseInt(background.slice(start, start + 2), 16));
    expect(b).toBeGreaterThan(r);
    expect(b).toBeGreaterThanOrEqual(g);
    expect(contrast(tokens.selfg!, background)).toBeGreaterThanOrEqual(4.5);
  });
});

describe.each(THEMES)("the design system v3 palette, %s theme", (theme) => {
  const ds = rootTokens(DS_CSS, theme);
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
  // A selected or hovered row keeps its secondary text readable (review of the v3 mockup, 2026-11-16).
  for (const tone of ["ds-muted", "ds-faint", "ds-accent"]) {
    for (const surface of ["ds-accent-bg", "ds-hover"]) {
      test(`--${tone} text reaches 4.5:1 on the row background --${surface}`, () => {
        expect(contrast(ds[tone]!, ds[surface]!)).toBeGreaterThanOrEqual(4.5);
      });
    }
  }
  // The border of a field or a switch track is a non-text control edge: 3:1 (WCAG 1.4.11).
  for (const surface of ["ds-bg", "ds-surface", "ds-raised"]) {
    test(`the control border --ds-control reaches 3:1 on --${surface}`, () => {
      expect(contrast(ds["ds-control"]!, ds[surface]!)).toBeGreaterThanOrEqual(3);
    });
  }
});

/* Owner request 2026-11-16: the accent and the three status hues are pastels (light, low chroma),
 * and the legacy sheet of the not yet moved screens carries the same four hues. */
describe("the pastel hues of the dark theme", () => {
  const ds = rootTokens(DS_CSS);
  const channels = (hex: string) => [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);

  for (const tone of ["ds-accent", "ds-ok", "ds-warn", "ds-err"]) {
    test(`--${tone} is light and low in chroma`, () => {
      const rgb = channels(ds[tone]!);
      const [max, min] = [Math.max(...rgb), Math.min(...rgb)];
      expect((max + min) / 2).toBeGreaterThanOrEqual(0.75);
      expect(max - min).toBeLessThanOrEqual(0.35);
    });
  }

  for (const theme of THEMES) {
    for (const [legacy, tone] of [["primary", "ds-accent"], ["ok", "ds-ok"], ["warn", "ds-warn"], ["err", "ds-err"]] as const) {
      test(`the legacy --${legacy} equals --${tone} in the ${theme} theme`, () => {
        expect(rootTokens(MOCKUP_CSS, theme)[legacy]!.toLowerCase()).toBe(rootTokens(DS_CSS, theme)[tone]!.toLowerCase());
      });
    }
  }
});
