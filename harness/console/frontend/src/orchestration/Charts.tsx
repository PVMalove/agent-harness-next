/* The mockup's Orchestration tabs over the server's snapshot: the grouped pipeline map of
   "Поток" and the chart cards of "Поток", "Качество", "Runtime" and "Решения". Every figure is
   the kernel's (analytics) or the ledger's (open stages); a mockup card without a source keeps
   an explicit no-data state with its reason. Only an edge into a running role moves. */
import { Panel as DsPanel } from "../ds";
import { useI18n } from "../i18n";
import { Bar, NoData, roleName } from "../steps/ActivityViews";
import type { Figure, OrchestrationSnapshot } from "../ws/ledger";
import { AGING, AGING_BUCKETS, ROLE_NODE, liveSteps, seconds } from "./format";
import { GateTrend } from "./OrchViews";

const ACTIVE = new Set(["working", "dispatched", "approved"]);
const ATTENTION = new Set(["failed", "blocked", "auto_stop"]);
const DONE = new Set(["completed", "accepted", "merged", "done", "passed", "published", "closed"]);
const WAITING = new Set(["awaiting", "awaiting_decision", "needs_decision", "queued", "pending", "held"]);
/** A state's tone by its meaning, so a waiting state is never painted in the blocker hue: attention
    in rose, live work in the accent, finished work in mint, waiting in sand; any other key takes the
    neutral tones in turn (UI audit 2026-11-17: the tone used to follow the position). */
function toneOf(key: string, index: number): string {
  if (ATTENTION.has(key)) return "violet";
  if (ACTIVE.has(key)) return "cyan";
  if (DONE.has(key)) return "mint";
  if (WAITING.has(key)) return "lavender";
  return ["blue", "muted"][index % 2]!;
}

type Counts = Record<string, number>;
const counts = (figure: Figure | undefined): Counts =>
  figure && typeof figure === "object" && !Array.isArray(figure) ? (figure as Counts) : {};
const total = (values: Counts) => Object.values(values).reduce((sum, value) => sum + value, 0);
const minutes = (value: number) => Math.round(value / 60);

function Card({ title, note, wide, id, children }: { title: string; note?: string; wide?: boolean; id?: string; children: React.ReactNode }) {
  return (
    <article className={wide ? "orch-chart wide" : "orch-chart"} id={id}>
      <div className="orch-chart-head">
        <h3>{title}</h3>
        {note ? <span>{note}</span> : null}
      </div>
      {children}
    </article>
  );
}

function Rows({ values, tone = "cyan", name = (key) => key, unit = (value) => String(value) }: {
  values: Counts;
  tone?: string;
  name?: (key: string) => string;
  unit?: (value: number) => string;
}) {
  const { t } = useI18n();
  const entries = Object.entries(values);
  if (!entries.length) return <p className="orch-note">{t("в ledger нет данных")}</p>;
  const max = Math.max(...entries.map(([, value]) => value));
  return (
    <>
      {entries.map(([key, value]) => (
        <div className="work-stat-row orch-row" key={key}>
          <span>{name(key)}</span>
          <Bar value={value} max={max} tone={tone} />
          <b>{unit(value)}</b>
        </div>
      ))}
    </>
  );
}

/** The mockup's stacked bar with its legend. */
function Stack({ values, name }: { values: Counts; name: (key: string) => string }) {
  const { t } = useI18n();
  const entries = Object.entries(values).filter(([, value]) => value > 0);
  const sum = total(values);
  if (!entries.length) return <p className="orch-note">{t("в ledger нет данных")}</p>;
  return (
    <>
      <div className="orch-stack">
        {entries.map(([key, value], index) => (
          <i key={key} className={toneOf(key, index)} style={{ width: `${Math.round((value / sum) * 100)}%` }} title={`${name(key)}: ${value}`} />
        ))}
      </div>
      <div className="orch-legend">
        {entries.map(([key, value], index) => (
          <span key={key}>
            <i className={toneOf(key, index)} />
            {name(key)} <b>{value}</b>
          </span>
        ))}
      </div>
    </>
  );
}

