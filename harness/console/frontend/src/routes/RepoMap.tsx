/* Repo Map uses the same snapshot as TUI; opening it never builds or installs anything. */
import { useState } from "react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { ConfirmDialog } from "../commands/ConfirmDialog";
import { PHASE_LABELS } from "../commands/JobOutput";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import type { RepoMapFacts } from "../ws/repoMap";
import { useRepoMap } from "./useRepoMap";
import { Fields, Files, Links, Settings, Symbols } from "./repoMapViews";
import { NoData } from "../steps/ActivityViews";
import { snapshotClock } from "../update/format";
import { TabList, TabPanels } from "../views/Tabs";

const REPO_TABS = ["Обзор", "Символы", "Связи", "Настройки"];

const ERROR_LABELS: Readonly<Record<string, string>> = {
  invalid: "Сервер вернул некорректный снимок Repo Map",
  invalid_build: "Результат построения не соответствует схеме Repo Map",
  truncated: "Вывод Repo Map CLI обрезан: карта слишком велика",
  build_failed: "Не удалось построить Repo Map",
  snapshot_expired: "Снимок Repo Map устарел: обновите страницу",
};

const COVERAGE_TONES = [["source", "cyan"], ["docs", "blue"], ["tests", "mint"], ["excluded", "muted"]] as const;

/** The mockup coverage panel: a stacked bar and a legend of the kernel's file classes. */
function Coverage({ coverage }: { coverage: RepoMapFacts["coverage"] }) {
  const { t } = useI18n();
  const none = (why: string) => <b className="muted no-data" title={t(why)}>{t("нет данных")}</b>;
  const value = (kind: (typeof COVERAGE_TONES)[number][0]) => coverage === null ? null : coverage[kind];
  const included = coverage === null ? 0 : coverage.source + coverage.docs + coverage.tests;
  const sum = included + (coverage?.excluded ?? 0);
  return <section className="panel repo-coverage"><div className="panel-head"><h2>{t("Покрытие")}</h2>
    <span className="small muted">{coverage === null || coverage.excluded === null || sum === 0 ? t("нет данных")
      : t("{percent}% включено", { percent: Math.round((included / sum) * 100) })}</span></div>
    <div className="repo-coverage-body">
      <div className="orch-stack">{sum > 0 && COVERAGE_TONES.map(([kind, tone]) => {
        const count = value(kind) ?? 0;
        return count > 0 ? <i key={kind} className={tone} style={{ width: `${Math.round((count / sum) * 100)}%` }} title={`${kind}: ${count}`} /> : null;
      })}</div>
      <div className="orch-legend">{COVERAGE_TONES.map(([kind, tone]) => {
        const count = value(kind);
        return <span key={kind} data-kind={kind}><i className={tone} />{kind}
          {count === null ? none(coverage === null ? "Покрытие считается только для карты из кэша сервера" : "Git не перечислил файлы коммита карты")
            : <b>{count}</b>}</span>;
      })}</div>
      <p className="orch-note">{t("excluded — файлы коммита, которые не попали в карту.")}</p>
    </div></section>;
}

/** «Python 3.14 · linux_x86_64» from the parser provenance tags, else null. */
function platformLine(map: RepoMapFacts["map"]): string | null {
  const provenance = map?.parser_provenance ?? {};
  const python = typeof provenance.python_tag === "string" ? provenance.python_tag.replace(/^cp(\d)(\d+)$/, "Python $1.$2") : null;
  const platform = typeof provenance.platform_tag === "string" ? provenance.platform_tag : null;
  return python || platform ? [python, platform].filter(Boolean).join(" · ") : null;
}

