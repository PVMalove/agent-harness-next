/* Home: the blocks of the mockup filled only with facts of the Home snapshot. A fact the
   snapshot does not carry is shown as unavailable, never invented. */
import { useEffect, useRef, useState } from "react";
import { Icon } from "../icons";
import { groupLabel, useI18n } from "../i18n";
import { href } from "../navigation";
import { preRelease } from "../AppShell";
import { useConsole } from "../useConsole";
import type { AreaCounters, HealthCounters, HomeSnapshot, Problem, RecentSession } from "../ws/types";
import { healthTotal } from "../ws/types";

/** Offline mode asks again this long after each reply. */
export const OFFLINE_REFRESH_MS = 15000;
/** Orchestration events are coalesced into one refresh after this pause. */
export const EVENTS_DEBOUNCE_MS = 1000;

const STATUS_ICON: Record<string, string> = { ok: "check", warn: "warning", fail: "x", skipped: "clock" };

/** The explicit no-data state of a field without a source. */
function NoData() {
  const { t } = useI18n();
  return (
    <dd className="muted no-data" title={t("Недоступно в текущем снимке")}>
      {t("нет данных")}
    </dd>
  );
}

function Fact({ label, value, tone = "" }: { label: string; value: string | null; tone?: string }) {
  return (
    <div>
      <dt>{label}</dt>
      {value === null ? <NoData /> : <dd className={tone}>{value}</dd>}
    </div>
  );
}

/** The page a health area opens: its own section when the console has one, else Diagnostics. */
export function areaRoute(group: string): string {
  if (group === "skills" || group === "files") return "update-harness";
  if (group === "repo_map" || group === "repo-map") return "repo-map";
  if (group === "orchestration") return "orchestration";
  return "diagnostics";
}

function useStatusLabel() {
  const { t } = useI18n();
  return (status: string): string =>
    ({ ok: t("пройдено"), warn: t("внимание"), fail: t("ошибки"), skipped: t("пропущено") })[status] ?? status;
}

function AttentionRows({ problems }: { problems: Problem[] }) {
  const { t, language } = useI18n();
  const statusLabel = useStatusLabel();
  if (!problems.length) {
    return <p className="empty">{t("В списке нет проблем; это не подтверждает полноту проверок")}</p>;
  }
  return (
    <>
      {problems.map((problem, index) => (
        <div className="it" key={`${problem.id}-${index}`}>
          <span
            className={`home-alert-icon ${problem.status === "fail" ? "err" : problem.status}`}
            role="img"
            aria-label={statusLabel(problem.status)}
          >
            <Icon name={STATUS_ICON[problem.status] ?? "info"} />
          </span>
          <div className="t">
            <b>{problem.id}</b>
            <small>
              {problem.message}
              {problem.group ? ` · ${groupLabel(language, problem.group)}` : ""}
            </small>
          </div>
          <a href={href(areaRoute(problem.group))}>{t("Открыть →")}</a>
        </div>
      ))}
    </>
  );
}

function CheckRows({ rows }: { rows: Problem[] }) {
  const { t, language } = useI18n();
  const statusLabel = useStatusLabel();
  if (!rows.length) {
    return <div className="empty">{t("Нет проверок в этом фильтре. Это не доказывает отсутствие проблем вне списка.")}</div>;
  }
  return (
    <>
      {rows.map((row, index) => (
        <a className="check-row" key={`${row.id}-${index}`} href={href(areaRoute(row.group))}>
          <span className={`check-icon ${row.status}`} role="img" aria-label={statusLabel(row.status)}>
            <Icon name={STATUS_ICON[row.status] ?? "info"} />
          </span>
          <span className="check-main">
            <b>{row.id}</b>
            <small>{row.message}</small>
          </span>
          <span className="check-area">{row.group ? groupLabel(language, row.group) : "—"}</span>
        </a>
      ))}
    </>
  );
}

