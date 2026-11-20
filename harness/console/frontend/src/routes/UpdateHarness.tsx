/* Update Harness (#/update-harness) on the design system v3: the version summary, the files of
   the drift report grouped by what happens to them, the selected file with the tabs Изменения
   (its diff, update_harness.diff) / Решение (what each real update mode does with it), and the
   aside «Как обновить» with the tabs Режим / Seed / План / Миграция. Only facts of
   update_harness.snapshot are shown; a fact the snapshot lacks (per-file line counts, the
   capability of a file, step durations, a pre-release tag) is marked «нет данных».
   «Обновить» runs only through the CommandPanel of the job section `update`, and every run opens
   the confirmation first: cancelling it starts nothing. */
import { useEffect, useMemo, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { PageHeader, Panel, PipeTabs, StatusIcon, Summary, Switch } from "../ds";
import type { Tone as DsTone } from "../ds";
import { NoData } from "../harness/HarnessOverview";
import { plural, useI18n } from "../i18n";
import { Icon } from "../icons";
import { href } from "../navigation";
import { useServedRepo } from "../project/format";
import { useConsole } from "../useConsole";
import type { JobSummary } from "../ws/jobs";
import { useScreen } from "../screens/useScreen";
import { TabPanel } from "../views/Tabs";
import {
  DIFF_KINDS,
  MODES,
  MODE_CARDS,
  MODE_CONSEQUENCES,
  SEED_MODE,
  diffFiles,
  diffText,
  filesText,
  migrationSteps,
  planReason,
  renderDrift,
  renderVersions,
  seedFiles,
  snapshotClock,
  stopWarning,
  updateCommand,
} from "../update/format";
import type { DiffFile, MigrationState, UpdateMode } from "../update/format";
import type { UpdateHarnessFacts } from "../ws/projectScreens";
import { parseUpdateDiff, parseUpdateHarness } from "../ws/projectScreens";

const lineClass = (line: string) =>
  line.startsWith("+") && !line.startsWith("+++") ? "ds-diff-line ds-diff-add" : line.startsWith("-") && !line.startsWith("---") ? "ds-diff-line ds-diff-del" : "ds-diff-line";

/** The ds tone of a drift tone. */
const DS_TONE: Readonly<Record<string, DsTone>> = { ok: "ok", warn: "warn", fail: "err", skipped: "info" };

/** One file's diff, read when it is mounted (a click on the file). */
function DiffPane({ file }: { file: DiffFile }) {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "update_harness.diff", params: { path: file.path } }, parseUpdateDiff);
  const text = screen.data ? diffText(screen.data.text, language) : "";
  return (
    <>
      <p className="ds-note">{t(file.meaning)}</p>
      {screen.error ? (
        <p className="ds-alert ds-alert-err" role="alert">
          {t("diff недоступен:")} {screen.error.message || screen.error.code}
        </p>
      ) : !screen.data ? (
        <p className="ds-empty">{t("загружается…")}</p>
      ) : text ? (
        <pre className="ds-code ds-diff">
          {text.split("\n").map((line, index) => (
            <span key={index} className={lineClass(line)}>
              {line}
              {"\n"}
            </span>
          ))}
        </pre>
      ) : (
        <p className="ds-note">{t("Файл уже совпадает с тем, что запишет обновление.")}</p>
      )}
    </>
  );
}

const STEP_TONE: Readonly<Record<MigrationState, DsTone>> = { pending: "wait", done: "ok", nodata: "info", after: "info" };
const STEP_LABEL: Readonly<Record<MigrationState, string>> = { pending: "ожидает", done: "выполнено", nodata: "нет данных", after: "после миграции" };

/** «Миграция runtime-store»: the plan read from the project's store facts. The console never
    runs a migration; the coordinator command is shown as text only. Step durations are not facts
    of the snapshot. */
