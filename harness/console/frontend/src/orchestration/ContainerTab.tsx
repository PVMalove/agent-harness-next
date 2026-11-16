/* The Container tab of Orchestration: the dispatch containers of orchestration.snapshot (the
   ledger records that carry a runtime-supervised execution or a container QA). The state is the
   ledger's (the dispatch stage), never runtime liveness: the caption says so and the selected
   container links to «Контейнерный маршрут». No container yields an explicit empty state. */
import { useState } from "react";
import { Panel, StatusIcon } from "../ds";
import type { Tone } from "../ds";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { roleName } from "../steps/ActivityViews";
import { CONTAINER_STATES } from "../ws/ledger";
import type { ContainerSnapshot, ContainerState } from "../ws/ledger";

const STATE_TONE: Readonly<Record<ContainerState, Tone>> = { running: "ok", "not-created": "warn", stopped: "info", unknown: "off" };
const STATE_LABEL: Readonly<Record<ContainerState, string>> = {
  running: "Работает",
  "not-created": "Не создан",
  stopped: "Остановлен",
  unknown: "Нет данных",
};

export function ContainerTab({ containers }: { containers: ContainerSnapshot | null }) {
  const { t, state: stateText } = useI18n();
  const list = containers?.containers ?? [];
  const [selected, setSelected] = useState<string | null>(null);
  if (list.length === 0) {
    return (
      <Panel title={t("Контейнеры")} fill id="orch-containers">
        <p className="ds-empty" id="orch-containers-empty">
          {t("Контейнеров нет: ни один dispatch не запускался через контейнерный исполнитель")}
        </p>
      </Panel>
    );
  }
  const current = list.find((item) => item.dispatch_id === selected) ?? list[0]!;
  const route = `${href("container-route")}?batch=${encodeURIComponent(current.batch_id)}`;
  return (
    <div className="ds-split">
      <Panel title={t("Контейнеры")} count={list.length} meta={t("состояние по ledger")} fill scroll="list" id="orch-containers">
        <div className="ds-engine" id="orch-container-summary">
          {CONTAINER_STATES.map((state) => (
            <span key={state} className="ds-status-line" data-state={state}>
              <StatusIcon tone={STATE_TONE[state]} label={t(STATE_LABEL[state])} />
              {t(STATE_LABEL[state])} <b>{containers?.counts[state] ?? 0}</b>
            </span>
          ))}
        </div>
        {list.map((item) => (
          <button
            key={item.dispatch_id}
            type="button"
            className="ds-row ds-row-button"
            data-container={item.dispatch_id}
            data-state={item.state}
            aria-pressed={item.dispatch_id === current.dispatch_id}
            onClick={() => setSelected(item.dispatch_id)}
          >
            <StatusIcon tone={STATE_TONE[item.state]} label={t(STATE_LABEL[item.state])} />
            <span className="ds-row-main">
              <span className="ds-row-title">{`${item.dispatch_id} · ${item.ticket || item.batch_id}`}</span>
              <span className="ds-row-sub">{`${roleName(item.role)} · ${item.kind === "qa" ? t("контейнерный QA") : t("worker под runtime")}`}</span>
            </span>
            <span className="ds-row-end">{t(STATE_LABEL[item.state])}</span>
          </button>
        ))}
      </Panel>
      <Panel
        title={current.dispatch_id}
        fill
        scroll="text"
        id="orch-container-detail"
        actions={
          <a className="ds-btn ds-btn-sm" id="orch-container-route" href={route}>
            {t("Контейнерный маршрут")}
          </a>
        }
      >
        <dl className="ds-kv">
          <div className="ds-kv-row">
            <dt>{t("Состояние")}</dt>
            <dd className="ds-status-line">
              <StatusIcon tone={STATE_TONE[current.state]} /> {t(STATE_LABEL[current.state])}
            </dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Этап в ledger")}</dt>
            <dd>{current.stage_state ? stateText(current.stage_state) : t("нет данных")}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>Batch</dt>
            <dd>{current.batch_id || t("нет данных")}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Роль")}</dt>
            <dd>{roleName(current.role)}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>Engine</dt>
            <dd>{current.engine || t("нет данных")}</dd>
          </div>
          <div className="ds-kv-row">
            <dt>{t("Образ worker")}</dt>
            <dd>{current.image ? <code>{current.image}</code> : t("нет данных")}</dd>
          </div>
        </dl>
        <p className="ds-note">{t("Состояние выведено из этапа dispatch в ledger. Живость контейнера наблюдает runtime: откройте «Контейнерный маршрут».")}</p>
      </Panel>
    </div>
  );
}
