/* The mockup's Orchestration tabs over the server's snapshot: the grouped pipeline map of
   "Схема" and the chart cards of "Поток", "Качество", "Runtime" and "Гейты". Every figure is
   the kernel's (analytics) or the ledger's (open stages); a mockup card without a source keeps
   an explicit no-data state with its reason. Only an edge into a running role moves. */
import { useI18n } from "../i18n";
import { Bar, NoData, roleName } from "../steps/ActivityViews";
import type { Figure, OrchestrationSnapshot } from "../ws/ledger";
import { AGING, AGING_BUCKETS, seconds } from "./format";
import { GateTrend } from "./OrchViews";

const ACTIVE = new Set(["working", "dispatched", "approved"]);
const ATTENTION = new Set(["failed", "blocked", "auto_stop"]);
const TONES = ["cyan", "mint", "violet", "lavender", "blue", "muted"];

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
          <i key={key} className={TONES[index % TONES.length]} style={{ width: `${Math.round((value / sum) * 100)}%` }} title={`${name(key)}: ${value}`} />
        ))}
      </div>
      <div className="orch-legend">
        {entries.map(([key, value], index) => (
          <span key={key}>
            <i className={TONES[index % TONES.length]} />
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
            {([[p50[key], "cyan"], [p95[key], "violet"]] as const).map(([value, tone]) => (
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
          <i className="violet" />
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

function Panel({ tab, title, note, children }: { tab: string; title: string; note: string; children: React.ReactNode }) {
  return (
    <section className="panel orch-analytics" id="orch-tab-view" data-tab={tab}>
      <div className="orch-analytics-head">
        <h2>{title}</h2>
        <span>{note}</span>
      </div>
      <div className="orch-analytics-grid">{children}</div>
    </section>
  );
}

export function FlowTab({ data }: { data: OrchestrationSnapshot }) {
  const { t, language, state } = useI18n();
  const flow = data.analytics.flow;
  const aging = counts(flow.aging);
  const prs = Array.isArray(flow.pr_per_day) ? flow.pr_per_day.reduce<number>((sum, value) => sum + (value ?? 0), 0) : 0;
  return (
    <Panel tab="flow" title={t("Поток")} note={t("срез, не тренд")}>
      <Card title={t("В работе по состояниям")} note={t("{count} батчей", { count: total(counts(flow.by_state)) })} wide>
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
  const place = (roles: string[]): Place => {
    const open = data.ledger.stages.filter((stage) => roles.includes(stage.role) && (ACTIVE.has(stage.state) || ATTENTION.has(stage.state)));
    if (!open.length) return { tone: "idle", chip: "", count: 0 };
    const tone = open.some((stage) => ATTENTION.has(stage.state)) ? "err" : "active";
    return { tone, chip: open.at(-1)!.ticket, count: open.length };
  };
  const arch = place(["architect"]);
  const dev = place(["developer"]);
  const rev = place(["review", "code-review"]);
  const qa = place(["qa"]);
  const batches = data.ledger.batches;
  const working = batches.filter((batch) => batch.state === "active").length;
  const blocked = batches.filter((batch) => ATTENTION.has(batch.state)).length;
  const awaiting = batches.filter((batch) => batch.state === "awaiting_approval").length;
  const gate = typeof data.analytics.gates.awaiting === "number" && data.analytics.gates.awaiting > 0 ? "wait" : "idle";
  const node = (x: number, y: number, w: number, h: number, type: string, tone: string, title: string, sub: string, at?: Place) => (
    <g className={`orch-map-node ${type} ${tone}`} data-node={title}>
      <rect x={x} y={y} width={w} height={h} rx="7" className="orch-map-bg" />
      <rect x={x} y={y + 9} width="3" height={h - 18} rx="1.5" className="orch-map-accent" />
      <text className="orch-map-title" x={x + 14} y={y + 21}>
        {title}
      </text>
      <text className="orch-map-sub" x={x + 14} y={y + 36}>
        {at?.chip ? `${at.chip} · ` : ""}
        {sub}
      </text>
      <g className={`orch-map-count ${at?.count ? "on" : ""}`}>
        <circle cx={x + w - 12} cy={y + 11} r="8" />
        <text x={x + w - 12} y={y + 14} textAnchor="middle">
          {at?.count ?? 0}
        </text>
      </g>
    </g>
  );
  const edge = (d: string, tone: string, into?: Place, dashed = false) => (
    <path className={`orch-map-edge ${tone} ${into?.tone === "active" ? "active" : ""} ${dashed ? "dashed" : ""}`} d={d} markerEnd={`url(#om-${tone})`} />
  );
  return (
    <section className="panel orch-map-panel orch-scheme" id="orch-scheme">
      <div className="panel-head">
        <h2>{t("Пайплайн")}</h2>
        <span className="small muted">{t("сгруппированный поток · текущие задачи в узлах")}</span>
      </div>
      <div className="orch-map-statusbar">
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
      </div>
      <div className="orch-map-scroll" tabIndex={0} role="region" aria-label={t("Схема ролей оркестрации")}>
        <svg className="orch-map" viewBox="0 0 1200 416" role="img" aria-label={t("Схема ролей оркестрации")}>
          <defs>
            {(
              [
                ["aqua", "#7fc9bb"],
                ["sky", "#70c2d8"],
                ["rose", "#b79ae8"],
                ["orange", "#6f9fe0"],
              ] as const
            ).map(([id, fill]) => (
              <marker key={id} id={`om-${id}`} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="5" markerHeight="5" orient="auto">
                <path d="M0 0 8 4 0 8z" fill={fill} />
              </marker>
            ))}
          </defs>
          {(
            [
              ["violet", 20, 220, t("01 · План и approve")],
              ["sky", 260, 560, t("02 · Сборка и review с находками")],
              ["peach", 840, 340, t("03 · Evidence и публикация")],
            ] as const
          ).map(([tone, x, w, label]) => (
            <g className={`orch-group ${tone}`} key={tone}>
              <rect x={x} y="24" width={w} height="372" rx="8" className="orch-group-bg" />
              <text className="orch-group-label" x={x + 16} y="44">
                {label}
              </text>
              <line x1={x} y1="56" x2={x + w} y2="56" className="orch-group-line" />
            </g>
          ))}
          {node(40, 80, 180, 58, "human", "idle", t("Approve плана"), t("гейт человека"))}
          {node(280, 80, 220, 52, "role", arch.tone, t("Архитектор"), t("разбор задачи"), arch)}
          {node(280, 145, 220, 52, "role", dev.tone, t("Разработчик"), t("контекст + TDD"), dev)}
          {node(280, 210, 220, 52, "role", rev.tone, "Code review", t("свежесть базы"), rev)}
          {node(280, 275, 220, 52, "role", qa.tone, "QA · clean-room", t("закреплённый SHA"), qa)}
          {node(540, 210, 240, 52, "exception", "review", t("Находки review"), t("возврат в Developer"))}
          {node(540, 275, 240, 52, "exception", "qa", t("Находки QA"), t("повтор или дефект"))}
          {node(860, 80, 280, 52, "human", gate, "Approve QA", t("гейт человека"))}
          {node(860, 145, 280, 52, "coord", "idle", t("Итоговый отчёт"), t("evidence + решение"))}
          {node(860, 210, 280, 52, "coord", "idle", t("Публикация"), t("принятый SHA"))}
          {node(860, 275, 280, 52, "human", "idle", "/to-pull-requests", t("передача человеку"))}
          {edge("M220 109H280", "aqua", arch)}
          {edge("M390 132V145", "aqua", dev)}
          {edge("M390 197V210", "sky", rev)}
          {edge("M390 262V275", "aqua", qa)}
          {edge("M500 236H540", "rose")}
          {edge("M500 301H540", "rose")}
          {edge("M540 236H520V160H500", "rose", undefined, true)}
          {edge("M540 301H510V205H440V197", "rose", undefined, true)}
          {edge("M390 327V350H800V106H860", "aqua")}
          {edge("M780 301H810V171H860", "orange", undefined, true)}
          {edge("M1000 132V145", "aqua")}
          {edge("M1000 197V210", "aqua")}
          {edge("M1000 262V275", "aqua")}
        </svg>
      </div>
    </section>
  );
}