function MigrationTab({ facts }: { facts: UpdateHarnessFacts }) {
  const { t } = useI18n();
  const store = facts.store;
  const target = facts.store_target_schema;
  const steps = migrationSteps(store, target, t);
  const none = t("нет данных");
  const cells: [string, string][] = [
    ["schema", `${store?.schema ?? "?"} → ${target ?? "?"}`],
    ["authority", store?.authority ?? none],
    ["generation", store?.generation ?? none],
    ["audit", store?.audit_records === null || store?.audit_records === undefined ? none : String(store.audit_records)],
    ["cutover", store?.cutover_at ? store.cutover_at.slice(0, 10) : none],
  ];
  return (
    <div id="update-migration">
      <ol className="ds-rows ds-steps">
        {steps.map((step) => (
          <li className="ds-row" key={step.num} data-state={step.state}>
            <StatusIcon tone={STEP_TONE[step.state]} label={t(STEP_LABEL[step.state])} />
            <span className="ds-row-main">
              <span className="ds-row-title">
                {step.num} · {step.title}
              </span>
              <span className="ds-row-sub">{step.caption}</span>
            </span>
            <span className="ds-row-end">
              {step.num === "04" ? <a href={href("diagnostics")}>{t(STEP_LABEL[step.state])}</a> : t(STEP_LABEL[step.state])}
            </span>
          </li>
        ))}
      </ol>
      <dl className="ds-kv">
        {cells.map(([label, value]) => (
          <div className="ds-kv-row" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
        <div className="ds-kv-row">
          <dt>{t("Длительность шагов")}</dt>
          <dd>
            <NoData />
          </dd>
        </div>
      </dl>
      <p className="ds-note">
        {store?.reason ? `${t("нет данных")} · ${store.reason}. ` : ""}
        {t("Миграцию выполняет координатор (ledger migrate); консоль только показывает план и не мигрирует store.")}
      </p>
    </div>
  );
}

/** The update jobs of this console server: the list the server keeps for its own jobs. */
function useUpdateJobs(): JobSummary[] {
  const { client } = useConsole();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  useEffect(() => {
    const ids = new Set<string>(MODES.map(([key]) => key));
    const stop = client.subscribeJobs((event) => {
      if (event.type === "jobs") setJobs(event.jobs.filter((job) => ids.has(job.command_id)));
      else if (event.type === "job" && ids.has(event.job.command_id)) {
        const { output: _output, ...summary } = event.job;
        setJobs((known) => [...known.filter((item) => item.id !== summary.id), summary]);
      }
    });
    client.listJobs();
    return stop;
  }, [client]);
  return jobs;
}

const PHASE_TONE: Readonly<Record<string, DsTone>> = { completed: "ok", failed: "err", cancelled: "warn", running: "wait" };
const PHASE_LABEL: Readonly<Record<string, string>> = { completed: "завершено", failed: "ошибка", cancelled: "отменено", running: "выполняется" };

/** «Результат последнего запуска»: the newest update job of this console, or why there is none. */
function LastRun() {
  const { t } = useI18n();
  const jobs = useUpdateJobs();
  const last = jobs.at(-1) ?? null;
  return (
    <div id="update-result">
      <h3 className="ds-group-title">{t("Результат последнего запуска")}</h3>
      {last ? (
        <div className="ds-row" data-phase={last.phase}>
          <StatusIcon tone={PHASE_TONE[last.phase] ?? "info"} label={t(PHASE_LABEL[last.phase] ?? last.phase)} />
          <span className="ds-row-main">
            <code className="ds-row-title">{last.command_id}</code>
            <span className="ds-row-sub">
              {t(PHASE_LABEL[last.phase] ?? last.phase)}
              {last.returncode === null ? "" : ` · ${t("код")} ${last.returncode}`}
              {last.error ? ` · ${last.error}` : ""}
            </span>
          </span>
        </div>
      ) : (
        <p className="ds-note">{t("Ещё не запускалось в этой консоли · запуски harness update вне консоли не записываются.")}</p>
      )}
    </div>
  );
}

type FileTab = "diff" | "decide";
type HowTab = "mode" | "seed" | "plan" | "migration";

export function UpdateHarness() {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "update_harness.snapshot" }, parseUpdateHarness);
  const facts = screen.data;
  const repo = useServedRepo();
  const [mode, setMode] = useState<UpdateMode>("update");
  const [ticked, setTicked] = useState<string[]>([]);
  const [opened, setOpened] = useState<string | null>(null);
  const [request, setRequest] = useState<RunRequest | null>(null);
  const [fileTab, setFileTab] = useState<FileTab>("diff");
  const [howTab, setHowTab] = useState<HowTab>("mode");

  const drift = facts?.drift ?? null;
  const seeds = seedFiles(drift);
  const selected = seeds.filter((path) => ticked.includes(path));
  const files = diffFiles(drift);
  const file = files.find((item) => item.path === opened) ?? files[0] ?? null;
  const clock = useMemo(() => snapshotClock(screen.ageSeconds, language), [screen.data, screen.ageSeconds, language]);
  const command = updateCommand(mode, repo ?? "<repo>", mode === SEED_MODE ? selected : []);
  const reason = facts ? planReason(facts, mode, selected) : null;
  const warning = stopWarning(drift, mode, t, language);
  const [consequence, tone] = MODE_CONSEQUENCES[mode];
  const modeName = MODES.find(([key]) => key === mode)?.[1] ?? "";
  const versions = facts ? renderVersions(facts, t) : null;
  const changes = renderDrift(drift, t);
  const unavailable = t("Недоступно в текущем снимке");
  const state = facts?.state;

  const run = () => {
    if (!facts || reason !== null) return;
    setRequest({
      command_id: mode,
      values: mode === SEED_MODE ? { paths: selected.join("\n") } : {},
      nonce: Date.now(),
      reason: [command, t(consequence), ...(warning ?? [])].join("\n"),
    });
  };
  const toggle = (path: string, on: boolean) =>
    setTicked(on ? [...ticked.filter((item) => item !== path), path] : ticked.filter((item) => item !== path));
  /** «Взять версию пакета» for `item`: a seed file is ticked for the seed mode, any other file
      needs the overwrite of the managed files. «Оставить мой файл»: the seed is unticked, or the
      normal mode keeps the local edits. */
  const take = (item: DiffFile) => {
    if (seeds.includes(item.path)) {
      setMode(SEED_MODE);
      toggle(item.path, true);
    } else {
      setMode("update-force-managed");
    }
    setHowTab("plan");
  };
  const keep = (item: DiffFile) => {
    if (seeds.includes(item.path)) toggle(item.path, false);
    else setMode("update");
    setHowTab("plan");
  };
  const groups = DIFF_KINDS.map(([field, tag, , kindTone]) => [field, tag, kindTone, files.filter((item) => item.field === field)] as const).filter(
    ([, , , items]) => items.length > 0,
  );

  return (
    <div className="ds-page ds-fit" data-section="Update Harness">
      <PageHeader
        title={t("Обновление")}
        subtitle={t("Сначала показываем, что изменится в управляемых файлах. Запуск — только после вашего подтверждения.")}
        actions={
          <>
            <button id="update-recheck" className="ds-btn" type="button" onClick={() => screen.refresh(true)}>
              <Icon name="refresh" className="ds-ic-sm" /> {t("Проверить заново")}
            </button>
            <a className="ds-btn" href={href("diagnostics")}>
              <Icon name="pulse" className="ds-ic-sm" /> {t("Диагностика")}
            </a>
          </>
        }
      />

      {screen.error && !facts && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      <Summary
        id="update-versions"
        label={t("Версии")}
        stats={[
          {
            label: t("Установлено"),
            value: state ? (state.installed ? state.installed_version : "—") : "—",
            caption: versions?.missing[0] ?? (state ? plural(language, state.managed_files, ["управляемый файл", "управляемых файла", "управляемых файлов"], ["managed file", "managed files"]) : unavailable),
          },
          {
            label: t("Доступно"),
            value: facts ? facts.package_version : "—",
            caption: versions?.verdict ? <span className={`ds-verdict-${versions.verdict.tone}`}>{versions.verdict.text}</span> : <NoData />,
          },
          {
            label: t("Расхождения"),
            value: facts ? files.length : "—",
            caption: changes.line ? changes.line.text : changes.rows.map((row) => `${row.count} ${row.label}`).join(" · "),
          },
          {
            label: "Runtime store",
            value: facts ? `schema ${facts.store?.schema ?? "?"} → ${facts.store_target_schema ?? "?"}` : "—",
            caption: facts?.store?.authority ?? <NoData />,
          },
        ]}
        facts={
          facts && state?.installed ? (
            <>
              <span>{`${state.installed_version} → ${facts.package_version}`}</span>
              <span>{plural(language, state.skills, ["навык", "навыка", "навыков"], ["skill", "skills"])}</span>
              {versions?.rows.map(([label, value]) => (
                <span key={label}>
                  {label}: {value}
                </span>
              ))}
              <span>
                pre-release: <NoData />
              </span>
            </>
          ) : undefined
        }
        snapshot={
          facts ? (
            <span id="update-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <Icon name="clock" className="ds-ic-sm" /> {clock}
            </span>
          ) : undefined
        }
      />

      {facts && (
        <div className="ds-update">
          <Panel title={t("Файлы")} count={files.length} fill scroll="list" id="update-diff" label={t("Файлы")} meta={filesText(files.length, language)}>
            {files.length === 0 ? (
              <p className="ds-empty">{t("Расхождений нет: показывать нечего.")}</p>
            ) : (
              <div>
                {groups.map(([field, tag, kindTone, items]) => (
                  <div key={field} data-kind={field}>
                    <h3 className="ds-group-title">
                      {t(tag)} · {items.length}
                    </h3>
                    {items.map((item) => (
                      <button
                        key={item.path}
                        type="button"
                        aria-pressed={item.path === file?.path}
                        className="ds-row ds-row-button ds-diff-file"
                        data-path={item.path}
                        onClick={() => setOpened(item.path)}
                      >
                        <StatusIcon tone={DS_TONE[kindTone]} label={t(item.tag)} />
                        <span className="ds-row-main">
                          <code className="ds-row-title ds-diff-path" title={item.path}>
                            <bdi>{item.path}</bdi>
                          </code>
                        </span>
                        <span className="ds-row-end ds-diff-kind">{t(item.tag)}</span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel
            title={file ? <code>{file.path}</code> : t("Файл")}
            label={t("Файл")}
            fill
            scroll="text"
            id="update-diff-view"
            meta={file ? t(file.tag) : undefined}
          >
            {file ? (
              <div className="ds-update-file">
                <PipeTabs
                  id="update-file"
                  label={t("Файл")}
                  value={fileTab}
                  onChange={(id) => setFileTab(id as FileTab)}
                  tabs={[
                    { id: "diff", label: t("Изменения"), count: "±" },
                    { id: "decide", label: t("Решение"), count: file.field === "conflict" ? "!" : "✓" },
                  ]}
                />
                <TabPanel id="update-file" tab="diff" value={fileTab}>
                    <DiffPane key={file.path} file={file} />
                    <dl className="ds-kv">
                      <div className="ds-kv-row">
                        <dt>{t("Строк +/−")}</dt>
                        <dd>
                          <NoData />
                        </dd>
                      </div>
                      <div className="ds-kv-row">
                        <dt>Capability</dt>
                        <dd>
                          <NoData />
                        </dd>
                      </div>
                    </dl>
                </TabPanel>
                <TabPanel id="update-file" tab="decide" value={fileTab}>
                  <div id="update-decision" className="ds-pad">
                    <p className={file.field === "conflict" ? "ds-alert ds-alert-err" : "ds-note"}>{t(file.meaning)}</p>
                    <div className="ds-actions">
                      <button type="button" className="ds-btn" onClick={() => take(file)}>
                        {t("Взять версию пакета")}
                      </button>
                      <button type="button" className="ds-btn" onClick={() => keep(file)}>
                        {t("Оставить мой файл")}
                      </button>
                    </div>
                    <p className="ds-note">
                      {seeds.includes(file.path)
                        ? t("Seed-файл: «взять версию пакета» отмечает его для перезаписи выбранных seed-файлов, «оставить мой файл» снимает отметку.")
                        : t("«Взять версию пакета» — режим с перезаписью управляемых файлов; «оставить мой файл» — обычное обновление, которое сохраняет правки и останавливается на конфликтах.")}
                    </p>
                  </div>
                </TabPanel>
              </div>
            ) : (
              <p className="ds-empty">{t("Выберите файл, чтобы увидеть его изменения.")}</p>
            )}
          </Panel>

          <Panel title={t("Как обновить")} fill scroll="text" id="update-how" label={t("Как обновить")}>
            <div className="ds-update-how">
              <PipeTabs
                id="update-how"
                label={t("Как обновить")}
                value={howTab}
                onChange={(id) => setHowTab(id as HowTab)}
                tabs={[
                  { id: "mode", label: t("Режим"), count: MODES.findIndex(([key]) => key === mode) + 1 },
                  { id: "seed", label: "Seed", count: mode === SEED_MODE ? selected.length : "–" },
                  { id: "plan", label: t("План") },
                  { id: "migration", label: t("Миграция") },
                ]}
              />
                <TabPanel id="update-how" tab="mode" value={howTab} keepMounted>
                <div className="ds-rows" role="radiogroup" aria-label={t("Режим обновления")} id="update-modes-card">
                  {MODES.map(([key, label]) => {
                    const [description, tag] = MODE_CARDS[key];
                    return (
                      <label key={key} className="ds-row ds-choice" data-on={key === mode}>
                        <input type="radio" name="update-mode" checked={key === mode} onChange={() => setMode(key)} aria-label={t(label)} />
                        <span className="ds-row-main">
                          <span className="ds-row-title">{t(label)}</span>
                          <span className="ds-row-sub">{t(description)}</span>
                        </span>
                        <span className="ds-tag">{t(tag)}</span>
                      </label>
                    );
                  })}
                </div>
                </TabPanel>
                <TabPanel id="update-how" tab="seed" value={howTab} keepMounted>
                <div id="update-seeds">
                  {mode !== SEED_MODE && (
                    <p className="ds-note" id="update-seed-locked">
                      {t("Seed-файлы перезаписывает только режим «С перезаписью выбранных seed-файлов».")}{" "}
                      <button type="button" className="ds-btn ds-btn-sm" onClick={() => setMode(SEED_MODE)}>
                        {t("Выбрать этот режим")}
                      </button>
                    </p>
                  )}
                  <p className="ds-note" id="update-seed-count">
                    {t("отмечено {ticked} из {total}", { ticked: selected.length, total: seeds.length })}
                  </p>
                  <ul className="ds-rows">
                    {seeds.map((path) => (
                      <li key={path} className="ds-row">
                        <Switch checked={selected.includes(path)} onChange={(next) => toggle(path, next)} label={path} disabled={mode !== SEED_MODE} describedBy="update-seed-locked" />
                        <code className="ds-row-main">{path}</code>
                      </li>
                    ))}
                  </ul>
                  <p className={seeds.length ? "ds-alert ds-alert-warn" : "ds-note"}>
                    {seeds.length ? t("Отмечены файлы, которые будут перезаписаны эталоном; их правки пропадут.") : t("Seed-файлы совпадают с шаблоном — перезаписывать нечего.")}
                  </p>
                  <div className="ds-actions">
                    <button className="ds-btn ds-btn-sm" type="button" disabled={mode !== SEED_MODE} onClick={() => setTicked(seeds)}>
                      {t("Выбрать все")}
                    </button>
                    <button className="ds-btn ds-btn-sm" type="button" disabled={mode !== SEED_MODE} onClick={() => setTicked([])}>
                      {t("Снять выбор")}
                    </button>
                  </div>
                </div>
                </TabPanel>
                <TabPanel id="update-how" tab="plan" value={howTab} keepMounted>
                <div id="update-plan">
                  <h3 className="ds-group-title">
                    {t("План")} · {t(modeName)}
                  </h3>
                  <pre className="ds-code">
                    <code id="update-plan-command">{command}</code>
                  </pre>
                  <p className={tone === "warn" ? "ds-alert ds-alert-warn" : "ds-note"} id="update-mode-caption">
                    {t(consequence)}
                  </p>
                  {warning && (
                    <div className="ds-alert ds-alert-warn" id="update-warning">
                      <div>
                        <b>{warning[0]}</b>
                        <p>{warning[1]}</p>
                      </div>
                    </div>
                  )}
                  <div id="update-changes">
                    <h3 className="ds-group-title">{t("Что изменится в управляемых файлах")}</h3>
                    <ul className="ds-rows">
                      {changes.rows.map((row) => (
                        <li className="ds-row ds-update-count" data-tone={row.tone} key={row.label}>
                          <StatusIcon tone={DS_TONE[row.tone]} label={row.label} />
                          <b>{row.count}</b>
                          <span className="ds-row-main">{row.label}</span>
                        </li>
                      ))}
                      {changes.line && <li className="ds-row">{changes.line.text}</li>}
                    </ul>
                  </div>
                  <LastRun />
                </div>
                </TabPanel>
              <TabPanel id="update-how" tab="migration" value={howTab} keepMounted>
                <MigrationTab facts={facts} />
              </TabPanel>
            </div>
            <div className="ds-panel-foot">
              <span className="ds-note">
                {t("Команда перезаписывает файлы харнесса в проекте (управляемые или seed) — незакоммиченные правки в них пропадут.")}{" "}
                {t("Перед запуском будет запрошено подтверждение.")}
              </span>
              {reason && <span className="ds-note">{t(reason)}</span>}
              <button id="update-run" className="ds-btn ds-btn-primary" type="button" disabled={reason !== null} title={reason ? t(reason) : undefined} onClick={run}>
                <Icon name="download" className="ds-ic-sm" /> {t("Обновить")}
              </button>
            </div>
          </Panel>
        </div>
      )}

      <div className="ds-legacy-island">
        <CommandPanel section="update" confirmAll listed={false} request={request} onJobDone={() => screen.refresh(true)} />
      </div>
    </div>
  );
}
