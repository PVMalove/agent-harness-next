/* The 13 sections of docs/design/web-console-mockups/navigation-a.md in their three groups. */
import type { IconName } from "./icons";

export interface NavItem {
  /** Hash route without the leading "#/"; Home is the empty route. */
  route: string;
  /** Section key of kernel/i18n.py `_SECTIONS`. */
  section: string;
  icon: IconName;
  /** The mockup's menu caption when it differs from the section title, a catalog key. */
  label?: string;
}

export interface NavGroup {
  /** Russian group title, a key of the translation catalog. */
  label: string;
  items: readonly NavItem[];
}

export const NAV_GROUPS: readonly NavGroup[] = [
  {
    label: "Обзор",
    items: [
      { route: "", section: "Home", icon: "home" },
      { route: "diagnostics", section: "Diagnostics", icon: "pulse" },
      { route: "update-harness", section: "Update Harness", icon: "refresh", label: "Обновление" },
      { route: "open-project", section: "Open project", icon: "folder", label: "Проект" },
    ],
  },
  {
    label: "Работа",
    items: [
      { route: "board", section: "Доска задач", icon: "board" },
      { route: "agent-activity", section: "Ход работы", icon: "activity" },
      { route: "orchestration", section: "Orchestration", icon: "orchestration" },
      { route: "reports", section: "Reports", icon: "reports" },
      { route: "publish", section: "Публикация", icon: "github" },
    ],
  },
  {
    label: "Контекст",
    items: [
      { route: "harness", section: "Harness", icon: "harness" },
      { route: "repo-map", section: "Repo Map", icon: "map" },
      { route: "configuration", section: "Configuration", icon: "settings", label: "Настройки" },
      { route: "help", section: "Help", icon: "help" },
    ],
  },
];

export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** Routes without a menu item, each with the section it belongs to: the TUI opens Recovery and
    Container route from Orchestration, so the Orchestration item stays highlighted. */
export const HIDDEN_ROUTES: Readonly<Record<string, string>> = {
  recovery: "orchestration",
  "container-route": "orchestration",
};

/** The footer captions of the routes without a menu item, catalog keys. */
export const HIDDEN_LABELS: Readonly<Record<string, string>> = {
  recovery: "Восстановление",
  "container-route": "Контейнеры",
};

/** The menu item a route belongs to: its own, a hidden route's owner, else Home. */
export function navItemOf(route: string): NavItem {
  const owner = HIDDEN_ROUTES[route] ?? route;
  return NAV_ITEMS.find((item) => item.route === owner) ?? NAV_ITEMS[0];
}

/** Keyboard shortcuts of the mockup: key -> route. */
export const SHORTCUTS: Readonly<Record<string, string>> = {
  g: "",
  d: "diagnostics",
  o: "orchestration",
  "?": "help",
};

export const href = (route: string): string => `#/${route}`;

/** Routes already built on the design system v3. The other screens render into a main area that
    keeps the old page style (`ds-main--legacy`) until their slice of epic #1090 moves them. */
export const DS_ROUTES: ReadonlySet<string> = new Set<string>(["repo-map", "harness", "help"]);
