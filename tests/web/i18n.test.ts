import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, test } from "vitest";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import {
  LanguageProvider,
  factLabel,
  initialLanguage,
  useI18n,
  sectionLabel,
  translate,
} from "../../harness/console/frontend/src/i18n";
import { NAV_GROUPS } from "../../harness/console/frontend/src/navigation";

const SRC = resolve(__dirname, "../../harness/console/frontend/src");

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(name) ? [readFileSync(path, "utf-8")] : [];
  });
}

/** Every literal the SPA passes to t(), section() or fact(). */
function declared(call: "t" | "section" | "fact"): Set<string> {
  const pattern = new RegExp(`\\b${call}\\(\\s*("(?:[^"\\\\]|\\\\.)*")`, "g");
  const keys = new Set<string>();
  for (const text of sources(SRC)) {
    for (const match of text.matchAll(pattern)) keys.add(JSON.parse(match[1]!) as string);
  }
  return keys;
}

describe("the translation catalog", () => {
  test("holds every string the SPA declares", () => {
    const strings = declared("t");
    for (const group of NAV_GROUPS) strings.add(group.label);
    expect(strings.size).toBeGreaterThan(5);
    expect([...strings].filter((key) => !(key in catalog.en))).toEqual([]);
    const sections = declared("section");
    for (const group of NAV_GROUPS) for (const item of group.items) sections.add(item.section);
    expect([...sections].filter((key) => !(key in catalog.sections))).toEqual([]);
    expect([...declared("fact")].filter((key) => !(key in catalog.facts))).toEqual([]);
  });

  test("translates with the TUI tables", () => {
    expect(translate("ru", "Разделы консоли")).toBe("Разделы консоли");
    expect(translate("en", "Разделы консоли")).toBe(catalog.en["Разделы консоли"]);
    expect(translate("en", "{count} проверок", { count: 3 })).toBe("3 checks");
    expect(sectionLabel("en", "Home")).toBe("Home");
    expect(sectionLabel("ru", "Home")).toBe("Главная");
    expect(factLabel("en", "Ветка")).toBe("Branch");
    expect(factLabel("ru", "Ветка")).toBe("Ветка");
  });

  test("starts from the URL language, then the stored one, then Russian", () => {
    expect(initialLanguage("#/?lang=en", "ru")).toBe("en");
    expect(initialLanguage("#/", "en")).toBe("en");
    expect(initialLanguage("#/?lang=xx", null)).toBe("ru");
    expect(initialLanguage("", null)).toBe("ru");
  });
});

function Probe() {
  const { t, language, setLanguage } = useI18n();
  return createElement(
    "button",
    { type: "button", onClick: () => setLanguage(language === "ru" ? "en" : "ru") },
    t("Разделы консоли"),
  );
}

test("switching ru and en re-renders without a reload and is remembered", () => {
  const marker = Symbol("same page");
  (window as unknown as Record<symbol, boolean>)[marker] = true;
  render(createElement(LanguageProvider, null, createElement(Probe)));
  expect(document.documentElement.lang).toBe("ru");
  act(() => fireEvent.click(screen.getByRole("button", { name: "Разделы консоли" })));
  expect(screen.getByRole("button").textContent).toBe(catalog.en["Разделы консоли"]);
  expect(document.documentElement.lang).toBe("en");
  expect(localStorage.getItem("harness-console-lang")).toBe("en");
  act(() => fireEvent.click(screen.getByRole("button")));
  expect(screen.getByRole("button").textContent).toBe("Разделы консоли");
  expect((window as unknown as Record<symbol, boolean>)[marker]).toBe(true);
});
