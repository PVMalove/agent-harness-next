/* The production build (npm run build) ships only local files and the mockup stylesheet as is. */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, test } from "vitest";

const REPO = resolve(__dirname, "../..");
const DIST = join(REPO, "harness/console/frontend/dist");
const MOCKUP_CSS = join(REPO, "docs/design/web-console-mockups/execution-console.css");

/** URL-like strings in the bundle that are identifiers, never loaded: XML namespaces, React's
 * error-decoder link and React Router's URL-parsing base and doc link in a warning text. */
const NOT_LOADED = [
  /^http:\/\/www\.w3\.org\//,
  /^https:\/\/react\.dev\/errors\//,
  /^http:\/\/localhost$/,
  /^https:\/\/reactrouter\.com\//,
];
const URL_PATTERN = /https?:\/\/[^\s"'`)<>]*/g;

function files(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory() ? files(join(dir, entry.name)) : [join(dir, entry.name)],
  );
}

describe("the build in harness/console/frontend/dist", () => {
  test("exists: run `npm run build` in harness/console/frontend first", () => {
    expect(existsSync(join(DIST, "index.html"))).toBe(true);
  });

  const all = existsSync(DIST) ? files(DIST) : [];
  const ofType = (extension: string) => all.filter((path) => path.endsWith(extension));
  const text = (path: string) => readFileSync(path, "utf-8");

  test("holds the page, a script, styles, local fonts and the icon", () => {
    expect(ofType(".js").length).toBeGreaterThan(0);
    expect(ofType(".css").length).toBeGreaterThan(1);
    expect(ofType(".woff2").length).toBeGreaterThanOrEqual(6);
    expect(existsSync(join(DIST, "favicon.svg"))).toBe(true);
  });

  test("ships the mockup stylesheet byte for byte", () => {
    expect(readFileSync(join(DIST, "execution-console.css")).equals(readFileSync(MOCKUP_CSS))).toBe(
      true,
    );
  });

  test("index.html links local files only, with no inline script or style", () => {
    const page = text(join(DIST, "index.html"));
    expect(page.match(URL_PATTERN)).toBeNull();
    expect(page).not.toMatch(/<script(?![^>]*\bsrc=)[^>]*>/);
    expect(page).not.toMatch(/\sstyle=/);
    expect(page).not.toMatch(/<style/);
    expect(page.indexOf("/execution-console.css")).toBeLessThan(page.indexOf("/assets/"));
  });

  test("stylesheets reference no remote URL and no data: font", () => {
    for (const path of ofType(".css")) {
      expect(text(path).match(URL_PATTERN), path).toBeNull();
      expect(text(path), path).not.toMatch(/url\(\s*["']?data:/);
    }
  });

  test("ships the Harness commands panel over the job protocol of the same server", () => {
    const scripts = ofType(".js").map(text).join("\n");
    expect(scripts).toContain("job.catalog");
    expect(scripts).toContain("job.subscribe");
  });

  test("ships the live step list over the steps feed of the same server", () => {
    const scripts = ofType(".js").map(text).join("\n");
    expect(scripts).toContain("steps.subscribe");
    expect(scripts).toContain("структура недоступна");
  });

  test("ships Diagnostics and Harness over the screen snapshots of the same server", () => {
    const scripts = ofType(".js").map(text).join("\n");
    for (const request of ["diagnostics.snapshot", "harness.overview", "harness.maintenance", "snapshot.page"]) {
      expect(scripts).toContain(request);
    }
    // The export is a Blob download: no data: URL, no inline script.
    expect(scripts).toContain("createObjectURL");
    expect(scripts).not.toMatch(/data:application\/json/);
  });

  test("the server's CSP for the build stays strict", () => {
    const source = readFileSync(join(REPO, "harness/console/backend/api/static.py"), "utf-8");
    expect(source).toContain(
      `"default-src 'none'; script-src 'self'; style-src 'self'; font-src 'self'; "`,
    );
    expect(source).toContain(`f"img-src 'self'; connect-src 'self' ws://127.0.0.1:{port}; base-uri 'none'; "`);
    expect(source).not.toMatch(/unsafe-(inline|eval)/);
  });

  test("scripts contain no URL outside the not-loaded allowlist", () => {
    for (const path of ofType(".js")) {
      const foreign = (text(path).match(URL_PATTERN) ?? []).filter(
        (url) => !NOT_LOADED.some((allowed) => allowed.test(url)),
      );
      expect(foreign, path).toEqual([]);
    }
  });
});
