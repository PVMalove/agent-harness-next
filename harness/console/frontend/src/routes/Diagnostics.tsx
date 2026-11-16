/* Diagnostics on the design system v3 with two tabs. «Функции»: the Harness feature registry of
   features.snapshot (FeaturesView). «Проверки»: the `harness health --json` report of the
   diagnostics.snapshot screen snapshot; counts come from the report's summary, never recounted.
   The fix commands of the section run as server jobs through the command panel; a finished fix
   job's report (its stdout, with the fixes it applied) replaces the shown one, as in the TUI.
   The diagnostics command panel is mounted only in the Checks tab. */
import { useCallback, useEffect, useMemo, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { CheckDetail } from "../diagnostics/CheckDetail";
import { CheckList, visibleChecks } from "../diagnostics/CheckList";
import type { CheckFilter } from "../diagnostics/CheckList";
import { downloadJson, exportName, exportPayload } from "../diagnostics/exportReport";
import { FeaturesView } from "../diagnostics/FeaturesView";
import { PageHeader, Panel, PipeTabs, Summary } from "../ds";
import { Icon } from "../icons";
import { checkTitle, groupLabel, useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import type { LocalJob } from "../ws/jobs";
import { parseFeatures } from "../ws/features";
import { checkTotal, parseHealthReport } from "../ws/screens";
import type { HealthReport } from "../ws/screens";
import { snapshotClock } from "../update/format";
import { TabPanel } from "../views/Tabs";

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

type Tab = "features" | "checks";

export function Diagnostics() {
  const { t, section, language } = useI18n();
  const [tab, setTab] = useState<Tab>("features");
  const [online, setOnline] = useState(false);
  const screen = useScreen({ type: "diagnostics.snapshot", online }, parseHealthReport);
  const features = useScreen({ type: "features.snapshot" }, parseFeatures);
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
    features.refresh(true);
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
  const counters: [keyof NonNullable<typeof summary>, string][] = [
    ["ok", t("пройдено")],
    ["warn", t("внимание")],
    ["fail", t("ошибки")],
    ["skipped", t("пропущено")],
  ];
  const snapshot = features.data;

  return (
    <div className="ds-page ds-fit" data-section="Diagnostics">
      <PageHeader
        title={section("Diagnostics")}
        subtitle={t("Состояние функций Harness и отчёт harness health. Команды «Как исправить» консоль не выполняет — запустите их вручную.")}
        actions={
          <>
            <button id="diag-refresh" className="ds-btn" type="button" onClick={refresh}>
              <Icon name="refresh" className="ds-ic-sm" /> {t("Проверить")}
            </button>
            <button id="diag-export" className="ds-btn" type="button" disabled={!report} onClick={exportReport}>
              <Icon name="reports" className="ds-ic-sm" /> {t("Экспорт")}
            </button>
            <a className="ds-btn ds-btn-primary" href={href("update-harness")}>
              {t("Обновление")}
            </a>
          </>
        }
      />

      <PipeTabs
        id="diagnostics"
        label={section("Diagnostics")}
        value={tab}
        onChange={(id) => setTab(id as Tab)}
        tabs={[
          { id: "features", label: t("Функции"), count: snapshot ? snapshot.features.length : "—" },
          { id: "checks", label: t("Проверки"), count: summary ? total : "—" },
        ]}
      />

      <TabPanel id="diagnostics" tab="features" value={tab} className="ds-tabpanel">
        {features.error && !snapshot && (
          <p className="ds-alert ds-alert-err" role="alert" data-code={features.error.code}>
            {t("Функции недоступны")}: {features.error.message || features.error.code}
          </p>
        )}
        {snapshot ? (
          <FeaturesView snapshot={snapshot} />
        ) : (
          !features.error && <p className="ds-empty">{t("Функции загружаются…")}</p>
        )}
      </TabPanel>

      <TabPanel id="diagnostics" tab="checks" value={tab} className="ds-tabpanel">
        {screen.error && !report && (
          <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
            {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
          </p>
        )}
        {fixError && (
          <p className="ds-alert ds-alert-err" role="alert">
            {t("Исправление не удалось")}: {fixError}
          </p>
        )}
        <Summary
          id="diag-summary"
          label={t("Сводка здоровья")}
          stats={counters.map(([key, label]) => ({
            label,
            value: <span id={`diag-${key}`}>{summary ? summary[key] : "—"}</span>,
          }))}
          facts={
            <>
              <span id="diag-total">{report ? t("{count} проверок", { count: total }) : t("Недоступно в текущем снимке")}</span>
              {report && <span>{t("групп: {count}", { count: groups })}</span>}
              <span id="diag-checked">
                {clock} ·{" "}
                {summary
                  ? t("проверено {checked} из {total}", { checked: total - summary.skipped, total })
                  : screen.loading
                    ? t("Отчёт строится…")
                    : t("Недоступно в текущем снимке")}
              </span>
              <span className="ds-filter" role="group" aria-label={t("Режим проверки")}>
                <button type="button" aria-pressed={!online} onClick={() => switchMode(false)}>
                  {t("Офлайн")}
                </button>
                <button type="button" aria-pressed={online} onClick={() => switchMode(true)}>
                  {t("Онлайн")}
                </button>
              </span>
              <span id="diag-mode">{shownOnline ? t("онлайн") : t("офлайн")}</span>
              <code>{cliLine(shownOnline)}</code>
            </>
          }
          snapshot={
            screen.data && !fixed ? (
              <span id="diag-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
                <Icon name="clock" className="ds-ic-sm" /> {snapshotClock(screen.ageSeconds, language)}
              </span>
            ) : undefined
          }
        />

        {report && (
          <div className="ds-diag-checks">
            <Panel title={t("Проверки")} count={<span id="diag-count">{t("{shown} из {total}", { shown: visible.length, total: report.checks.length })}</span>} fill scroll="list" id="diag-checks" label={t("Список проверок")}>
              <div className="ds-legacy-island">
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
                  bare
                />
              </div>
            </Panel>
            <Panel title={t("Детали проверки")} fill scroll="text" id="diag-detail-panel" label={t("Детали проверки")}>
              <div id="diag-detail" className="ds-legacy-island">
                <CheckDetail
                  check={current}
                  cli={cliLine(report.online)}
                  online={report.online}
                  clock={clock}
                  onFix={fix}
                />
                {report.fixes_applied.length > 0 && (
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
            </Panel>
          </div>
        )}
      </TabPanel>
    </div>
  );
}
