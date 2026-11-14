/* Wording of the Update Harness page, ported from the pure renderers of
   harness/console/tui/screens/update_harness.py (`MODES`, `_MODE_CONSEQUENCES`, `_DRIFT_ROWS`,
   `_DIFF_KINDS`, `render_versions`, `version_verdict`, `render_drift`, `_stop_warning`,
   `_plan_reasons`, `_plural`). Every version and counter is the server's; the Russian strings are
   the TUI's and are the translation keys. tests/web/fixtures/update-harness-facts.json pins them. */
import type { Language } from "../i18n";
import type { UpdateHarnessFacts } from "../ws/projectScreens";
import type { StoreFacts } from "../ws/types";
import { shellJoin } from "../project/format";

type Translate = (text: string) => string;
export type Tone = "ok" | "warn" | "fail" | "skipped";
export const ICONS: Readonly<Record<Tone, string>> = { ok: "✔", warn: "⚠", fail: "✖", skipped: "○" };

export const SEED_MODE = "update-seed-selected";
export type UpdateMode = "update" | "update-force-managed" | typeof SEED_MODE;
export const MODES: readonly (readonly [UpdateMode, string])[] = [
  ["update", "Обычное"],
  ["update-force-managed", "С перезаписью управляемых файлов"],
  [SEED_MODE, "С перезаписью выбранных seed-файлов"],
];
export const MODE_CONSEQUENCES: Readonly<Record<UpdateMode, readonly [string, Tone | null]>> = {
  update: ["Локальные правки сохраняются. Остановится на конфликтах.", null],
  "update-force-managed": ["⚠ Заменит и конфликтные файлы версией пакета: ваши правки в них пропадут.", "warn"],
  [SEED_MODE]: ["Только отмеченные seed-файлы; остальное не меняется.", null],
};
/** The mockup mode cards: (mode, short description, tag, tag tone). */
export const MODE_CARDS: Readonly<Record<UpdateMode, readonly [string, string, "ok" | "err" | "active"]>> = {
  update: ["Локальные правки сохраняются; стоп на конфликтах.", "рекомендуется", "ok"],
  "update-force-managed": ["Заменит управляемые и конфликтные файлы; правки пропадут.", "опасно", "err"],
  [SEED_MODE]: ["Только отмеченные seed-файлы.", "выборочно", "active"],
};
/** The mockup icon of a drift tone (count rows and diff list). */
export const TONE_ICONS: Readonly<Record<Tone, string>> = { ok: "check", warn: "warning", fail: "x", skipped: "info" };
export const TONE_CLASS: Readonly<Record<Tone, string>> = { ok: "ok", warn: "warn", fail: "err", skipped: "muted" };
const DRIFT_ROWS: readonly (readonly [string, string, Tone])[] = [
  ["package_changed", "обновятся", "ok"],
  ["added", "добавятся", "ok"],
  ["missing", "будут восстановлены", "warn"],
  ["retired", "будут убраны", "warn"],
  ["local_changed", "с локальными правками (сохранятся)", "warn"],
  ["conflict", "в конфликте (нужна перезапись)", "fail"],
];
/** The files the diff block lists: (field, tag, what happens to the file, tone). */
export const DIFF_KINDS: readonly (readonly [string, string, string, Tone])[] = [
  ["conflict", "конфликт", "Изменён и у вас, и в пакете: обычное обновление остановится, перезапись заменит файл версией пакета.", "fail"],
  ["package_changed", "обновится", "Файл будет заменён версией из пакета.", "ok"],
  ["added", "добавится", "Новый файл пакета: будет добавлен.", "ok"],
  ["missing", "восстановится", "Файла нет на диске: он будет восстановлен.", "warn"],
  ["retired", "удалится", "Файла больше нет в пакете: он будет удалён.", "warn"],
  ["local_changed", "ваши правки", "Ваши локальные правки: обычное обновление их сохранит.", "warn"],
  ["seed_differing", "seed", "Seed-файл отличается от шаблона: обновление его не трогает, пока не выбрана перезапись.", "warn"],
];

