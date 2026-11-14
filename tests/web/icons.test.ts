/* Every icon of the mockup set (docs/design/web-console-mockups/harness-icons.js) is ported to the
   SPA with the same geometry: roles, states, hosting marks, health areas and maintenance. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test } from "vitest";
import { Icon } from "../../harness/console/frontend/src/icons";

const SOURCE = readFileSync(resolve(__dirname, "../../docs/design/web-console-mockups/harness-icons.js"), "utf-8");

/** name → inner SVG markup; a repeated key keeps its last value, as in the JS object literal. */
function mockupIcons(): Map<string, string> {
  const icons = new Map<string, string>();
  for (const match of SOURCE.matchAll(/^\s{4}'?([a-z-]+)'?: '(.*)',?$/gm)) icons.set(match[1], match[2]);
  return icons;
}

const normalize = (markup: string) =>
  markup.replace(/><\/\w+>/g, "/>").replace(/\s*\/>/g, "/>").replace(/<(\w+)([^>]*)\/>/g, (_all, tag: string, attrs: string) => {
    const sorted = [...attrs.matchAll(/([\w-]+)="([^"]*)"/g)].map((m) => `${m[1]}="${m[2]}"`).sort();
    return `<${tag} ${sorted.join(" ")}/>`;
  });

const inner = (name: string) =>
  normalize(renderToStaticMarkup(createElement(Icon, { name })).replace(/^<svg[^>]*>|<\/svg>$/g, ""));

describe("the icon set", () => {
  const icons = mockupIcons();

  test("the mockup set is read", () => {
    for (const name of ["architect", "developer", "review", "qa", "play", "blocked", "awaiting", "completed", "github-mark", "gitlab-mark"]) {
      expect(icons.has(name)).toBe(true);
    }
  });

  for (const [name, markup] of icons) {
    test(`${name} is drawn as in the mockup`, () => {
      expect(inner(name)).toBe(normalize(markup));
    });
  }
});
