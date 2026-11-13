/* Task Board wording and the client-side filters. The columns, the card order and the prompt are
   the server's; a field the snapshot lacks is worded "нет данных". */
import type { I18n } from "../i18n";
import type { BoardCard, BoardColumn } from "../ws/taskBoard";

type Translate = I18n["t"];

export const SPEC_KEY = "harness-console-board-spec";

/** The column names and hints of the #board mockup. */
export function columnLabels(t: Translate): Readonly<Record<BoardColumn, { name: string; hint: string }>> {
  return {
    backlog: { name: t("Бэклог"), hint: t("blocked / без статуса") },
    ready: { name: t("Готово к работе"), hint: "status::ready" },
    progress: { name: t("В работе"), hint: "status::in-progress" },
    review: { name: t("Review / QA"), hint: t("dispatch или PR") },
    done: { name: t("Готово"), hint: t("закрыт после merge") },
  };
}

/** The label of a `TRACKER_FAILURES` reason; an unknown reason keeps its id. */
export function trackerReason(t: Translate, reason: string): string {
  switch (reason) {
    case "not_configured":
      return t("Трекер не настроен");
    case "tool_missing":
      return t("CLI трекера не установлен");
    case "timeout":
      return t("Трекер не ответил вовремя");
    case "auth":
      return t("Нет доступа к трекеру");
    case "failed":
      return t("Трекер вернул ошибку");
    case "bad_output":
      return t("Трекер вернул непонятный ответ");
    case "not_found":
      return t("Трекер не нашёл данные");
    default:
      return reason;
  }
}

/** The age of a snapshot in whole seconds, minutes or hours; null is "нет данных". */
export function ageText(t: Translate, seconds: number | null): string {
  if (seconds === null) return t("нет данных");
  const s = Math.floor(seconds);
  if (s < 60) return t("{n} с", { n: s });
  if (s < 3600) return t("{n} мин", { n: Math.floor(s / 60) });
  return t("{n} ч", { n: Math.floor(s / 3600) });
}

/** An http(s) link of the tracker, or null: any other scheme is never rendered as a link. */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const protocol = new URL(url).protocol;
    return protocol === "http:" || protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}

export const firstLine = (text: string): string => text.split("\n").find((line) => line.trim()) ?? "";

/** "P0" of `priority::p0`; empty without a priority. */
export const priorityLabel = (card: BoardCard): string =>
  card.priority ? card.priority.replace("priority::", "").toUpperCase() : "";

/** The way a ticket is implemented, from the command the server derives from its labels
    (`launch_command`): `/fast-implement` for pipeline::fast, `/to-guide` for human-in-the-loop. */
export type ImplementationKind = "fast" | "full" | "guide";

export function implementationKind(card: BoardCard): ImplementationKind {
  if (card.command.includes("fast-implement")) return "fast";
  if (card.command.includes("to-guide")) return "guide";
  return "full";
}

export function implementationLabel(t: Translate, kind: ImplementationKind): string {
  return { fast: t("быстрая"), full: t("полная"), guide: t("с человеком") }[kind];
}

/** The blocker badges of a card: the open ones by id (at most `shown`), then how many more. */
export function blockerBadges(card: BoardCard, shown = 3): { ids: string[]; more: number } {
  const open = card.blockers.filter((blocker) => blocker.state === "open").map((blocker) => blocker.id);
  return { ids: open.slice(0, shown), more: Math.max(0, card.open_blockers - Math.min(shown, open.length)) };
}

export interface BoardFilters {
  query: string;
  priority: string;
  free: boolean;
}

export const NO_FILTERS: BoardFilters = { query: "", priority: "all", free: false };

/** Whether a card passes the search, priority and "only without blockers" filters. */
export function visible(card: BoardCard, filters: BoardFilters): boolean {
  if (filters.priority !== "all" && card.priority !== filters.priority) return false;
  if (filters.free && card.open_blockers > 0) return false;
  const query = filters.query.trim().toLowerCase();
  if (!query) return true;
  const haystack = [
    card.id,
    card.title,
    card.what,
    ...card.labels,
    ...card.blockers.flatMap((blocker) => [blocker.id, blocker.why]),
    ...card.files.map((file) => file.path),
  ]
    .join("\n")
    .toLowerCase();
  return haystack.includes(query);
}
