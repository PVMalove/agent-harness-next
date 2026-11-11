/* A section's catalog commands as server jobs: run, confirm by the class the server reports,
   follow the output, show the job that keeps the console busy and cancel it after a confirmation.
   Labels and reasons are the server's Russian source strings; catalog.json translates them.
   A page may hand over the digests of the cleanup plans it shows (a plan_required command then
   runs bound to that plan), ask to run a command from its own buttons through the same
   server-driven confirmation, hide the command table when it runs commands only from its own
   controls, and learn when the shown job finishes. */
import { useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import type { CommandDescriptor, LocalJob } from "../ws/jobs";
import { ConfirmDialog } from "./ConfirmDialog";
import type { ConfirmRequest } from "./ConfirmDialog";
import { JobOutput } from "./JobOutput";
import { useJobs } from "./useJobs";
import type { Section } from "./useJobs";

/** A run a page asks for; a new `nonce` asks again. */
export interface RunRequest {
  command_id: string;
  values: Record<string, string>;
  nonce: number;
  /** What the page says the run will do, shown in the confirmation instead of the server's
      class reason. */
  reason?: string;
}

type Pending =
  | { kind: "start"; command: CommandDescriptor; values: Record<string, string>; dialog: ConfirmRequest }
  | { kind: "cancel"; jobId: string; dialog: ConfirmRequest };

/** Why `command` cannot run here, or null when it can. */
function blockedText(
  t: (text: string) => string,
  command: CommandDescriptor,
  planDigests: Readonly<Record<string, string>>,
): string | null {
  if (!command.available) return t("Команда недоступна для выбранного проекта");
  if (command.plan_required && !planDigests[command.command_id]) {
    return t("Нужно превью плана очистки: запустите команду из TUI");
  }
  return null;
}

function CommandRow({
  command,
  blocked,
  onRun,
}: {
  command: CommandDescriptor;
  blocked: string | null;
  onRun: (command: CommandDescriptor, values: Record<string, string>) => void;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState<Record<string, string>>({});
  const filled = command.inputs.every((name) => (values[name] ?? "").trim() !== "");
  const tone = command.reversibility === "reversible" ? "mint" : "violet";
  return (
    <div className="harness-command-row" data-command={command.command_id}>
      <code>{command.command_id}</code>
      <span title={blocked ?? t(command.title)}>{blocked ?? t(command.title)}</span>
      <em className={`orch-pill ${tone}`}>{t(command.reversibility_label)}</em>
      <span className="command-inputs">
        {command.inputs.map((name) => (
          <input
            key={name}
            aria-label={name}
            placeholder={name}
            value={values[name] ?? ""}
            disabled={blocked !== null}
            onChange={(event) => setValues({ ...values, [name]: event.target.value })}
          />
        ))}
      </span>
      <button
        className="btn"
        type="button"
        disabled={blocked !== null || !filled}
        aria-label={`${t("Запустить")} ${command.command_id}`}
        onClick={() => onRun(command, values)}
      >
        {t("Запустить")}
      </button>
    </div>
  );
}

const NO_DIGESTS: Readonly<Record<string, string>> = {};

export function CommandPanel({
  section,
  planDigests = NO_DIGESTS,
  request,
  onJobDone,
  confirmAll = false,
  listed = true,
}: {
  section: Section;
  /** Every run opens the confirmation first, whatever the command's class: a reversible
      command is then started with `confirmed: true` too. */
  confirmAll?: boolean;
  /** Whether the section's command table is shown; a page that runs its commands only from
      its own controls passes false, so no free-text input of a command is offered. */
  listed?: boolean;
  /** command_id -> the server digest of the plan the page shows. */
  planDigests?: Readonly<Record<string, string>>;
  request?: RunRequest | null;
  onJobDone?: (job: LocalJob) => void;
}) {
  const { t } = useI18n();
  const jobs = useJobs(section);
  const [pending, setPending] = useState<Pending | null>(null);
  const [unavailable, setUnavailable] = useState<string | null>(null);
  const handled = useRef<number | null>(null);
  const finished = useRef(new Set<string>());

  const digest = (command: CommandDescriptor) =>
    command.plan_required ? { plan_digest: planDigests[command.command_id] } : {};

  const run = (command: CommandDescriptor, values: Record<string, string>, reason?: string) => {
    setUnavailable(null);
    if (!command.needs_confirmation && !confirmAll) {
      jobs.start({ command_id: command.command_id, values, ...digest(command) });
      return;
    }
    setPending({
      kind: "start",
      command,
      values,
      dialog: {
        title: t("Подтвердите запуск"),
        command: command.command_id,
        reason: reason ?? t(command.confirmation_reason ?? command.title),
        typed: command.typed_confirmation,
        action: t("Запустить"),
      },
    });
  };
  const askCancel = (jobId: string, commandId: string) =>
    setPending({
      kind: "cancel",
      jobId,
      dialog: {
        title: t("Подтвердите отмену job"),
        command: commandId,
        reason: t(jobs.cancelReason ?? ""),
        typed: null,
        action: t("Отменить job"),
      },
    });
  const confirm = (confirmation: string | undefined) => {
    if (pending?.kind === "start") {
      jobs.start({
        command_id: pending.command.command_id,
        values: pending.values,
        confirmed: true,
        ...(confirmation === undefined ? {} : { confirmation }),
        ...digest(pending.command),
      });
    } else if (pending?.kind === "cancel") {
      jobs.cancel(pending.jobId);
    }
    setPending(null);
  };

  const { busy, shown, refusal, commands } = jobs;

  // A page's run request: once per nonce, as soon as the catalog is known.
  useEffect(() => {
    if (!request || commands === null || handled.current === request.nonce) return;
    handled.current = request.nonce;
    const command = commands.find((item) => item.command_id === request.command_id);
    const blocked = command ? blockedText(t, command, planDigests) : t("Команда недоступна для выбранного проекта");
    if (!command || blocked !== null) {
      setUnavailable(blocked);
      return;
    }
    run(command, request.values, request.reason);
    // `run` and `t` change with every render; the nonce decides.
  }, [request, commands]);

  // The shown job reached a final phase: tell the page once per job.
  useEffect(() => {
    if (!shown || !shown.done || shown.phase === "running" || finished.current.has(shown.id)) return;
    finished.current.add(shown.id);
    onJobDone?.(shown);
  }, [shown, onJobDone]);
  return (
    <div className="command-panel" data-section={section}>
      {busy && (
        <div className="panel command-busy" role="status">
          <span>{t("Занято: {command}", { command: busy.command_id })}</span>
          <span className="command-busy-actions">
            {shown?.id !== busy.id && (
              <button className="btn small" type="button" onClick={() => jobs.show(busy.id)}>
                {t("Показать вывод")}
              </button>
            )}
            <button className="btn small" type="button" onClick={() => askCancel(busy.id, busy.command_id)}>
              {t("Отменить job")}
            </button>
          </span>
        </div>
      )}
      {refusal && (
        <p className="command-refusal err" role="alert" data-code={refusal.code}>
          {t(JOB_ERROR_LABELS[refusal.code] ?? "Сервер ответил ошибкой.")}
        </p>
      )}
      {unavailable && (
        <p className="command-refusal err" role="alert">
          {unavailable}
        </p>
      )}
      {listed && <section className="panel harness-commands">
        <div className="panel-head">
          <h2>{t("Команды")}</h2>
        </div>
        {commands === null ? (
          <p className="harness-note">{t("Загрузка каталога команд…")}</p>
        ) : commands.length === 0 ? (
          <p className="harness-note">{t("В этом разделе нет команд")}</p>
        ) : (
          <div className="harness-command-table">
            {commands.map((command) => (
              <CommandRow
                key={command.command_id}
                command={command}
                blocked={blockedText(t, command, planDigests)}
                onRun={run}
              />
            ))}
          </div>
        )}
      </section>}
      {shown && <JobOutput job={shown} onCancel={() => askCancel(shown.id, shown.command_id)} />}
      {pending && <ConfirmDialog request={pending.dialog} onConfirm={confirm} onClose={() => setPending(null)} />}
    </div>
  );
}
