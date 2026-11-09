/* The wording of a ticket status change: the drop targets of a card from the server's moves, the
   refusal captions of the #board mockup and the result line `harness ticket-status` prints. The
   server and the command decide every move; nothing here allows one on its own. */
import type { I18n } from "../i18n";
import type { OutputFragment } from "../ws/jobs";
import type { BoardCard, BoardColumn, BoardMove } from "../ws/taskBoard";

type Translate = I18n["t"];

/** The catalog command of the status change (kernel/catalog.py BOARD_STATUS). */
export const STATUS_COMMAND = "board-status";

/** What `harness ticket-status` prints as its last stdout line. */
export interface StatusResult {
  ticket: string;
  from: string | null;
  to: string;
  result: "changed" | "refused" | "write_error";
  reason: string | null;
  blockers: string[];
  batch: string | null;
  message: string;
}

export const moveOf = (card: BoardCard, to: BoardColumn): BoardMove | undefined =>
  card.moves.find((move) => move.to === to);

/** The drop-target class of a column while `card` is dragged: allowed, refused or its own. */
export function dropClass(card: BoardCard, to: BoardColumn): "drop-ok" | "drop-no" | "" {
  const move = moveOf(card, to);
  if (!move || move.reason === "same") return "";
  return move.allowed ? "drop-ok" : "drop-no";
}

export interface RefusalFacts {
  blockers?: readonly string[];
  batch?: string | null;
  /** The running job of a `busy` refusal. */
  job?: string;
}

/** The caption of a refusal reason, from the server's moves, the command or the job service. */
export function refusalCaption(t: Translate, reason: string | null, facts: RefusalFacts = {}): string {
  switch (reason) {
    case "open_blockers":
      return t("Открыты блокеры: {list}", { list: (facts.blockers ?? []).join(", ") });
    case "active_batch":
      return t("Активный batch {batch}", { batch: facts.batch ?? "" });
    case "busy":
      return t("Занято: {command}", { command: facts.job ?? "" });
    case "write_failed":
      return t("Ошибка записи в трекер: изменение не сохранено");
    case "tracker_unavailable":
      return t("Трекер недоступен: смена статуса не записана");
    case "review_target":
      return t("«Review / QA» вычисляют dispatch и PR; карточку туда не переносят");
    case "done_target":
      return t("«Готово» заполняет закрытие тикета после подтверждённого merge");
    case "closed":
      return t("Закрытый тикет не переносится");
    case "in_review":
      return t("У тикета активный batch или PR");
    case "via_ready":
      return t("Переход идёт через «Готово к работе»");
    case "not_found":
      return t("Тикет не найден в спеке");
    case "ledger_unavailable":
      return t("Леджер оркестрации недоступен: перенос не записан");
    default:
      return t("Смена статуса не выполнена");
  }
}

/** The running job a `busy` refusal names: its command from "Busy: <job> (<command>)", else its id. */
export function busyJob(message: string, jobId: string | null): string {
  const command = /\(([^()]+)\)\s*$/.exec(message)?.[1];
  return command ?? jobId ?? "";
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const RESULTS = ["changed", "refused", "write_error"];

/** The command's result: the last stdout line that parses as its JSON; null without one. */
export function parseStatusResult(output: readonly OutputFragment[]): StatusResult | null {
  const lines = output
    .filter((fragment) => fragment.channel === "stdout")
    .map((fragment) => fragment.text)
    .join("")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  for (const line of lines.reverse()) {
    let value: unknown;
    try {
      value = JSON.parse(line);
    } catch {
      continue;
    }
    if (
      isObject(value) &&
      typeof value.ticket === "string" &&
      typeof value.to === "string" &&
      RESULTS.includes(String(value.result)) &&
      (value.reason === null || typeof value.reason === "string") &&
      Array.isArray(value.blockers) &&
      value.blockers.every((item) => typeof item === "string") &&
      (value.batch === null || typeof value.batch === "string") &&
      typeof value.message === "string"
    ) {
      return value as unknown as StatusResult;
    }
  }
  return null;
}