/** A drift field is a list of paths; a bare number is also accepted (`_count`). */
export function driftCount(value: unknown): number {
  if (Array.isArray(value)) return value.length;
  return Number.isSafeInteger(value) ? (value as number) : 0;
}

/** `count` with its noun: Russian one/few/many forms, English singular/plural (`_plural`). */
export function plural(language: Language, count: number, ru: readonly [string, string, string], en: readonly [string, string]): string {
  if (language === "en") return `${count} ${count === 1 ? en[0] : en[1]}`;
  const last = count % 10;
  const tens = count % 100;
  const form = last === 1 && tens !== 11 ? ru[0] : last >= 2 && last <= 4 && !(tens >= 12 && tens <= 14) ? ru[1] : ru[2];
  return `${count} ${form}`;
}
export const conflictsText = (count: number, language: Language) =>
  plural(language, count, ["конфликт", "конфликта", "конфликтов"], ["conflict", "conflicts"]);
export const filesText = (count: number, language: Language) =>
  plural(language, count, ["файл", "файла", "файлов"], ["file", "files"]);

export interface VersionsView {
  installed: boolean;
  /** Not installed: the two lines of why; installed: empty. */
  missing: string[];
  pairs: (readonly [string, string])[];
  verdict: { tone: Tone; text: string } | null;
  rows: (readonly [string, string])[];
}

/** Installed against available version with the verdict and the set (`render_versions`). */
export function renderVersions(facts: UpdateHarnessFacts, t: Translate): VersionsView {
  const state = facts.state;
  if (!state.installed) {
    return {
      installed: false,
      missing: [t("Харнесс не установлен: нет читаемого .harness/harness.lock"), t("Установите его через «Открыть проект».")],
      pairs: [],
      verdict: null,
      rows: [],
    };
  }
  const current = state.installed_version === facts.package_version;
  return {
    installed: true,
    missing: [],
    pairs: [
      [t("Установлено"), state.installed_version],
      [t("Доступно"), facts.package_version],
    ],
    verdict: current ? { tone: "ok", text: t("Версия актуальна") } : { tone: "warn", text: t("Доступно обновление") },
    rows: [
      [t("Состав"), state.capabilities.join(", ") || t("нет")],
      [t("Скилов"), String(state.skills)],
      [t("Управляемых файлов"), String(state.managed_files)],
      [t("Lock обновлён"), state.updated_at],
    ],
  };
}

export interface DriftRow {
  count: number;
  tone: Tone;
  label: string;
}

/** What an update would touch, from the drift counters (`render_drift`): the rows, or one line. */
export function renderDrift(drift: Record<string, unknown> | null, t: Translate): { rows: DriftRow[]; line: { tone: Tone | null; text: string } | null } {
  if (drift === null) {
    return { rows: [], line: { tone: "fail", text: t("Не удалось проверить дрейф") } };
  }
  const rows = DRIFT_ROWS.filter(([field]) => driftCount(drift[field])).map(([field, label, tone]) => ({
    count: driftCount(drift[field]),
    tone,
    label: t(label),
  }));
  if (rows.length) return { rows, line: null };
  if (drift.state === "clean") return { rows, line: { tone: "ok", text: t("Расхождений нет") } };
  return { rows, line: { tone: null, text: `${t("Состояние:")} ${String(drift.state ?? t("неизвестно"))}` } };
}

/** A normal update stops on conflicts: said in the plan (`_stop_warning`, wide terminal). */
export function stopWarning(drift: Record<string, unknown> | null, mode: UpdateMode, t: Translate, language: Language): readonly [string, string] | null {
  const conflicts = driftCount(drift?.conflict);
  if (!conflicts || mode !== "update") return null;
  return [
    `${t("Обычное обновление остановится:")} ${conflictsText(conflicts, language)}`,
    t("Выберите режим с перезаписью или разберите файл вручную (см. diff ниже)."),
  ];
}

