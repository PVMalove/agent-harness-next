/* A section's catalog commands as server jobs: run, confirm by the class the server reports,
   follow the output, show the job that keeps the console busy and cancel it after a confirmation. */
import { useState } from "react";
import { useI18n } from "../i18n";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import type { CommandDescriptor } from "../ws/jobs";
import { ConfirmDialog } from "./ConfirmDialog";
import type { ConfirmRequest } from "./ConfirmDialog";
import { JobOutput } from "./JobOutput";
import { useJobs } from "./useJobs";
import type { Section } from "./useJobs";

/* The Russian labels and reasons of kernel/catalog.py (REVERSIBILITY_LABELS,
   CONFIRMATION_REASONS); catalog.json translates them. */
export const REVERSIBILITY_LABELS: Readonly<Record<string, string>> = {
  reversible: "✔ обратимо",
  "deletes-local-data": "✖ удаление",
  "terminal-coordinator-action": "⚠ решение",
  "external-change": "⚠ внешнее",
  "overwrites-managed-files": "⚠ перезапись",
  "downloads-files": "⚠ загрузка",
};

export const CONFIRMATION_REASONS: Readonly<Record<string, string>> = {
  "deletes-local-data": "Команда удаляет локальные данные — восстановить их нельзя.",
  "terminal-coordinator-action": "Команда записывает терминальное решение coordinator — отменить его нельзя.",
  "external-change": "Команда меняет внешнюю систему: это видят другие люди или это расходует токены.",
  "overwrites-managed-files":
    "Команда перезаписывает файлы харнесса в проекте (управляемые или seed) — незакоммиченные правки в них пропадут.",
  "downloads-files":
    "Команда скачивает файлы из сети (PyPI, нужны доступ и время) и заменяет локальный bundle парсеров проекта.",
};

const CANCEL_KEEPS_CHANGES = "Отмена останавливает команду; уже внесённые изменения не откатываются.";

type Pending =
  | { kind: "start"; command: CommandDescriptor; values: Record<string, string>; dialog: ConfirmRequest }
  | { kind: "cancel"; jobId: string; dialog: ConfirmRequest };

function CommandRow({
  command,
  onRun,
}: {
  command: CommandDescriptor;
  onRun: (command: CommandDescriptor, values: Record<string, string>) => void;
}) {
  const { t } = useI18n();
  const [values, setValues] = useState<Record<string, string>>({});
  const filled = command.inputs.every((name) => (values[name] ?? "").trim() !== "");
  const blocked = !command.available
    ? t("Команда недоступна для выбранного проекта")
    : command.plan_required
      ? t("Нужно превью плана очистки: запустите команду из TUI")
      : null;
  const tone = command.reversibility === "reversible" ? "mint" : "violet";
  return (
    <div className="harness-command-row" data-command={command.command_id}>
      <code>{command.command_id}</code>
      <span title={blocked ?? t(command.title)}>{blocked ?? t(command.title)}</span>
      <em className={`orch-pill ${tone}`}>{t(REVERSIBILITY_LABELS[command.reversibility] ?? command.reversibility)}</em>
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

export function CommandPanel({ section }: { section: Section }) {
  const { t } = useI18n();
  const jobs = useJobs(section);
  const [pending, setPending] = useState<Pending | null>(null);

  const run = (command: CommandDescriptor, values: Record<string, string>) => {
    if (!command.needs_confirmation) {
      jobs.start({ command_id: command.command_id, values });
      return;
    }
    setPending({
      kind: "start",
      command,
      values,
      dialog: {
        title: t("Подтвердите запуск"),
        command: command.command_id,
        reason: t(CONFIRMATION_REASONS[command.reversibility] ?? command.title),
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
        reason: t(CANCEL_KEEPS_CHANGES),
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
      });
    } else if (pending?.kind === "cancel") {
      jobs.cancel(pending.jobId);
    }
    setPending(null);
  };

  const { busy, shown, refusal, commands } = jobs;
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
      <section className="panel harness-commands">
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
              <CommandRow key={command.command_id} command={command} onRun={run} />
            ))}
          </div>
        )}
      </section>
      {shown && <JobOutput job={shown} onCancel={() => askCancel(shown.id, shown.command_id)} />}
      {pending && <ConfirmDialog request={pending.dialog} onConfirm={confirm} onClose={() => setPending(null)} />}
    </div>
  );
}
