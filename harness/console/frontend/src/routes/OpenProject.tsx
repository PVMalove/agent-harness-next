/* Open Project (#/open-project): the project this console server serves, its installation plan
   and the candidate projects of open_project.snapshot. The server is bound to one project and the
   page never asks it to switch: another project opens with its own command in a terminal, which
   the page only shows and copies. A typed path is turned into that command in the browser and is
   sent nowhere. The only change the page can start is the installation into the served project,
   through the CommandPanel of the job section `setup`, and every run opens the confirmation first. */
import { Fragment, useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { href } from "../navigation";
import {
  ACTION_WORDS,
  CAPABILITY_TEXT,
  DEFAULT_CAPABILITY,
  STAGES,
  installCommand,
  openCommand,
  pathStatus,
  projectName,
  targetSummary,
} from "../project/format";
import { useScreen } from "../screens/useScreen";
import type { LocalJob } from "../ws/jobs";
import { parseOpenProject } from "../ws/projectScreens";
import type { Candidate, OpenProjectFacts } from "../ws/projectScreens";
import { useConsole } from "../useConsole";
import { healthTotal } from "../ws/types";
import type { HomeSnapshot } from "../ws/types";

/** The capability shown first: the installed one with blockers known, else the default, else the
    first the server lists. */
function firstCapability(facts: OpenProjectFacts): string {
  const known = Object.keys(facts.blockers);
  const installed = facts.target?.capabilities.find((name) => known.includes(name));
  return installed ?? (known.includes(DEFAULT_CAPABILITY) ? DEFAULT_CAPABILITY : (known[0] ?? DEFAULT_CAPABILITY));
}

interface FlowNode {
  icon: string;
  label: string;
  value: string;
  sub: string;
  tone: "ok" | "warn" | "active" | "pending" | "after";
}

type Translate = (text: string, values?: Record<string, string | number>) => string;

/** The mockup «Схема внедрения»: project → harness → capability → runtime → health. Runtime and
    health come from the Home snapshot of the same server; without it they say so. */
function flowNodes(facts: OpenProjectFacts, home: HomeSnapshot | null, chosen: string, blocked: number, t: Translate): FlowNode[] {
  const target = facts.target;
  const store = home?.store ?? null;
  const health = home?.health ?? null;
  const total = health ? healthTotal(health) : 0;
  const installed = home?.harness?.installed ? home.harness.installed_version : null;
  return [
    {
      icon: "folder",
      label: "Проект",
      value: projectName(facts.repo),
      sub: target ? t("Git-проект найден") : t(facts.error.split("\n")[0] || "нет данных"),
      tone: target ? "ok" : "warn",
    },
    {
      icon: "harness",
      label: "Harness",
      value: installed && home ? `${installed} → ${home.harness_version}` : t("не установлен"),
      sub: target ? t(ACTION_WORDS[target.action]) : "—",
      tone: target?.action === "update" ? "ok" : "warn",
    },
    {
      icon: "settings",
      label: "Capability",
      value: chosen,
      sub: blocked ? t("заблокировано: {n}", { n: blocked }) : t(CAPABILITY_TEXT[chosen]?.[1] ?? "готово к установке"),
      tone: blocked ? "warn" : "active",
    },
    store && store.authority !== "none"
      ? {
          icon: "store",
          label: "Runtime",
          value: `schema ${store.schema ?? "?"}`,
          sub: `${store.generation ?? t("нет данных")} · audit ${store.audit_records ?? t("нет данных")}`,
          tone: "pending",
        }
      : { icon: "store", label: "Runtime", value: t("нет данных"), sub: t(store ? "в проекте нет состояния оркестрации" : "снимок Home ещё не получен"), tone: "pending" },
    {
      icon: "pulse",
      label: "Health",
      value: health && total ? t("{ok}/{total} пройдено", { ok: health.ok, total }) : t("после установки"),
      sub: t("проверки — на странице «Диагностика»"),
      tone: "after",
    },
  ];
}

function Stepper({ stage }: { stage: number }) {
  const { t } = useI18n();
  return (
    <div className="install-steps" id="open-project-steps" tabIndex={0} role="region" aria-label={t("Шаги установки")}>
      <div className="install-steps-track">
        {STAGES.map((name, index) => (
          <Fragment key={name}>
            <span className={`install-step ${index < stage ? "done" : index === stage ? "active" : "pending"}`}>
              <Icon name={index < stage ? "check" : index === stage ? "play" : "clock"} />
              {t(name)}
            </span>
            {index < STAGES.length - 1 && <i className="install-sep">—</i>}
          </Fragment>
        ))}
      </div>
      <span className="install-step-count">{t("Шаг {current} из {total}", { current: stage + 1, total: STAGES.length })}</span>
    </div>
  );
}

function useCopy(): [string, (text: string) => void] {
  const [copied, setCopied] = useState("");
  const copy = (text: string) => {
    void navigator.clipboard?.writeText(text).then(
      () => setCopied(text),
      () => setCopied(""),
    );
  };
  return [copied, copy];
}

type CheckState = "ok" | "warn" | "fail" | "skip";
const CHECK_ICON: Readonly<Record<CheckState, string>> = { ok: "check", warn: "warning", fail: "x", skip: "clock" };
const CHECK_WORD: Readonly<Record<CheckState, string>> = { ok: "пройдено", warn: "внимание", fail: "ошибка", skip: "не проверено" };

function ProjectCheck({ label, state, text }: { label: string; state: CheckState; text: string }) {
  const { t } = useI18n();
  return (
    <div className="project-check">
      <span className={`project-check-icon ${state}`}>
        <Icon name={CHECK_ICON[state]} />
      </span>
      <span className="project-check-main">
        <b>{label}</b>
        <small>{text}</small>
      </span>
      <span className={`project-check-state ${state}`}>{t(CHECK_WORD[state])}</span>
    </div>
  );
}

const TRACKER_ICON: Readonly<Record<string, string>> = { github: "github-mark", gitlab: "gitlab-mark" };
const TRACKER_NAME: Readonly<Record<string, string>> = { github: "GitHub", gitlab: "GitLab" };

/** «Детали проекта». The facts of the served project come from its Home and Open Project
    snapshots; another candidate is only listed, so what the snapshots do not read says so. */
function CandidateDetail({ item, facts, home, copied, onCopy }: { item: Candidate; facts: OpenProjectFacts; home: HomeSnapshot | null; copied: string; onCopy: (text: string) => void }) {
  const { t, plural } = useI18n();
  const tracker = home?.project?.tracker ?? "";
  const notRead = t("нет данных · снимок читает только проект этого сервера");
  const install = home?.harness ?? null;
  const drift = home?.drift_counts ?? null;
  const health = home?.health ?? null;
  const target = facts.target;
  const checks: { label: string; state: CheckState; text: string }[] = item.current
    ? [
        { label: "Git repository", state: target ? "ok" : "fail", text: target ? item.path : t(facts.error || "путь не является Git-репозиторием") },
        { label: "Harness config", state: item.installed ? "ok" : "warn", text: item.installed ? t(".harness/project.json найден") : t("Harness не установлен") },
        { label: "Capability", state: install?.capability_names.length ? "ok" : "skip", text: install?.capability_names.join(", ") || t("нет данных") },
        {
          label: "Skills snapshot",
          state: drift === null || install === null ? "skip" : drift.total ? "warn" : "ok",
          text: install && drift ? t("{skills} навыков · drift {drift}", { skills: install.skills, drift: drift.total }) : t("нет данных · дрейф не прочитан"),
        },
        {
          label: t("Локальные правки управляемых файлов"),
          state: drift === null ? "skip" : drift.local_changed ? "warn" : "ok",
          text: drift === null ? t("нет данных · дрейф не прочитан") : drift.local_changed ? t("{n} файлов с локальными правками", { n: drift.local_changed }) : t("нет локальных правок"),
        },
      ]
    : [
        { label: "Git repository", state: "skip", text: notRead },
        { label: "Harness config", state: item.installed ? "ok" : "warn", text: item.installed ? t("Harness установлен") : t("Harness не установлен") },
        { label: "Capability", state: "skip", text: notRead },
        { label: "Skills snapshot", state: "skip", text: notRead },
        { label: t("Локальные правки управляемых файлов"), state: "skip", text: notRead },
      ];
  return (
    <section className="panel project-detail-panel" id="open-project-detail">
      <div className="panel-head">
        <h2>{t("Детали проекта")}</h2>
        <span className={`project-pill ${item.current ? "ok" : "muted"}`}>{t(item.current ? "Открыт" : "Не открыт")}</span>
      </div>
      <div className="project-detail-body">
        <div className="project-detail-top">
          {item.current && tracker ? (
            <span className="project-provider">
              <Icon name={TRACKER_ICON[tracker] ?? "folder"} /> {TRACKER_NAME[tracker] ?? tracker}
            </span>
          ) : (
            <span className="project-provider">
              <Icon name="folder" /> {item.current ? t("трекер не определён") : t("локальный путь")}
            </span>
          )}
          <code>harness</code>
        </div>
        <h3>{projectName(item.path)}</h3>
        <code className="project-path">{item.path}</code>
        <div className="project-meta">
          {item.current && home?.project ? (
            <>
              <span>
                <Icon name="branch" /> {home.project.branch ?? "—"}
              </span>
              <span>
                <Icon name="harness" /> {install?.installed ? install.installed_version : t("не установлен")}
              </span>
              <span>
                {health
                  ? `${plural(health.fail, ["ошибка", "ошибки", "ошибок"], ["error", "errors"])} · ${health.warn} ${t("внимание")}`
                  : t("health не проверен")}
              </span>
            </>
          ) : (
            <span>{item.installed ? t("Harness установлен") : t("Harness не установлен")}</span>
          )}
        </div>
        <div className="project-checks">
          {checks.map((check) => (
            <ProjectCheck key={check.label} {...check} />
          ))}
        </div>
        <div className="project-command">
          <div className="project-command-head">
            <span>{t("Команда для другой консоли")}</span>
            <button className="btn" type="button" id="open-project-copy" disabled={item.current} onClick={() => onCopy(item.command)}>
              <Icon name="download" /> {t("Копировать")}
            </button>
          </div>
          <code id="open-project-command">{item.command}</code>
          {copied === item.command && (
            <p className="project-hint" role="status">
              {t("Команда скопирована")}
            </p>
          )}
        </div>
        <div className="project-actions">
          {item.current ? (
            <button className="btn" type="button" disabled>
              {t("Уже открыт")}
            </button>
          ) : null}
          <span className="project-note">
            {item.current ? t("Этот проект уже открыт этим сервером") : t("Другой проект открывается своей командой в терминале; сервер не переключается.")}
          </span>
        </div>
      </div>
    </section>
  );
}

export function OpenProject() {
  const { t, section } = useI18n();
  const { snapshot: home, client } = useConsole();
  const [online, setOnline] = useState(false);
  const [checked, setChecked] = useState("");
  const screen = useScreen({ type: "open_project.snapshot" }, parseOpenProject);
  const facts = screen.data;
  const [selected, setSelected] = useState<string | null>(null);
  const [capability, setCapability] = useState<string | null>(null);
  const [path, setPath] = useState("");
  const [copied, copy] = useCopy();
  const [request, setRequest] = useState<RunRequest | null>(null);
  const [installed, setInstalled] = useState(false);

  const target = facts?.target ?? null;
  const candidates = facts?.candidates ?? [];
  const shown = candidates.find((item) => item.path === selected) ?? candidates.find((item) => item.current) ?? candidates[0] ?? null;
  const chosen = facts ? (capability !== null && capability in facts.blockers ? capability : firstCapability(facts)) : DEFAULT_CAPABILITY;
  const blocked = facts?.blockers[chosen] ?? [];
  const summary = target ? targetSummary(target, t) : null;
  const stage = target === null ? 0 : installed ? 3 : 1;
  const typed = path.trim();
  const reason = target === null ? t(facts?.error || "План появится после проверки пути.") : blocked.length ? t("заблокировано: {n}", { n: blocked.length }) : "";
  const health = home?.health ?? null;
  const total = health ? healthTotal(health) : 0;
  const run = health ? health.ok + health.warn + health.fail : 0;
  const tracker = home?.project?.tracker ?? "";
  const mode = (next: boolean) => {
    setOnline(next);
    client.requestHome({ force: true, online: next });
  };

  const install = () => {
    if (!target || blocked.length) return;
    setRequest({
      command_id: `setup-${target.action}`,
      values: { capability: chosen },
      nonce: Date.now(),
      reason: `${installCommand(target, chosen)}\n${t("Перезаписывает только управляемые файлы Harness.")}`,
    });
  };
  const onJobDone = (job: LocalJob) => {
    if (job.phase === "completed" && job.returncode === 0) setInstalled(true);
    screen.refresh(true);
  };

  return (
    <div className="project-page work-page" data-section="Open project">
      <div className="page-title project-title">
        <div>
          <h1>{t("Проект")}</h1>
          <p>{t("Сервер консоли обслуживает один проект; другой проект открывается своей командой в терминале.")}</p>
          {facts && (
            <div className="home-facts" id="open-project-facts" title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <span>{home?.project?.name ?? projectName(facts.repo)}</span>
              <span>{home?.project?.branch ?? t("ветка неизвестна")}</span>
              <span>{home?.harness?.installed ? home.harness.installed_version : t("Harness не установлен")}</span>
            </div>
          )}
        </div>
        <div className="actions">
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {section("Diagnostics")}
          </a>
        </div>
      </div>

      <Stepper stage={stage} />

      {screen.error && !facts && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {facts && (
        <section className="panel current-project" id="open-project-current">
          <div className="current-project-icon">
            <Icon name="folder" />
          </div>
          <div className="current-project-main">
            <span className="eyebrow">{t("Текущий проект")}</span>
            <h2>{home?.project?.name ?? projectName(facts.repo)}</h2>
            <code>{facts.repo}</code>
            {target ? (
              <div className="current-project-meta">
                <Icon name="branch" /> {home?.project?.branch ?? t("ветка неизвестна")} · <Icon name={TRACKER_ICON[tracker] ?? "folder"} />{" "}
                {TRACKER_NAME[tracker] ?? (tracker || t("трекер не определён"))}
              </div>
            ) : (
              <p className="command-refusal err">{t(facts.error)}</p>
            )}
          </div>
          <div className="current-project-stats" id="open-project-kpi">
            <div>
              <span>Harness</span>
              <b>{home?.harness?.installed ? home.harness.installed_version : "—"}</b>
            </div>
            <div>
              <span>{t("Скиллов")}</span>
              <b>{home?.harness?.skills || "—"}</b>
            </div>
            <div>
              <span>Managed</span>
              <b>{home?.harness?.managed_files || "—"}</b>
            </div>
            <div>
              <span>Health</span>
              <b>{health && total ? `${health.ok}/${total}` : "—"}</b>
            </div>
          </div>
        </section>
      )}

      {facts && (
        <div className="project-grid">
          <div className="project-left">
            <section className="panel projects-panel" id="open-project-list">
              <div className="panel-head">
                <h2>{t("Проекты")}</h2>
                <span className="small muted">{t("{count} найдено", { count: candidates.length })}</span>
              </div>
              <div className="project-list" role="listbox" aria-label={t("Проекты")}>
                {candidates.length === 0 && <p className="harness-note">{t("Проектов для открытия не найдено")}</p>}
                {candidates.map((item) => (
                  <button
                    key={item.path}
                    type="button"
                    role="option"
                    aria-selected={item.path === shown?.path}
                    className={`project-row${item.path === shown?.path ? " on" : ""}`}
                    data-path={item.path}
                    onClick={() => setSelected(item.path)}
                  >
                    <span className="project-row-icon">
                      <Icon name="folder" />
                    </span>
                    <span className="project-row-main">
                      <b>{projectName(item.path)}</b>
                      <small>{item.path}</small>
                      <small>
                        {item.current && home?.project && home.harness?.installed
                          ? `${home.project.branch ?? "—"} · ${home.harness.installed_version}`
                          : item.installed
                            ? t("Harness установлен")
                            : t("Harness не установлен")}
                      </small>
                    </span>
                    <span className={`project-pill ${item.current ? "ok" : "muted"}`}>{t(item.current ? "Открыт" : "Не открыт")}</span>
                  </button>
                ))}
              </div>
              <div className="project-list-foot">{t("Выберите проект, чтобы увидеть проверки справа.")}</div>
            </section>
            <section className="panel project-path-panel" id="open-project-path">
              <div className="panel-head">
                <h2>{t("Путь к другому проекту")}</h2>
                <span className="small muted">{t("без чтения Git")}</span>
              </div>
              <div className="project-path-body">
                <label className="field">
                  {t("Путь к локальному Git-проекту")}
                  <input value={path} placeholder="/home/…/project" onChange={(event) => setPath(event.target.value)} />
                </label>
                <button className="btn" type="button" onClick={() => setChecked(t(pathStatus(path)))}>
                  <Icon name="check" /> {t("Проверить путь")}
                </button>
              </div>
              {typed && (
                <div className="project-command">
                  <div className="project-command-head">
                    <span>{t("Команда для другой консоли")}</span>
                    <button className="btn" type="button" id="open-project-path-copy" onClick={() => copy(openCommand(typed))}>
                      <Icon name="download" /> {t("Копировать команду")}
                    </button>
                  </div>
                  <code id="open-project-path-command">{openCommand(typed)}</code>
                  {copied === openCommand(typed) && (
                    <p className="project-hint" role="status">
                      {t("Команда скопирована")}
                    </p>
                  )}
                </div>
              )}
              <div className="project-path-info">
                <span id="open-project-path-status" role="status">{checked}</span>
                <span className="project-hint">{t("Проверка пути не читает Git и .harness: команда открывает проект своим сервером.")}</span>
              </div>
            </section>
          </div>
          {shown && <CandidateDetail item={shown} facts={facts} home={home} copied={copied} onCopy={copy} />}
        </div>
      )}

      {facts && (
        <section className="panel install-flow-panel" id="open-project-flow">
          <div className="panel-head">
            <h2>{t("Схема внедрения")}</h2>
            <span className="small muted">{t("путь проекта → harness → capability → runtime → health")}</span>
          </div>
          <div className="install-flow">
            {flowNodes(facts, home, chosen, blocked.length, t).map((node, index, nodes) => (
              <Fragment key={node.label}>
                <div className={`install-flow-node ${node.tone}`}>
                  <span className="install-flow-num">{String(index + 1).padStart(2, "0")}</span>
                  <span className="install-flow-icon">
                    <Icon name={node.icon} />
                  </span>
                  <b>{node.label}</b>
                  <span className="install-flow-value" data-flow-cap={node.label === "Capability" ? "" : undefined}>
                    {node.value}
                  </span>
                  <small>{node.sub}</small>
                </div>
                {index < nodes.length - 1 && <span className="install-flow-arrow">→</span>}
              </Fragment>
            ))}
          </div>
        </section>
      )}

      {facts && (
        <div className="install-bottom-grid">
          <section className="panel install-plan" id="open-project-plan">
            <div className="panel-head">
              <h2>{t("План установки")}</h2>
              {target && <span className="update-pill warn">{t(ACTION_WORDS[target.action])}</span>}
            </div>
            <div className="install-plan-body">
              {target && summary ? (
                <>
                  <p className={`install-plan-summary ${summary.kind === "warning" ? "warn" : "ok"}`}>
                    <b>{summary.first}</b> <span>{summary.facts}</span>
                  </p>
                  <dl className="install-plan-facts">
                    <div>
                      <dt>{t("Проект")}</dt>
                      <dd>{projectName(target.repo)}</dd>
                    </div>
                    <div>
                      <dt>{t("Состав")}</dt>
                      <dd>{`${CAPABILITY_TEXT[chosen] ? t(CAPABILITY_TEXT[chosen]![0]) : "Capability"} (${chosen})`}</dd>
                    </div>
                    <div>
                      <dt>{t("Конфликты")}</dt>
                      <dd className={blocked.length ? "err" : target.conflicts.length ? "warn" : "ok"}>
                        {blocked.length ? t("заблокировано: {n}", { n: blocked.length }) : target.conflicts.length ? target.conflicts.join(", ") : t("нет")}
                      </dd>
                    </div>
                  </dl>
                  {target.conflicts.length > 0 && <p className="plan-warning">{t("Force/replace не включены. При конфликте операция остановится.")}</p>}
                  <div className="install-command-label">{t("Команда")}</div>
                  <pre id="open-project-install-command" className="install-command">
                    {installCommand(target, chosen)}
                  </pre>
                </>
              ) : (
                <p className="harness-note">{reason}</p>
              )}
              <div className="install-plan-actions">
                <button id="open-project-install" className="btn primary" type="button" disabled={!target || blocked.length > 0} title={reason || undefined} onClick={install}>
                  <Icon name="download" /> {t("Установить")}
                </button>
                <span>{reason || t("Потребуется подтверждение")}</span>
              </div>
            </div>
          </section>
          <section className="panel install-capabilities" id="open-project-capability">
            <div className="panel-head">
              <h2>{t("Состав Harness")}</h2>
              <span className="small muted">{t("что будет установлено")}</span>
            </div>
            <div className="cap-list" role="radiogroup" aria-label={t("Состав Harness")}>
              {Object.entries(facts.blockers).map(([name, paths]) => {
                const [title, description] = CAPABILITY_TEXT[name] ?? [name, ""];
                return (
                  <label key={name} className={`cap-row${name === chosen ? " on" : ""}`}>
                    <input type="radio" name="open-project-capability" aria-label={`${t(title)} (${name})`} checked={name === chosen} onChange={() => setCapability(name)} />
                    <span className="cap-copy">
                      <b>{t(title)}</b>
                      {target?.capabilities.includes(name) && <span className="cap-status">{t("установлено")}</span>}
                      <small>{description ? t(description) : name}</small>
                      {paths.length > 0 && (
                        <small className="cap-blocked">
                          <Icon name="x" /> {t("заблокировано: {n}", { n: paths.length })}
                        </small>
                      )}
                    </span>
                  </label>
                );
              })}
            </div>
            <p className="cap-footer">{CAPABILITY_TEXT[chosen] ? t(CAPABILITY_TEXT[chosen]![2]) : chosen}</p>
            {blocked.length > 0 && (
              <div className="plan-warning" id="open-project-blockers">
                <p>{t("Установка заблокирована; проверьте собственные/изменённые пути:")}</p>
                <ul>
                  {blocked.map((item) => (
                    <li key={item}>
                      <code>{item}</code>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
          <section className="panel install-checks" id="open-project-checks">
            <div className="panel-head">
              <h2>{t("Проверки")}</h2>
              <span className="small muted">{health ? t("{run} из {total} проверено", { run, total }) : t("нет данных")}</span>
            </div>
            <div className="install-checks-body">
              <div className="install-check-actions">
                <button className={`chip${online ? "" : " on"}`} type="button" aria-pressed={!online} onClick={() => mode(false)}>
                  {t("Офлайн")}
                </button>
                <button className={`chip${online ? " on" : ""}`} type="button" aria-pressed={online} onClick={() => mode(true)}>
                  {t("Онлайн")}
                </button>
                <a className="btn" href={href("diagnostics")}>
                  <Icon name="pulse" /> {t("Исправить")}
                </a>
                <a className="btn" href={href("configuration")}>
                  <Icon name="settings" /> {t("Настройка")}
                </a>
              </div>
              {health ? (
                <>
                  <div className="install-health">
                    <span className="ok">
                      <Icon name="check" /> {t("{n} пройдено", { n: health.ok })}
                    </span>
                    <span className="warn">
                      <Icon name="warning" /> {t("{n} внимание", { n: health.warn })}
                    </span>
                    <span className="err">
                      <Icon name="x" /> {t("{n} ошибки", { n: health.fail })}
                    </span>
                    <span className="skip">
                      <Icon name="clock" /> {t("{n} не проверено", { n: health.skipped })}
                    </span>
                  </div>
                  <div className="install-health-bar" role="img" aria-label={t("{run} из {total} проверено", { run, total })}>
                    {(["ok", "warn", "fail", "skip"] as const).map((key) => {
                      const value = key === "skip" ? health.skipped : health[key];
                      return <span key={key} className={key} style={{ width: `${total ? (value / total) * 100 : 0}%` }} />;
                    })}
                  </div>
                </>
              ) : (
                <p className="harness-note">{t("нет данных · снимок Home ещё не получен")}</p>
              )}
              <p className="install-checks-note">{t("Онлайн — отдельная проверка трекера и прав доступа. Проверки песочницы анализируют настройки; фактические доступы могут остаться непроверенными.")}</p>
            </div>
          </section>
        </div>
      )}

      <CommandPanel section="setup" confirmAll listed={false} request={request} onJobDone={onJobDone} />
    </div>
  );
}
