/* Views over the shared TUI snapshot; styles come from the accepted Repo Map mockup. */
import { useState } from "react";
import type { ReactNode } from "react";
import { useI18n } from "../i18n";
import { SYMBOL_KINDS } from "../ws/repoMap";
import type { MapFile, RepoMap as MapData, RepoMapFacts, SymbolKind } from "../ws/repoMap";

export function Panel({ title, children, className = "repo-index" }: {
  title: string; children: ReactNode; className?: string;
}) {
  const { t } = useI18n();
  return <section className={`panel ${className}`}><div className="panel-head"><h2>{t(title)}</h2></div>
    <div className="repo-index-body">{children}</div></section>;
}

export function Fields({ rows }: { rows: [string, ReactNode][] }) {
  const { t } = useI18n();
  return <>{rows.map(([label, value]) => <div className="repo-index-row" key={label}>
    <span>{t(label)}</span><b>{value ?? "—"}</b></div>)}</>;
}

export function Settings({ facts }: { facts: RepoMapFacts }) {
  const { t } = useI18n();
  const { memory: m, parsers: p, tier } = facts;
  const parserState = p === null ? t("Состояние парсеров не прочитано") :
    p.source !== null && p.problem === null ? t("Bundle готов, режим full доступен") :
      `${t("Bundle не готов")}${p.problem ? `: ${p.problem}` : ""}`;
  return <div className="repo-grid">
    <Panel title="Настройки"><Fields rows={[["В политике проекта", tier.tier],
      ["Политику можно изменить", t(tier.editable ? "да" : "нет")], ["Причина", t(tier.reason) || "—"]]} />
      <p className="repo-note">orchestration.json → repo_map_policy</p>
    </Panel>
    <Panel title="Память"><Fields rows={[
      ["Состояние", t(m.problem ? "Память недоступна" : m.active ? "включена" : m.enabled ? "включена, но не читает источники" : "выключена")],
      ["Причина", m.problem || t(m.inactive) || "—"], ["Источники", m.source_types.join(", ") || "—"],
      ["Документов в индексе", m.indexed ?? t("не построен")], ["top_k", m.top_k], ["max_tokens", m.max_tokens],
    ]} /></Panel>
    <Panel title="Парсеры"><Fields rows={[["Состояние", parserState],
      ["Пара", p?.pair], ["Источник", p?.source], ["Каталог", p?.registry], ["Грамматики", p?.grammars.join(", ")]]} /></Panel>
    <Panel title="Языки проекта"><Fields rows={Object.entries(facts.language_files)} /></Panel>
  </div>;
}

function FileTree({ files, selected, select }: { files: MapFile[]; selected: string | null; select: (path: string) => void }) {
  const render = (prefix: string): ReactNode => {
    const nested = new Set<string>();
    return files.filter((f) => f.path.startsWith(prefix)).map((f) => {
      const rest = f.path.slice(prefix.length);
      const slash = rest.indexOf("/");
      if (slash >= 0) {
        const directory = rest.slice(0, slash + 1);
        if (nested.has(directory)) return null;
        nested.add(directory);
        return <details key={directory} open><summary className="repo-dir">▾ {directory}</summary>{render(prefix + directory)}</details>;
      }
      return <button key={f.path} type="button" className={`repo-file ${selected === f.path ? "on" : ""}`}
        aria-label={f.path} aria-pressed={selected === f.path} onClick={() => select(f.path)}>{rest}</button>;
    });
  };
  return <>{render("")}</>;
}

function Relations({ map, path }: { map: MapData; path: string }) {
  const { t } = useI18n();
  return <>{(["Исходящие", "Входящие"] as const).map((label, index) => {
    const edges = map.edges.filter((e) => index === 0 ? e.source === path : e.target === path);
    return <div className="repo-rel-group" key={label}><h4>{t(label)}</h4>
      {edges.length === 0 ? <p className="repo-rel-empty">{t("связей нет")}</p> : edges.map((edge, i) =>
        <div className="repo-rel-item" key={i}><span className={`repo-rel-weight ${edge.confidence}`}>{edge.confidence}</span>
          <code title={index === 0 ? edge.target : edge.source}>{index === 0 ? edge.target : edge.source}</code>
          <small title={edge.kind}>{edge.kind}</small></div>)}
    </div>;
  })}</>;
}

export function Files({ map }: { map: MapData }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const file = map.files.find((f) => f.path === selected) ?? map.files[0];
  return <section className="panel repo-files-panel"><div className="panel-head"><h2>{t("Файлы")}</h2></div>
    <div className="repo-files-layout"><div className="repo-tree"><div className="repo-tree-root">{map.commit.slice(0, 12)} · {map.tier}</div>
      <FileTree files={map.files} selected={file?.path ?? null} select={setSelected} /></div>
      <div>{file ? <><div className="repo-file-head"><b>{file.path}</b><span>{file.parser_status ?? "—"}</span></div>
        <div className="repo-file-layout"><div className="repo-code"><div className="repo-code-head">{t("Сигнатуры")}</div>
          <pre>{file.signatures?.map((signature, i) => <span className="repo-line" key={i}><i aria-hidden="true" /><code>{signature}</code></span>)}</pre>
          {!file.signatures?.length && <p className="repo-empty">{t("Сигнатур нет")}</p>}</div>
          <aside className="repo-rel-panel"><h3>{t("Связи")}</h3><Relations map={map} path={file.path} /></aside></div>
      </> : <p className="repo-empty">{t("Файлов нет")}</p>}</div>
    </div></section>;
}

