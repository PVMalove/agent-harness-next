import { useEffect, useState } from "react";
import { ConfirmDialog } from "../commands/ConfirmDialog";
import type { ConfirmRequest } from "../commands/ConfirmDialog";
import { JobOutput } from "../commands/JobOutput";
import { useJobs } from "../commands/useJobs";
import { useI18n } from "../i18n";
import type { CommandDescriptor } from "../ws/jobs";
import { JOB_ERROR_LABELS } from "../ws/jobs";
import type { DecisionItem } from "../ws/decisions";
import { useDecisions } from "./useDecisions";

const KINDS: Readonly<Record<string, string>> = {
  "native-permission": "Запрос native permission", "dispatch-approval": "Approval dispatch",
  "report-decision": "Решение по отчёту", "batch-approval": "Утверждение batch", attention: "Требуется внимание",
};

function DecisionAction({ item, command, disabled, onRun }: {
  item: DecisionItem; command: CommandDescriptor; disabled: boolean;
  onRun: (command: CommandDescriptor, values: Record<string, string>) => void;
}) {
  const { t } = useI18n();
  const [entered, setEntered] = useState<Record<string, string>>({});
  const fields = command.fields ?? command.inputs.map((dest) => ({ dest, required: true,
    choices: null, takes_value: true, repeatable: false, help: "", default: null, flag: dest }));
  const values = { ...entered, ...item.values };
  const ready = fields.every((field) => !field.required || Boolean(values[field.dest]?.trim())) &&
    (command.command_id !== "dispatch-create" || Boolean(values.transition_digest?.trim()));
  const renderField = (field: (typeof fields)[number]) => {
    if (Object.hasOwn(item.values, field.dest)) return null;
    const change = (value: string) => setEntered({ ...entered, [field.dest]: value });
    return <label key={field.dest} className="decision-field">
      <span>{field.dest}{field.required || field.dest === "transition_digest" ? " *" : ""}</span>
      {field.choices ? <select aria-label={`${command.command_id} ${field.dest}`}
        value={entered[field.dest] ?? ""} onChange={(event) => change(event.target.value)}>
        <option value="">{t("Выберите значение")}</option>
        {field.choices.map((choice) => <option key={choice} value={choice}>{choice}</option>)}
      </select> : !field.takes_value ? <input type="checkbox" aria-label={`${command.command_id} ${field.dest}`}
        checked={Boolean(entered[field.dest])} onChange={(event) => change(event.target.checked ? "true" : "")} />
      : field.repeatable ? <textarea aria-label={`${command.command_id} ${field.dest}`}
        value={entered[field.dest] ?? ""} onChange={(event) => change(event.target.value)} />
      : <input aria-label={`${command.command_id} ${field.dest}`} autoComplete="off"
        value={entered[field.dest] ?? ""} onChange={(event) => change(event.target.value)} />}
    </label>;
  };
  return <form className="decision-action" data-command={command.command_id}
    onSubmit={(event) => { event.preventDefault(); if (ready && !disabled && command.available) onRun(command, values); }}>
    <div className="decision-fields">{fields.filter((field) => field.required || field.dest === "transition_digest").map(renderField)}</div>
    {fields.some((field) => !field.required && field.dest !== "transition_digest") &&
      <details><summary>{t("Дополнительные параметры")}</summary>
        <div className="decision-fields">{fields.filter((field) => !field.required && field.dest !== "transition_digest").map(renderField)}</div>
      </details>}
    <button type="submit" className="btn" disabled={disabled || !ready || !command.available}>{t(command.title)}</button>
    {!command.available && <p>{t("Команда недоступна для выбранного проекта")}</p>}
  </form>;
}

type Pending = { itemKey: string; command: CommandDescriptor; values: Record<string, string>; dialog: ConfirmRequest }
  | { jobId: string; dialog: ConfirmRequest };

