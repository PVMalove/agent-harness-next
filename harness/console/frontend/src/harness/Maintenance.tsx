/* The "Обслуживание" panel of the Harness overview: the soft cleanup plan with its server-computed
   sizes, categories and skips, the extra of the hard plan, the plan details and the worktree
   facts. Cleaning and removing a worktree are asked of the Commands tab, whose command panel
   runs them with the server's confirmation and the digest of the plan shown here. */
import { useState } from "react";
import { reasonText, useI18n } from "../i18n";
import { Icon } from "../icons";
import type { MaintenanceFacts } from "../ws/screens";
import { baseName, formatSize } from "./format";

export function Maintenance({
  facts,
  error,
  onClean,
  onRemove,
  onRefresh,
}: {
  facts: MaintenanceFacts | null;
  /** Why the maintenance snapshot could not be read at all. */
  error: string | null;
  onClean: () => void;
  onRemove: (path: string) => void;
  onRefresh: () => void;
}) {
  const { t, language } = useI18n();
  const [details, setDetails] = useState(false);
  const view = facts?.maintenance ?? null;
  const failure = error ?? (facts && facts.error ? facts.error : null);
  const soft = view?.soft ?? null;
  const sizes = new Map((view?.tree_sizes ?? []).map((entry) => [entry.path, entry.size]));
  const removable = view ? view.worktrees.filter((tree) => tree.reason === "").length : 0;

  return (
    <section className="panel harness-commands harness-maintenance" id="harness-maintenance">
      <div className="panel-head">
        <h2>{t("Обслуживание")}</h2>
        <span className="harness-maintenance-actions">
          <button className="btn" type="button" disabled={!view} aria-expanded={details} onClick={() => setDetails(!details)}>
            <Icon name="reports" /> {t("План")}
          </button>
          <button
            className="btn primary"
            type="button"
            disabled={!soft || soft.items === 0}
            onClick={onClean}
          >
            <Icon name="x" /> {t("Очистить…")}
          </button>
          <button className="btn" type="button" aria-label={t("Обновить")} onClick={onRefresh}>
            <Icon name="refresh" />
          </button>
        </span>
      </div>
      <div className="harness-maintenance-body">
        <h3>
          <Icon name="clock" /> {t("Временные файлы")}
        </h3>
        {failure ? (
          <p className="harness-maintenance-error" role="alert">
            {t("Ошибка плана очистки: ")}
            {failure}
          </p>
        ) : !view || !soft ? (
          <p className="muted">{t("Статистика считается…")}</p>
        ) : (
          <ul className="harness-maintenance-lines">
            {soft.items === 0 && <li>{t("Временных файлов нет")}</li>}
            <li>
              {formatSize(soft.total.bytes)} · {soft.total.files} {t("файлов")}
            </li>
            {Object.entries(soft.categories).map(([name, size]) => (
              <li key={name}>
                {name}: {formatSize(size.bytes)} · {size.files}
              </li>
            ))}
            <li>
              {t("Пропущено")}: {soft.plan.skipped.length}
            </li>
            <li>
              {t("Жёсткий режим: +")}
              {formatSize(Math.max(0, view.hard.total.bytes - soft.total.bytes))}
            </li>
          </ul>
        )}
        {details && soft && (
          <div className="harness-plan" id="harness-plan">
            {soft.plan.remove.map((item) => (
              <div key={`${item.kind}:${item.path}`}>
                <b>{item.kind}</b> <code>{item.path}</code>
              </div>
            ))}
            {soft.plan.skipped.map((item) => (
              <div key={`skip:${item.path}`} className="muted">
                ○ <code>{item.path}</code>: {reasonText(language, item.reason)}
              </div>
            ))}
            {soft.plan.remove.length === 0 && soft.plan.skipped.length === 0 && <div>{t("Временных файлов нет")}</div>}
          </div>
        )}
        <h3>
          <Icon name="branch" /> Worktree
        </h3>
        {!view ? (
          <p className="muted">Worktree: …</p>
        ) : view.worktree_error ? (
          <p className="muted">{reasonText(language, view.worktree_error)}</p>
        ) : (
          <>
            <p className="muted" id="worktree-count">
              Worktree: {view.worktrees.length} · {t("можно удалить")}: {removable}
            </p>
            {view.worktrees.map((tree) => {
              const size = sizes.get(tree.path);
              return (
                <div className="worktree-row" key={tree.path} data-worktree={tree.path} title={tree.path}>
                  <span>
                    <b>{baseName(tree.path)}</b> · dirty: {tree.dirty ?? "?"} · {size ? formatSize(size.bytes) : "?"} ·{" "}
                    {reasonText(language, tree.reason)}
                  </span>
                  <button
                    className="btn"
                    type="button"
                    disabled={tree.reason !== ""}
                    aria-label={`${t("Удалить…")} ${baseName(tree.path)}`}
                    onClick={() => onRemove(tree.path)}
                  >
                    <Icon name="x" /> {t("Удалить…")}
                  </button>
                </div>
              );
            })}
          </>
        )}
      </div>
    </section>
  );
}
