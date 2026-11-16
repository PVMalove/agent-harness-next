/* Open Project (#/open-project) on the design system v3: a five-step wizard (Выбор проекта,
   Предварительные проверки, Установка / внедрение, Настройка, Итоговая диагностика) over the
   project this console server serves, its installation plan and the candidate projects of
   open_project.snapshot. Counts the snapshot lacks (files, skills and hooks of a composition) are
   marked «нет данных». The server is bound to one project and the
   page never asks it to switch: another project opens with its own command in a terminal, which
   the page only shows and copies. A typed path is turned into that command in the browser and is
   sent nowhere. The only change the page can start is the installation into the served project,
   through the CommandPanel of the job section `setup`, and every run opens the confirmation first.
   Every step is a TabPanel (kept mounted) built of ds components; only the shared CommandPanel
   still sits in `.ds-legacy-island`. The KPIs (Harness, Скиллов, Managed, Health) live in the
   summary only. */
import { useState } from "react";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { PageHeader, Panel, PipeTabs, StatusIcon, Summary } from "../ds";
import type { PipeTab, Tone } from "../ds";
import { NoData } from "../harness/HarnessOverview";
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
import { snapshotClock } from "../update/format";
import type { LocalJob } from "../ws/jobs";
import { parseOpenProject } from "../ws/projectScreens";
import type { Candidate, OpenProjectFacts } from "../ws/projectScreens";
import { useConsole } from "../useConsole";
import { TabPanel } from "../views/Tabs";
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

/** The spoken word of a check status; the shape is StatusIcon's. */
const CHECK_LABEL: Readonly<Partial<Record<Tone, string>>> = { ok: "пройдено", warn: "внимание", err: "ошибка", wait: "не проверено" };

/** The Home health counters of the checks step: the count key, its status and its words. */
const HEALTH_ROWS: readonly (readonly ["ok" | "warn" | "fail" | "skipped", Tone, string])[] = [
  ["ok", "ok", "{n} пройдено"],
  ["warn", "warn", "{n} внимание"],
  ["fail", "err", "{n} ошибки"],
  ["skipped", "wait", "{n} не проверено"],
];

/** One check row of the project details: StatusIcon, the check and its fact. */
function ProjectCheck({ label, tone, text }: { label: string; tone: Tone; text: string }) {
  const { t } = useI18n();
  return (
    <li className="ds-row" data-tone={tone}>
      <StatusIcon tone={tone} label={t(CHECK_LABEL[tone] ?? "")} />
      <span className="ds-row-main">
        <span className="ds-row-title">{label}</span>
        <span className="ds-row-sub">{text}</span>
      </span>
    </li>
  );
}

