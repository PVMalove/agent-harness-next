/* Repo Map on the design system v3: the summary counts the whole snapshot, the three tabs (Files,
   Symbols, Links) show the fragment the server passed. It uses the same snapshot as the TUI;
   opening it never builds or installs anything. */
import { useState } from "react";
import { PageHeader, PipeTabs, Panel, StatusIcon, Summary } from "../ds";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { ConfirmDialog } from "../commands/ConfirmDialog";
import { PHASE_LABELS } from "../commands/JobOutput";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import type { RepoMapFacts } from "../ws/repoMap";
import { useRepoMap } from "./useRepoMap";
import { Files, Links, Symbols } from "./repoMapViews";
import { snapshotClock } from "../update/format";
import { TabPanels } from "../views/Tabs";

const REPO_TABS = ["Файлы", "Символы", "Связи"];

const ERROR_LABELS: Readonly<Record<string, string>> = {
  invalid: "Сервер вернул некорректный снимок Repo Map",
  invalid_build: "Результат построения не соответствует схеме Repo Map",
  truncated: "Вывод Repo Map CLI обрезан: карта слишком велика",
  build_failed: "Не удалось построить Repo Map",
  snapshot_expired: "Снимок Repo Map устарел: обновите страницу",
};

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
  const [tab, setTab] = useState("Файлы");
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
    onClick={() => { if (facts?.head) setPending({ head: facts.head }); }}><Icon name="refresh" className="ds-ic-sm" /> {t("Перестроить")}</button>;
  const symbols = map ? map.files.reduce((n, f) => n + (f.signatures?.length ?? 0), 0) : 0;
  const budget = map?.parser_provenance.max_tokens;
  const platform = platformLine(map);
  return <div className="ds-page ds-fit ds-repo" data-section="Repo Map">
    <PageHeader title="Repo Map" subtitle={t("Индекс символов, модулей и импортов.")} actions={<>
      <button className="ds-btn ds-btn-icon" type="button" aria-label={t("Обновить")} title={t("Обновить")}
        onClick={() => client.requestRepoMap(true)} disabled={state.status !== "connected"}><Icon name="refresh" className="ds-ic-sm" /></button>
      {rebuild("ds-btn")}
      <button className="ds-btn" type="button" disabled={!map} onClick={exportMap}><Icon name="download" className="ds-ic-sm" /> {t("Экспорт")}</button>
    </>} />
    {jobs.busy && <p role="status" className="ds-note">{t("Занято: {command}", { command: jobs.busy.command_id })} · {jobs.busy.id}</p>}
    {jobs.refusal && <p role="alert" className="ds-alert ds-alert-err" data-code={jobs.refusal.code}>{t(JOB_ERROR_LABELS[jobs.refusal.code] ?? "Сервер ответил ошибкой.")}</p>}
    {shown && <Panel title={<code>{shown.command_id}</code>} className="ds-job"
      meta={<span role="status">{t(PHASE_LABELS[failed ? "failed" : shown.phase] ?? shown.phase)}</span>}
      actions={!shown.done ? <button className="ds-btn ds-btn-sm" type="button" onClick={() => setPending({ job: shown.id })}>{t("Отменить job")}</button> : undefined}>
      <p className="ds-note">{shown.id} · {t("Код возврата: {code}", { code: shown.returncode ?? "—" })}</p>
      {shown.truncated && <p className="ds-note">{t("Вывод обрезан")}</p>}
      {failed && <pre className="ds-code">{shown.output.filter((f) => f.channel === "stderr").map((f) => f.text).join("") || shown.error}</pre>}
    </Panel>}
    {error && <p role="alert" className="ds-alert ds-alert-err" data-code={error}>{t(ERROR_LABELS[error] ?? "Не удалось прочитать Repo Map")}</p>}
    {!facts ? <p className="ds-empty">{t("Читаю снимок Repo Map…")}</p> : <>
      <Summary id="repo-facts" label={t("Сводка Repo Map")}
        stats={[
          { label: t("Файлы"), value: map?.files.length ?? "—" },
          { label: t("Символы"), value: map ? symbols : "—" },
          { label: t("Связи"), value: map?.edges.length ?? "—" },
          { label: t("Токены"), value: map ? `≈${map.estimated_tokens}` : "—",
            caption: map && typeof budget === "number" ? t("бюджет {budget}", { budget }) : undefined },
        ]}
        facts={map ? <>
          <span>{t("Уровень")} <b>{map.tier}</b></span>
          <span>{t("Парсер")} <b>{map.parser}</b></span>
          {platform && <span>{platform}</span>}
          <span>{t("HEAD индекса")} <b>{map.commit.slice(0, 8)}</b></span>
        </> : <span>HEAD {facts.head?.slice(0, 12) ?? "—"}</span>}
        snapshot={<span title={`${t("Кэш")} · ${ageSeconds ?? 0} s`}><Icon name="clock" className="ds-ic-sm" /> {t("Снимок")} {snapshotClock(ageSeconds, language)}</span>} />
      {stale && <div className="ds-alert ds-alert-warn" id="repo-stale" role="status"><StatusIcon tone="warn" label={t("Внимание")} /><div>
        <b>{t("Карта устарела для HEAD")}</b>
        <p>{t("Для HEAD {head} карты в кэше нет; показана последняя карта коммита {commit}.", { head: facts.head?.slice(0, 12) ?? "—", commit: stale.commit.slice(0, 12) })}</p>
      </div>{rebuild("ds-btn ds-btn-primary")}</div>}
      <PipeTabs id="repo" label="Repo Map" tabs={REPO_TABS.map((name) => ({ id: name, label: t(name) }))} value={tab} onChange={setTab} />
      <TabPanels id="repo" tabs={REPO_TABS.map((name) => [name, name] as const)} value={tab} className="ds-tabpanel">
      {!map ? <section className="ds-panel ds-empty-state" id="repo-empty"><p className="ds-empty">{t(facts.head ? "Кэша карты для HEAD нет" : "HEAD не найден")}</p>
          {facts.head && <p className="ds-note">{t("Карта строится по запросу и хранится в кэше для одного коммита; после нового коммита её нужно перестроить.")}</p>}
          {facts.head && <div className="ds-pad">{rebuild("ds-btn ds-btn-primary")}</div>}</section> :
        tab === "Символы" ? <Symbols map={map} kinds={facts.map ? facts.symbol_kinds : null} selectedPath={path} onClear={() => setPath(null)} /> :
        tab === "Связи" ? <Links map={map} select={(p) => { setPath(p); setTab("Символы"); }} /> : <Files map={map} />}
      </TabPanels>
      {map && <p className="ds-note ds-foot-note"><Icon name="info" className="ds-ic-sm" /> {t("Счётчики сверху — весь снимок. В просмотре: {files} файлов, {symbols} символов и {edges} связей.", { files: map.files.length, symbols, edges: map.edges.length })}</p>}
    </>}
    {pending && <div className="ds-legacy-island"><ConfirmDialog request={"head" in pending ? {
      title: t("Построить Repo Map для HEAD {commit}?", { commit: pending.head.slice(0, 12) }),
      command: `repo-map-build --commit ${pending.head}`, typed: null, action: t("Собрать"),
      reason: t("Построение карты запускает Repo Map CLI для HEAD. В режиме tier=full CLI может установить offline parser bundle (uv pip install --offline) в .harness/.sandboxes/cache/repo_map/parser_bundle/; сеть не используется. Результат сохраняется в кэш Repo Map."),
    } : { title: t("Подтвердите отмену job"), command: pending.job, reason: t(jobs.cancelReason ?? ""), typed: null, action: t("Отменить job") }}
      onClose={() => setPending(null)} onConfirm={() => {
        if ("head" in pending) start(pending.head); else jobs.cancel(pending.job);
        setPending(null);
      }} /></div>}
  </div>;
}
