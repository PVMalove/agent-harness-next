/* The colour theme of the console: the system scheme by default, or a theme the viewer pinned.
   The sheets hold every colour as light-dark(light, dark); a pinned theme only sets data-theme on
   <html>, and the CSS turns it into color-scheme. The choice lives in this browser only. */
import type { IconName } from "./icons";

export type Theme = "system" | "light" | "dark";

const THEME_KEY = "harness-console-theme";

/** The switch steps through the three themes in this order. */
export const NEXT_THEME: Record<Theme, Theme> = { system: "light", light: "dark", dark: "system" };

export const THEME_LABEL: Record<Theme, string> = {
  system: "Тема: как в системе",
  light: "Тема: светлая",
  dark: "Тема: тёмная",
};

export const THEME_ICON: Record<Theme, IconName> = { system: "contrast", light: "sun", dark: "moon" };

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

/** Pins the theme on <html>, or hands it back to the system scheme, and remembers the choice. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  try {
    if (theme === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* Storage is optional: the theme still applies for this page. */
  }
}
