/* An in-process worker runs inside the coordinator session and has no step stream (#1015): the
   panel says so and shows what the ledger records of it instead, its heartbeat, its model
   self-report and its newest checkpoints. */
import { useI18n } from "../i18n";
import { dateTimeText } from "../reports/format";
import type { RosterDispatch } from "../ws/steps";

/** The Russian text of each stream reason code the server sends (catalog.json translates it). */
const REASON_LABELS: Readonly<Record<string, string>> = {
  in_process:
    "In-process воркер работает внутри сессии coordinator и не отдаёт поток событий. Ход работы виден по heartbeat, self-report модели и чекпоинтам.",
};

const moment = (value: string) => dateTimeText(value) ?? "—";

export function InProcessPanel({ session }: { session: RosterDispatch | null }) {
  const { t } = useI18n();
  const observation = session?.observation;
  if (!observation) return null;
  const reason = REASON_LABELS[observation.stream_reason];
  const report = observation.self_report;
  const { checkpoints, checkpoint_count: count } = observation;
  return (
    <section className="panel work-observation" id="work-observation">
      <div className="panel-head">
        <h2>{t("Нет потока событий")}</h2>
        <span className="small muted">{t("данные ledger")}</span>
      </div>
      <p className="work-observation-reason">{reason ? t(reason) : observation.stream_reason}</p>
      <dl className="work-observation-facts">
        <dt>{t("Heartbeat")}</dt>
        <dd>{moment(observation.heartbeat_at)}</dd>
        <dt>{t("Self-report модели")}</dt>
        <dd>
          {report ? (
            <>
              <b>{report.reported_model}</b>{" "}
              <span>{t(report.match ? "совпадает с назначенной" : "не совпадает с назначенной")}</span>
            </>
          ) : (
            t("ещё не отправлен")
          )}
        </dd>
      </dl>
      <h3 className="work-observation-title">{t("Чекпоинты")}</h3>
      {checkpoints.length ? (
        <ul className="work-observation-checkpoints">
          {checkpoints.map((item) => (
            <li key={item.checkpoint_id} data-checkpoint={item.checkpoint_id}>
              <b>{item.checkpoint_id}</b> <code>{item.commit_sha.slice(0, 7)}</code> <span>{moment(item.created_at)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="work-observation-reason muted">{t("Чекпоинтов пока нет.")}</p>
      )}
      {count > checkpoints.length ? (
        <p className="work-observation-reason muted">
          {t("Показаны последние {shown} из {count}.", { shown: checkpoints.length, count })}
        </p>
      ) : null}
    </section>
  );
}