export function RepoMap() {
  const { t, language } = useI18n();
  const { client, state, jobs, facts, ageSeconds, map: current, error, start, starting } = useRepoMap();
  // HEAD has no cached map: the latest cached map of another commit is shown, marked stale.
  const stale = current ? null : (facts?.stale_map ?? null);
  const map = current ?? stale;
  const [pending, setPending] = useState<{ head: string } | { job: string } | null>(null);
  const [tab, setTab] = useState("Обзор");
  const [path, setPath] = useState<string | null>(null);
  const shown = jobs.shown;
  const failed = shown !== null && (shown.phase === "failed" ||
    (shown.done && shown.returncode !== null && shown.returncode !== 0));
  const exportMap = () => {
    if (!map) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(map, null, 2)], { type: "application/json" }));
    const a = document.createElement("a"); a.href = url; a.download = `repo-map-${map.commit.slice(0, 12)}.json`;
    a.click(); URL.revokeObjectURL(url);
  };
  const rebuild = (className: string) => <button className={className} type="button" disabled={!facts?.head || starting || jobs.busy !== null || state.status !== "connected"}
    onClick={() => { if (facts?.head) setPending({ head: facts.head }); }}><Icon name="refresh" /> {t("Перестроить")}</button>;
  const exportButton = <button className="btn" type="button" disabled={!map} onClick={exportMap}><Icon name="download" /> {t("Экспорт")}</button>;
  const symbols = map ? map.files.reduce((n, f) => n + (f.signatures?.length ?? 0), 0) : 0;
  const edgeKinds = map ? [...new Set(map.edges.map((edge) => edge.kind))] : [];
  const budget = map?.parser_provenance.max_tokens;
  const platform = platformLine(map);
  return <div className="repo-page"><div className="page-title repo-title"><div><h1>Repo Map</h1>
    <p>{t("Индекс символов, модулей и импортов.")}</p><div className="home-facts" id="repo-facts">
      {map ? <><span>tier {map.tier}</span><span>{t("{count} файлов", { count: map.files.length })}</span>
        <span>{t("{count} символов", { count: symbols })}</span>
        <span>{t("{count} связей", { count: map.edges.length })}</span></> : <span>HEAD {facts?.head?.slice(0, 12) ?? "—"}</span>}
      {facts && <span title={`${t("Кэш")} · ${ageSeconds ?? 0} s`}>{snapshotClock(ageSeconds, language)}</span>}</div></div>
    <div className="actions"><button className="icon-btn" type="button" aria-label={t("Обновить")} title={t("Обновить")}
      onClick={() => client.requestRepoMap(true)} disabled={state.status !== "connected"}><Icon name="refresh" /></button>
      {rebuild("btn")}
      {exportButton}</div></div>
    {jobs.busy && <p role="status">{t("Занято: {command}", { command: jobs.busy.command_id })} · {jobs.busy.id}</p>}
    {jobs.refusal && <p role="alert" data-code={jobs.refusal.code}>{t(JOB_ERROR_LABELS[jobs.refusal.code] ?? "Сервер ответил ошибкой.")}</p>}
    {shown && <section className="panel command-output"><div className="panel-head"><h2>{shown.command_id}</h2>
      <span role="status">{t(PHASE_LABELS[failed ? "failed" : shown.phase] ?? shown.phase)}</span>
      {!shown.done && <button className="btn" onClick={() => setPending({ job: shown.id })}>{t("Отменить job")}</button>}</div>
      <p className="repo-note">{shown.id} · {t("Код возврата: {code}", { code: shown.returncode ?? "—" })}</p>
      {shown.truncated && <p>{t("Вывод обрезан")}</p>}
      {failed && <pre className="command-output-text">{shown.output.filter((f) => f.channel === "stderr").map((f) => f.text).join("") || shown.error}</pre>}
    </section>}
    {error && <p role="alert" data-code={error}>{t(ERROR_LABELS[error] ?? "Не удалось прочитать Repo Map")}</p>}
    {!facts ? <p className="repo-empty">{t("Читаю снимок Repo Map…")}</p> : <>
      <div className="repo-kpis">{([
        ["Уровень", "cyan", map?.tier, platform ?? <NoData why={t("В provenance парсера нет python_tag и platform_tag")} />],
        ["Файлы", "mint", map?.files.length, map && t("{count} символов", { count: symbols })],
        ["Связи", "blue", map?.edges.length, map && (edgeKinds.join(" / ") || t("связей нет"))],
        ["Токены", "violet", map && `≈${map.estimated_tokens}`,
          typeof budget === "number" ? t("бюджет {budget}", { budget }) : <NoData why={t("В provenance парсера нет max_tokens")} />],
      ] as [string, string, ReactNode, ReactNode][]).map(([label, tone, value, caption]) =>
        <div key={label}><span>{t(label)}</span><b className={tone}>{value ?? "—"}</b>{map && <small>{caption}</small>}</div>)}</div>
      {stale && <div className="plan-warning warn repo-stale" id="repo-stale" role="status"><Icon name="warning" /><div>
        <b>{t("Карта устарела для HEAD")}</b>
        <p>{t("Для HEAD {head} карты в кэше нет; показана последняя карта коммита {commit}.", { head: facts.head?.slice(0, 12) ?? "—", commit: stale.commit.slice(0, 12) })}</p>
      </div>{rebuild("btn primary")}</div>}
      <TabList id="repo" label="Repo Map" className="orch-tabbar repo-tabbar" tabs={REPO_TABS.map((name) => [name, t(name)] as const)} value={tab} onChange={setTab} />
      <TabPanels id="repo" tabs={REPO_TABS.map((name) => [name, name] as const)} value={tab}>
      {tab === "Настройки" ? <Settings facts={facts} map={map} /> : !map ? <section className="panel repo-empty-state" id="repo-empty"><p className="repo-empty">{t(facts.head ? "Кэша карты для HEAD нет" : "HEAD не найден")}</p>
          {facts.head && <p className="repo-note">{t("Карта строится по запросу и хранится в кэше для одного коммита; после нового коммита её нужно перестроить.")}</p>}
          {facts.head && rebuild("btn primary")}</section> :
        tab === "Символы" ? <Symbols map={map} kinds={facts.map ? facts.symbol_kinds : null} selectedPath={path} onClear={() => setPath(null)} /> :
        tab === "Связи" ? <Links map={map} select={(path) => { setPath(path); setTab("Символы"); }} /> : <>
          <div className="repo-grid"><section className="panel repo-index"><div className="panel-head"><h2>{t("Индекс")}</h2>
            <span className={`orch-pill ${stale ? "amber" : "mint"}`}>{stale ? "stale" : "fresh"}</span></div>
            <div className="repo-index-body"><Fields rows={[
              ["Уровень", [map.tier, map.parser, platform].filter(Boolean).join(" · ")],
              ["Generation", <NoData why={t("Кэш Repo Map не хранит generation")} />],
              ["Построен", <NoData why={t("Кэш Repo Map не хранит время построения")} />],
              ["Объём", `${map.files.length} files · ${map.edges.length} edges · ≈${map.estimated_tokens} tokens`],
            ]} /><div className="repo-index-actions">{rebuild("btn")}{exportButton}</div></div></section>
            <Coverage coverage={facts.coverage} /></div>
          <Files map={map} />
        </>}
      </TabPanels>
    </>}
    {pending && <ConfirmDialog request={"head" in pending ? {
      title: t("Построить Repo Map для HEAD {commit}?", { commit: pending.head.slice(0, 12) }),
      command: `repo-map-build --commit ${pending.head}`, typed: null, action: t("Собрать"),
      reason: t("Построение карты запускает Repo Map CLI для HEAD. В режиме tier=full CLI может установить offline parser bundle (uv pip install --offline) в .harness/.sandboxes/cache/repo_map/parser_bundle/; сеть не используется. Результат сохраняется в кэш Repo Map."),
    } : { title: t("Подтвердите отмену job"), command: pending.job, reason: t(jobs.cancelReason ?? ""), typed: null, action: t("Отменить job") }}
      onClose={() => setPending(null)} onConfirm={() => {
        if ("head" in pending) start(pending.head); else jobs.cancel(pending.job);
        setPending(null);
      }} />}
  </div>;
}
