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
  DEFAULT_CAPABILITY,
  STAGES,
  installCommand,
  openCommand,
  projectName,
  targetSummary,
} from "../project/format";
import { useScreen } from "../screens/useScreen";
import type { LocalJob } from "../ws/jobs";
import { parseOpenProject } from "../ws/projectScreens";
import type { Candidate, OpenProjectFacts } from "../ws/projectScreens";

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

/** The mockup «Схема внедрения»: project → harness → capability → runtime → health. The open
    project snapshot reads neither the runtime store nor the health checks: those two nodes say so. */
function flowNodes(facts: OpenProjectFacts, chosen: string, blocked: number, t: (text: string, values?: Record<string, string | number>) => string): FlowNode[] {
  const target = facts.target;
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
      value: target ? t(ACTION_WORDS[target.action]) : "—",
      sub: target?.capabilities.join(", ") || t("не установлен"),
      tone: target?.action === "update" ? "ok" : "warn",
    },
    {
      icon: "settings",
      label: "Capability",
      value: chosen,
      sub: blocked ? t("✖ заблокировано: {n}", { n: blocked }) : t("готово к установке"),
      tone: blocked ? "warn" : "active",
    },
    { icon: "store", label: "Runtime", value: t("нет данных"), sub: t("снимок проекта не читает runtime store"), tone: "pending" },
    { icon: "pulse", label: "Health", value: t("после установки"), sub: t("проверки — на странице «Диагностика»"), tone: "after" },
  ];
}

