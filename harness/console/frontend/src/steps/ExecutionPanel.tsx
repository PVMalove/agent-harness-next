/* What the runtime observes of a supervised execution, a worker process or a container (#1296):
   its state, engine and image, the deadline, the exit, the cleanup of its objects and the last
   lines of its stderr. A field the runtime did not report says so; nothing here is a decision. */
import { useI18n } from "../i18n";
import { dateTimeText } from "../reports/format";
import type { RosterDispatch } from "../ws/steps";

/** The tone of each execution state of the runtime. */
const STATE_TONE: Readonly<Record<string, string>> = {
  launching: "ok",
  running: "ok",
  stopping: "warn",
  exited: "",
  lost: "err",
  unknown: "warn",
};

const moment = (value: string) => dateTimeText(value) ?? value;

export function ExecutionPanel({ session }: { session: RosterDispatch | null }) {
  const { t, state: stateText } = useI18n();
  const execution = session?.execution;
  if (!execution) return null;
  const none = t("не сообщается");
  const exit =
    execution.exit_code === null && !execution.stopped_by
      ? t("ещё не завершилось")
      : [
          execution.exit_code === null ? null : t("код {code}", { code: execution.exit_code }),
          execution.stopped_by ? t("остановлено: {by}", { by: execution.stopped_by }) : null,
          execution.oom_killed ? t("нехватка памяти (OOM)") : null,
        ]
          .filter(Boolean)
          .join(" · ");
  const teardown =
    execution.teardown === "removed"
      ? t("объекты удалены")
      : execution.teardown
        ? execution.teardown
        : t("ещё не выполнялась");
  return (
    <section className="panel work-execution" id="work-execution" aria-label={t("Выполнение в runtime")}>
      <div className="panel-head">
        <h2>{t(execution.kind === "container" ? "Контейнер" : "Процесс worker")}</h2>
        <span className={`work-status ${STATE_TONE[execution.state] ?? "warn"}`}>
          {execution.state ? stateText(execution.state) : none}
        </span>
      </div>
      <dl className="work-observation-facts work-execution-facts">
        <dt>{t("Движок")}</dt>
        <dd>{execution.engine || none}</dd>
        <dt>{t("Образ")}</dt>
        <dd>{execution.image ? <code>{execution.image}</code> : none}</dd>
        {execution.container_id ? (
          <>
            <dt>{t("Контейнер")}</dt>
            <dd>
              <code>{execution.container_id.slice(0, 12)}</code>
            </dd>
          </>
        ) : null}
        <dt>{t("Дедлайн")}</dt>
        <dd>{execution.deadline ? moment(execution.deadline) : none}</dd>
        <dt>{t("Наблюдалось")}</dt>
        <dd>{execution.observed_at ? moment(execution.observed_at) : none}</dd>
        <dt>{t("Завершение")}</dt>
        <dd>{exit}</dd>
        <dt>{t("Очистка")}</dt>
        <dd>{teardown}</dd>
      </dl>
      {execution.stderr_tail.length ? (
        <>
          <h3 className="work-observation-title">{t("Последние строки stderr")}</h3>
          <pre className="work-execution-stderr">{execution.stderr_tail.join("\n")}</pre>
        </>
      ) : null}
    </section>
  );
}
