/* Repo Map uses the same snapshot as TUI; opening it never builds or installs anything. */
import { useState } from "react";
import { useI18n } from "../i18n";
import { ConfirmDialog } from "../commands/ConfirmDialog";
import { PHASE_LABELS } from "../commands/JobOutput";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import { useRepoMap } from "./useRepoMap";
import { Fields, Files, Links, Panel, Settings, Symbols } from "./repoMapViews";

const ERROR_LABELS: Readonly<Record<string, string>> = {
  invalid: "Сервер вернул некорректный снимок Repo Map",
  invalid_build: "Результат построения не соответствует схеме Repo Map",
  truncated: "Вывод Repo Map CLI обрезан: карта слишком велика",
  build_failed: "Не удалось построить Repo Map",
  snapshot_expired: "Снимок Repo Map устарел: обновите страницу",
};

export function RepoMap() {
  const { t } = useI18n();
  const { client, state, jobs, facts, map, error, start, starting } = useRepoMap();
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
  return <div className="repo-page"><div className="page-title repo-title"><div><h1>Repo Map</h1>
    <p>{t("Индекс символов, модулей и импортов.")}</p><div className="home-facts" id="repo-facts"><span>HEAD {facts?.head?.slice(0, 12) ?? "—"}</span>
      {map && <><span>tier {map.tier}</span><span>{t("{count} файлов", { count: map.files.length })}</span>
        <span>{t("{count} связей", { count: map.edges.length })}</span></>}</div></div>
    <div className="actions"><button className="btn" onClick={() => client.requestRepoMap(true)} disabled={state.status !== "connected"}>{t("Обновить")}</button>
      <button className="btn" disabled={!facts?.head || starting || jobs.busy !== null || state.status !== "connected"}
        onClick={() => { if (facts?.head) setPending({ head: facts.head }); }}>{t("Перестроить")}</button>
      <button className="btn" disabled={!map} onClick={exportMap}>{t("Экспорт")}</button></div></div>
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
      <div className="repo-kpis">{[["Уровень", map?.tier], ["Файлы", map?.files.length],
        ["Связи", map?.edges.length], ["Оценка токенов", map?.estimated_tokens]].map(([label, value]) =>
        <div key={label}><span>{t(String(label))}</span><b className="cyan">{value ?? "—"}</b></div>)}</div>
      <div className="orch-tabbar repo-tabbar" role="tablist">{["Обзор", "Символы", "Связи", "Настройки"].map((name) =>
        <button className={`orch-tab ${name === tab ? "on" : ""}`} role="tab" aria-selected={name === tab} key={name} onClick={() => setTab(name)}>{t(name)}</button>)}</div>
      {tab === "Настройки" ? <Settings facts={facts} /> : !map ? <p className="repo-empty">{t(facts.head ? "Кэша карты для HEAD нет" : "HEAD не найден")}</p> :
        tab === "Символы" ? <Symbols map={map} selectedPath={path} onClear={() => setPath(null)} /> :
        tab === "Связи" ? <Links map={map} select={(path) => { setPath(path); setTab("Символы"); }} /> : <>
          <div className="repo-grid"><Panel title="Индекс"><Fields rows={[["Коммит", map.commit], ["Парсер", map.parser],
            ["Причина", t(map.degradation_reason)], ["Сигнатуры", map.tier === "minimal" ? "—" : map.files.reduce((n, f) => n + (f.signatures?.length ?? 0), 0)],
            ["Generation", t("нет данных")], [t("Построен"), t("нет данных")]]} /></Panel>
            <Panel title="Покрытие"><Fields rows={[["С сигнатурами", map.files.filter((f) => f.signatures?.length).length],
              ["Успешно разобраны", map.files.filter((f) => f.parser_status === "ok").length], ["Диагностики", map.diagnostics.length],
              ...["source", "docs", "tests", "excluded"].map((kind): [string, string] => [kind, t("нет данных")])]} /></Panel></div>
          <Files map={map} /><Panel title="Provenance парсера"><Fields rows={Object.entries(map.parser_provenance).map(([key, value]) =>
            [key, typeof value === "object" && value !== null ? JSON.stringify(value) : String(value ?? "—")])} /></Panel>
          <Panel title="Диагностики">{map.diagnostics.length ? map.diagnostics.map((d, i) => <p key={i}>{d.code}: {d.path}</p>) : t("диагностик нет")}</Panel>
        </>}
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
