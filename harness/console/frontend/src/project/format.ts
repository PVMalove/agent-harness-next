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

/** Title, one-line description and footer of each catalog capability, as
    kernel/project_target.py words them (`_LABELS` split at « — », `_DETAILS`); the Russian texts
    are translation keys. A capability of harness/CAPABILITIES.json without an entry fails a test. */
export const CAPABILITY_TEXT: Readonly<Record<string, readonly [string, string, string]>> = {
  "project-foundation": [
    "Основа",
    "Небольшой набор инструкций и навыков",
    "Добавляет инструкции и базовые навыки. Не создаёт project.json и orchestration.json; подходит, когда нужен только общий каркас.",
  ],
  "mattpocock-suite": [
    "Upstream",
    "Полный закреплённый набор навыков",
    "Полный закреплённый upstream-набор навыков. Не содержит workflow project.json; подходит, когда нужны только навыки.",
  ],
  "engineering-suite": [
    "Workflow",
    "Задачи, QA и ручная настройка project.json",
    "Workflow задач, QA и code-review; создаёт project.json. Нужен для мастера project.json; без ролей оркестрации.",
  ],
  "backend-orchestration": [
    "Backend",
    "Workflow и роли; добавляет orchestration.json",
    "Всё из workflow плюс роли и координатор; добавляет orchestration.json. Выбирайте для backend-проекта с автоматизацией этапов.",
  ],
};

/** The local check of a typed path: no Git, no .harness, nothing is sent. */
export function pathStatus(path: string): string {
  const typed = path.trim();
  if (!typed) return "Введите путь к проекту";
  if (!typed.startsWith("/") && !typed.startsWith("~")) return "Нужен абсолютный путь";
  return "Путь выглядит корректно · откройте его своей командой";
}

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
