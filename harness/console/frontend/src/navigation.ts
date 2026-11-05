/* The 13 sections of docs/design/web-console-mockups/navigation-a.md in their three groups. */
import type { IconName } from "./icons";

export interface NavItem {
  /** Hash route without the leading "#/"; Home is the empty route. */
  route: string;
  /** Section key of kernel/i18n.py `_SECTIONS`. */
  section: string;
  icon: IconName;
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
      { route: "update-harness", section: "Update Harness", icon: "refresh" },
      { route: "open-project", section: "Open project", icon: "folder" },
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
      { route: "configuration", section: "Configuration", icon: "settings" },
      { route: "help", section: "Help", icon: "help" },
    ],
  },
];

export const NAV_ITEMS: readonly NavItem[] = NAV_GROUPS.flatMap((group) => group.items);

/** Keyboard shortcuts of the mockup: key -> route. */
export const SHORTCUTS: Readonly<Record<string, string>> = {
  g: "",
  d: "diagnostics",
  o: "orchestration",
  "?": "help",
};

export const href = (route: string): string => `#/${route}`;
