/* Home: the blocks of the mockup filled only with facts of the Home snapshot. A fact the
   snapshot does not carry is shown as unavailable, never invented. */
import { useEffect, useRef, useState } from "react";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useConsole } from "../useConsole";
import type { HomeSnapshot, Problem } from "../ws/types";
import { healthTotal } from "../ws/types";

/** Offline mode asks again this long after each reply. */
export const OFFLINE_REFRESH_MS = 15000;
/** Orchestration events are coalesced into one refresh after this pause. */
export const EVENTS_DEBOUNCE_MS = 1000;

const STATUS_ICON: Record<string, string> = { ok: "check", warn: "warning", fail: "x", skipped: "clock" };

function Unavailable() {
  const { t } = useI18n();
  return (
    <dd className="muted" title={t("Недоступно в текущем снимке")}>
      —
    </dd>
  );
}

function Fact({ label, value }: { label: string; value: string | null }) {
  const { t } = useI18n();
  return (
    <div>
      <dt>{label}</dt>
      {value === null ? (
        <dd className="muted" title={t("Недоступно в текущем снимке")}>
          {t("Недоступно в текущем снимке")}
        </dd>
      ) : (
        <dd>{value}</dd>
      )}
    </div>
  );
}

function ProblemRows({ problems, attention }: { problems: Problem[]; attention: boolean }) {
  const { t } = useI18n();
  const statusLabel: Record<string, string> = {
    ok: t("пройдено"),
    warn: t("внимание"),
    fail: t("ошибки"),
    skipped: t("пропущено"),
  };
  if (!problems.length) {
    return <p className="muted">{t("В списке нет проблем; это не подтверждает полноту проверок")}</p>;
  }
  return (
    <>
      {problems.map((problem, index) => {
        const known = Object.hasOwn(STATUS_ICON, problem.status);
        const tone = attention && problem.status === "fail" ? "err" : problem.status;
        return (
          <div className={attention ? "it" : "check-row"} key={`${problem.id}-${index}`}>
            <span
              className={`${attention ? "home-alert-icon" : "check-icon"}${known ? ` ${tone}` : ""}`}
              role="img"
              aria-label={statusLabel[problem.status] ?? problem.status}
            >
              <Icon name={STATUS_ICON[problem.status] ?? "info"} />
            </span>
            <span className={attention ? "t" : "check-main"}>
              <b>{problem.id}</b>
              <small>{problem.message}</small>
            </span>
          </div>
        );
      })}
    </>
  );
}

