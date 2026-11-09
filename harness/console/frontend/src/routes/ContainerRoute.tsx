/* Container route (hidden route #/container-route?batch=&role=&runtime=): the dispatch container
   executor route of harness/console/kernel/container_route.py, as the TUI ContainerRouteScreen
   draws it, read from container_route.view. Six stage tabs only switch the pane; every row, tab
   state, blocker and action availability is the kernel's.

   Choice recorded for the spec conflict of #887 (ADR 0029 follow-up): `#container-route` is this
   dispatch route (mockup execution-console.js: «Контейнерный запуск»). The Harness «Контейнеры»
   tab of the mockup is the engine inventory (containers, images, cleanup); the kernel and the TUI
   have no facts for it, so it stays unshown, as Harness.tsx documents. One implementation, no
   duplicate.

   Only «Перепроверить» / «Обновить эффективный план» are interactive here: they read the view
   again (`dispatch preflight` is read-only). Propose, approve, send, QA and cleanup run in the TUI
   through its local coordinator client; they are not server job catalog commands, so the page
   shows them disabled with that reason and starts no command. */
import { useState } from "react";
import { useSearchParams } from "react-router";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { ActionBar, RowList } from "../views/RowList";
import { parseRouteView } from "../ws/views";
import type { Stage, ViewAction, ViewRow } from "../ws/views";

export const TUI_ONLY = "Действие доступно только в TUI: команда не входит в каталог job сервера";
/** The actions that only read: they ask for the view again. */
const READS = new Set(["recheck"]);

/** The page's buttons: a read stays as the kernel offers it, every other action is disabled. */
export const pageActions = (actions: readonly ViewAction[]): ViewAction[] =>
  actions.map((action) => (READS.has(action.key) ? action : { ...action, enabled: false, reason: TUI_ONLY }));

/** The environment facts of the mockup: the first row of any stage whose label names the fact. */
function envFact(view: { stages: Record<string, { rows: readonly ViewRow[] }> } | null, pattern: RegExp): ViewRow | null {
  if (!view) return null;
  for (const stage of Object.values(view.stages)) {
    const row = stage.rows.find((item) => pattern.test(item.label));
    if (row) return row;
  }
  return null;
}

export function ContainerRoute() {
  const { t, section } = useI18n();
  const [params, setParams] = useSearchParams();
  const selection = {
    batch: params.get("batch") ?? "",
    role: params.get("role") || "developer",
    runtime: params.get("runtime") ?? "",
  };
  const [draft, setDraft] = useState(selection);
  const [stage, setStage] = useState<Stage>("setup");
  const screen = useScreen({ type: "container_route.view", params: selection }, parseRouteView);
  const view = screen.data;
  const current = view?.stages[stage];
  const tab = view?.tabs.find((item) => item.stage === stage);

  const apply = () => {
    const next: Record<string, string> = { batch: draft.batch.trim(), role: draft.role.trim() || "developer" };
    if (draft.runtime.trim()) next.runtime = draft.runtime.trim();
    setParams(next);
  };

  return (
    <div className="route-page work-page" data-section="Orchestration">
      <div className="page-title">
        <div>
          <h1>{t("Контейнерный запуск")}</h1>
          <p>{t("Rootless Podman · среда, этапы и свидетельства.")}</p>
          {view && (
            <p id="route-context">
              {view.context.map(([label, value], index) => (
                <span key={label}>
                  {index > 0 && "  ·  "}
                  {`${t(label)}: ${t(value)}`}
                </span>
              ))}
            </p>
          )}
        </div>
        <div className="actions">
          <a className="btn" href={href("orchestration")}>
            {section("Orchestration")}
          </a>
        </div>
      </div>

      <form
        className="panel route-select"
        id="route-select"
        onSubmit={(event) => {
          event.preventDefault();
          apply();
        }}
      >
        {(["batch", "role", "runtime"] as const).map((name) => (
          <input
            key={name}
            aria-label={name}
            placeholder={name}
            value={draft[name]}
            onChange={(event) => setDraft({ ...draft, [name]: event.target.value })}
          />
        ))}
        <button className="btn" type="submit">
          {t("Применить выбор")}
        </button>
      </form>

      {screen.error && !view && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}

      <div className="grid" id="route-summary">
        <section className="panel">
          <div className="panel-head">
            <h2>{t("Маршрут")}</h2>
          </div>
          {view ? (
            <ol className="timeline" id="route-stages">
              {view.tabs.map((item, index) => (
                <li key={item.stage} data-state={item.state}>
                  <b>{`${index + 1} · ${t(item.title)}`}</b>
                  <small>
                    {t(item.mark)}
                    {item.reason ? ` · ${t(item.reason)}` : ""}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <div className="body">
              <p className="muted">{t("нет данных")}</p>
            </div>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <h2>{t("Факты среды")}</h2>
          </div>
          <div className="body">
            <dl className="fields" id="route-env">
              {(
                [
                  ["Podman", envFact(view, /podman/i)],
                  ["SELinux", envFact(view, /selinux/i)],
                  ["Cgroups", null],
                ] as const
              ).map(([label, row]) => (
                <span key={label} style={{ display: "contents" }}>
                  <dt>{label}</dt>
                  <dd className={row ? "" : "muted no-data"}>{row ? t(row.value) : t("нет данных")}</dd>
                </span>
              ))}
            </dl>
          </div>
        </section>
      </div>

      {view && current && (
        <section className="panel route-view" id="route-view">
          <div className="orch-tabbar route-tabs" role="tablist" aria-label={t("Контейнерный маршрут")}>
            {view.tabs.map((item) => (
              <button
                key={item.stage}
                type="button"
                role="tab"
                className={`orch-tab${item.stage === stage ? " on" : ""}`}
                aria-selected={item.stage === stage}
                data-stage={item.stage}
                data-state={item.state}
                title={item.reason ? t(item.reason) : undefined}
                onClick={() => setStage(item.stage)}
              >
                {`${item.mark.split(" ")[0]} ${t(item.title)}`}
              </button>
            ))}
          </div>
          {tab && (
            <p className="route-tab-state" id="route-tab-state">
              {t(tab.mark)}
              {tab.reason ? ` · ${t(tab.reason)}` : ""}
            </p>
          )}
          <div role="tabpanel" data-stage={stage}>
            <RowList rows={current.rows} blockers={current.blockers} notes={current.notes} actions={current.actions} />
            <ActionBar
              actions={pageActions(current.actions)}
              busy={screen.loading}
              onAction={(action) => {
                if (READS.has(action.key)) screen.refresh(true);
              }}
            />
          </div>
        </section>
      )}
    </div>
  );
}