/** The mockup's symbol chips: Functions are functions and methods, Modules are the types. */
const CHIPS: [string, string, readonly SymbolKind[]][] = [
  ["all", "Все", SYMBOL_KINDS],
  ["function", "Functions", ["function", "method"]],
  ["module", "Modules", ["class", "struct", "interface"]],
];

export function Symbols({ map, kinds, selectedPath, onClear }: {
  map: MapData; kinds: Record<string, SymbolKind[]> | null; selectedPath: string | null; onClear: () => void;
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [chip, setChip] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const noKinds = t("Вид символа считается только для карты из кэша сервера");
  const symbols = map.files.flatMap((f) => (f.signatures ?? []).map((name, i) =>
    ({ name, path: f.path, id: `${f.path}:${i}`, kind: kinds?.[f.path]?.[i] ?? null })));
  const allowed = CHIPS.find(([key]) => key === chip)?.[2] ?? SYMBOL_KINDS;
  const matches = symbols.filter((s) => (!selectedPath || s.path === selectedPath) &&
    (chip === "all" || (s.kind !== null && allowed.includes(s.kind))) &&
    `${s.name} ${s.path}`.toLowerCase().includes(query.trim().toLowerCase()));
  const item = matches.find((s) => s.id === selected) ?? matches[0];
  return <div className="repo-symbol-grid"><section className="panel repo-symbols"><div className="panel-head"><h2>{t("Символы")}</h2>
    <span>{matches.length} / {symbols.length}</span></div><div className="repo-filters"><div className="chips" id="repo-kind-chips">
      {CHIPS.map(([key, label, members]) => <button key={key} type="button" className={`chip ${chip === key ? "on" : ""}`}
        aria-pressed={chip === key} data-repo-kind={key} disabled={key !== "all" && kinds === null}
        title={key !== "all" && kinds === null ? noKinds : undefined} onClick={() => setChip(key)}>
        {t(label)} {key === "all" ? symbols.length : kinds === null ? "—" : symbols.filter((s) => s.kind !== null && members.includes(s.kind)).length}
      </button>)}</div>
      <input type="search" aria-label={t("Поиск символа")}
      placeholder={t("Найти символ")} value={query} onChange={(e) => setQuery(e.target.value)} />
      {selectedPath && <button className="btn" onClick={onClear}>{t("Все файлы")}</button>}</div>
    {matches.map((s) => <button className={`repo-symbol-row ${s.id === item?.id ? "on" : ""}`} key={s.id} onClick={() => setSelected(s.id)}>
      {s.kind === null ? <span className="repo-kind muted no-data" title={noKinds}>{t("нет данных")}</span> :
        <span className={`repo-kind ${s.kind}`}>{s.kind}</span>}
      <span className="repo-symbol-main"><b>{s.name}</b><small>{s.path}</small></span></button>)}
    {!matches.length && <p className="repo-empty">{t("Символов с такими фильтрами нет.")}</p>}</section>
    <Panel title="Символ" className="repo-detail">{item && <><code className="repo-symbol-name">{item.name}</code>
      <p>{item.path} · {item.kind ?? <span className="muted no-data" title={noKinds}>{t("нет данных")}</span>}</p>
      <Fields rows={[["Строка", <span className="muted no-data" title={t("Схема Repo Map v1 не хранит строки, связи уровня символа и summary")}>{t("нет данных")}</span>]]} />
      <Relations map={map} path={item.path} /></>}</Panel></div>;
}

export function Links({ map, select }: { map: MapData; select: (path: string) => void }) {
  const { t } = useI18n();
  const counts = new Map<string, number>();
  const pairs = new Set<string>();
  for (const edge of map.edges) {
    const pair = JSON.stringify([edge.source, edge.target]);
    if (!pairs.has(pair)) counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1);
    pairs.add(pair);
  }
  const hubs = [...counts].sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).slice(0, 10);
  const paths = [...new Set(map.edges.flatMap((e) => [e.source, e.target]))].slice(0, 10);
  return <><Panel title="Связи" className="repo-links">
    <p className="repo-note">{t("Граф файлов: показано {shown} из {total}", { shown: paths.length, total: new Set(map.edges.flatMap((e) => [e.source, e.target])).size })}</p>
    {paths.length > 0 && <div className="repo-graph-scroll"><svg className="repo-graph" viewBox={`0 0 800 ${paths.length * 42}`} role="img" aria-label={t("Связи файлов")}>
      {map.edges.filter((e) => paths.includes(e.source) && paths.includes(e.target)).map((e, i) =>
        <path key={i} className="repo-edge" d={`M 370 ${paths.indexOf(e.source) * 42 + 18} Q 750 ${(paths.indexOf(e.source) + paths.indexOf(e.target)) * 21 + 18} 370 ${paths.indexOf(e.target) * 42 + 18}`} />)}
      {paths.map((path, i) => <g key={path} className="repo-node" role="button" tabIndex={0} aria-label={path}
        onClick={() => select(path)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(path); } }}>
        <rect x="0" y={i * 42} width="370" height="34" rx="5" /><text className="repo-node-title" x="10" y={i * 42 + 21}>{path}</text></g>)}
    </svg></div>}
    <div className="repo-link-table"><div className="repo-link-head"><span>from</span><span>to</span><span>type</span><span>{t("Достоверность")}</span></div>
      {map.edges.map((e, i) => <div className="repo-link-row" key={i}><b>{e.source}</b><span>{e.target}</span><span>{e.kind}</span><span>{e.confidence}</span></div>)}</div>
    {!map.edges.length && <p className="repo-empty">{t("связей нет")}</p>}</Panel>
    <Panel title="Хабы"><Fields rows={hubs} /></Panel></>;
}
