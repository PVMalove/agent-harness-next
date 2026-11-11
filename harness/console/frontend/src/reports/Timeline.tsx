/* A batch chronology from reports.timeline: its state, start, time to PR and route, then every
   event in order. Event texts are the server's own; nothing is reordered here. */
import { useI18n } from "../i18n";
import { useScreen } from "../screens/useScreen";
import { parseTimeline } from "../ws/ledger";
import type { BatchSummary } from "../ws/ledger";
import { batchStartText, batchStatus, batchTimingText, renderStatus, roleFlowText } from "./format";

export function BatchList({
  batches,
  selected,
  onSelect,
}: {
  batches: readonly BatchSummary[];
  selected: string | null;
  onSelect: (batchId: string) => void;
}) {
  const { t, language } = useI18n();
  if (!batches.length) return <p className="report-empty">{t("Ничего не найдено")}</p>;
  return (
    <div className="report-list" id="batch-list">
      {batches.map((batch) => {
        const status = batchStatus(batch);
        return (
          <button
            key={batch.batch_id}
            type="button"
            className={`report-row${batch.batch_id === selected ? " on" : ""}`}
            data-batch={batch.batch_id}
            aria-pressed={batch.batch_id === selected}
            onClick={() => onSelect(batch.batch_id)}
          >
            <span className="report-row-main">
              <b>{t(batchStartText(batch))}</b>
              <small>
                {batch.ticket} · {batch.batch_id}
              </small>
            </span>
            <span className={`report-status ${status.kind}`}>{renderStatus(status, language)}</span>
            <span className="report-time">{batchTimingText(batch, language)}</span>
          </button>
        );
      })}
    </div>
  );
}

export function Timeline({ batchId }: { batchId: string }) {
  const { t, language } = useI18n();
  const screen = useScreen({ type: "reports.timeline", params: { batch_id: batchId } }, parseTimeline);
  const timeline = screen.data;
  return (
    <section className="panel report-timeline" id="report-timeline">
      <div className="panel-head">
        <h2>{t("Хронология batch")}</h2>
        <code>{batchId}</code>
      </div>
      {screen.error && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {screen.error.message || screen.error.code}
        </p>
      )}
      {timeline && (
        <>
          <div className="report-meta">
            <span>{renderStatus(batchStatus(timeline.batch), language)}</span>
            <span>{t(batchStartText(timeline.batch))}</span>
            <span>{batchTimingText(timeline.batch, language)}</span>
          </div>
          <p className="report-route">
            {t("маршрут")}: <span>{roleFlowText(timeline)}</span>
          </p>
          <ol className="timeline">
            {timeline.events.map((event, index) => (
              <li key={index} data-kind={event.kind}>
                <small>
                  {event.at || "?"} · {event.kind}
                  {event.role ? ` · ${event.role}` : ""}
                </small>
                <span>{event.text}</span>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
