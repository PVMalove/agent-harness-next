import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, test } from "vitest";
import catalog from "../../harness/console/frontend/src/i18n/catalog.json";
import {
  LanguageProvider,
  checkTitle,
  factLabel,
  plural,
  stateLabel,
  groupLabel,
  initialLanguage,
  reasonText,
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

  test("words cleanup reasons and check groups with the server's tables", () => {
    expect(reasonText("ru", "")).toBe("Можно удалить");
    expect(reasonText("en", "")).toBe(catalog.en["Можно удалить"]);
    expect(reasonText("ru", "worktree has uncommitted changes")).toBe(catalog.reasons["worktree has uncommitted changes"]);
    expect(reasonText("en", "worktree has uncommitted changes")).toBe("worktree has uncommitted changes");
    expect(reasonText("ru", "a reason the table lacks")).toBe("a reason the table lacks");
    expect(groupLabel("ru", "hooks")).toBe(catalog.groups.hooks);
    expect(groupLabel("en", "hooks")).toBe(catalog.en[catalog.groups.hooks as keyof typeof catalog.en]);
    expect(groupLabel("en", "unknown-group")).toBe("unknown-group");
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

describe("states, check titles and plurals", () => {
  test("a raw state is worded in both languages", () => {
    expect(stateLabel("ru", "abandoned")).toBe("Брошен");
    expect(stateLabel("ru", "working")).toBe("Выполняется");
    expect(stateLabel("ru", "awaiting_approval")).toBe("Ждёт решения");
    expect(stateLabel("en", "abandoned")).toBe("Abandoned");
    expect(stateLabel("ru", "WARN")).toBe("Внимание");
  });

  test("a check shows its title, not its id", () => {
    expect(checkTitle("ru", "files.skill_snapshot")).toBe("Снимок навыков");
    expect(checkTitle("en", "files.skill_snapshot")).toBe("Skill snapshot");
    expect(checkTitle("ru", "memory.index")).not.toContain("memory.");
  });

  test("Russian counters take the right plural form", () => {
    const forms = ["ошибка", "ошибки", "ошибок"] as const;
    const en = ["error", "errors"] as const;
    expect([1, 2, 5, 11, 12, 21, 22, 25, 101, 111].map((n) => plural("ru", n, forms, en))).toEqual([
      "1 ошибка", "2 ошибки", "5 ошибок", "11 ошибок", "12 ошибок", "21 ошибка", "22 ошибки", "25 ошибок",
      "101 ошибка", "111 ошибок",
    ]);
    expect(plural("en", 1, forms, en)).toBe("1 error");
    expect(plural("en", 3, forms, en)).toBe("3 errors");
  });
});