function AreaRows({ areas }: { areas: AreaCounters[] }) {
  const { t, language } = useI18n();
  if (!areas.length) return <p className="empty">{t("нет данных")}</p>;
  return (
    <>
      {areas.map((area) => {
        const total = area.ok + area.warn + area.fail + area.skipped || 1;
        const name = groupLabel(language, area.area);
        const segments: [number, string][] = [
          [area.ok, "ok"],
          [area.warn, "warn"],
          [area.fail, "fail"],
          [area.skipped, "skip"],
        ];
        return (
          <div className="health-row" key={area.area}>
            <span className="health-name">
              <Icon name="pulse" />
              <span>{name}</span>
            </span>
            <span
              className="health-bar"
              role="img"
              aria-label={`${name}: ok ${area.ok}, warn ${area.warn}, fail ${area.fail}, skip ${area.skipped}`}
            >
              {segments.map(([value, css]) =>
                value ? <i key={css} className={css} style={{ width: `${(value / total) * 100}%` }} /> : null,
              )}
            </span>
            <span className="health-count">
              {area.ok}✓ {area.warn}⚠ {area.fail}✖ {area.skipped}–
            </span>
          </div>
        );
      })}
    </>
  );
}

const ROLE_NAMES: Record<string, string> = {
  architect: "Architect",
  developer: "Developer",
  "code-review": "Review",
  review: "Review",
  qa: "QA",
};

function sessionTone(state: string): string {
  if (["blocked", "failed", "abandoned", "auto_stop"].includes(state)) return "err";
  if (["active", "working", "running"].includes(state)) return "ok";
  return "warn";
}

