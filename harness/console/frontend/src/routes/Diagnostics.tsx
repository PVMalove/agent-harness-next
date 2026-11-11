/* Diagnostics: the `harness health --json` report of the diagnostics.snapshot screen snapshot,
   laid out as the mockup's #diagnostics. Counts come from the report's summary, never recounted.
   The fix commands of the section run as server jobs through the command panel; a finished fix
   job's report (its stdout, with the fixes it applied) replaces the shown one, as in the TUI. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { CheckDetail } from "../diagnostics/CheckDetail";
import { CheckList, visibleChecks } from "../diagnostics/CheckList";
import type { CheckFilter } from "../diagnostics/CheckList";
import { downloadJson, exportName, exportPayload } from "../diagnostics/exportReport";
import { Icon } from "../icons";
import { checkTitle, groupLabel, useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import type { LocalJob } from "../ws/jobs";
import { checkTotal, parseHealthReport } from "../ws/screens";
import type { HealthReport } from "../ws/screens";
import { snapshotClock } from "../update/format";
import { HealthStrip } from "./Home";

/** The catalog commands that run the internal fixers and print the new report. */
export const FIX_COMMANDS: Readonly<Record<string, boolean>> = {
  "diagnostics-fix": false,
  "diagnostics-online-fix": true,
};

const cliLine = (online: boolean) => (online ? "harness health . --online" : "harness health .");

/** The report a finished fix job printed, or null when it has none. */
export function fixReport(job: LocalJob): HealthReport | null {
  if (job.phase !== "completed" || job.returncode === null) return null;
  const stdout = job.output
    .filter((fragment) => fragment.channel === "stdout")
    .map((fragment) => fragment.text)
    .join("");
  try {
    return parseHealthReport(JSON.parse(stdout));
  } catch {
    return null;
  }
}