/** Decisions stay in their work context; all choices use the server's existing job boundary. */
export function DecisionPanel({ kinds, hideWhenEmpty = false }: { kinds?: readonly string[]; hideWhenEmpty?: boolean }) {
  const { t } = useI18n();
  const decisions = useDecisions();
  const jobs = useJobs("decisions");
  const [pending, setPending] = useState<Pending | null>(null);
  const { snapshot, fresh } = decisions;
  // A changed request, a failed read or a lost connection invalidates a pending confirmation.
  useEffect(() => {
    setPending((current) => current && "itemKey" in current &&
      (!fresh || !snapshot?.items.some((item) => JSON.stringify(item) === current.itemKey)) ? null : current);
  }, [fresh, snapshot]);
  const cancel = () => {
    if (!jobs.shown) return;
    setPending({ jobId: jobs.shown.id, dialog: { title: t("Подтвердите отмену job"),
      command: jobs.shown.command_id, reason: t(jobs.cancelReason ?? ""), typed: null, action: t("Отменить job") } });
  };
  const run = (item: DecisionItem, command: CommandDescriptor, values: Record<string, string>) => {
    // A proposal only describes the transition. Its output must be read before a separate approval.
    if (!command.needs_confirmation) { jobs.start({ command_id: command.command_id, values }); return; }
    setPending({ itemKey: JSON.stringify(item), command, values: { ...values }, dialog: {
      title: t("Подтвердите решение"), command: command.command_id,
      reason: t(command.confirmation_reason ?? command.title), typed: command.typed_confirmation,
      context: JSON.stringify({ ticket: item.ticket, batch: item.batch_id, dispatch: item.dispatch_id, ...values }, null, 2),
      action: t("Подтвердить"),
    } });
  };
  const confirm = (word: string | undefined) => {
    if (pending && "itemKey" in pending && fresh && snapshot?.items.some((item) => JSON.stringify(item) === pending.itemKey)) {
      jobs.start({ command_id: pending.command.command_id, values: pending.values, confirmed: true,
        ...(word === undefined ? {} : { confirmation: word }) });
    } else if (pending && "jobId" in pending) jobs.cancel(pending.jobId);
    setPending(null);
  };
  const items = snapshot?.items.filter((item) => !kinds || kinds.includes(item.kind)) ?? [];
  if (hideWhenEmpty && items.length === 0 && decisions.error === null &&
      jobs.shown === null && !jobs.starting && jobs.refusal === null && pending === null) return null;
  return <section className="decision-panel">
    <div className="panel-head"><h2>{t("Ожидающие решения")}</h2>
      <button className="btn small" onClick={decisions.refresh}>{t("Обновить")}</button></div>
    <p>{t("Решения проверяются сервером и записываются в журнал команд.")}</p>
    {decisions.error ? <p role="alert" data-code={decisions.error}>{t("Не удалось прочитать ожидающие решения")} <code>{decisions.error}</code></p>
      : snapshot === null ? <p role="status">{t("Загрузка решений…")}</p>
      : snapshot.unavailable ? <p role="status">{t("Оркестрация недоступна")}</p>
      : items.length === 0 ? <p role="status">{t("Нет ожидающих решений")}</p> : null}
    {snapshot && snapshot.total > snapshot.items.length && <p role="status">{t("Показана часть решений. Обновите список после обработки.")}</p>}
    {jobs.busy && <p role="status">{t("Занято: {command}", { command: jobs.busy.command_id })}</p>}
    {jobs.refusal && <p role="alert" className="command-refusal err">{t(JOB_ERROR_LABELS[jobs.refusal.code] ?? "Сервер ответил ошибкой.")}</p>}
    {items.map((item) => <article className="panel decision-card" key={JSON.stringify(item)}>
      <div className="panel-head"><h3>{t(KINDS[item.kind] ?? item.kind)}</h3><span className="orch-pill violet">{item.ticket}</span></div>
      <dl className="decision-context"><dt>batch</dt><dd>{item.batch_id}</dd>
        {item.dispatch_id && <><dt>dispatch</dt><dd>{item.dispatch_id}</dd></>}
        {item.role && <><dt>{t("Роль")}</dt><dd>{item.role}</dd></>}
        {Object.entries(item.details).filter(([, value]) => value).map(([name, value]) =>
          <div key={name}><dt>{name}</dt><dd><pre>{value}</pre></dd></div>)}
      </dl>
      {item.kind === "dispatch-approval" && <p>{t("Сначала предложите переход и прочитайте вывод. Для approval введите его transition_digest.")}</p>}
      {item.command_ids.map((id) => {
        const command = jobs.commands?.find((entry) => entry.command_id === id);
        return command ? <DecisionAction key={id} item={item} command={command}
          disabled={!fresh || jobs.busy !== null || jobs.starting} onRun={(entry, values) => run(item, entry, values)} /> :
          <p key={id}>{t("Загрузка каталога команд…")} <code>{id}</code></p>;
      })}
    </article>)}
    {jobs.shown && <JobOutput job={jobs.shown} onCancel={cancel} />}
    {pending && <ConfirmDialog request={pending.dialog} onConfirm={confirm} onClose={() => setPending(null)} />}
  </section>;
}
