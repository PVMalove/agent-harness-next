/* The filtered stage list of the Reports page as the mockup's report rows: the role icon, the
   role and ticket over the short id and outcome, the status words in their tone, and the time.
   Every field is untrusted ledger text, rendered as text. */
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { roleIcon } from "../steps/ActivityViews";
import type { ReportHead, StageHead } from "../ws/ledger";
import { kindTone, shortId, stageStatus, statusWords, timestamp } from "./format";
import type { StageFilters } from "./format";

const two = (value: number) => String(value).padStart(2, "0");
/** The mockup's report time: HH:MM of the stage, UTC as the ledger records it. */
export const clockTime = (at: string) => {
  const date = timestamp(at);
  return date ? `${two(date.getUTCHours())}:${two(date.getUTCMinutes())}` : "—";
};

const TEXT_FILTERS: [keyof StageFilters, string][] = [
  ["ticket", "тикет"],
  ["role", "роль"],
  ["outcome", "outcome"],
  ["date", "дата (2026-09-27)"],
  ["state", "статус стадии"],
];

export function StageFilterBar({ filters, onChange }: { filters: StageFilters; onChange: (next: StageFilters) => void }) {
  const { t } = useI18n();
  return (
    <div className="report-filters" id="report-filters">
      <div className="report-filter-row">
        {TEXT_FILTERS.map(([key, label]) => (
          <input
            key={key}
            id={`filter-${key}`}
            type="search"
            aria-label={t(label)}
            placeholder={t(label)}
            value={String(filters[key])}
            onChange={(event) => onChange({ ...filters, [key]: event.target.value })}
          />
        ))}
      </div>
      <div className="report-filter-row">
        <select
          id="filter-completion"
          aria-label={t("Все стадии")}
          value={filters.completion}
          onChange={(event) => onChange({ ...filters, completion: event.target.value as StageFilters["completion"] })}
        >
          <option value="all">{t("Все стадии")}</option>
          <option value="open">{t("Незавершённые")}</option>
          <option value="finished">{t("Завершённые")}</option>
        </select>
        <select
          id="sort-field"
          aria-label={t("По времени")}
          value={filters.sortBy}
          onChange={(event) => onChange({ ...filters, sortBy: event.target.value as StageFilters["sortBy"] })}
        >
          <option value="time">{t("По времени")}</option>
          <option value="ticket">{t("По тикету")}</option>
          <option value="role">{t("По роли")}</option>
          <option value="state">{t("По статусу")}</option>
        </select>
        <select
          id="sort-direction"
          aria-label={t("По убыванию")}
          value={filters.descending ? "desc" : "asc"}
          onChange={(event) => onChange({ ...filters, descending: event.target.value === "desc" })}
        >
          <option value="desc">{t("По убыванию")}</option>
          <option value="asc">{t("По возрастанию")}</option>
        </select>
      </div>
    </div>
  );
}

export function StageList({
  stages,
  reports,
  selected,
  onSelect,
}: {
  stages: readonly StageHead[];
  reports: Map<string, ReportHead>;
  selected: string | null;
  onSelect: (dispatchId: string) => void;
}) {
  const { t, language } = useI18n();
  if (!stages.length) return <p className="report-empty">{t("Ничего не найдено")}</p>;
  return (
    <div id="report-list" className="report-list">
      {stages.map((stage) => {
        const report = stage.report === null ? undefined : reports.get(stage.report);
        const status = stageStatus(stage, report);
        return (
          <button
            key={stage.dispatch_id}
            type="button"
            className={`report-row${stage.dispatch_id === selected ? " on" : ""}`}
            data-stage={stage.dispatch_id}
            aria-pressed={stage.dispatch_id === selected}
            onClick={() => onSelect(stage.dispatch_id)}
          >
            <span className="report-type-icon">
              <Icon name={roleIcon(stage.role)} />
            </span>
            <span className="report-row-main">
              <b>
                {stage.role} · {stage.ticket || "—"}
              </b>
              <small>
                {shortId(stage.dispatch_id, "dispatch-")} · {stage.batch_id || "—"} · {report?.outcome || stage.state}
              </small>
            </span>
            <span className={`report-status ${kindTone(status.kind)}`}>{statusWords(status, language)}</span>
            <span className="report-time">{clockTime(stage.at)}</span>
          </button>
        );
      })}
    </div>
  );
}
