/* The three Repo Map tabs on the design system v3: Files (tree and file), Symbols and Links. They
   read the shared snapshot of the TUI; nothing here runs a command. */
import { useState } from "react";
import type { ReactNode } from "react";
import { Panel } from "../ds";
import { useI18n } from "../i18n";
import { Icon } from "../icons";
import { SYMBOL_KINDS } from "../ws/repoMap";
import type { MapFile, RepoMap as MapData, SymbolKind } from "../ws/repoMap";

export function Fields({ rows }: { rows: [string, ReactNode][] }) {
  const { t } = useI18n();
  return (
    <dl className="ds-kv">
      {rows.map(([label, value]) => (
        <div className="ds-kv-row" key={label}>
          <dt>{t(label)}</dt>
          <dd>{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

/** One row per folder and file, indented 16px per level; a folder row folds
    its subtree, a file row carries its parser status. */
function FileTree({ files, selected, select }: { files: MapFile[]; selected: string | null; select: (path: string) => void }) {
  const [folded, setFolded] = useState<ReadonlySet<string>>(new Set());
  const toggle = (path: string) => {
    const next = new Set(folded);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setFolded(next);
  };
  const indent = (depth: number) => <span className="ds-tree-indent" style={{ width: `${depth * 16}px` }} />;
  const render = (prefix: string, depth: number): ReactNode[] => {
    const nested = new Set<string>();
    return files.filter((f) => f.path.startsWith(prefix)).flatMap((f) => {
      const rest = f.path.slice(prefix.length);
      const slash = rest.indexOf("/");
      if (slash >= 0) {
        const directory = rest.slice(0, slash);
        if (nested.has(directory)) return [];
        nested.add(directory);
        const path = prefix + directory + "/";
        const open = !folded.has(path);
        return [
          <button key={path} type="button" className="ds-tree-row ds-tree-dir" aria-expanded={open} onClick={() => toggle(path)}>
            {indent(depth)}
            <Icon name="folder" className="ds-ic-sm" />
            <b>{directory}/</b>
          </button>,
          ...(open ? render(path, depth + 1) : []),
        ];
      }
      return [
        <button key={f.path} type="button" className="ds-tree-row ds-tree-file" aria-pressed={selected === f.path}
          title={f.path} onClick={() => select(f.path)}>
          {indent(depth)}
          <Icon name="terminal" className="ds-ic-sm" />
          {/* The accessible name is the whole path; the row shows the file name. */}
          <span className="ds-sr">{f.path}</span>
          <span className="ds-tree-name" aria-hidden="true">{rest}</span>
          <em className="ds-tree-status" aria-hidden="true">{f.parser_status ?? "—"}</em>
        </button>,
      ];
    });
  };
  return <div className="ds-tree">{render("", 0)}</div>;
}

function Relations({ map, path }: { map: MapData; path: string }) {
  const { t } = useI18n();
  return (
    <>
      {(["Исходящие", "Входящие"] as const).map((label, index) => {
        const edges = map.edges.filter((e) => (index === 0 ? e.source === path : e.target === path));
        return (
          <div className="ds-rel-group" key={label}>
            <h3 className="ds-rel-title">{t(label)}</h3>
            {edges.length === 0 ? (
              <p className="ds-rel-empty">{t("связей нет")}</p>
            ) : (
              edges.map((edge, i) => (
                <div className="ds-rel-item" key={i}>
                  <span className="ds-tag">{edge.confidence}</span>
                  <code title={index === 0 ? edge.target : edge.source}>{index === 0 ? edge.target : edge.source}</code>
                  <small title={edge.kind}>{edge.kind}</small>
                </div>
              ))
            )}
          </div>
        );
      })}
    </>
  );
}

const moduleOf = (path: string) => (path.includes("/") ? path.slice(0, path.indexOf("/") + 1) : "./");

export function Files({ map }: { map: MapData }) {
  const { t } = useI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [module, setModule] = useState("");
  const modules = [...new Set(map.files.map((f) => moduleOf(f.path)))].sort();
  const shown = map.files.filter((f) => (module === "" || moduleOf(f.path) === module) && f.path.toLowerCase().includes(query.trim().toLowerCase()));
  const file = shown.find((f) => f.path === selected) ?? shown[0];
  return (
    <>
      <div className="ds-toolbar">
        <label className="ds-search">
          <Icon name="search" className="ds-ic-sm" />
          <input className="ds-input" type="search" aria-label={t("Поиск файла или пути")} placeholder={t("Поиск файла или пути")}
            value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <select className="ds-select" aria-label={t("Модуль")} value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">{t("Все модули")}</option>
          {modules.map((name) => <option key={name} value={name}>{name}</option>)}
        </select>
        <button className="ds-btn ds-btn-sm" type="button" disabled={!query && !module} onClick={() => { setQuery(""); setModule(""); }}>{t("Сбросить")}</button>
      </div>
      <div className="ds-files">
        <Panel title={t("Модули")} count={modules.length} meta={t("Файлы в снимке")} fill className="ds-files-tree" id="repo-files">
          {shown.length ? <FileTree files={shown} selected={file?.path ?? null} select={setSelected} /> : <p className="ds-empty">{t("Файлов нет")}</p>}
        </Panel>
        <Panel title={file ? (file.path.split("/").pop() ?? file.path) : t("Файл")} meta={file ? <span className="ds-tag">{file.parser_status ?? "—"}</span> : undefined} fill className="ds-files-detail">
          {file ? (
            <>
              <div className="ds-file-path"><code>{file.path}</code></div>
              <div className="ds-file-cols">
                <div className="ds-file-code">
                  <h3 className="ds-rel-title">{t("Сигнатуры")}</h3>
                  {file.signatures?.length ? (
                    <pre className="ds-code">{file.signatures.map((signature, i) => (
                      <span className="ds-line" key={i}><i aria-hidden="true">{i + 1}</i><code>{signature}</code>{"\n"}</span>
                    ))}</pre>
                  ) : <p className="ds-empty">{t("Сигнатур нет")}</p>}
                </div>
                <aside className="ds-file-rel"><h3 className="ds-rel-title">{t("Связи")}</h3><Relations map={map} path={file.path} /></aside>
              </div>
            </>
          ) : <p className="ds-empty">{t("Файлов нет")}</p>}
        </Panel>
      </div>
    </>
  );
}

/** Functions are functions and methods, Modules are the types. */
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
  const noData = (why: string) => <span className="ds-muted" title={why}>{t("нет данных")}</span>;
  const symbols = map.files.flatMap((f) => (f.signatures ?? []).map((name, i) =>
    ({ name, path: f.path, id: `${f.path}:${i}`, kind: kinds?.[f.path]?.[i] ?? null })));
  const allowed = CHIPS.find(([key]) => key === chip)?.[2] ?? SYMBOL_KINDS;
  const matches = symbols.filter((s) => (!selectedPath || s.path === selectedPath) &&
    (chip === "all" || (s.kind !== null && allowed.includes(s.kind))) &&
    `${s.name} ${s.path}`.toLowerCase().includes(query.trim().toLowerCase()));
  const item = matches.find((s) => s.id === selected) ?? matches[0];
  return (
    <div className="ds-split">
      <Panel title={t("Символы")} meta={`${matches.length} / ${symbols.length}`} fill className="ds-symbols">
        <div className="ds-toolbar ds-toolbar-flat">
          <div className="ds-filter" id="repo-kind-chips">
            {CHIPS.map(([key, label, members]) => (
              <button key={key} type="button" aria-pressed={chip === key} data-repo-kind={key}
                disabled={key !== "all" && kinds === null} title={key !== "all" && kinds === null ? noKinds : undefined} onClick={() => setChip(key)}>
                {t(label)} {key === "all" ? symbols.length : kinds === null ? "—" : symbols.filter((s) => s.kind !== null && members.includes(s.kind)).length}
              </button>
            ))}
          </div>
          <input className="ds-input" type="search" aria-label={t("Поиск символа")} placeholder={t("Найти символ")} value={query} onChange={(e) => setQuery(e.target.value)} />
          {selectedPath && <button className="ds-btn ds-btn-sm" type="button" onClick={onClear}>{t("Все файлы")}</button>}
        </div>
        {matches.map((s) => (
          <button className="ds-row ds-row-button ds-symbol-row" type="button" aria-pressed={s.id === item?.id} key={s.id} onClick={() => setSelected(s.id)}>
            {s.kind === null ? noData(noKinds) : <span className="ds-tag ds-kind">{s.kind}</span>}
            <span className="ds-row-main"><b className="ds-row-title">{s.name}</b><small className="ds-row-sub">{s.path}</small></span>
          </button>
        ))}
        {!matches.length && <p className="ds-empty">{t("Символов с такими фильтрами нет.")}</p>}
      </Panel>
      <Panel title={t("Символ")} fill className="ds-symbol-detail">
        {item && (
          <div className="ds-pad">
            <code className="ds-symbol-name">{item.name}</code>
            <p className="ds-muted">{item.path} · {item.kind ?? noData(noKinds)}</p>
            <Fields rows={[["Строка", noData(t("Схема Repo Map v1 не хранит строки, связи уровня символа и summary"))]]} />
            <Relations map={map} path={item.path} />
          </div>
        )}
      </Panel>
    </div>
  );
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
  return (
    <div className="ds-split">
      <Panel title={t("Связи")} meta={t("Граф файлов: показано {shown} из {total}", { shown: paths.length, total: new Set(map.edges.flatMap((e) => [e.source, e.target])).size })} fill className="ds-links">
        {paths.length > 0 && (
          <div className="ds-graph-scroll">
            <svg className="ds-graph" viewBox={`0 0 800 ${paths.length * 40}`} role="group" aria-label={t("Связи файлов")}>
              {map.edges.filter((e) => paths.includes(e.source) && paths.includes(e.target)).map((e, i) => (
                <path key={i} className="ds-edge" d={`M 370 ${paths.indexOf(e.source) * 40 + 16} Q 750 ${(paths.indexOf(e.source) + paths.indexOf(e.target)) * 20 + 16} 370 ${paths.indexOf(e.target) * 40 + 16}`} />
              ))}
              {paths.map((path, i) => (
                <g key={path} className="ds-node" role="button" tabIndex={0} aria-label={path}
                  onClick={() => select(path)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(path); } }}>
                  <rect x="0" y={i * 40} width="370" height="32" rx="8" />
                  <text className="ds-node-title" x="12" y={i * 40 + 20}>{path}</text>
                </g>
              ))}
            </svg>
          </div>
        )}
        <div className="ds-link-table" role="region" tabIndex={0} aria-label={t("Связи")}>
          <div className="ds-link-head"><span>from</span><span>to</span><span>type</span><span>{t("Достоверность")}</span></div>
          {map.edges.map((e, i) => (
            <div className="ds-link-row" key={i}><b>{e.source}</b><span>{e.target}</span><span>{e.kind}</span><span>{e.confidence}</span></div>
          ))}
        </div>
        {!map.edges.length && <p className="ds-empty">{t("связей нет")}</p>}
      </Panel>
      <Panel title={t("Хабы")} fill className="ds-hubs"><Fields rows={hubs} /></Panel>
    </div>
  );
}