/** p50 and p95 per key, in minutes, as the mockup's paired bars. */
function Pairs({ p50, p95 }: { p50: Counts; p95: Counts }) {
  const { t } = useI18n();
  const keys = [...new Set([...Object.keys(p50), ...Object.keys(p95)])];
  if (!keys.length) return <p className="orch-note">{t("в ledger нет данных")}</p>;
  const max = Math.max(1, ...keys.map((key) => minutes(p95[key] ?? p50[key] ?? 0)));
  return (
    <>
      {keys.map((key) => (
        <div className="orch-stage-row" key={key}>
          <span>{roleName(key)}</span>
          <div className="orch-stage-bars">
            {([[p50[key], "cyan"], [p95[key], "lavender"]] as const).map(([value, tone]) => (
              <div key={tone}>
                <Bar value={minutes(value ?? 0)} max={max} tone={tone} />
                <small>{value === undefined ? "—" : minutes(value)}</small>
              </div>
            ))}
          </div>
        </div>
      ))}
      <div className="orch-legend">
        <span>
          <i className="cyan" />
          p50
        </span>
        <span>
          <i className="lavender" />
          p95
        </span>
      </div>
    </>
  );
}

function Missing({ title, why }: { title: string; why: string }) {
  return (
    <Card title={title}>
      <p className="orch-note">
        <NoData why={why} />
      </p>
    </Card>
  );
}

/** The body of an analytics tab. The v3 panel around it carries the tab's title, so this draws no
    frame and no heading of its own, only the tab's note above the charts. */
function Panel({ tab, note, children }: { tab: string; title: string; note: string; children: React.ReactNode }) {
  return (
    <div className="orch-analytics ds-analytics" id="orch-tab-view" data-tab={tab}>
      <p className="ds-note">{note}</p>
      <div className="orch-analytics-grid">{children}</div>
    </div>
  );
}

export function FlowTab({ data }: { data: OrchestrationSnapshot }) {
  const { t, language, state } = useI18n();
  const flow = data.analytics.flow;
  const aging = counts(flow.aging);
  const prs = Array.isArray(flow.pr_per_day) ? flow.pr_per_day.reduce<number>((sum, value) => sum + (value ?? 0), 0) : 0;
  return (
    <Panel tab="flow" title={t("Поток")} note={t("срез, не тренд")}>
      <Card title={t("В работе по состояниям")} note={t("{count} batch", { count: total(counts(flow.by_state)) })} wide>
        <Stack values={counts(flow.by_state)} name={state} />
      </Card>
      <Card title={t("Старение работы")} note={t("незавершённые batch")}>
        <div className="orch-aging-head">
          <span />
          {AGING_BUCKETS.map((bucket) => (
            <span key={bucket}>{AGING[language][bucket]}</span>
          ))}
        </div>
        <div className="orch-aging-row">
          <span>batch</span>
          {AGING_BUCKETS.map((bucket, index) => (
            <span key={bucket} className={`orch-aging-cell ${aging[bucket] ? "on" : ""} t${index}`}>
              {aging[bucket] || ""}
            </span>
          ))}
          <small>{total(aging)}</small>
        </div>
      </Card>
      <Card title={t("Время цикла p50 / p95")} note={t("минуты")}>
        <Pairs p50={counts(flow.stage_p50_by_role)} p95={counts(flow.stage_p95_by_role)} />
      </Card>
      <Card title={t("Ожидание")} note={t("p50, минуты")} wide>
        <Rows values={counts(flow.wait_p50_by_role)} tone="blue" name={roleName} unit={(value) => String(minutes(value))} />
      </Card>
      <article className="orch-chart wide orch-mini-flow">
        <div>
          <span>{t("PR за 7 дней")}</span>
          <b>{prs}</b>
        </div>
        <div>
          <span>{t("Цикл до PR p50 / p95")}</span>
          <b>
            {seconds(flow.cycle_p50_seconds, language)} / {seconds(flow.cycle_p95_seconds, language)}
          </b>
        </div>
        <div>
          <span>{t("Эффективность потока")}</span>
          <b>
            <NoData why={t("Активное время роли не отделено от ожидания в ledger")} />
          </b>
        </div>
      </article>
    </Panel>
  );
}