function RecentTasks({ sessions }: { sessions: RecentSession[] }) {
  const { t, section, language, state: stateText } = useI18n();
  const active = sessions.find((session) => sessionTone(session.state) === "ok") ?? sessions[0] ?? null;
  const time = (iso: string) => {
    const date = new Date(iso);
    return Number.isNaN(date.getTime())
      ? iso
      : new Intl.DateTimeFormat(language, { dateStyle: "short", timeStyle: "short" }).format(date);
  };
  return (
    <section id="home-tasks" className="panel tasks-panel">
      <div className="panel-head">
        <h2>
          {t("Последние задачи")} <span className="small muted">{sessions.length}</span>
        </h2>
        <a className="small" href={href("orchestration")}>
          {section("Orchestration")} →
        </a>
      </div>
      {sessions.length ? (
        <>
          <div className="task-head">
            <span>{t("Сессия")}</span>
            <span />
            <span>{t("Задача")}</span>
            <span>{t("Статус")}</span>
            <span>{t("Время")}</span>
          </div>
          <div className="task-list">
            {sessions.map((session) => (
              <a className="task-row" key={session.batch_id} href={href("orchestration")}>
                <span className="task-id">{session.ticket || "—"}</span>
                <span className="task-role">
                  <Icon name="activity" />
                </span>
                <span className="task-title" title={t("Название задачи недоступно; показана ветка")}>
                  {session.branch || session.batch_id}
                </span>
                <span className={`task-status ${sessionTone(session.state)}`}>{session.state}</span>
                <span className="task-time">{time(session.created_at)}</span>
              </a>
            ))}
          </div>
        </>
      ) : (
        <div className="body">
          <p className="empty">{t("Сессий в ledger нет")}</p>
        </div>
      )}
      {active ? (
        <div className="active-route">
          <div className="route-head">
            <h3>{t("Маршрут сессии {id}", { id: active.ticket || active.batch_id })}</h3>
            <a href={href("agent-activity")} className="small">
              {section("Ход работы")} →
            </a>
          </div>
          <div className="route-scroll">
            <div className="route-steps">
              {active.route.length ? (
                active.route.map((step, index) => (
                  <div
                    className={`route-step ${["working", "running", "dispatched"].includes(step.state) ? "current" : "done"}`}
                    key={`${step.role}-${index}`}
                  >
                    <span className="route-dot" />
                    <span className="route-copy">
                      <b>{ROLE_NAMES[step.role] ?? step.role}</b>
                      <small>{stateText(step.state)}</small>
                    </span>
                  </div>
                ))
              ) : (
                <p className="empty">{t("нет данных")}</p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

/** The health strip of Home and Diagnostics: one bar per status, sized by the server's counts. */
export function HealthStrip({ health }: { health: HealthCounters }) {
  const { t } = useI18n();
  const total = healthTotal(health);
  const parts: [keyof typeof health, string, string][] = [
    ["ok", "var(--ok)", "bar-ok"],
    ["warn", "var(--warn)", "bar-warn"],
    ["fail", "var(--err)", "bar-fail"],
    ["skipped", "#6b7686", "bar-muted"],
  ];
  let x = 0;
  const label = `${t("пройдено")}: ${health.ok}; ${t("внимание")}: ${health.warn}; ${t("ошибки")}: ${health.fail}; ${t("пропущено")}: ${health.skipped}`;
  return (
    <svg
      className="health-strip"
      width="100%"
      height="8"
      viewBox="0 0 100 8"
      preserveAspectRatio="none"
      role="img"
      aria-label={label}
    >
      {parts.map(([key, fill, css]) => {
        const width = total ? (health[key] / total) * 100 : 0;
        const rect = <rect key={key} className={css} fill={fill} x={x} y="0" width={width} height="8" />;
        x += width;
        return rect;
      })}
    </svg>
  );
}

function Contour({ snapshot }: { snapshot: HomeSnapshot | null }) {
  const { t } = useI18n();
  const store = snapshot?.store ?? null;
  const value = (text: string | number | null | undefined) =>
    text === null || text === undefined ? <b className="muted">{t("нет данных")}</b> : <b>{text}</b>;
  return (
    <section id="home-contour" className="panel contour-panel">
      <div className="panel-head">
        <h2>{t("Контур Harness")}</h2>
        <span className="small muted">{store ? store.authority : t("нет данных")}</span>
      </div>
      <div className="body">
        <div className="contour-scroll">
          <svg className="contour-svg" viewBox="0 0 800 110" role="img" aria-label={t("Схема контура Harness")}>
            <path className="edge" d="M160 50H210 M360 50H410 M560 50H610" />
            <rect className="node" x="10" y="25" width="150" height="50" />
            <text className="node-label" x="22" y="55">
              Python policy
            </text>
            <rect className="node" x="210" y="25" width="150" height="50" />
            <text className="node-label" x="224" y="55">
              IPC
            </text>
            <rect className="node" x="410" y="25" width="150" height="50" />
            <text className="node-label" x="422" y="55">
              Rust runtime
            </text>
            <rect className="node" x="610" y="25" width="175" height="50" />
            <text className="node-label" x="622" y="55">
              SQLite WAL / audit
            </text>
          </svg>
        </div>
        <div className="contour-facts">
          <div>
            <span>authority</span>
            {value(store?.authority)}
          </div>
          <div>
            <span>schema</span>
            {value(store?.schema)}
          </div>
          <div>
            <span>generation</span>
            {value(store?.generation)}
          </div>
          <div>
            <span>audit</span>
            {value(store?.audit_records)}
          </div>
          <div>
            <span>cutover</span>
            {value(null)}
          </div>
          <div>
            <span>Repo Map</span>
            {value(snapshot?.repo_map.tier)}
          </div>
        </div>
        <p className="contour-note">{t("Схема показывает устройство контура, а не поток конкретного batch.")}</p>
      </div>
    </section>
  );
}

export function Home() {
  const { t, section, fact, language, state: stateText } = useI18n();
  const { state, client, replies, events } = useConsole();
  const [online, setOnline] = useState(false);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
  const [filter, setFilter] = useState<"all" | "problem" | "skipped">("all");
  const firstEvents = useRef(events);
  const snapshot = state.snapshot;
  const unavailable = t("Недоступно в текущем снимке");

  // Offline mode re-reads Home 15 s after each reply; online refreshes only on request.
  useEffect(() => {
    if (replies === 0) return;
    setCheckedAt(new Date());
    if (online) return;
    const timer = window.setTimeout(() => client.requestHome(), OFFLINE_REFRESH_MS);
    return () => window.clearTimeout(timer);
  }, [replies, online, client]);

  // New orchestration events: one non-forced refresh after they settle.
  useEffect(() => {
    if (events === firstEvents.current) return;
    const timer = window.setTimeout(() => client.requestHome({ online }), EVENTS_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [events, online, client]);

  const switchMode = (next: boolean) => {
    setOnline(next);
    client.requestHome({ force: true, online: next });
  };

  const health = snapshot?.health;
  const total = health ? healthTotal(health) : 0;
  const map = snapshot?.repo_map.head_map ?? null;
  const memory = snapshot?.memory;
  const policy = memory?.policy ?? null;
  const shown = snapshot?.problems ?? [];
  const project = snapshot?.project ?? null;
  const install = snapshot?.harness ?? null;
  const store = snapshot?.store ?? null;
  const drift = snapshot?.drift_counts ?? null;
  const skipped = snapshot?.skipped_checks ?? [];
  const checkRows = filter === "problem" ? shown : filter === "skipped" ? skipped : [...shown, ...skipped];
  const channel = snapshot && preRelease(snapshot.harness_version) ? " · pre-release" : "";
  const fails = shown.filter((problem) => problem.status === "fail").length;
  const warns = shown.length - fails;
  const clock = checkedAt
    ? new Intl.DateTimeFormat(language, { timeStyle: "medium" }).format(checkedAt)
    : "—";
  const number = (value: number) => new Intl.NumberFormat(language).format(value);

  return (
    <div id="home">
      <div className="page-title home-title">
        <div>
          <h1>{t("Состояние харнесса")}</h1>
          <p>{t("Здоровье, runtime-store, навыки и контекст проекта.")}</p>
          <div className="home-facts" id="home-chips">
            {snapshot ? (
              <>
                <span>
                  {snapshot.harness_version}
                  {channel}
                </span>
                {install?.installed ? <span>{t("установлено {version}", { version: install.installed_version })}</span> : null}
                {store ? <span>{store.authority}</span> : null}
                <span id="home-facts">
                  {health ? `${health.ok} ok · ${health.warn} warn · ${health.fail} fail · ${health.skipped} skip` : unavailable}
                </span>
                {install ? <span>{t("{count} навыков", { count: install.skills })}</span> : null}
                {snapshot.repo_map.tier ? <span>Repo Map {snapshot.repo_map.tier}</span> : null}
                <span id="snapshot-status">
                  {state.cached ? t("Кэш") : t("Новый снимок")} · {state.ageSeconds ?? 0} s
                </span>
              </>
            ) : (
              <span id="home-facts">{unavailable}</span>
            )}
          </div>
        </div>
        <div className="actions">
          <button
            id="home-refresh"
            className="btn"
            type="button"
            disabled={state.status !== "connected"}
            onClick={() => client.requestHome({ force: true, online })}
          >
            <Icon name="refresh" /> {t("Проверить")}
          </button>
          <a className="btn" href={href("diagnostics")}>
            <Icon name="pulse" /> {section("Diagnostics")}
          </a>
          <a className="btn primary" href={href("update-harness")}>
            {t("Обновление")}
          </a>
        </div>
      </div>

      <div className="home-main">
        <section id="home-attention" className="panel home-attn">
          <div className="panel-head">
            <h2>{t("Требует внимания")}</h2>
            <span id="problem-count" className="small muted">
              {snapshot
                ? `${t("{fail} ошибки · {warn} предупреждения", { fail: fails, warn: warns })} · ${shown.length} / ${snapshot.problems_total}`
                : "—"}
            </span>
          </div>
          <div id="attention-list">{snapshot ? <AttentionRows problems={shown} /> : <p className="empty">{unavailable}</p>}</div>
        </section>

        <section id="home-context" className="panel context-panel">
          <div className="panel-head">
            <h2>{t("Контекст")}</h2>
            <span className="small muted">{project?.name ?? t("нет данных")}</span>
          </div>
          <div className="context-grid">
            <div className="context-section">
              <h3>
                <Icon name="github" /> {t("Проект")}
                {project?.tracker ? <span className="provider">{project.tracker}</span> : null}
              </h3>
              <dl className="kv">
                <Fact label={fact("Имя")} value={project?.name ?? null} />
                <Fact label={fact("Ветка")} value={project?.branch ?? null} />
                <Fact label={fact("Трекер")} value={project?.tracker || null} />
              </dl>
            </div>
            <div className="context-section">
              <h3>
                <Icon name="harness" /> Harness
              </h3>
              <dl className="kv">
                <Fact label={fact("Пакет")} value={snapshot ? `${snapshot.harness_version}${channel}` : null} tone="good" />
                <Fact
                  label={fact("Установлено")}
                  value={install ? (install.installed ? install.installed_version : t("не установлен")) : null}
                />
                <Fact label="Capability" value={install ? String(install.capabilities) : null} />
                <Fact
                  label={fact("Скиллы")}
                  value={install ? `${install.skills} · drift ${drift ? drift.total : "—"}` : null}
                  tone={drift?.total ? "warning" : ""}
                />
              </dl>
            </div>
            <div className="context-section">
              <h3>
                <Icon name="store" /> Runtime store
              </h3>
              <dl className="kv">
                <Fact label="Authority" value={store?.authority ?? null} tone="good" />
                <Fact label="Schema" value={store?.schema != null ? String(store.schema) : null} />
                <Fact label="Generation" value={store?.generation ?? null} />
                <Fact
                  label="Audit"
                  value={store?.audit_records != null ? t("{count} записей", { count: store.audit_records }) : null}
                />
                <Fact label="Cutover" value={null} />
              </dl>
            </div>
            <div className="context-section">
              <h3>
                <Icon name="map" /> Repo Map
              </h3>
              <dl className="kv">
                <Fact label={fact("Уровень")} value={snapshot?.repo_map.tier ?? null} tone="good" />
                <Fact label={t("Файлы")} value={map ? number(map.files) : null} />
                <Fact label={t("Связи")} value={map ? number(map.edges) : null} />
                <Fact
                  label={t("Объём")}
                  value={map ? t("≈{count} токенов", { count: number(map.estimated_tokens) }) : null}
                />
                <Fact
                  label="HEAD"
                  value={snapshot ? (map ? `${map.origin} · ${map.commit}` : t("Нет карты для HEAD")) : null}
                />
              </dl>
            </div>
            <div className="context-section">
              <h3>
                <Icon name="memory" /> {t("Память")}
              </h3>
              <dl className="kv">
                <Fact
                  label={fact("Состояние")}
                  value={memory?.state ? `${stateText(memory.state.status)}: ${t(memory.state.message)}` : null}
                  tone={memory?.state && memory.state.status !== "ok" ? "warning" : ""}
                />
                <Fact label={t("Источники")} value={policy ? policy.source_types.join(" · ") || "—" : null} />
                <Fact
                  label={t("Лимит")}
                  value={
                    policy && policy.top_k !== null && policy.max_tokens !== null
                      ? t("{top} · {tokens} токенов", { top: policy.top_k, tokens: number(policy.max_tokens) })
                      : null
                  }
                />
              </dl>
              {policy && (policy.problem || policy.inactive) ? (
                <p className="aside-note">{`${policy.problem} ${policy.inactive}`.trim()}</p>
              ) : null}
            </div>
          </div>
        </section>

        <RecentTasks sessions={snapshot?.recent_sessions ?? []} />

        <section id="home-health" className="panel health-panel">
          <div className="panel-head">
            <div className="health-head-title">
              <h2>{t("Здоровье")}</h2>
              <span id="home-checked" className="small muted">
                {clock} · {t("{count} проверок", { count: total })}
              </span>
            </div>
            <div className="health-mode">
              <span id="health-mode-note" className="small muted">
                {online ? t("Онлайн · обновление только по запросу") : t("Офлайн · обновление каждые 15 секунд")}
              </span>
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
              <div className="hs-item">
                <span id="health-ok" className="ok">{health ? health.ok : "—"}</span>
                <small>{t("пройдено")}</small>
              </div>
              <div className="hs-item">
                <span id="health-warn" className="warn">{health ? health.warn : "—"}</span>
                <small>{t("внимание")}</small>
              </div>
              <div className="hs-item">
                <span id="health-fail" className="err">{health ? health.fail : "—"}</span>
                <small>{t("ошибки")}</small>
              </div>
              <div className="hs-item">
                <span id="health-skipped" className="muted">{health ? health.skipped : "—"}</span>
                <small>{t("пропущено")}</small>
              </div>
            </div>
            {snapshot ? <HealthStrip health={snapshot.health} /> : null}
            <div className="health-cols">
              <section id="home-areas" className="health-areas">
                <div className="subhead">
                  <h3>{t("По областям")}</h3>
                  <a href={href("diagnostics")} className="small">
                    {t("Все проверки →")}
                  </a>
                </div>
                <div className="health-areas-grid">
                  <AreaRows areas={snapshot?.areas ?? []} />
                </div>
              </section>
              <section className="health-checks">
                <div className="subhead">
                  <h3>{t("Проверки")}</h3>
                  <div className="chips" id="home-filters">
                    {(
                      [
                        ["all", t("Все")],
                        ["problem", t("Проблемы")],
                        ["skipped", t("Пропущено")],
                      ] as const
                    ).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        className={`chip ${filter === key ? "on" : ""}`}
                        aria-pressed={filter === key}
                        onClick={() => setFilter(key)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
                <p id="problems-limit" className="small muted">
                  {snapshot
                    ? t("Показано {shown} из {total} · Полный каталог проверок недоступен", {
                        shown: shown.length,
                        total: snapshot.problems_total,
                      })
                    : t("Полный каталог проверок недоступен")}
                </p>
                <div
                  id="home-checks"
                  className="checks-scroll"
                  tabIndex={0}
                  aria-label={t("Проверки; прокрутите список, чтобы увидеть остальные")}
                >
                  {snapshot ? <CheckRows rows={checkRows} /> : unavailable}
                </div>
              </section>
            </div>
          </div>
        </section>

        <Contour snapshot={snapshot} />
      </div>
    </div>
  );
}
