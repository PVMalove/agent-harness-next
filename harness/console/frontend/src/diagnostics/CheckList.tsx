/* The Diagnostics check list of the mockup: status filter chips with the report's counts, a search
   over the id, the title, the group and the message, rows sorted by severity. A row names the check
   by its catalog title and its status in words (kernel STATE_LABELS), never the raw id or FAIL/OK. */
import { Icon } from "../icons";
import { groupLabel, useI18n } from "../i18n";
import type { CheckStatus, HealthCheck, HealthReport } from "../ws/screens";

export type CheckFilter = "all" | "problem" | "skipped" | "ok";

export const STATUS_META: Readonly<Record<CheckStatus, { word: string; icon: string; tone: string }>> = {
  fail: { word: "ошибки", icon: "x", tone: "err" },
  warn: { word: "внимание", icon: "warning", tone: "warn" },
  skipped: { word: "пропущено", icon: "clock", tone: "skip" },
  ok: { word: "пройдено", icon: "check", tone: "ok" },
};

const ORDER: Readonly<Record<CheckStatus, number>> = { fail: 0, warn: 1, skipped: 2, ok: 3 };

const inFilter = (check: HealthCheck, filter: CheckFilter): boolean =>
  filter === "all" ||
  (filter === "problem" && (check.status === "fail" || check.status === "warn")) ||
  check.status === filter;

/** The checks of `report` the filter and the query keep, the most severe first, in report order
    within one status. */
export function visibleChecks(
  report: HealthReport,
  filter: CheckFilter,
  query: string,
  group: (id: string) => string,
  title: (id: string) => string = (id) => id,
): HealthCheck[] {
  const needle = query.trim().toLowerCase();
  return report.checks
    .map((check, index) => ({ check, index }))
    .filter(
      ({ check }) =>
        inFilter(check, filter) &&
        (!needle || [check.id, title(check.id), check.group, group(check.group), check.message].join(" ").toLowerCase().includes(needle)),
    )
    .sort((a, b) => ORDER[a.check.status] - ORDER[b.check.status] || a.index - b.index)
    .map(({ check }) => check);
}

export function CheckList({
  report,
  filter,
  query,
  visible,
  selected,
  onFilter,
  onQuery,
  onSelect,
  cli,
}: {
  report: HealthReport;
  filter: CheckFilter;
  query: string;
  visible: readonly HealthCheck[];
  selected: string | null;
  onFilter: (filter: CheckFilter) => void;
  onQuery: (query: string) => void;
  onSelect: (id: string) => void;
  cli: string;
}) {
  const { t, language, state, check: checkName } = useI18n();
  const { summary } = report;
  const counts: Record<CheckFilter, number> = {
    all: report.checks.length,
    problem: summary.fail + summary.warn,
    skipped: summary.skipped,
    ok: summary.ok,
  };
  const chips: [CheckFilter, string][] = [
    ["all", t("Все")],
    ["problem", t("Проблемы")],
    ["skipped", t("Пропущено")],
    ["ok", t("Пройдено")],
  ];
  return (
    <section className="panel diag-list-panel">
      <div className="panel-head">
        <h2>{t("Проверки")}</h2>
        <span className="small muted" id="diag-count">
          {t("{shown} из {total}", { shown: visible.length, total: report.checks.length })}
        </span>
      </div>
      <div className="diag-tools">
        <div className="chips">
          {chips.map(([key, label]) => (
            <button
              key={key}
              className={`chip${filter === key ? " on" : ""}`}
              type="button"
              aria-pressed={filter === key}
              data-diag-filter={key}
              onClick={() => onFilter(key)}
            >
              {label} {counts[key]}
            </button>
          ))}
        </div>
        <label className="diag-search">
          <input
            type="search"
            value={query}
            placeholder={t("Найти проверку")}
            aria-label={t("Найти проверку")}
            onChange={(event) => onQuery(event.target.value)}
          />
        </label>
      </div>
      <div id="diag-list">
        {visible.length === 0 ? (
          <div className="diag-empty">
            <b>{t("Ничего не найдено")}</b>
            <span>{t("Нет проверок для этого фильтра")}</span>
            <button
              className="btn"
              type="button"
              onClick={() => {
                onFilter("all");
                onQuery("");
              }}
            >
              {t("Сбросить")}
            </button>
          </div>
        ) : (
          visible.map((check) => {
            const meta = STATUS_META[check.status];
            return (
              <button
                key={check.id}
                type="button"
                className={`diag-row ${meta.tone}`}
                data-check={check.id}
                aria-pressed={check.id === selected}
                onClick={() => onSelect(check.id)}
              >
                <span className={`diag-status-icon ${meta.tone}`} role="img" aria-label={t(meta.word)}>
                  <Icon name={meta.icon} />
                </span>
                <span className="diag-row-main">
                  <b>{checkName(check.id)}</b>
                  <small>
                    {groupLabel(language, check.group)} · {check.message}
                  </small>
                </span>
                <span className={`diag-pill ${meta.tone}`}>{state(check.status)}</span>
                <span className="diag-chevron">
                  <Icon name="chevron" />
                </span>
              </button>
            );
          })
        )}
      </div>
      <div className="diag-list-foot">
        {t("Полный отчёт")}: <code>{cli}</code>
      </div>
    </section>
  );
}