export function QualityTab({ data }: { data: OrchestrationSnapshot }) {
  const { t, state } = useI18n();
  const quality = data.analytics.quality;
  const passed = typeof quality.qa_first_pass === "number" ? quality.qa_first_pass : 0;
  const tickets = typeof quality.qa_tickets === "number" ? quality.qa_tickets : 0;
  const why = t("Источника в ledger нет");
  return (
    <Panel tab="quality" title={t("Качество")} note={t("переработки и evidence")}>
      <Card title={t("Повторы по ролям")} note={t("{count} возвратов", { count: total(counts(quality.rework_by_role)) })}>
        <Rows values={counts(quality.rework_by_role)} tone="violet" name={roleName} />
        <div className="orch-findings">
          <span>{t("находки review")}</span>
          {Object.entries(counts(quality.findings_by_severity)).map(([severity, count]) => (
            <b key={severity}>
              {state(severity)} {count}
            </b>
          ))}
        </div>
      </Card>
      <Card title={t("Возвраты и first-pass")} note={t("доля")}>
        <Rows values={counts(quality.returns_by_role)} tone="lavender" name={roleName} />
        <div className="work-stat-row orch-row">
          <span>{t("QA с первого раза")}</span>
          <Bar value={passed} max={tickets} tone="cyan" />
          <b>{tickets ? `${passed} / ${tickets}` : "—"}</b>
        </div>
      </Card>
      <Card title={t("Итоги отчётов")} note={t("{count} отчётов", { count: total(counts(quality.outcomes)) })}>
        <Stack values={counts(quality.outcomes)} name={state} />
      </Card>
      <Card title={t("Отчёты по ролям")}>
        <Rows values={counts(quality.reports_by_role)} name={roleName} />
        <p className="orch-note">{t("Неудачные попытки QA")}: {typeof quality.qa_attempts_failed === "number" ? quality.qa_attempts_failed : 0}</p>
      </Card>
      <Missing title={t("Типы проверок")} why={why} />
      <Missing title="Release Gate" why={why} />
    </Panel>
  );
}

export function RuntimeTab({ data }: { data: OrchestrationSnapshot }) {
  const { t, language, state } = useI18n();
  const runtime = data.analytics.runtime;
  const num = (value: Figure | undefined) => (typeof value === "number" ? value : 0);
  const why = t("Источника в ledger нет");
  return (
    <Panel tab="runtime" title="Runtime" note={t("heartbeat · lease · восстановление")}>
      <Card title={t("Наблюдаемые факты")} wide>
        <div className="orch-health">
          <div>
            <span>{t("Не завершено")}</span>
            <b>{num(runtime.unfinished)}</b>
          </div>
          <div>
            <span>{t("Старейшая не завершённая")}</span>
            <b>{seconds(runtime.oldest_unfinished_seconds, language)}</b>
          </div>
          <div>
            <span>{t("Без движения")}</span>
            <b>{num(runtime.stale)}</b>
          </div>
          <div>
            <span>{t("Heartbeat p95")}</span>
            <b>{seconds(runtime.heartbeat_age_p95_seconds, language)}</b>
          </div>
        </div>
      </Card>
      <Card title={t("Состояния стадий")} note={t("{count} dispatch", { count: total(counts(runtime.stage_states)) })}>
        <Stack values={counts(runtime.stage_states)} name={state} />
      </Card>
      <Card title={t("Возраст открытых этапов")} note={t("минуты")}>
        <Rows values={counts(runtime.open_age_by_role)} tone="blue" name={roleName} unit={(value) => String(minutes(value))} />
      </Card>
      <Missing title="Operations" why={why} />
      <Missing title={t("Удержания восстановления")} why={why} />
    </Panel>
  );
}

