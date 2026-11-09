/* Recovery (hidden route #/recovery?batch=): the batch history with its recovery gate and, once a
   batch is opened, the recovery view the kernel builds for the TUI (recovery.view). Nothing is
   decided here: rows, blockers, notes and action availability are the core's. Every action that
   changes something runs only through the CommandPanel of the job section `recovery`, and every
   run opens the confirmation first (`confirmAll`): cancelling it starts nothing. «Проверить
   состояние» and «Скрыть advisory» only read the view again. The TUI wizard «edit at pointer» of
   Fix is not offered: Fix previews the core's normalization and Fix-apply writes it. */
import { useState } from "react";
import { useSearchParams } from "react-router";
import { CommandPanel } from "../commands/CommandPanel";
import type { RunRequest } from "../commands/CommandPanel";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { useScreen } from "../screens/useScreen";
import { ActionBar, RowList } from "../views/RowList";
import type { LocalJob } from "../ws/jobs";
import { parseRecoveryView } from "../ws/views";
import type { ResumePlan, ViewAction } from "../ws/views";

/** The command a recovery action runs; `status`, `skip` and `resend` start none. */
export const RECOVERY_COMMANDS: Readonly<Record<string, string>> = {
  reload: "recovery-reload",
  fix: "recovery-fix",
  "fix-apply": "recovery-fix-apply",
  resume: "recovery-resume",
  abort: "recovery-abort",
};

export const FIX_APPLY_REASON =
  "Запись пойдёт через транзакцию конфигурации: проверка устаревания, резервная копия.";
export const ABORT_REASON =
  "Выход с сохранением не отменяет batch, не останавливает worker и не очищает worktree.";

const FIX_APPLY: ViewAction = {
  key: "fix-apply",
  label: "Записать нормализацию",
  enabled: true,
  reason: "",
  effect: "delete",
  needs_confirmation: true,
};

/** The confirmation text of Resume, worded as the TUI builds it. */
export function resumeText(plan: ResumePlan, t: (text: string) => string): string {
  const checks = plan.checks.map(([name, status]) => `${name}: ${status}`).join(", ");
  return [
    plan.command,
    `${t("проверки")}: ${checks}`,
    `${t("одобрение человека")}: ${t(plan.approval_required ? "нужно" : "не требуется")}`,
    `${t("дальше")}: ${plan.next_step}`,
  ].join("\n");
}

const utcSeconds = () => new Date().toISOString().replace(/\.\d{3}Z$/, "+00:00");

