/* Home: the blocks of the mockup filled only with facts of the Home snapshot. A fact the
   snapshot does not carry is shown as unavailable, never invented. */
import { useEffect, useRef, useState } from "react";
import { Icon } from "../icons";
import { groupLabel, useI18n } from "../i18n";
import { href } from "../navigation";
import { preRelease } from "../AppShell";
import { useConsole } from "../useConsole";
import type {
  AreaCounters,
  HarnessInstall,
  HealthCounters,
  HomeSnapshot,
  Problem,
  RecentSession,
  StoreFacts,
} from "../ws/types";
import { healthTotal } from "../ws/types";

/** Offline mode asks again this long after each reply. */
export const OFFLINE_REFRESH_MS = 15000;
/** Orchestration events are coalesced into one refresh after this pause. */
export const EVENTS_DEBOUNCE_MS = 1000;

const STATUS_ICON: Record<string, string> = { ok: "check", warn: "warning", fail: "x", skipped: "clock" };

/** The icon of the git hosting `resolve_project_tracker` resolved; local work has a folder. */
const HOSTING_ICON: Record<string, string> = { github: "github-mark", gitlab: "gitlab-mark", local: "folder" };

type Translate = (text: string, values?: Readonly<Record<string, string | number>>) => string;

/** The installed capability names; a name outside the catalog is marked. */
function capabilityText(install: HarnessInstall, t: Translate): string {
  if (!install.capability_names.length) return t("не установлены");
  return install.capability_names
    .map((name) => (install.uncatalogued.includes(name) ? `${name} (${t("вне каталога")})` : name))
    .join(" · ");
}

/** The cutover time of the runtime store; the file ledger has had none. */
function cutoverText(store: StoreFacts | null, t: Translate): string | null {
  if (!store || store.authority === "none") return null;
  if (store.cutover_at) return store.cutover_at.slice(0, 16).replace("T", " ");
  return store.authority === "file-ledger" ? t("не выполнен") : null;
}

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
  const { t, language, check } = useI18n();
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
            <b title={problem.id}>{check(problem.id)}</b>
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
  const { t, language, check } = useI18n();
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
            <b title={row.id}>{check(row.id)}</b>
            <small>{row.message}</small>
          </span>
          <span className="check-area">{row.group ? groupLabel(language, row.group) : "—"}</span>
        </a>
      ))}
    </>
  );
}

/** The mockup's icon of each health area (docs/design/web-console-mockups, homeAreas). */
const AREA_ICON: Record<string, string> = {
  files: "harness",
  skills: "skills",
  directories: "folder",
  repo_map: "map",
  "repo-map": "map",
  memory: "memory",
  environment: "terminal",
  hooks: "shield",
  tracker: "github",
  integration: "github",
  orchestration: "orchestration",
  runtime: "runtime",
  store: "store",
};

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
              <Icon name={AREA_ICON[area.area] ?? "pulse"} />
              <span>{name}</span>
            </span>
            <span
              className="health-bar"
              role="img"
              aria-label={`${name}: ${t("пройдено")} ${area.ok}, ${t("внимание")} ${area.warn}, ${t("ошибки")} ${area.fail}, ${t("пропущено")} ${area.skipped}`}
            >
              {segments.map(([value, css]) =>
                value ? <i key={css} className={css} style={{ width: `${(value / total) * 100}%` }} /> : null,
              )}
            </span>
            <span className="health-count">
              <span className="ok">{area.ok}✓</span> <span className="warn">{area.warn}⚠</span>{" "}
              <span className="fail">{area.fail}✖</span> <span className="skip">{area.skipped}–</span>
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

/** The mockup's role icons; a role without one keeps the activity glyph. */
const ROLE_ICON: Record<string, string> = {
  architect: "architect",
  developer: "developer",
  "code-review": "review",
  review: "review",
  qa: "qa",
};

function sessionTone(state: string): string {
  if (["blocked", "failed", "abandoned", "auto_stop"].includes(state)) return "err";
  if (["active", "working", "running"].includes(state)) return "ok";
  return "warn";
}

const TONE_ICON: Record<string, string> = { ok: "play", err: "blocked", warn: "awaiting" };
const RUNNING = ["working", "running", "dispatched"];

