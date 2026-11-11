/* Wording of the Open Project page, mirroring harness/console/tui/screens/project_setup.py
   (`_STAGES`, `_ACTION_WORDS`, `_target_summary`) and the POSIX command line of
   kernel/open_project_snapshot.py `open_command`. The plan and candidate facts are the server's;
   tests/web/fixtures/open-project-facts.json pins the texts to the TUI's. */
import { useScreen } from "../screens/useScreen";
import { parseOpenProject } from "../ws/projectScreens";
import type { ProjectTarget, SetupAction } from "../ws/projectScreens";

/** The five stages of the TUI wizard. */
export const STAGES = [
  "Выбор проекта",
  "Предварительные проверки",
  "Установка / внедрение",
  "Настройка",
  "Итоговая диагностика",
] as const;

export const ACTION_WORDS: Readonly<Record<SetupAction, string>> = {
  update: "обновление",
  init: "новая установка",
  adopt: "внедрение",
};

/** The capability the TUI preselects. */
export const DEFAULT_CAPABILITY = "engineering-suite";

const SAFE = /^[A-Za-z0-9_@%+=:,./-]+$/;

/** Python `shlex.quote`. */
export function shellQuote(text: string): string {
  if (text === "") return "''";
  if (SAFE.test(text)) return text;
  return `'${text.replace(/'/g, `'"'"'`)}'`;
}

/** Python `shlex.join`. */
export const shellJoin = (argv: readonly string[]): string => argv.map(shellQuote).join(" ");

/** The command that starts the Web console in the project at `path`; the browser only shows it. */
export const openCommand = (path: string): string => shellJoin(["harness", "console", "--web", path]);

/** The name of a project directory, as Python's `Path(path).name or path`. */
export const projectName = (path: string): string => path.replace(/\/+$/, "").split("/").pop() || path;

/** The plan summary of a checked project: its kind and its two lines (`_target_summary`), each
    phrase worded by `t` as the TUI translates it. */
export function targetSummary(
  target: ProjectTarget,
  t: (text: string) => string = (text) => text,
): { kind: "warning" | "accepted"; first: string; facts: string } {
  const first = `${t("Git-проект найден · действие:")} ${t(ACTION_WORDS[target.action])}`;
  let facts: string;
  if (target.action === "update") {
    facts = `${t("harness.lock есть · установлено:")} ${target.capabilities.join(", ") || t("нет")}`;
  } else if (target.action === "adopt") {
    facts = `${t("Найдено:")} ${target.found.join(", ")} ${t("— конфликты разберите до установки.")}`;
  } else {
    facts = t("Файлов Harness в проекте нет.");
  }
  return { kind: target.action === "adopt" ? "warning" : "accepted", first, facts };
}

/** The installation command of the plan (`installation_entry(...).cli_argv`). */
export const installCommand = (target: ProjectTarget, capability: string): string =>
  shellJoin(["harness", target.action, target.repo, "--capability", capability]);

/** The path of the project the server serves, from its Open Project facts; null until known. */
export function useServedRepo(): string | null {
  return useScreen({ type: "open_project.snapshot" }, parseOpenProject).data?.repo ?? null;
}
