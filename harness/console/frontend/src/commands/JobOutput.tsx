/* The output of one job as the server streamed it, with its phase, exit code and cut. */
import { useI18n } from "../i18n";
import type { LocalJob } from "../ws/jobs";

export const PHASE_LABELS: Readonly<Record<string, string>> = {
  running: "Выполняется",
  completed: "Завершена",
  failed: "Не удалась",
  cancelled: "Отменена",
};

const PHASE_TONE: Readonly<Record<string, string>> = {
  running: "blue",
  completed: "mint",
  failed: "lavender",
  cancelled: "violet",
};

export function JobOutput({ job, onCancel }: { job: LocalJob; onCancel: () => void }) {
  const { t } = useI18n();
  const text = job.output.map((fragment) => fragment.text).join("");
  return (
    <section className="panel command-output" aria-label={t("Вывод")} data-job={job.id}>
      <div className="panel-head">
        <h2>
          <code>{job.command_id}</code>
        </h2>
        <span className="command-output-state">
          <em className={`orch-pill ${PHASE_TONE[job.phase] ?? ""}`} role="status">
            {t(PHASE_LABELS[job.phase] ?? job.phase)}
          </em>
          {job.returncode !== null && (
            <span className="small muted">{t("Код возврата: {code}", { code: job.returncode })}</span>
          )}
          {job.phase === "running" && (
            <button className="btn small" type="button" onClick={onCancel}>
              {t("Отменить job")}
            </button>
          )}
        </span>
      </div>
      <pre className="command-output-text" aria-live="polite">
        {text || t("Вывода пока нет")}
      </pre>
      {job.truncated && <p className="harness-note">{t("Вывод обрезан")}</p>}
    </section>
  );
}