export function GatesTab({ data }: { data: OrchestrationSnapshot }) {
  const { t, language, state } = useI18n();
  const gates = data.analytics.gates;
  return (
    <Panel tab="gates" title={t("Гейты")} note={t("ожидание решения человека")}>
      <GateTrend gates={gates} />
      <Card title={t("Ожидание по гейтам")} note={t("p50 / p95, минуты")} wide>
        <Pairs p50={counts(gates.latency_p50_by_gate)} p95={counts(gates.latency_p95_by_gate)} />
      </Card>
      <Card title={t("Очередь гейтов")} wide>
        <div className="orch-health">
          <div>
            <span>{t("Ждут подтверждения")}</span>
            <b>{typeof gates.awaiting === "number" ? gates.awaiting : 0}</b>
          </div>
          <div>
            <span>{t("Ожидание p50 / p95")}</span>
            <b>
              {seconds(gates.approval_p50_seconds, language)} / {seconds(gates.approval_p95_seconds, language)}
            </b>
          </div>
          <div>
            <span>{t("Старейшее ожидание")}</span>
            <b>{seconds(gates.approval_oldest_seconds, language)}</b>
          </div>
        </div>
      </Card>
      <Card title={t("Решения по вердиктам")}>
        <Rows values={counts(gates.decisions_by_verdict)} tone="lavender" name={state} />
      </Card>
      <Card title={t("PR по состояниям")}>
        <Stack values={counts(gates.pr_states)} name={state} />
      </Card>
    </Panel>
  );
}

interface Place {
  tone: string;
  chip: string;
  count: number;
}

/** The mockup's grouped pipeline: plan and approve, build and review with findings, evidence and
    publish. A role node holds the ledger's open stages; the edge into it moves only then. */