/** A command for another console with its copy button and the copied notice. */
function CommandBlock({ command, id, copyId, copyLabel, disabled = false, copied, onCopy }: { command: string; id: string; copyId: string; copyLabel: string; disabled?: boolean; copied: string; onCopy: (text: string) => void }) {
  const { t } = useI18n();
  return (
    <div className="ds-project-command">
      <div className="ds-actions">
        <span className="ds-sub">{t("Команда для другой консоли")}</span>
        <button className="ds-btn ds-btn-sm" type="button" id={copyId} disabled={disabled} onClick={() => onCopy(command)}>
          <Icon name="download" className="ds-ic-sm" /> {copyLabel}
        </button>
      </div>
      <code id={id}>{command}</code>
      {copied === command && (
        <p className="ds-note" role="status">
          {t("Команда скопирована")}
        </p>
      )}
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
  const checks: { label: string; tone: Tone; text: string }[] = item.current
    ? [
        { label: "Git repository", tone: target ? "ok" : "err", text: target ? item.path : t(facts.error || "путь не является Git-репозиторием") },
        { label: "Harness config", tone: item.installed ? "ok" : "warn", text: item.installed ? t(".harness/project.json найден") : t("Harness не установлен") },
        { label: "Capability", tone: install?.capability_names.length ? "ok" : "wait", text: install?.capability_names.join(", ") || t("нет данных") },
        {
          label: "Skills snapshot",
          tone: drift === null || install === null ? "wait" : drift.total ? "warn" : "ok",
          text: install && drift ? t("{skills} навыков · drift {drift}", { skills: install.skills, drift: drift.total }) : t("нет данных · дрейф не прочитан"),
        },
        {
          label: t("Локальные правки управляемых файлов"),
          tone: drift === null ? "wait" : drift.local_changed ? "warn" : "ok",
          text: drift === null ? t("нет данных · дрейф не прочитан") : drift.local_changed ? t("{n} файлов с локальными правками", { n: drift.local_changed }) : t("нет локальных правок"),
        },
      ]
    : [
        { label: "Git repository", tone: "wait", text: notRead },
        { label: "Harness config", tone: item.installed ? "ok" : "warn", text: item.installed ? t("Harness установлен") : t("Harness не установлен") },
        { label: "Capability", tone: "wait", text: notRead },
        { label: "Skills snapshot", tone: "wait", text: notRead },
        { label: t("Локальные правки управляемых файлов"), tone: "wait", text: notRead },
      ];
  return (
    <Panel title={t("Детали проекта")} id="open-project-detail" meta={<span className="ds-tag" data-on={item.current}>{t(item.current ? "Открыт" : "Не открыт")}</span>} fill scroll="text" label={t("Детали проекта")}>
      <div className="ds-project-about">
        <p className="ds-sub ds-project-provider">
          {item.current && tracker ? (
            <>
              <Icon name={TRACKER_ICON[tracker] ?? "folder"} className="ds-ic-sm" /> {TRACKER_NAME[tracker] ?? tracker}
            </>
          ) : (
            <>
              <Icon name="folder" className="ds-ic-sm" /> {item.current ? t("трекер не определён") : t("локальный путь")}
            </>
          )}
          <span className="ds-tag">harness</span>
        </p>
        <h3 className="ds-project-name">{projectName(item.path)}</h3>
        <code className="ds-row-sub">{item.path}</code>
        <p className="ds-sub ds-project-meta">
          {item.current && home?.project ? (
            <>
              <span>
                <Icon name="branch" className="ds-ic-sm" /> {home.project.branch ?? "—"}
              </span>
              <span>
                <Icon name="harness" className="ds-ic-sm" /> {install?.installed ? install.installed_version : t("не установлен")}
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
        </p>
      </div>
      <ul className="ds-rows" id="open-project-detail-checks">
        {checks.map((check) => (
          <ProjectCheck key={check.label} {...check} />
        ))}
      </ul>
      <CommandBlock command={item.command} id="open-project-command" copyId="open-project-copy" copyLabel={t("Копировать")} disabled={item.current} copied={copied} onCopy={onCopy} />
      <div className="ds-actions">
        {item.current ? (
          <button className="ds-btn" type="button" disabled>
            {t("Уже открыт")}
          </button>
        ) : null}
        <span className="ds-note">
          {item.current ? t("Этот проект уже открыт этим сервером") : t("Другой проект открывается своей командой в терминале; сервер не переключается.")}
        </span>
      </div>
    </Panel>
  );
}

export function OpenProject() {
  const { t, section, language } = useI18n();
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
  const [chosenStep, setStep] = useState<string | null>(null);

  const target = facts?.target ?? null;
  const candidates = facts?.candidates ?? [];
  const shown = candidates.find((item) => item.path === selected) ?? candidates.find((item) => item.current) ?? candidates[0] ?? null;
  const chosen = facts ? (capability !== null && capability in facts.blockers ? capability : firstCapability(facts)) : DEFAULT_CAPABILITY;
  const blocked = facts?.blockers[chosen] ?? [];
  const summary = target ? targetSummary(target, t) : null;
  const stage = target === null ? 0 : installed ? 3 : 1;
  const step = chosenStep ?? "0";
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

  const steps: PipeTab[] = STAGES.map((name, index) => ({
    id: String(index),
    label: t(name),
    count: index < stage ? "✓" : index + 1,
  }));
  const composition = (
    <dl className="ds-kv" id="open-project-composition-counts">
      {[t("Файлов"), t("Навыков"), t("Хуков")].map((label) => (
        <div className="ds-kv-row" key={label}>
          <dt>{label}</dt>
          <dd>
            <NoData />
          </dd>
        </div>
      ))}
    </dl>
  );

  return (
    <div className="ds-page ds-fit" data-section="Open project">
      <PageHeader
        title={t("Проект")}
        subtitle={t("Сервер консоли обслуживает один проект; другой проект открывается своей командой в терминале.")}
        actions={
          <a className="ds-btn" href={href("diagnostics")}>
            <Icon name="pulse" className="ds-ic-sm" /> {section("Diagnostics")}
          </a>
        }
      />

      {screen.error && !facts && (
        <p className="ds-alert ds-alert-err" role="alert" data-code={screen.error.code}>
          {t("Данные не получены")}: {screen.error.message || screen.error.code}
        </p>
      )}

      <Summary
        id="open-project-facts"
        label={t("Текущий проект")}
        stats={[
          { label: "Harness", value: home?.harness?.installed ? home.harness.installed_version : "—", caption: home?.harness_version ? t("доступно {version}", { version: home.harness_version }) : <NoData /> },
          { label: t("Скиллов"), value: home?.harness?.skills || "—" },
          { label: "Managed", value: home?.harness?.managed_files || "—" },
          { label: "Health", value: health && total ? `${health.ok}/${total}` : "—" },
        ]}
        facts={
          facts ? (
            <>
              <span>{home?.project?.name ?? projectName(facts.repo)}</span>
              <span>{home?.project?.branch ?? t("ветка неизвестна")}</span>
              <span>{home?.harness?.installed ? home.harness.installed_version : t("Harness не установлен")}</span>
            </>
          ) : undefined
        }
        snapshot={
          facts ? (
            <span title={`${screen.cached ? t("Кэш") : t("Новый снимок")} · ${screen.ageSeconds ?? 0} s`}>
              <Icon name="clock" className="ds-ic-sm" /> {snapshotClock(screen.ageSeconds, language)}
            </span>
          ) : undefined
        }
      />

      <div className="ds-wizard" id="open-project-steps">
        <PipeTabs id="open-project-step" label={t("Шаги установки")} tabs={steps} value={step} onChange={(id) => setStep(id)} />
        <span className="ds-note">{t("Шаг {current} из {total}", { current: stage + 1, total: STAGES.length })}</span>
      </div>

      {facts && (
        <>
          <TabPanel id="open-project-step" tab="0" value={step} className="ds-tabpanel ds-project-step" keepMounted>
            <div className="ds-project-select">
              <div className="ds-project-left">
                <Panel title={t("Текущий проект")} id="open-project-current">
                  <div className="ds-row ds-project-current">
                    <span className="ds-project-icon">
                      <Icon name="folder" />
                    </span>
                    <span className="ds-row-main">
                      <span className="ds-row-title">{home?.project?.name ?? projectName(facts.repo)}</span>
                      <code className="ds-row-sub">{facts.repo}</code>
                      {target ? (
                        <span className="ds-row-sub ds-project-meta">
                          <Icon name="branch" className="ds-ic-sm" /> {home?.project?.branch ?? t("ветка неизвестна")} · <Icon name={TRACKER_ICON[tracker] ?? "folder"} className="ds-ic-sm" />{" "}
                          {TRACKER_NAME[tracker] ?? (tracker || t("трекер не определён"))}
                        </span>
                      ) : (
                        <span className="ds-alert ds-alert-err">{t(facts.error)}</span>
                      )}
                    </span>
                  </div>
                </Panel>
                <Panel title={t("Проекты")} id="open-project-list" meta={t("{count} найдено", { count: candidates.length })} fill scroll="list" label={t("Проекты")}>
                  {candidates.length === 0 && <p className="ds-empty">{t("Проектов для открытия не найдено")}</p>}
                  <div className="ds-rows" role="listbox" aria-label={t("Проекты")}>
                    {candidates.map((item) => (
                      <button
                        key={item.path}
                        type="button"
                        role="option"
                        aria-selected={item.path === shown?.path}
                        className="ds-row ds-row-button"
                        data-path={item.path}
                        onClick={() => setSelected(item.path)}
                      >
                        <span className="ds-project-icon">
                          <Icon name="folder" />
                        </span>
                        <span className="ds-row-main">
                          <span className="ds-row-title">{projectName(item.path)}</span>
                          <span className="ds-row-sub">{item.path}</span>
                          <span className="ds-row-sub">
                            {item.current && home?.project && home.harness?.installed
                              ? `${home.project.branch ?? "—"} · ${home.harness.installed_version}`
                              : item.installed
                                ? t("Harness установлен")
                                : t("Harness не установлен")}
                          </span>
                        </span>
                        <span className="ds-tag" data-on={item.current}>
                          {t(item.current ? "Открыт" : "Не открыт")}
                        </span>
                      </button>
                    ))}
                  </div>
                  <p className="ds-note" id="open-project-list-foot">
                    {t("Выберите проект, чтобы увидеть проверки справа.")}
                  </p>
                </Panel>
                <Panel title={t("Путь к другому проекту")} id="open-project-path" meta={t("без чтения Git")}>
                  <div className="ds-actions ds-project-path">
                    <label className="ds-project-field">
                      {t("Путь к локальному Git-проекту")}
                      <input className="ds-input" value={path} placeholder="/home/…/project" onChange={(event) => setPath(event.target.value)} />
                    </label>
                    <button className="ds-btn" type="button" onClick={() => setChecked(t(pathStatus(path)))}>
                      <Icon name="check" className="ds-ic-sm" /> {t("Проверить путь")}
                    </button>
                  </div>
                  {typed && (
                    <CommandBlock command={openCommand(typed)} id="open-project-path-command" copyId="open-project-path-copy" copyLabel={t("Копировать команду")} copied={copied} onCopy={copy} />
                  )}
                  <p className="ds-note">
                    <span id="open-project-path-status" role="status">
                      {checked}
                    </span>{" "}
                    {t("Проверка пути не читает Git и .harness: команда открывает проект своим сервером.")}
                  </p>
                </Panel>
              </div>
              {shown && (
                <div className="ds-project-detail">
                  <CandidateDetail item={shown} facts={facts} home={home} copied={copied} onCopy={copy} />
                </div>
              )}
            </div>
          </TabPanel>

          <TabPanel id="open-project-step" tab="1" value={step} className="ds-tabpanel ds-project-step" keepMounted>
            <Panel title={t("Проверки")} id="open-project-checks" meta={health ? t("{run} из {total} проверено", { run, total }) : t("нет данных")} fill scroll="text">
              <div className="ds-actions ds-project-check-actions">
                <span className="ds-filter" role="group" aria-label={t("Режим проверки")}>
                  <button type="button" aria-pressed={!online} onClick={() => mode(false)}>
                    {t("Офлайн")}
                  </button>
                  <button type="button" aria-pressed={online} onClick={() => mode(true)}>
                    {t("Онлайн")}
                  </button>
                </span>
                <a className="ds-btn" href={href("diagnostics")}>
                  <Icon name="pulse" className="ds-ic-sm" /> {t("Исправить")}
                </a>
                <a className="ds-btn" href={href("configuration")}>
                  <Icon name="settings" className="ds-ic-sm" /> {t("Настройка")}
                </a>
              </div>
              {health ? (
                <>
                  <ul className="ds-rows" id="open-project-health">
                    {HEALTH_ROWS.map(([key, tone, text]) => (
                      <li className="ds-row" data-tone={tone} key={key}>
                        <StatusIcon tone={tone} label={t(CHECK_LABEL[tone] ?? "")} />
                        <span className="ds-row-main">{t(text, { n: health[key] })}</span>
                      </li>
                    ))}
                  </ul>
                  <div className="ds-project-bar" role="img" aria-label={t("{run} из {total} проверено", { run, total })}>
                    {HEALTH_ROWS.map(([key, tone]) => (
                      <span key={key} data-tone={tone} style={{ width: `${total ? (health[key] / total) * 100 : 0}%` }} />
                    ))}
                  </div>
                </>
              ) : (
                <p className="ds-note">{t("нет данных · снимок Home ещё не получен")}</p>
              )}
              <p className="ds-note">{t("Онлайн — отдельная проверка трекера и прав доступа. Проверки песочницы анализируют настройки; фактические доступы могут остаться непроверенными.")}</p>
            </Panel>
          </TabPanel>

          <TabPanel id="open-project-step" tab="2" value={step} className="ds-tabpanel ds-project-step" keepMounted>
            <Panel title={t("Схема внедрения")} id="open-project-flow" meta={t("путь проекта → harness → capability → runtime → health")}>
              <ol className="ds-loop ds-project-flow">
                {flowNodes(facts, home, chosen, blocked.length, t).map((node, index) => (
                  <li className="ds-loop-node" data-tone={node.tone} key={node.label}>
                    <Icon name={node.icon} className="ds-ic-sm" />
                    <span>
                      <small>{String(index + 1).padStart(2, "0")}</small>
                      <b>{node.label}</b>
                      <span className="ds-project-flow-value" data-flow-cap={node.label === "Capability" ? "" : undefined}>
                        {node.value}
                      </span>
                      <small>{node.sub}</small>
                    </span>
                  </li>
                ))}
              </ol>
            </Panel>
            <div className="ds-project-install">
              <Panel title={t("План установки")} id="open-project-plan" meta={target ? t(ACTION_WORDS[target.action]) : undefined} fill scroll="text">
                {target && summary ? (
                  <>
                    <p className={summary.kind === "warning" ? "ds-alert ds-alert-warn" : "ds-note"} id="open-project-plan-summary">
                      <b>{summary.first}</b> <span>{summary.facts}</span>
                    </p>
                    <dl className="ds-kv">
                      <div className="ds-kv-row">
                        <dt>{t("Проект")}</dt>
                        <dd>{projectName(target.repo)}</dd>
                      </div>
                      <div className="ds-kv-row">
                        <dt>{t("Состав")}</dt>
                        <dd>{`${CAPABILITY_TEXT[chosen] ? t(CAPABILITY_TEXT[chosen]![0]) : "Capability"} (${chosen})`}</dd>
                      </div>
                      <div className="ds-kv-row">
                        <dt>{t("Конфликты")}</dt>
                        <dd data-tone={blocked.length ? "err" : target.conflicts.length ? "warn" : "ok"}>
                          {blocked.length ? t("заблокировано: {n}", { n: blocked.length }) : target.conflicts.length ? target.conflicts.join(", ") : t("нет")}
                        </dd>
                      </div>
                    </dl>
                    {target.conflicts.length > 0 && <p className="ds-alert ds-alert-warn">{t("Force/replace не включены. При конфликте операция остановится.")}</p>}
                    <h3 className="ds-group-title">{t("Команда")}</h3>
                    <div className="ds-project-command">
                      <code id="open-project-install-command">{installCommand(target, chosen)}</code>
                    </div>
                  </>
                ) : (
                  <p className="ds-note">{reason}</p>
                )}
                <div className="ds-actions">
                  <button id="open-project-install" className="ds-btn ds-btn-primary" type="button" disabled={!target || blocked.length > 0} title={reason || undefined} onClick={install}>
                    <Icon name="download" className="ds-ic-sm" /> {t("Установить")}
                  </button>
                  <span className="ds-sub">{reason || t("Потребуется подтверждение")}</span>
                </div>
              </Panel>
              <Panel title={t("Состав Harness")} id="open-project-capability" meta={t("что будет установлено")} fill scroll="list" label={t("Состав Harness")}>
                <div className="ds-rows ds-project-caps" role="radiogroup" aria-label={t("Состав Harness")}>
                  {Object.entries(facts.blockers).map(([name, paths]) => {
                    const [title, description] = CAPABILITY_TEXT[name] ?? [name, ""];
                    return (
                      <label key={name} className="ds-row ds-choice" data-on={name === chosen}>
                        <input type="radio" name="open-project-capability" aria-label={`${t(title)} (${name})`} checked={name === chosen} onChange={() => setCapability(name)} />
                        <span className="ds-row-main">
                          <span className="ds-row-title">{t(title)}</span>
                          <span className="ds-row-sub">{description ? t(description) : name}</span>
                          {paths.length > 0 && <span className="ds-row-sub ds-verdict-err">{t("заблокировано: {n}", { n: paths.length })}</span>}
                        </span>
                        {target?.capabilities.includes(name) && <span className="ds-tag">{t("установлено")}</span>}
                      </label>
                    );
                  })}
                </div>
                <p className="ds-note" id="open-project-capability-footer">
                  {CAPABILITY_TEXT[chosen] ? t(CAPABILITY_TEXT[chosen]![2]) : chosen}
                </p>
                {blocked.length > 0 && (
                  <div className="ds-alert ds-alert-warn" id="open-project-blockers">
                    <div>
                      <p>{t("Установка заблокирована; проверьте собственные/изменённые пути:")}</p>
                      <ul>
                        {blocked.map((item) => (
                          <li key={item}>
                            <code>{item}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
                {composition}
              </Panel>
            </div>
          </TabPanel>

          <TabPanel id="open-project-step" tab="3" value={step} className="ds-tabpanel ds-project-step" keepMounted>
            <Panel title={t("Настройка")} id="open-project-settings" fill>
              <p className="ds-note">{t("project.json и orchestration.json настраиваются на странице «Настройка»: черновик, проверка и подтверждённая запись.")}</p>
              <div className="ds-actions">
                <a className="ds-btn" href={href("configuration")}>
                  <Icon name="settings" className="ds-ic-sm" /> {t("Настройка")}
                </a>
              </div>
            </Panel>
          </TabPanel>

          <TabPanel id="open-project-step" tab="4" value={step} className="ds-tabpanel ds-project-step" keepMounted>
            <Panel title={t("Итоговая диагностика")} id="open-project-final" fill>
              {health ? (
                <dl className="ds-kv">
                  <div className="ds-kv-row"><dt>{t("пройдено")}</dt><dd>{health.ok}</dd></div>
                  <div className="ds-kv-row"><dt>{t("внимание")}</dt><dd>{health.warn}</dd></div>
                  <div className="ds-kv-row"><dt>{t("ошибки")}</dt><dd>{health.fail}</dd></div>
                  <div className="ds-kv-row"><dt>{t("пропущено")}</dt><dd>{health.skipped}</dd></div>
                </dl>
              ) : (
                <p className="ds-empty">
                  <NoData />
                </p>
              )}
              <div className="ds-actions">
                <a className="ds-btn" href={href("diagnostics")}>
                  <Icon name="pulse" className="ds-ic-sm" /> {section("Diagnostics")}
                </a>
              </div>
            </Panel>
          </TabPanel>
        </>
      )}

      <div className="ds-legacy-island">
        <CommandPanel section="setup" confirmAll listed={false} request={request} onJobDone={onJobDone} />
      </div>
    </div>
  );
}