function Stepper({ stage }: { stage: number }) {
  const { t } = useI18n();
  return (
    <div className="install-steps" id="open-project-steps" tabIndex={0} role="region" aria-label={t("Шаги установки")}>
      <div className="install-steps-track">
        {STAGES.map((name, index) => (
          <span key={name}>
            <span className={`install-step ${index < stage ? "done" : index === stage ? "active" : "pending"}`}>
              {index < stage ? "✔ " : index === stage ? "▶ " : "○ "}
              {t(name)}
            </span>
            {index < STAGES.length - 1 && <i className="install-sep">—</i>}
          </span>
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

function CandidateDetail({ item, copied, onCopy }: { item: Candidate; copied: string; onCopy: (text: string) => void }) {
  const { t } = useI18n();
  return (
    <section className="panel project-detail-panel" id="open-project-detail">
      <div className="panel-head">
        <h2>{t("Детали проекта")}</h2>
        <span className={`project-pill ${item.current ? "ok" : "muted"}`}>{t(item.current ? "Открыт" : "Не открыт")}</span>
      </div>
      <div className="project-detail-body">
        <h3>{projectName(item.path)}</h3>
        <code className="project-path">{item.path}</code>
        <div className="project-meta">
          <span>{item.installed ? `✔ ${t("Harness установлен")}` : `○ ${t("Harness не установлен")}`}</span>
        </div>
        <div className="project-command">
          <div className="project-command-head">
            <span>{t("Команда для другой консоли")}</span>
            <button className="btn" type="button" id="open-project-copy" disabled={item.current} onClick={() => onCopy(item.command)}>
              <Icon name="download" /> {t("Копировать команду")}
            </button>
          </div>
          <code id="open-project-command">{item.command}</code>
          {item.current && <p className="project-hint">{t("Этот проект уже открыт этим сервером")}</p>}
          {copied === item.command && (
            <p className="project-hint" role="status">
              {t("Команда скопирована")}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

export function OpenProject() {
  const { t, section } = useI18n();
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
  const blockerCount = facts ? Object.values(facts.blockers).filter((paths) => paths.length > 0).length : 0;
  const stage = target === null ? 0 : installed ? 3 : 1;
  const typed = path.trim();
  const reason = target === null ? t(facts?.error || "План появится после проверки пути.") : blocked.length ? t("✖ заблокировано: {n}", { n: blocked.length }) : "";

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
            <div className="home-facts">
              <span id="open-project-cache">
                {screen.cached ? t("Кэш") : t("Новый снимок")} · {screen.ageSeconds ?? 0} s
              </span>
            </div>
          )}
        </div>
        <div className="actions">
          <button id="open-project-refresh" className="btn" type="button" onClick={() => screen.refresh(true)}>
            <Icon name="refresh" /> {t("Обновить")}
          </button>
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
            <h2>{projectName(facts.repo)}</h2>
            <code>{facts.repo}</code>
            {summary ? (
              <div className={`current-project-meta ${summary.kind === "warning" ? "warn" : "ok"}`}>
                <b>{summary.first}</b>
                <span>{summary.facts}</span>
              </div>
            ) : (
              <p className="command-refusal err">{t(facts.error)}</p>
            )}
          </div>
          <div className="current-project-stats" id="open-project-kpi">
            <div>
              <span>{t("Действие")}</span>
              <b>{target ? t(ACTION_WORDS[target.action]) : "—"}</b>
            </div>
            <div>
              <span>{t("Установлено")}</span>
              <b>{target?.capabilities.join(", ") || t("нет")}</b>
            </div>
            <div data-tone={target?.conflicts.length ? "warning" : undefined}>
              <span>{t("Конфликты")}</span>
              <b>{target?.conflicts.length ?? 0}</b>
            </div>
            <div data-tone={blockerCount ? "warning" : undefined}>
              <span>{t("Заблокированные составы")}</span>
              <b>{blockerCount}</b>
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
                <span className="small muted">{candidates.length}</span>
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
                      <small>{item.installed ? `✔ ${t("Harness установлен")}` : `○ ${t("Harness не установлен")}`}</small>
                    </span>
                    <span className={`project-pill ${item.current ? "ok" : "muted"}`}>{t(item.current ? "Открыт" : "Не открыт")}</span>
                  </button>
                ))}
              </div>
            </section>
            <section className="panel project-path-panel" id="open-project-path">
              <div className="panel-head">
                <h2>{t("Путь к другому проекту")}</h2>
              </div>
              <div className="project-path-body">
                <label className="field">
                  {t("Путь к локальному Git-проекту")}
                  <input value={path} placeholder="/home/…/project" onChange={(event) => setPath(event.target.value)} />
                </label>
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
                <span className="project-hint">{t("Проверка пути не читает Git и .harness: команда открывает проект своим сервером.")}</span>
              </div>
            </section>
          </div>
          {shown && <CandidateDetail item={shown} copied={copied} onCopy={copy} />}
        </div>
      )}

      {facts && (
        <section className="panel install-flow-panel" id="open-project-flow">
          <div className="panel-head">
            <h2>{t("Схема внедрения")}</h2>
            <span className="small muted">{t("путь проекта → harness → capability → runtime → health")}</span>
          </div>
          <div className="install-flow">
            {flowNodes(facts, chosen, blocked.length, t).map((node, index, nodes) => (
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
              {target ? (
                <>
                  <dl className="install-plan-facts">
                    <div>
                      <dt>{t("Проект")}</dt>
                      <dd>{projectName(target.repo)}</dd>
                    </div>
                    <div>
                      <dt>{t("Состав")}</dt>
                      <dd>{chosen}</dd>
                    </div>
                    <div>
                      <dt>{t("Конфликты")}</dt>
                      <dd>{blocked.length ? t("✖ заблокировано: {n}", { n: blocked.length }) : target.conflicts.length ? `⚠ ${target.conflicts.join(", ")}` : t("✔ нет")}</dd>
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
              {Object.entries(facts.blockers).map(([name, paths]) => (
                <label key={name} className={`cap-row${name === chosen ? " on" : ""}`}>
                  <input type="radio" name="open-project-capability" checked={name === chosen} onChange={() => setCapability(name)} />
                  <span className="cap-copy">
                    <b>{name}</b>
                    {target?.capabilities.includes(name) && <span className="cap-status">{t("установлено")}</span>}
                    {paths.length > 0 && <small className="warn">{t("✖ заблокировано: {n}", { n: paths.length })}</small>}
                  </span>
                </label>
              ))}
            </div>
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
            </div>
            <div className="install-checks-body">
              <div className="install-check-actions">
                <a className="btn" href={href("diagnostics")}>
                  <Icon name="pulse" /> {section("Diagnostics")}
                </a>
                <a className="btn" href={href("configuration")}>
                  <Icon name="settings" /> {section("Configuration")}
                </a>
              </div>
              <p className="install-checks-note">{t("Проверки здоровья проекта собирает страница «Диагностика»; этот снимок их не запускает.")}</p>
            </div>
          </section>
        </div>
      )}

      <CommandPanel section="setup" confirmAll listed={false} request={request} onJobDone={onJobDone} />
    </div>
  );
}
