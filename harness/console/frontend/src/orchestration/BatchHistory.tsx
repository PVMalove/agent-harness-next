/* The state filter and the batch history of the Orchestration page; choosing a batch opens its
   chronology (reports.timeline) and becomes the batch the Recovery and Container route links carry. */
import { useI18n } from "../i18n";
import { Timeline } from "../reports/Timeline";
import type { Ledger } from "../ws/ledger";
import { ALL_STATES, STATE_LABELS, batchLabel, batchesInState, stateFilterItems } from "./format";

/** The filter label in the page language: the state's word, then its count. */
const filterLabel = (t: (text: string) => string, key: string, label: string) => {
  const count = /\((\d+)\)$/.exec(label)?.[1] ?? "0";
  return `${t(key === ALL_STATES ? "все" : (STATE_LABELS[key] ?? key))} (${count})`;
};

export function BatchHistory({
  ledger,
  state,
  onState,
  selected,
  onSelect,
}: {
  ledger: Ledger;
  state: string;
  onState: (state: string) => void;
  selected: string | null;
  onSelect: (batchId: string) => void;
}) {
  const { t } = useI18n();
  const batches = batchesInState(ledger, state);
  return (
    <div className="orch-history-grid">
      <section className="panel orch-history" id="batch-history">
        <div className="panel-head">
          <h2>{t("История batch")}</h2>
          <select id="state-filter" aria-label={t("Фильтр по состоянию")} value={state} onChange={(event) => onState(event.target.value)}>
            {stateFilterItems(ledger).map(([key, label]) => (
              <option key={key} value={key}>
                {filterLabel(t, key, label)}
              </option>
            ))}
          </select>
        </div>
        {batches.length ? (
          <div className="orch-batches">
            {batches.map((batch) => {
              const [head, id] = batchLabel(batch);
              return (
                <button
                  key={batch.batch_id}
                  type="button"
                  className={`orch-batch${batch.batch_id === selected ? " on" : ""}`}
                  data-batch={batch.batch_id}
                  aria-pressed={batch.batch_id === selected}
                  onClick={() => onSelect(batch.batch_id)}
                >
                  <b>{head}</b>
                  <code className="orch-batch-id">{id}</code>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="report-empty">{t("Ничего не найдено")}</p>
        )}
      </section>
      {selected ? (
        <Timeline key={selected} batchId={selected} />
      ) : (
        <section className="panel report-timeline">
          <div className="report-empty">{t("Выберите batch, чтобы открыть его хронологию")}</div>
        </section>
      )}
    </div>
  );
}
