/* The status-change confirmation of the #board mockup (#board-confirm) and the line that words the
   last move: a refusal with its reason, or the updated status. Ticket text is plain React text. */
import { useEffect, useId, useRef } from "react";
import { useI18n } from "../i18n";
import type { PendingMove, StatusNotice } from "./useStatusChange";
import { columnLabels } from "./format";

/** Where the label changes, as the confirmation names the tracker. */
function trackerName(t: (key: string) => string, tracker: string): string {
  if (tracker === "github") return "GitHub";
  if (tracker === "gitlab") return "GitLab";
  return t("локальном трекере");
}

export function StatusConfirm({
  move,
  tracker,
  onConfirm,
  onClose,
}: {
  move: PendingMove;
  tracker: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }, []);

  const name = columnLabels(t)[move.to].name;
  return (
    <dialog
      ref={ref}
      className="board-dialog board-confirm"
      id="board-confirm"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div id="board-confirm-body">
        <div className="board-modal-head">
          <div>
            <span className="eyebrow">{t("СМЕНА СТАТУСА")}</span>
            <h2 id={titleId}>
              {move.card.id} → {name}
            </h2>
            <p>{move.card.title}</p>
          </div>
          <button className="icon-btn" type="button" aria-label={t("Закрыть")} onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="board-confirm-diff">
          <s>{move.card.column}</s>
          <b>→</b>
          <ins>{move.to}</ins>
        </div>
        <p className="board-confirm-note">
          {t("Сервер запустит смену метки в {tracker} как мутирующий job и обновит доску.", {
            tracker: trackerName(t, tracker),
          })}
        </p>
        <div className="actions">
          <button className="btn" type="button" onClick={onClose}>
            {t("Отмена")}
          </button>
          <button className="btn primary" type="button" id="board-confirm-ok" onClick={onConfirm}>
            {t("Сменить статус")}
          </button>
        </div>
      </div>
    </dialog>
  );
}

export function StatusNoticeLine({
  notice,
  running,
  id = "board-move-notice",
}: {
  notice: StatusNotice | null;
  running: boolean;
  id?: string;
}) {
  const { t } = useI18n();
  if (running) {
    return (
      <p className="small muted board-move-notice" role="status" id={id} data-reason="running">
        {t("Смена статуса…")}
      </p>
    );
  }
  if (!notice) return null;
  return (
    <p
      className={notice.kind === "err" ? "command-refusal err board-move-notice" : "small muted board-move-notice"}
      role={notice.kind === "err" ? "alert" : "status"}
      id={id}
      data-reason={notice.reason}
    >
      {notice.text}
    </p>
  );
}