/** Why «Обновить» is unavailable, or null (`_plan_reasons` without the busy console). */
export function planReason(facts: UpdateHarnessFacts, mode: UpdateMode, selected: readonly string[]): string | null {
  if (!facts.state.installed) return "Harness не установлен";
  if (mode === SEED_MODE && selected.length === 0) return "Отметьте хотя бы один файл";
  return null;
}

/** The CLI line the mode runs (`entry.cli_line`, `seed_update_entry`). */
export function updateArgv(mode: UpdateMode, repo: string, seeds: readonly string[]): string[] {
  if (mode === "update-force-managed") return ["harness", "update", repo, "--force-managed-files"];
  if (mode === SEED_MODE) return ["harness", "update", repo, ...seeds.flatMap((path) => ["--force-seed-file", path])];
  return ["harness", "update", repo];
}
export const updateCommand = (mode: UpdateMode, repo: string, seeds: readonly string[]) => shellJoin(updateArgv(mode, repo, seeds));

export interface DiffFile {
  path: string;
  field: string;
  tag: string;
  meaning: string;
  tone: Tone;
}

/** The listed files in the TUI order: by kind, sorted, each file once (`_fill_diff_files`). */
export function diffFiles(drift: Record<string, unknown> | null): DiffFile[] {
  const seen = new Set<string>();
  const files: DiffFile[] = [];
  for (const [field, tag, meaning, tone] of DIFF_KINDS) {
    const paths = drift?.[field];
    if (!Array.isArray(paths)) continue;
    for (const path of paths.filter((item): item is string => typeof item === "string").sort()) {
      if (seen.has(path)) continue;
      seen.add(path);
      files.push({ path, field, tag, meaning, tone });
    }
  }
  return files;
}

/** The diff text in `language`: the English headers name the project and the update. */
export function diffText(text: string, language: Language): string {
  if (language !== "en") return text;
  return text.replace("--- проект/", "--- project/").replace("+++ после обновления/", "+++ after update/");
}

/** The seed files of the drift report. */
export function seedFiles(drift: Record<string, unknown> | null): string[] {
  const paths = drift?.seed_differing;
  return Array.isArray(paths) ? paths.filter((item): item is string => typeof item === "string") : [];
}

/** The wall-clock time of a snapshot `ageSeconds` old, as the mockup's `HH:MM:SS`. */
export function snapshotClock(ageSeconds: number | null, language: Language, now: number = Date.now()): string {
  return new Intl.DateTimeFormat(language, { timeStyle: "medium", hour12: false }).format(new Date(now - (ageSeconds ?? 0) * 1000));
}

export type MigrationState = "pending" | "done" | "nodata" | "after";
export interface MigrationStep {
  num: string;
  title: string;
  caption: string;
  state: MigrationState;
}

/** The four steps of the runtime-store migration plan (`migration-track` of the mockup) from the
    project's store facts; the console only shows the plan and never runs a migration. */
export function migrationSteps(store: StoreFacts | null, target: number | null, t: Translate): MigrationStep[] {
  const from = store?.schema ?? null;
  const schema = `Schema ${from ?? "?"} → ${target ?? "?"}`;
  const migrated = store?.authority === "runtime-store";
  if (migrated) {
    return [
      { num: "01", title: "Backup", caption: t("факт резервной копии в указателе не хранится"), state: "nodata" },
      { num: "02", title: `Schema ${from ?? "?"}`, caption: t("схема runtime-store"), state: "done" },
      { num: "03", title: "Cutover", caption: store?.cutover_at ? store.cutover_at.slice(0, 16).replace("T", " ") : t("время cutover не записано"), state: "done" },
      { num: "04", title: "Health", caption: t("harness health после миграции"), state: "after" },
    ];
  }
  return [
    { num: "01", title: "Backup", caption: t("копия runtime.db до записи"), state: "pending" },
    { num: "02", title: schema, caption: `schema ${from ?? "?"} → ${target ?? "?"}`, state: "pending" },
    { num: "03", title: "Cutover", caption: "authority runtime-store", state: "pending" },
    { num: "04", title: "Health", caption: t("harness health после миграции"), state: "after" },
  ];
}
