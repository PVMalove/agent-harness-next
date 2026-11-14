/* Update Harness (#/update-harness): the installed and available versions, the drift counters,
   the three update modes with the plan, the seed files, the runtime-store migration plan, the last
   run result and the file diffs of update_harness.snapshot. The diff of one file at a time is read
   (update_harness.diff): the first file opens without a click, another one once it is clicked.
   «Обновить» runs only through the CommandPanel of the job section `update`, and every run opens
   the confirmation first: cancelling it starts nothing. */
import { Fragment, useEffect, useMemo, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { plural, useI18n } from "../i18n";
import { Icon } from "../icons";
import { href } from "../navigation";
import { useServedRepo } from "../project/format";
import { useConsole } from "../useConsole";
import type { JobSummary } from "../ws/jobs";
import { useScreen } from "../screens/useScreen";
import {
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
  TONE_CLASS,
  TONE_ICONS,
  updateCommand,
} from "../update/format";
import type { DiffFile, MigrationState, UpdateMode } from "../update/format";
import type { UpdateHarnessFacts } from "../ws/projectScreens";
import { parseUpdateDiff, parseUpdateHarness } from "../ws/projectScreens";

const lineClass = (line: string) =>
  line.startsWith("+") && !line.startsWith("+++") ? "diff-line add" : line.startsWith("-") && !line.startsWith("---") ? "diff-line del" : "diff-line";

/** One file's diff, read when it is mounted (a click on the file). */
function DiffPane({ file }: { file: DiffFile }) {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "update_harness.diff", params: { path: file.path } }, parseUpdateDiff);
  const text = screen.data ? diffText(screen.data.text, language) : "";
  return (
    <>
      <div className="diff-detail-head">
        <span className={`diff-status ${TONE_CLASS[file.tone]}`}>
          <Icon name={TONE_ICONS[file.tone]} />
        </span>
        <code>{file.path}</code>
        <span className={`update-pill ${TONE_CLASS[file.tone]}`}>{t(file.tag)}</span>
      </div>
      <p className="diff-explain">{t(file.meaning)}</p>
      {screen.error ? (
        <p className="command-refusal err" role="alert">
          {t("diff недоступен:")} {screen.error.message || screen.error.code}
        </p>
      ) : !screen.data ? (
        <p className="harness-note">{t("загружается…")}</p>
      ) : text ? (
        <pre className="diff-code">
          {text.split("\n").map((line, index) => (
            <span key={index} className={lineClass(line)}>
              {line}
              {"\n"}
            </span>
          ))}
        </pre>
      ) : (
        <p className="harness-note ok">{t("Файл уже совпадает с тем, что запишет обновление.")}</p>
      )}
    </>
  );
}

const STEP_CLASS: Readonly<Record<MigrationState, string>> = { pending: "pending", done: "ready", nodata: "after", after: "after" };
const STEP_LABEL: Readonly<Record<MigrationState, string>> = { pending: "ожидает", done: "выполнено", nodata: "нет данных", after: "после миграции" };

/** «Миграция runtime-store»: the plan read from the project's store facts. The console never
    runs a migration; the coordinator command is shown as text only. */