export function Recovery() {
  const { t, section } = useI18n();
  const [params, setParams] = useSearchParams();
  const opened = params.get("batch") ?? "";
  const [choice, setChoice] = useState<string | null>(null);
  const [skip, setSkip] = useState<string[]>([]);
  const [approver, setApprover] = useState("");
  const [note, setNote] = useState("");
  const [diagnostic, setDiagnostic] = useState("");
  const [request, setRequest] = useState<RunRequest | null>(null);
  const [fixed, setFixed] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const batch = choice ?? opened;
  const screen = useScreen({ type: "recovery.view", params: { batch, skip } }, parseRecoveryView);
  const data = screen.data;
  const isOpen = batch !== "" && batch === opened;
  const view = isOpen ? data?.view : null;
  const actions = view ? [...view.actions, ...(fixed === batch ? [FIX_APPLY] : [])] : [];

  const choose = (next: string) => {
    setChoice(next === opened ? null : next);
    setSkip([]);
    setStatus("");
  };
  const open = () => {
    setParams({ batch });
    setChoice(null);
  };
  const run = (command: string, values: Record<string, string>, reason?: string) =>
    setRequest({ command_id: command, values: { batch, json: "1", ...values }, nonce: Date.now(), reason });

  const onAction = (action: ViewAction) => {
    if (!action.enabled) {
      setStatus(`✖ ${t(action.reason)}`);
      return;
    }
    setStatus("");
    if (action.key === "status") screen.refresh(true);
    else if (action.key === "skip") {
      const id = diagnostic.trim();
      if (id && !skip.includes(id)) setSkip([...skip, id]);
    } else if (action.key === "reload") run(RECOVERY_COMMANDS.reload, {});
    else if (action.key === "fix") run(RECOVERY_COMMANDS.fix, {});
    else if (action.key === "fix-apply") run(RECOVERY_COMMANDS["fix-apply"], {}, t(FIX_APPLY_REASON));
    else if (action.key === "abort") run(RECOVERY_COMMANDS.abort, {}, t(ABORT_REASON));
    else if (action.key === "resume" && data?.resume_plan) {
      const plan = data.resume_plan;
      const approval: Record<string, string> = plan.approval_required
        ? { approved_by: approver.trim(), note: note.trim(), approved_at: utcSeconds() }
        : {};
      run(RECOVERY_COMMANDS.resume, approval, resumeText(plan, t));
    }
  };
  const onJobDone = (job: LocalJob) => {
    if (job.command_id === RECOVERY_COMMANDS.fix && job.phase === "completed" && job.returncode === 0) setFixed(batch);
    if (job.command_id === RECOVERY_COMMANDS["fix-apply"]) setFixed(null);
    screen.refresh(true);
  };

  return (
    <div className="recovery-page work-page" data-section="Orchestration">
      <div className="page-title">
        <div>
          <h1>{t("Восстановление batch")}</h1>
          <p id="recovery-context">
            batch: {batch || t("не выбран")}
          </p>
        </div>
        <div className="actions">
          <button id="recovery-reload-list" className="btn" type="button" onClick={() => screen.refresh(true)}>
            {t("Обновить список")}
          </button>
          <a className="btn" href={href("orchestration")}>
            {section("Orchestration")}
          </a>
        </div>
      </div>

      {screen.error && !data && (
        <p className="command-refusal err" role="alert" data-code={screen.error.code}>
          {t("Отчёт не построен")}: {screen.error.message || screen.error.code}
        </p>
      )}

      {data && (
        <section className="panel recovery-history" id="recovery-history">
          <div className="panel-head">
            <h2>{t("История batch")}</h2>
          </div>
          {data.history_unavailable && <p className="command-refusal err">{t(data.history_unavailable)}</p>}
          <div className="report-list">
            {data.history.map((item) => (
              <button
                key={item.batch_id}
                type="button"
                className={`report-row${item.batch_id === batch ? " on" : ""}`}
                data-batch={item.batch_id}
                aria-pressed={item.batch_id === batch}
                onClick={() => choose(item.batch_id)}
              >
                <span className="report-row-main">{t(item.label)}</span>
              </button>
            ))}
          </div>
          <div className="recovery-entry">
            <span id="recovery-entry">{data.entry ? `${t(data.entry.mark)}  ${t(data.entry.reason)}` : ""}</span>
            <button
              id="recovery-open"
              className="btn primary"
              type="button"
              disabled={!(data.entry?.enabled && data.entry.batch_id === batch) || isOpen}
              onClick={open}
            >
              {t("Открыть recovery")}
            </button>
          </div>
        </section>
      )}

      {view && (
        <section className="panel recovery-view" id="recovery-view">
          <div className="panel-head">
            <h2>{t("Восстановление")}</h2>
            <code>{view.batch}</code>
          </div>
          <RowList rows={view.rows} blockers={view.blockers} notes={view.notes} actions={actions} />
          <ActionBar actions={actions} busy={false} onAction={onAction} />
          <div className="recovery-inputs" id="recovery-inputs">
            <input aria-label="approved-by" placeholder="approved-by" value={approver} onChange={(event) => setApprover(event.target.value)} />
            <input aria-label="note" placeholder="note" value={note} onChange={(event) => setNote(event.target.value)} />
            <input
              aria-label={t("ID диагностики")}
              placeholder={t("ID диагностики")}
              value={diagnostic}
              onChange={(event) => setDiagnostic(event.target.value)}
            />
          </div>
          {status && (
            <p className="command-refusal err" role="status" id="recovery-status">
              {status}
            </p>
          )}
        </section>
      )}

      {isOpen && <CommandPanel section="recovery" confirmAll request={request} onJobDone={onJobDone} />}
    </div>
  );
}
