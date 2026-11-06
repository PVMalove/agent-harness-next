/* The explicit confirmation of a run or a cancel: the reason of the command's class and, when the
   server asks for one, the exact word to type. The server checks both again. */
import { useEffect, useId, useRef, useState } from "react";
import { useI18n } from "../i18n";

export interface ConfirmRequest {
  title: string;
  /** The command id shown as code. */
  command: string;
  reason: string;
  /** The word the server expects in `confirmation`; null when a flag is enough. */
  typed: string | null;
  action: string;
  context?: string;
}

export function ConfirmDialog({
  request,
  onConfirm,
  onClose,
}: {
  request: ConfirmRequest;
  onConfirm: (confirmation: string | undefined) => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [word, setWord] = useState("");

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }, []);

  const ready = request.typed === null || word === request.typed;
  return (
    <dialog
      ref={ref}
      className="board-dialog board-confirm command-confirm"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <form
        className="command-confirm-body"
        onSubmit={(event) => {
          event.preventDefault();
          if (ready) onConfirm(request.typed === null ? undefined : word);
        }}
      >
        <h2 id={titleId}>{request.title}</h2>
        <p>
          <code>{request.command}</code>
        </p>
        <p className="board-confirm-note">{request.reason}</p>
        {request.context && <pre className="decision-confirm-context">{request.context}</pre>}
        {request.typed !== null && (
          <label className="command-confirm-typed">
            {t("Введите {word}, чтобы подтвердить", { word: request.typed })}
            <input
              value={word}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => setWord(event.target.value)}
            />
          </label>
        )}
        <div className="command-confirm-actions">
          <button className="btn" type="button" onClick={onClose}>
            {t("Отмена")}
          </button>
          <button className="btn primary" type="submit" disabled={!ready}>
            {request.action}
          </button>
        </div>
      </form>
    </dialog>
  );
}