function HealthStrip({ snapshot }: { snapshot: HomeSnapshot }) {
  const { t } = useI18n();
  const health = snapshot.health;
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

function Contour() {
  const { t } = useI18n();
  const note = t("Схема, состояние не проверено");
  return (
    <section id="home-contour" className="panel contour-panel">
      <div className="panel-head">
        <h2>{t("Контур Harness 2.0.0")}</h2>
        <span className="small muted">{note}</span>
      </div>
      <div className="body">
        <div className="contour-scroll">
          <svg className="contour-svg" viewBox="0 0 800 110" role="img" aria-label={note}>
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
        <p className="contour-note">
          {note}. {t("Недоступно в текущем снимке")}
        </p>
      </div>
    </section>
  );
}

export function Home() {
  const { t, section, fact, language } = useI18n();
  const { state, client, replies, events } = useConsole();
  const [online, setOnline] = useState(false);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);
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
  const clock = checkedAt
    ? new Intl.DateTimeFormat(language, { timeStyle: "medium" }).format(checkedAt)
    : "—";

  return (
    <div id="home">
      <div className="page-title home-title">
        <div>
          <h1>{t("Состояние харнесса")}</h1>
          <p>{t("Здоровье, контекст и последние задачи проекта")}</p>
          <div className="home-facts">
            <span id="home-facts">
              {health
                ? `${t("пройдено")}: ${health.ok} · ${t("внимание")}: ${health.warn} · ${t("ошибки")}: ${health.fail} · ${t("пропущено")}: ${health.skipped}`
                : unavailable}
            </span>
            {snapshot ? (
              <span id="snapshot-status">
                {state.cached ? t("Кэш") : t("Новый снимок")} · {state.ageSeconds ?? 0} s
              </span>
            ) : null}
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
            {section("Update Harness")}
          </a>
        </div>
      </div>

      <div className="home-main">
        <section id="home-attention" className="panel home-attn">
          <div className="panel-head">
            <h2>{t("Требует внимания")}</h2>
            <span id="problem-count" className="small muted">
              {snapshot ? `${shown.length} / ${snapshot.problems_total}` : "—"}
            </span>
          </div>
          <div id="attention-list" className="body">
            {snapshot ? <ProblemRows problems={shown} attention /> : unavailable}
          </div>
        </section>

        <section id="home-context" className="panel context-panel">
          <div className="panel-head">
            <h2>{t("Контекст")}</h2>
          </div>
          <div className="context-grid">
            <div className="context-section">
              <h3>{t("Проект")}</h3>
              <dl className="kv">
                {["Имя", "Ветка", "Трекер"].map((label) => (
                  <div key={label}>
                    <dt>{fact(label)}</dt>
                    <Unavailable />
                  </div>
                ))}
              </dl>
            </div>
            <div className="context-section">
              <h3>Harness</h3>
              <dl className="kv">
                <Fact label={fact("Пакет")} value={snapshot?.harness_version ?? null} />
                <Fact label={t("Дрейф")} value={snapshot?.drift ?? null} />
                {["Установлен", "Capability", "Скиллы"].map((label) => (
                  <div key={label}>
                    <dt>{fact(label)}</dt>
                    <Unavailable />
                  </div>
                ))}
              </dl>
            </div>
            <div className="context-section">
              <h3>Runtime store</h3>
              <dl className="kv">
                {["Authority", "Schema", "Generation", "Audit", "Cutover"].map((label) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <Unavailable />
                  </div>
                ))}
              </dl>
            </div>
            <div className="context-section">
              <h3>Repo Map</h3>
              <dl className="kv">
                <Fact label={fact("Уровень")} value={snapshot?.repo_map.tier ?? null} />
                <Fact
                  label="HEAD"
                  value={snapshot ? (map ? `${map.origin} · ${map.commit}` : t("Нет карты для HEAD")) : null}
                />
                <Fact
                  label={t("Детали")}
                  value={
                    snapshot
                      ? map
                        ? `${snapshot.repo_map.message} · ${map.files} files · ${map.edges} edges · ≈${map.estimated_tokens} tokens`
                        : snapshot.repo_map.message
                      : null
                  }
                />
              </dl>
            </div>
            <div className="context-section">
              <h3>{t("Память")}</h3>
              <dl className="kv">
                <Fact
                  label={fact("Состояние")}
                  value={memory?.state ? `${memory.state.status}: ${memory.state.message}` : null}
                />
                <Fact
                  label={t("Политика")}
                  value={
                    policy
                      ? `enabled=${policy.enabled} · active=${policy.active} · ${policy.source_types.join(", ")} · indexed=${policy.indexed ?? "—"} · top_k=${policy.top_k ?? "—"} · max_tokens=${policy.max_tokens ?? "—"} · ${policy.problem} ${policy.inactive}`.trim()
                      : null
                  }
                />
              </dl>
            </div>
          </div>
        </section>

        <section id="home-tasks" className="panel tasks-panel">
          <div className="panel-head">
            <h2>{t("Последние задачи")}</h2>
            <a className="small" href={href("orchestration")}>
              {section("Orchestration")} →
            </a>
          </div>
          <div className="body">
            <p>{t("Задачи, роли, возраст и маршрут не входят в текущий снимок")}</p>
            <dl className="kv">
              <Fact
                label={t("Активные batch")}
                value={snapshot && snapshot.active_batches !== null ? String(snapshot.active_batches) : null}
              />
            </dl>
          </div>
        </section>

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
                <button
                  className={online ? "" : "on"}
                  type="button"
                  aria-pressed={!online}
                  onClick={() => switchMode(false)}
                >
                  {t("Офлайн")}
                </button>
                <button
                  className={online ? "on" : ""}
                  type="button"
                  aria-pressed={online}
                  onClick={() => switchMode(true)}
                >
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
            {snapshot ? <HealthStrip snapshot={snapshot} /> : null}
            <div className="health-cols">
              <section id="home-areas" className="health-areas">
                <div className="subhead">
                  <h3>{t("По областям")}</h3>
                </div>
                <div className="health-areas-grid">
                  <p className="muted">{unavailable}</p>
                </div>
              </section>
              <section className="health-checks">
                <div className="subhead">
                  <h3>{t("Проверки")}</h3>
                  <span className="small muted">{t("Только проблемы из снимка")}</span>
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
                  {snapshot ? <ProblemRows problems={shown} attention={false} /> : unavailable}
                </div>
              </section>
            </div>
          </div>
        </section>

        <Contour />
      </div>
    </div>
  );
}