export function Diagnostics() {
  const { t, section, language } = useI18n();
  const [online, setOnline] = useState(false);
  const screen = useScreen({ type: "diagnostics.snapshot", online }, parseHealthReport);
  const [fixed, setFixed] = useState<HealthReport | null>(null);
  const [fixError, setFixError] = useState<string | null>(null);
  const [request, setRequest] = useState<RunRequest | null>(null);
  const [filter, setFilter] = useState<CheckFilter>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const report = fixed ?? screen.data;
  useEffect(() => {
    if (screen.data) setCheckedAt(new Date());
  }, [screen.data]);

  const group = useCallback((id: string) => groupLabel(language, id), [language]);
  const title = useCallback((id: string) => checkTitle(language, id), [language]);
  const visible = useMemo(
    () => (report ? visibleChecks(report, filter, query, group, title) : []),
    [report, filter, query, group, title],
  );
  const current = visible.find((check) => check.id === selected) ?? visible[0] ?? null;
  const shownOnline = report ? report.online : online;
  const clock = checkedAt ? new Intl.DateTimeFormat(language, { timeStyle: "medium" }).format(checkedAt) : "—";

  const refresh = () => {
    setFixed(null);
    setFixError(null);
    screen.refresh(true);
  };
  const switchMode = (next: boolean) => {
    setFixed(null);
    setFixError(null);
    setOnline(next);
  };
  const fix = () => {
    setFixError(null);
    setRequest({ command_id: shownOnline ? "diagnostics-online-fix" : "diagnostics-fix", values: {}, nonce: Date.now() });
  };
  const onJobDone = (job: LocalJob) => {
    if (!Object.hasOwn(FIX_COMMANDS, job.command_id)) return;
    const next = fixReport(job);
    if (next) {
      setFixed(next);
      setCheckedAt(new Date());
      return;
    }
    setFixError(job.error || t("Отчёт не построен"));
    setFixed(null);
    screen.refresh(true);
  };
  const exportReport = () => {
    if (report) downloadJson(exportName(new Date()), exportPayload(report, filter, query, visible));
  };

  const summary = report?.summary;
  const total = summary ? checkTotal(summary) : 0;
  const groups = report ? new Set(report.checks.map((check) => check.group)).size : 0;
  const counters: [keyof NonNullable<typeof summary>, string, string][] = [
    ["ok", "ok", t("пройдено")],
    ["warn", "warn", t("внимание")],
    ["fail", "err", t("ошибки")],
    ["skipped", "muted", t("пропущено")],
  ];

  return (
    <div className="diag-page" data-section="Diagnostics">
      <div className="page-title diag-title">
        <div>
          <h1>{section("Diagnostics")}</h1>
          <p>{t("Отчёт harness health. Команды «Как исправить» консоль не выполняет — запустите их вручную.")}</p>
          <div className="home-facts">
            <span id="diag-total">{report ? t("{count} проверок", { count: total }) : t("Недоступно в текущем снимке")}</span>
            {report && <span>{t("групп: {count}", { count: groups })}</span>}
            <span id="diag-mode">{shownOnline ? t("онлайн") : t("офлайн")}</span>
            {screen.data && !fixed && (
              <span id="diag-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
                {snapshotClock(screen.ageSeconds, language)}
              </span>
            )}
          </div>
        </div>
        <div className="actions">
          <button id="diag-refresh" className="btn" type="button" onClick={refresh}>
            <Icon name="refresh" /> {t("Проверить")}
          </button>
          <button id="diag-export" className="btn" type="button" disabled={!report} onClick={exportReport}>
            <Icon name="reports" /> {t("Экспорт")}
          </button>
          <a className="btn primary" href={href("update-harness")}>
            {t("Обновление")}
          </a>
        </div>
      </div>

      {screen.error && !report && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}
      {fixError && (
        <p className="command-refusal err" role="alert">
          {t("Исправление не удалось")}: {fixError}
        </p>
      )}

      <section className="panel diag-summary">
        <div className="panel-head">
          <h2>{t("Сводка здоровья")}</h2>
          <div className="health-mode">
            <span className="small muted">{shownOnline ? t("онлайн") : t("офлайн")}</span>
            <div className="seg">
              <button className={online ? "" : "on"} type="button" aria-pressed={!online} onClick={() => switchMode(false)}>
                {t("Офлайн")}
              </button>
              <button className={online ? "on" : ""} type="button" aria-pressed={online} onClick={() => switchMode(true)}>
                {t("Онлайн")}
              </button>
            </div>
          </div>
        </div>
        <div className="body">
          <div className="health-summary">
            {counters.map(([key, tone, label]) => (
              <div className="hs-item" key={key}>
                <span id={`diag-${key}`} className={tone}>
                  {summary ? summary[key] : "—"}
                </span>
                <small>{label}</small>
              </div>
            ))}
          </div>
          {summary ? <HealthStrip health={summary} /> : null}
          <div className="diag-summary-note">
            <span id="diag-checked">
              {clock} ·{" "}
              {summary
                ? t("проверено {checked} из {total}", { checked: total - summary.skipped, total })
                : screen.loading
                  ? t("Отчёт строится…")
                  : t("Недоступно в текущем снимке")}
            </span>
            <span>
              {t("Команды «Как исправить» консоль не выполняет — запустите их вручную.")} <code>{cliLine(shownOnline)}</code>
            </span>
          </div>
        </div>
      </section>

      {report && (
        <div className="diag-grid">
          <CheckList
            report={report}
            filter={filter}
            query={query}
            visible={visible}
            selected={current?.id ?? null}
            onFilter={setFilter}
            onQuery={setQuery}
            onSelect={setSelected}
            cli={cliLine(report.online)}
          />
          <div id="diag-detail">
            <CheckDetail
              check={current}
              cli={cliLine(report.online)}
              online={report.online}
              clock={clock}
              onFix={fix}
            />
          </div>
        </div>
      )}

      {report && report.fixes_applied.length > 0 && (
        <section className="panel diag-fixes" id="diag-fixes">
          <div className="panel-head">
            <h2>{t("Применённые фиксы:")}</h2>
            <span className="small muted">{report.fixes_applied.length}</span>
          </div>
          <ul className="diag-fixes-list">
            {report.fixes_applied.map((text, index) => (
              <li key={index}>{text}</li>
            ))}
          </ul>
        </section>
      )}

      <div className="diag-commands">
        <CommandPanel section="diagnostics" request={request} onJobDone={onJobDone} />
      </div>
    </div>
  );
}