/** The run time of a session, from its creation to its latest dispatch, in whole units. */
export function sessionDuration(created: string, updated: string, language: string): string {
  const start = Date.parse(created);
  const end = Date.parse(updated);
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "—";
  const minutes = Math.round((end - start) / 60000);
  const ru = language !== "en";
  if (minutes < 60) return ru ? `${minutes} мин` : `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return ru ? `${hours} ч` : `${hours} h`;
  const days = Math.round(hours / 24);
  return ru ? `${days} дн` : `${days} d`;
}

function RecentTasks({ sessions }: { sessions: RecentSession[] }) {
  const { t, section, language, state: stateText } = useI18n();
  const [query, setQuery] = useState("");
  const wanted = query.replace(/[^0-9]/g, "");
  const shown = wanted ? sessions.filter((session) => session.ticket.replace(/[^0-9]/g, "") === wanted) : sessions;
  const active =
    shown.find((session) => sessionTone(session.state) === "ok") ?? shown[0] ?? null;
  const lastRole = (session: RecentSession) => session.route[session.route.length - 1]?.role ?? "";
  return (
    <section id="home-tasks" className="panel tasks-panel">
      <div className="panel-head">
        <h2>
          {t("Последние задачи")} <span className="small muted">{sessions.length}</span>
        </h2>
        <label className="task-search">
          <Icon name="search" />
          <input
            type="search"
            inputMode="numeric"
            placeholder={t("Номер тикета")}
            aria-label={t("Поиск задачи по номеру")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
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
            {shown.map((session) => {
              const tone = sessionTone(session.state);
              const role = lastRole(session);
              return (
                <a className="task-row" key={session.batch_id} href={href("orchestration")}>
                  <span className="task-id">{session.ticket || "—"}</span>
                  <span className="task-role" title={ROLE_NAMES[role] ?? role}>
                    <Icon name={ROLE_ICON[role] ?? "activity"} />
                  </span>
                  <span className="task-title" title={t("Название задачи недоступно; показана ветка")}>
                    {session.branch || session.batch_id}
                  </span>
                  <span className={`task-status ${tone}`}>
                    <Icon name={TONE_ICON[tone]} /> {stateText(session.state)}
                  </span>
                  <span className="task-time" title={session.created_at}>
                    {sessionDuration(session.created_at, session.updated_at, language)}
                  </span>
                </a>
              );
            })}
            {wanted && !shown.length ? (
              <p className="empty">{t("Задача #{number} не найдена среди последних сессий", { number: wanted })}</p>
            ) : null}
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
            <a href={href("agent-activity")} className="small route-link">
              {section("Ход работы")} →
            </a>
          </div>
          <div className="route-scroll" tabIndex={0} role="region" aria-label={t("Маршрут сессии")}>
            <div className="route-steps route-steps-fill" key={active.batch_id}>
              {active.route.length ? (
                active.route.map((step, index) => (
                  <div
                    className={`route-step ${RUNNING.includes(step.state) ? "current" : "done"}`}
                    key={`${step.role}-${index}`}
                  >
                    <span className="route-dot">
                      <Icon name={ROLE_ICON[step.role] ?? "activity"} />
                    </span>
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

/** The Harness 2.0.0 contour of the mockup (homeContour): the structure is fixed, every value
    comes from the snapshot; the typed IPC edge moves only while a batch is active. */
function Contour({ snapshot }: { snapshot: HomeSnapshot | null }) {
  const { t } = useI18n();
  const store = snapshot?.store ?? null;
  const value = (text: string | number | null | undefined) =>
    text === null || text === undefined ? <b className="muted">{t("нет данных")}</b> : <b>{text}</b>;
  const live = (snapshot?.active_batches ?? 0) > 0 ? " live" : "";
  const fact = (text: string | number | null | undefined) => (text === null || text === undefined ? "—" : String(text));
  return (
    <section id="home-contour" className="panel contour-panel">
      <div className="panel-head">
        <h2>{t("Контур Harness")}</h2>
        <span className="contour-ready small">
          {store ? (
            <>
              <Icon name={store.authority === "none" ? "warning" : "check"} /> {store.authority}
            </>
          ) : (
            t("нет данных")
          )}
        </span>
      </div>
      <div className="body">
        <div className="contour-scroll" tabIndex={0} role="region" aria-label={t("Схема контура Harness")}>
          <svg className="contour-svg" viewBox="0 0 1000 400" role="img" aria-label={t("Схема контура Harness")}>
            <defs>
              <marker id="ct-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M0 0 8 4 0 8z" fill="#6b7787" />
              </marker>
            </defs>
            <rect className="ct-lane" x="12" y="10" width="976" height="105" rx="6" />
            <rect className="ct-lane" x="12" y="125" width="976" height="140" rx="6" />
            <rect className="ct-lane" x="12" y="272" width="976" height="112" rx="6" />
            <text className="ct-lane-label" x="24" y="31">01 · Policy</text>
            <text className="ct-lane-label" x="24" y="146">02 · Runtime</text>
            <text className="ct-lane-label" x="24" y="292">03 · Evidence</text>
            <g className="ct-node">
              <rect x="30" y="42" width="250" height="64" rx="7" />
              <text className="ct-title" x="43" y="61">Python policy</text>
              <text className="ct-sub" x="43" y="77">coordinator · approval</text>
              <text className="ct-sub" x="43" y="89">verification plan</text>
            </g>
            <g className="ct-node">
              <rect x="342" y="42" width="200" height="64" rx="7" />
              <text className="ct-title" x="355" y="61">runtime_client · IPC</text>
              <text className="ct-sub" x="355" y="77">typed request · revision CAS</text>
            </g>
            <g className="ct-node primary">
              <rect x="342" y="145" width="250" height="70" rx="7" />
              <text className="ct-title" x="355" y="165">Rust runtime</text>
              <text className="ct-sub" x="355" y="181">single writer · schema {fact(store?.schema)}</text>
            </g>
            <g className="ct-node">
              <rect x="680" y="140" width="296" height="54" rx="7" />
              <text className="ct-title" x="693" y="160">SQLite WAL store</text>
              <text className="ct-sub" x="693" y="176">generation {fact(store?.generation)}</text>
            </g>
            <g className="ct-node">
              <rect x="680" y="204" width="296" height="54" rx="7" />
              <text className="ct-title" x="693" y="224">Supervisor</text>
              <text className="ct-sub" x="693" y="240">process · OCI · QA</text>
            </g>
            <g className="ct-node">
              <rect x="342" y="292" width="250" height="54" rx="7" />
              <text className="ct-title" x="355" y="311">Audit chain</text>
              <text className="ct-sub" x="355" y="327">{t("{count} записей", { count: fact(store?.audit_records) })}</text>
            </g>
            <g className="ct-node">
              <rect x="680" y="292" width="296" height="54" rx="7" />
              <text className="ct-title" x="693" y="311">Execution receipts</text>
              <text className="ct-sub" x="693" y="327">exit evidence · lost evidence</text>
            </g>
            <path className="ct-edge" d="M280 74H342" markerEnd="url(#ct-arrow)" />
            <path className={`ct-edge blue${live}`} d="M542 74H600V112H465V145" markerEnd="url(#ct-arrow)" />
            <path className="ct-edge" d="M592 167H680" markerEnd="url(#ct-arrow)" />
            <path className="ct-edge" d="M592 200H646V231H680" markerEnd="url(#ct-arrow)" />
            <path className="ct-edge" d="M465 215V292" markerEnd="url(#ct-arrow)" />
            <path className="ct-edge" d="M828 258V292" markerEnd="url(#ct-arrow)" />
            <text className="ct-edge-label" x="288" y="68">decision</text>
            <text className="ct-edge-label" x="552" y="68">typed</text>
            <text className="ct-edge-label" x="600" y="161">write</text>
            <text className="ct-edge-label" x="600" y="194">launch</text>
            <text className="ct-edge-label" x="472" y="284">audit</text>
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
            {value(cutoverText(store, t))}
          </div>
          <div>
            <span>Repo Map</span>
            {value(snapshot?.repo_map.tier)}
          </div>
        </div>
        {store?.reason ? <p className="contour-note">{t(store.reason)}</p> : null}
        <p className="contour-note">
          {t("Схема показывает устройство контура, а не поток конкретного batch. Python решает; Rust пишет состояние и исполняет.")}
        </p>
      </div>
    </section>
  );
}

export function Home() {
  const { t, section, fact, language, state: stateText, plural } = useI18n();
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
  const stale = snapshot?.repo_map.stale_map ?? null;
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
                  {health ? `${health.ok} ${t("пройдено")} · ${health.warn} ${t("внимание")} · ${health.fail} ${t("ошибки")} · ${health.skipped} ${t("пропущено")}` : unavailable}
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
                ? `${plural(fails, ["ошибка", "ошибки", "ошибок"], ["error", "errors"])} · ${plural(warns, ["предупреждение", "предупреждения", "предупреждений"], ["warning", "warnings"])} · ${shown.length} / ${snapshot.problems_total}`
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
                <Icon name={HOSTING_ICON[project?.tracker ?? ""] ?? "folder"} /> {t("Проект")}
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
                <Fact label="Capability" value={install ? capabilityText(install, t) : null} />
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
                <Fact label="Cutover" value={cutoverText(store, t)} />
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
              {snapshot && !map && stale ? (
                <p className="stale-map small">
                  <Icon name="warning" />{" "}
                  {t("Карта {commit} устарела для HEAD: {files} файлов, ≈{tokens} токенов", {
                    commit: stale.commit.slice(0, 7),
                    files: number(stale.files),
                    tokens: number(stale.estimated_tokens),
                  })}{" "}
                  <a href={href("repo-map")}>
                    <Icon name="refresh" /> {t("Перестроить")}
                  </a>
                </p>
              ) : null}
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