export function PipelineMap({ data }: { data: OrchestrationSnapshot }) {
  const { t } = useI18n();
  const live = liveSteps(data.ledger);
  const liveNodes = new Set(live.map((step) => step.node));
  // Only the live step moves: an open stage that is not the newest of its batch stays still.
  const place = (roles: string[]): Place => {
    const open = data.ledger.stages.filter((stage) => roles.includes(stage.role) && (ACTIVE.has(stage.state) || ATTENTION.has(stage.state)));
    const node = ROLE_NODE[roles[0]!] ?? "";
    if (!open.length) return { tone: "idle", chip: "", count: 0 };
    const tone = open.some((stage) => ATTENTION.has(stage.state)) ? "err" : liveNodes.has(node) ? "active" : "warn";
    return { tone, chip: open.at(-1)!.ticket, count: open.length };
  };
  const gateLive = (name: string): Place | undefined => (liveNodes.has(name) ? { tone: "active", chip: "", count: 0 } : undefined);
  const arch = place(["architect"]);
  const dev = place(["developer"]);
  const rev = place(["review", "code-review"]);
  const qa = place(["qa"]);
  const batches = data.ledger.batches;
  const working = batches.filter((batch) => batch.state === "active").length;
  const blocked = batches.filter((batch) => ATTENTION.has(batch.state)).length;
  const awaiting = batches.filter((batch) => batch.state === "awaiting_approval").length;
  const gate = typeof data.analytics.gates.awaiting === "number" && data.analytics.gates.awaiting > 0 ? "wait" : "idle";
  // The mockup's compact geometry (screens-orch-map.js): 1200×270, every node 42 high.
  const h = 42;
  const node = (x: number, y: number, w: number, type: string, tone: string, title: string, sub: string, at?: Place, name: string = title) => (
    <g className={`orch-map-node ${type} ${tone}${type !== "role" && liveNodes.has(name) ? " live" : ""}`} data-node={title}>
      <rect x={x} y={y} width={w} height={h} rx="8" className="orch-map-bg" />
      <rect x={x} y={y + 9} width="3" height={h - 18} rx="1.5" className="orch-map-accent" />
      <text className="orch-map-title" x={x + 14} y={y + 18}>
        {title}
      </text>
      <text className="orch-map-sub" x={x + 14} y={y + 34}>
        {at?.chip ? `${at.chip} · ` : ""}
        {sub}
      </text>
      <g className={`orch-map-count ${at?.count ? "on" : ""}`}>
        <circle cx={x + w - 14} cy={y + 14} r="9" />
        <text x={x + w - 14} y={y + 18} textAnchor="middle">
          {at?.count ?? 0}
        </text>
      </g>
    </g>
  );
  const edge = (d: string, tone: string, into?: Place, dashed = false) => (
    <path className={`orch-map-edge ${tone} ${into?.tone === "active" ? "active" : ""} ${dashed ? "dashed" : ""}`} d={d} markerEnd={`url(#om-${tone})`} />
  );
  const status = (
      <span className="orch-map-statusbar">
        <span className="ok">
          <b>{working}</b> {t("в работе")}
        </span>
        <span className="err">
          <b>{blocked}</b> {t("заблокировано")}
        </span>
        <span className="warn">
          <b>{awaiting}</b> {t("ждёт")}
        </span>
        <span className="muted">{t("{count} задач в конвейере", { count: working + blocked + awaiting })}</span>
        <span className="orch-live">
          {live.length
            ? `${t("живой шаг")}: ${live.map((step) => `${step.ticket} · ${step.kind === "role" ? roleName(step.role) : step.node === "Approve QA" ? "Approve QA" : t(step.node)}`).join("; ")}`
            : t("живого шага нет")}
        </span>
      </span>
  );
  return (
    <DsPanel title={t("Конвейер")} meta={status} id="orch-scheme" className="orch-map-panel orch-scheme">
      {/* A phone scrolls the map sideways inside this focusable region, so the keyboard reaches it (WCAG 2.1.1). */}
      <div className="orch-map-scroll" role="region" tabIndex={0} aria-label={t("Конвейер")}>
        <svg className="orch-map" viewBox="0 0 1200 270" role="img" aria-label={t("Схема ролей оркестрации")}>
          <defs>
            {(
              [
                ["aqua", "var(--ok)"],
                ["sky", "var(--sky)"], // matches `.orch-map-edge.sky` in app.css
                ["rose", "var(--lavender)"], // matches `.orch-map-edge.rose` in app.css
                ["orange", "var(--primary)"],
              ] as const
            ).map(([id, fill]) => (
              <marker key={id} id={`om-${id}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M0 0 8 4 0 8z" fill={fill} />
              </marker>
            ))}
          </defs>
          {(
            [
              ["violet", 8, 224, t("01 · План и approve")],
              ["sky", 252, 580, t("02 · Сборка и review с находками")],
              ["peach", 852, 340, t("03 · Evidence и публикация")],
            ] as const
          ).map(([tone, x, w, label]) => (
            <g className={`orch-group ${tone}`} key={tone}>
              <rect x={x} y="4" width={w} height="262" rx="10" className="orch-group-bg" />
              <text className="orch-group-label" x={x + 16} y="21">
                {label}
              </text>
              <line x1={x} y1="28" x2={x + w} y2="28" className="orch-group-line" />
            </g>
          ))}
          {node(24, 36, 192, "human", "idle", t("Approve плана"), t("гейт человека"))}
          {node(268, 36, 228, "role", arch.tone, t("Архитектор"), t("разбор задачи"), arch)}
          {node(268, 90, 228, "role", dev.tone, t("Разработчик"), t("контекст + TDD"), dev)}
          {node(268, 144, 228, "role", rev.tone, "Code review", t("свежесть базы"), rev)}
          {node(268, 198, 228, "role", qa.tone, "QA · clean-room", t("закреплённый SHA"), qa)}
          {node(540, 144, 240, "exception", "review", t("Находки review"), t("возврат в Developer"))}
          {node(540, 198, 240, "exception", "qa", t("Находки QA"), t("повтор или дефект"))}
          {node(868, 36, 308, "human", gate, "Approve QA", t("гейт человека"), undefined, "Approve QA")}
          {node(868, 90, 308, "coord", "idle", t("Итоговый отчёт"), t("evidence + решение"), undefined, "Итоговый отчёт")}
          {node(868, 144, 308, "coord", "idle", t("Публикация"), t("принятый SHA"))}
          {node(868, 198, 308, "human", "idle", "/to-pull-requests", t("передача человеку"))}
          {edge("M216 57H268", "aqua", arch)}
          {edge("M382 78V90", "aqua", dev)}
          {edge("M382 132V144", "sky", rev)}
          {edge("M382 186V198", "aqua", qa)}
          {edge("M496 165H540", "rose")}
          {edge("M496 219H540", "rose")}
          {edge("M540 165H518V111H496", "rose", undefined, true)}
          {edge("M540 219H508V138H434V132", "rose", undefined, true)}
          {edge("M382 240V252H800V57H868", "aqua", gateLive("Approve QA"))}
          {edge("M780 219H820V111H868", "orange", undefined, true)}
          {edge("M1022 78V90", "aqua", gateLive("Итоговый отчёт"))}
          {edge("M1022 132V144", "aqua")}
          {edge("M1022 186V198", "aqua")}
        </svg>
      </div>
    </DsPanel>
  );
}
