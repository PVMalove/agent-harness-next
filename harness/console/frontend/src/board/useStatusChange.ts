/* A ticket status change of the Task Board: a refused move shows its reason at once, an allowed one
   waits for the confirmation, then runs `board-status` as the server's mutating job and follows it
   to its result. After the command answers (changed, refused or a write error) the board is asked
   again with force, keeping the shown board until the new snapshot: the snapshot that offered the
   move is no longer current. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { useConsole } from "../useConsole";
import type { BoardCard, BoardColumn } from "../ws/taskBoard";
import { columnLabels } from "./format";
import { STATUS_COMMAND, busyJob, moveOf, parseStatusResult, refusalCaption } from "./statusChange";

export interface StatusNotice {
  kind: "ok" | "err";
  /** The refusal reason (or `changed`), kept for the page and its tests. */
  reason: string;
  text: string;
}

export interface PendingMove {
  card: BoardCard;
  to: BoardColumn;
}

export interface StatusChange {
  /** The allowed move waiting for its confirmation. */
  pending: PendingMove | null;
  running: boolean;
  notice: StatusNotice | null;
  request(card: BoardCard, to: BoardColumn): void;
  confirm(): void;
  cancel(): void;
}

export function useStatusChange(spec: string, reload: () => void): StatusChange {
  const { client } = useConsole();
  const { t } = useI18n();
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState<StatusNotice | null>(null);
  // The move under way and its job id; "start" until the start reply names the job.
  const active = useRef<{ move: PendingMove; job: string } | null>(null);
  const words = useRef({ t, reload });
  words.current = { t, reload };

  const say = useCallback((move: PendingMove, kind: StatusNotice["kind"], reason: string, text: string) => {
    const name = columnLabels(words.current.t)[move.to].name;
    setNotice({
      kind,
      reason,
      text:
        kind === "ok"
          ? words.current.t("{ticket}: статус обновлён", { ticket: move.card.id })
          : words.current.t("{ticket} → «{column}»: {reason}", { ticket: move.card.id, column: name, reason: text }),
    });
  }, []);

  useEffect(
    () =>
      client.subscribeJobs((event) => {
        const current = active.current;
        if (!current) return;
        const { t: tr } = words.current;
        if (event.type === "job-error" && event.request === "job.start" && current.job === "start") {
          active.current = null;
          setRunning(false);
          const job = event.code === "busy" ? busyJob(event.message, event.jobId) : "";
          const reason = event.code === "busy" ? "busy" : "write_failed";
          say(current.move, "err", reason, refusalCaption(tr, reason, { job }));
          return;
        }
        if (event.type !== "job" || event.job.command_id !== STATUS_COMMAND) return;
        if (current.job === "start") current.job = event.job.id;
        if (event.job.id !== current.job || !event.job.done) return;
        active.current = null;
        setRunning(false);
        const result = parseStatusResult(event.job.output);
        if (result?.result === "changed") say(current.move, "ok", "changed", "");
        else {
          const reason = result?.reason ?? "write_failed";
          say(current.move, "err", reason, refusalCaption(tr, reason, result ?? {}));
        }
        words.current.reload();
      }),
    [client, say],
  );

  const request = useCallback(
    (card: BoardCard, to: BoardColumn) => {
      const move = moveOf(card, to);
      if (!move || move.reason === "same" || active.current) return;
      setNotice(null);
      if (move.allowed) {
        setPending({ card, to });
        return;
      }
      say({ card, to }, "err", move.reason ?? "", refusalCaption(words.current.t, move.reason, move));
    },
    [say],
  );

  const confirm = useCallback(() => {
    if (!pending) return;
    setPending(null);
    active.current = { move: pending, job: "start" };
    setRunning(true);
    const sent = client.startJob({
      command_id: STATUS_COMMAND,
      values: { spec, ticket: pending.card.id, to: pending.to },
      confirmed: true,
    });
    if (!sent) {
      active.current = null;
      setRunning(false);
      say(pending, "err", "write_failed", refusalCaption(words.current.t, "write_failed"));
    }
  }, [client, pending, say, spec]);

  const cancel = useCallback(() => setPending(null), []);

  return { pending, running, notice, request, confirm, cancel };
}