function MigrationPanel({ facts }: { facts: UpdateHarnessFacts }) {
  const { t } = useI18n();
  const store = facts.store;
  const target = facts.store_target_schema;
  const steps = migrationSteps(store, target, t);
  const none = t("нет данных");
  const cells: [string, string][] = [
    ["authority", store?.authority ?? none],
    ["generation", store?.generation ?? none],
    ["audit", store?.audit_records === null || store?.audit_records === undefined ? none : String(store.audit_records)],
    ["cutover", store?.cutover_at ? store.cutover_at.slice(0, 10) : none],
  ];
  return (
    <section className="panel migration-panel" id="update-migration">
      <div className="panel-head">
        <h2>{t("Миграция runtime-store")}</h2>
        <span className="small muted">{`schema ${store?.schema ?? "?"} → ${target ?? "?"}`}</span>
      </div>
      <div className="body">
        <div className="migration-track">
          {steps.map((step, index) => (
            <Fragment key={step.num}>
              {index > 0 && <span className="migration-arrow" aria-hidden="true">→</span>}
              <div className={`migration-step ${STEP_CLASS[step.state]}`}>
                <span className="migration-num">{step.num}</span>
                <b>{step.title}</b>
                <small>{step.caption}</small>
                {step.num === "04" ? (
                  <a className="migration-state" href={href("diagnostics")}>{t(STEP_LABEL[step.state])}</a>
                ) : (
                  <span className="migration-state">{t(STEP_LABEL[step.state])}</span>
                )}
              </div>
            </Fragment>
          ))}
        </div>
        <div className="migration-facts">
          {cells.map(([label, value]) => (
            <div key={label}>
              <span>{label}</span>
              <b>{value}</b>
            </div>
          ))}
        </div>
        <p className="migration-note">
          {store?.reason ? `${t("нет данных")} · ${store.reason}. ` : ""}
          {t("Миграцию выполняет координатор (ledger migrate); консоль только показывает план и не мигрирует store.")}
        </p>
      </div>
    </section>
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

const PHASE_TONE: Readonly<Record<string, string>> = { completed: "ok", failed: "err", cancelled: "warn", running: "active" };
const PHASE_LABEL: Readonly<Record<string, string>> = { completed: "завершено", failed: "ошибка", cancelled: "отменено", running: "выполняется" };

/** «Результат последнего запуска»: the newest update job of this console, or why there is none. */
function ResultPanel() {
  const { t } = useI18n();
  const jobs = useUpdateJobs();
  const last = jobs.at(-1) ?? null;
  return (
    <section className="panel result-panel" id="update-result">
      <div className="panel-head">
        <h2>{t("Результат последнего запуска")}</h2>
        <span className="small muted">{last ? last.command_id : t("ещё не запускалось")}</span>
      </div>
      {last ? (
        <div className={`result-row ${PHASE_TONE[last.phase] ?? ""}`}>
          <Icon name={last.phase === "completed" ? "check" : last.phase === "running" ? "play" : "x"} />
          <b>{last.command_id}</b>
          <span>{t(PHASE_LABEL[last.phase] ?? last.phase)}</span>
          <span>{last.returncode === null ? "" : `${t("код")} ${last.returncode}`}</span>
          {last.error && <small>{last.error}</small>}
        </div>
      ) : (
        <div className="result-empty">
          <Icon name="terminal" /> {t("Ещё не запускалось в этой консоли · запуски harness update вне консоли не записываются.")}
        </div>
      )}
    </section>
  );
}

export function UpdateHarness() {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "update_harness.snapshot" }, parseUpdateHarness);
  const facts = screen.data;
  const repo = useServedRepo();
  const [mode, setMode] = useState<UpdateMode>("update");
  const [ticked, setTicked] = useState<string[]>([]);
  const [opened, setOpened] = useState<string | null>(null);
  const [request, setRequest] = useState<RunRequest | null>(null);

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

  const run = () => {
    if (!facts || reason !== null) return;
    setRequest({
      command_id: mode,
      values: mode === SEED_MODE ? { paths: selected.join("\n") } : {},
      nonce: Date.now(),
      reason: [command, t(consequence), ...(warning ?? [])].join("\n"),
    });
  };
  const toggle = (path: string) => setTicked(ticked.includes(path) ? ticked.filter((item) => item !== path) : [...ticked, path]);

  return (
    <div className="update-page work-page" data-section="Update Harness">
      <div className="page-title update-title">
        <div>
          <h1>{t("Обновление")}</h1>
          <p>{t("Сначала показываем, что изменится в управляемых файлах. Запуск — только после вашего подтверждения.")}</p>
          {facts && (
            <div className="home-facts">
              {facts.state.installed && (
                <>
                  <span>{`${facts.state.installed_version} → ${facts.package_version}`}</span>
                  <span>{plural(language, facts.state.managed_files, ["управляемый файл", "управляемых файла", "управляемых файлов"], ["managed file", "managed files"])}</span>
                  <span>{plural(language, facts.state.skills, ["навык", "навыка", "навыков"], ["skill", "skills"])}</span>
                  <span>{`schema ${facts.store?.schema ?? "?"} → ${facts.store_target_schema ?? "?"}`}</span>
                </>
              )}
              <span id="update-cache" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
                {clock}
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="update-recheck" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Проверить заново")}
          </button>
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {t("Диагностика")}
          </a>
        </div>
      </div>

      {screen.error && !facts && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {facts && versions && (
        <div className="update-top-grid">
          <section className="panel versions-card" id="update-versions">
            <div className="panel-head">
              <h2>{t("Версии")}</h2>
              {versions.verdict && <span className={`update-pill ${versions.verdict.tone === "ok" ? "ok" : "warn"}`}>{versions.verdict.tone === "ok" ? t("актуально") : t("доступно")}</span>}
            </div>
            <div className="versions-body">
              {versions.missing.map((line, index) => (
                <p key={line} className={`harness-note${index === 0 ? " err" : ""}`}>
                  {index === 0 && <Icon name="x" />} {line}
                </p>
              ))}
              <div className="version-pair">
                {versions.pairs.map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <b>{value}</b>
                  </div>
                ))}
              </div>
              {versions.verdict && (
                <div className={`version-status ${versions.verdict.tone}`}>
                  <Icon name={versions.verdict.tone === "ok" ? "check" : "warning"} /> {versions.verdict.text}
                </div>
              )}
              <dl className="kv version-facts">
                {versions.rows.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
                <div>
                  <dt>Schema</dt>
                  <dd>{`${facts.store?.schema ?? "?"} → ${facts.store_target_schema ?? "?"}`}</dd>
                </div>
              </dl>
            </div>
            <div className="versions-changes" id="update-changes">
              <div className="integrated-head">
                <h3>{t("Что изменится в управляемых файлах")}</h3>
                <span>harness diff</span>
              </div>
              <div className="update-counts">
                {changes.rows.map((row) => (
                  <div className={`update-count-row ${TONE_CLASS[row.tone]}`} key={row.label}>
                    <span className="count-value">{row.count}</span>
                    <span className={`count-icon ${TONE_CLASS[row.tone]}`}>
                      <Icon name={TONE_ICONS[row.tone]} />
                    </span>
                    <span className="count-label">{row.label}</span>
                  </div>
                ))}
                {changes.line && (
                  <div className={`update-count-row ${changes.line.tone ? TONE_CLASS[changes.line.tone] : ""}`}>
                    {changes.line.tone && <Icon name={TONE_ICONS[changes.line.tone]} />} {changes.line.text}
                  </div>
                )}
              </div>
            </div>
            <div className="changes-foot">
              <span>{mode === SEED_MODE ? t("Seed-режим: отметьте файлы в панели Seed-файлы.") : t("Обычный режим сохранит локальные правки.")}</span>
              <button className="btn" type="button" onClick={() => screen.refresh(true)}>
                <Icon name="refresh" /> {t("Проверить заново")}
              </button>
            </div>
          </section>

          <section className="panel modes-card" id="update-modes-card">
            <div className="panel-head">
              <h2>{t("Режим обновления")}</h2>
            </div>
            <div className="update-modes" role="radiogroup" aria-label={t("Режим обновления")}>
              {MODES.map(([key, label]) => {
                const [description, tag, tagTone] = MODE_CARDS[key];
                return (
                  <label key={key} className={`update-mode-card${key === mode ? " on" : ""}`}>
                    <input type="radio" name="update-mode" checked={key === mode} onChange={() => setMode(key)} aria-label={t(label)} />
                    <span className="mode-copy">
                      <b>{t(label)}</b>
                      <small>{t(description)}</small>
                    </span>
                    <span className={`mode-tag ${tagTone}`}>{t(tag)}</span>
                  </label>
                );
              })}
            </div>
            <div className="modes-plan">
              <div className="integrated-head">
                <h3>{t("План")}</h3>
                <span>{t(modeName)}</span>
              </div>
              <div className="update-plan-body">
                <div className="plan-command">
                  <span>$</span>
                  <code id="update-plan-command">{command}</code>
                </div>
                <p className={`modes-foot${tone === "warn" ? " warn" : ""}`} id="update-mode-caption">
                  {t(consequence)}
                </p>
                {warning && (
                  <div className="plan-warning warn" id="update-warning">
                    <Icon name="warning" />
                    <div>
                      <b>{warning[0]}</b>
                      <p>{warning[1]}</p>
                    </div>
                  </div>
                )}
                <p className="plan-explain">
                  {t("Команда перезаписывает файлы харнесса в проекте (управляемые или seed) — незакоммиченные правки в них пропадут.")}{" "}
                  {t("Перед запуском будет запрошено подтверждение.")}
                </p>
                <button id="update-run" className="btn primary update-apply" type="button" disabled={reason !== null} title={reason ? t(reason) : undefined} onClick={run}>
                  <Icon name="download" /> {t("Обновить")}
                </button>
                {reason && <p className="plan-note">{t(reason)}</p>}
              </div>
            </div>
          </section>
        </div>
      )}

      {facts && mode === SEED_MODE && (
        <section className="panel seed-panel" id="update-seeds">
          <div className="panel-head">
            <h2>{t("Seed-файлы")}</h2>
            <span className="small muted" id="update-seed-count">
              {t("отмечено {ticked} из {total}", { ticked: selected.length, total: seeds.length })}
            </span>
          </div>
          <div className="seed-body">
            {seeds.map((path) => (
              <label key={path} className="seed-file">
                <input type="checkbox" checked={selected.includes(path)} onChange={() => toggle(path)} />
                <code>{path}</code>
              </label>
            ))}
            <p className={`seed-warning${seeds.length ? " warn" : " ok"}`}>
              <Icon name={seeds.length ? "warning" : "check"} />{" "}
              {seeds.length ? t("Отмечены файлы, которые будут перезаписаны эталоном; их правки пропадут.") : t("Seed-файлы совпадают с шаблоном — перезаписывать нечего.")}
            </p>
            <div className="seed-actions">
              <button className="btn small" type="button" onClick={() => setTicked(seeds)}>
                {t("Выбрать все")}
              </button>
              <button className="btn small" type="button" onClick={() => setTicked([])}>
                {t("Снять выбор")}
              </button>
            </div>
          </div>
        </section>
      )}

      {facts && (
        <section className="panel diff-panel update-diff-panel" id="update-diff">
          <div className="panel-head">
            <h2>{t("Diff — что изменится в файлах")}</h2>
            <span className="small muted">{`${t("выбор файла")} · ${filesText(files.length, language)} · ${clock}`}</span>
          </div>
          {files.length === 0 ? (
            <p className="harness-note">{t("Расхождений нет: показывать нечего.")}</p>
          ) : (
            <div className="diff-layout">
              <div className="diff-list" role="listbox" aria-label={t("Файлы")}>
                {files.map((item) => (
                  <button
                    key={item.path}
                    type="button"
                    role="option"
                    aria-selected={item.path === file?.path}
                    className={`diff-file${item.path === file?.path ? " on" : ""}`}
                    data-path={item.path}
                    onClick={() => setOpened(item.path)}
                  >
                    <span className={`diff-status ${TONE_CLASS[item.tone]}`}>
                      <Icon name={TONE_ICONS[item.tone]} />
                    </span>
                    <span className="diff-path">{item.path}</span>
                    <span className={`diff-kind ${TONE_CLASS[item.tone]}`}>{t(item.tag)}</span>
                  </button>
                ))}
              </div>
              <div className="diff-detail" id="update-diff-view">
                {file ? <DiffPane key={file.path} file={file} /> : <p className="harness-note">{t("Выберите файл, чтобы увидеть его изменения.")}</p>}
              </div>
            </div>
          )}
        </section>
      )}

      {facts && <MigrationPanel facts={facts} />}
      {facts && <ResultPanel />}

      <CommandPanel section="update" confirmAll listed={false} request={request} onJobDone={() => screen.refresh(true)} />
    </div>
  );
}
