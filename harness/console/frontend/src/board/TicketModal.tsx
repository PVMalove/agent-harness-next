/* The ticket modal of the #board mockup: labels, story points, issue / PR / branch, the current
   status with its status select (the same moves and refusals as drag and drop) and the Context,
   Acceptance and Prompt tabs; the Agent prompt button copies the prompt from any tab. Ticket text is untrusted: React text only, links only for http(s). */
import { useEffect, useId, useRef, useState } from "react";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { BOARD_COLUMNS } from "../ws/taskBoard";
import type { BoardCard, BoardColumn, TaskBoard } from "../ws/taskBoard";
import { columnLabels, safeUrl } from "./format";
import { StatusNoticeLine } from "./StatusConfirm";
import { refusalCaption } from "./statusChange";
import type { StatusNotice } from "./useStatusChange";

type Tab = "context" | "acceptance" | "prompt";

const pill = (label: string) => (label.includes("p0") ? "violet" : label.includes("p1") ? "blue" : "muted");

export function TicketModal({
  card,
  board,
  onClose,
  onMove,
  notice = null,
  running = false,
}: {
  card: BoardCard;
  board: TaskBoard;
  onClose: () => void;
  onMove?: (card: BoardCard, to: BoardColumn) => void;
  notice?: StatusNotice | null;
  running?: boolean;
}) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const manual = useRef<HTMLPreElement>(null);
  const titleId = useId();
  const [tab, setTab] = useState<Tab>("context");
  const [copied, setCopied] = useState(false);
  const [fallback, setFallback] = useState<string | null>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }, []);

  useEffect(() => {
    const pre = manual.current;
    if (!pre || fallback === null) return;
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(pre);
    selection?.removeAllRanges();
    selection?.addRange(range);
  }, [fallback]);

  const issue = safeUrl(card.url);
  const pr = card.pr ? safeUrl(card.pr.url) : null;
  const branch = card.branch ?? board.spec.branch;
  const labels = columnLabels(t);
  const status = labels[card.column].name;

  const copy = () => {
    const text = card.prompt;
    setCopied(false);
    setFallback(null);
    const failed = () => setFallback(text);
    try {
      void navigator.clipboard.writeText(text).then(() => setCopied(true), failed);
    } catch {
      failed();
    }
  };

  const tabs: [Tab, string][] = [
    ["context", t("Контекст")],
    ["acceptance", t("Acceptance ({count})", { count: card.criteria.length })],
    ["prompt", t("Промпт")],
  ];

  return (
    <dialog
      ref={ref}
      className="board-dialog"
      id="board-ticket"
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="board-modal" id="board-modal">
        <div className="board-modal-head">
          <div>
            <span className="eyebrow">
              {card.id} · {board.spec.title || t("нет данных")}
            </span>
            <h2 id={titleId}>{card.title}</h2>
            <div className="board-modal-labels">
              {card.labels.map((label) => (
                <em key={label} className={`orch-pill ${pill(label)}`}>
                  {label}
                </em>
              ))}
              <em className="orch-pill mint" id="board-sp">
                {card.sp ?? t("нет данных")} SP
              </em>
            </div>
          </div>
          <button className="icon-btn" type="button" aria-label={t("Закрыть")} onClick={onClose}>
            ✕
          </button>
        </div>
        <div className="board-modal-links">
          {issue ? (
            <a href={issue} target="_blank" rel="noopener noreferrer">
              issue {card.id}
            </a>
          ) : (
            <span>
              issue {card.id} · {t("нет данных")}
            </span>
          )}
          {card.pr &&
            (pr ? (
              <a href={pr} target="_blank" rel="noopener noreferrer">
                PR {card.pr.ref}
              </a>
            ) : (
              <span>PR {card.pr.ref}</span>
            ))}
          <span className="branch-inline">
            <b>{branch ?? t("нет данных")}</b>
          </span>
          <span className="board-status-label" id="board-status-label" aria-label={t("Текущий статус")}>
            {status}
          </span>
          {onMove && (
            <select
              id="board-status"
              aria-label={t("Сменить статус")}
              value={card.column}
              disabled={running}
              onChange={(event) => onMove(card, event.target.value as BoardColumn)}
            >
              {BOARD_COLUMNS.map((id) => {
                const move = card.moves.find((item) => item.to === id);
                const refused = move !== undefined && !move.allowed && move.reason !== "same";
                return (
                  <option
                    key={id}
                    value={id}
                    data-allowed={move?.allowed ? "true" : "false"}
                    title={refused ? refusalCaption(t, move.reason, move) : undefined}
                  >
                    {labels[id].name}
                    {refused ? " ✕" : ""}
                  </option>
                );
              })}
            </select>
          )}
        </div>
        <StatusNoticeLine notice={notice} running={running} id="board-modal-notice" />
        <div className="board-modal-tabs" role="tablist">
          {tabs.map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={tab === id ? "on" : ""}
              data-board-tab={id}
              onClick={() => {
                setTab(id);
                setCopied(false);
                setFallback(null);
              }}
            >
              {label}
            </button>
          ))}
          <button className="btn board-agent-prompt" type="button" id="board-copy" onClick={copy}>
            <Icon name="terminal" /> {t("Промпт агента")}
          </button>
        </div>
        {(copied || fallback !== null) && (
          <p className="small muted board-copy-status" role="status">
            {copied ? t("Промпт скопирован") : t("Скопируйте текст вручную")}
          </p>
        )}
        <div className="board-modal-body" role="tabpanel">
          {fallback !== null && (
            <pre className="board-prompt" ref={manual} id="board-copy-text">
              {fallback}
            </pre>
          )}
          {tab === "context" ? (
            <div className="board-context">
              <h4>{t("Блокеры")}</h4>
              {card.blockers.length ? (
                card.blockers.map((blocker) => (
                  <div className="board-blocker" key={blocker.id}>
                    <b>{blocker.id}</b>
                    <span>{blocker.why}</span>
                    <em className={`orch-pill ${blocker.state === "closed" ? "mint" : blocker.state === "open" ? "lavender" : "muted"}`}>
                      {blocker.state === "unknown" ? t("нет данных") : blocker.state}
                    </em>
                  </div>
                ))
              ) : (
                <p className="muted">{t("Блокеров нет.")}</p>
              )}
              <h4>Discovery Context</h4>
              {card.files.length ? (
                card.files.map((file) => (
                  <div className="board-file" key={file.path}>
                    <code>{file.path}</code>
                    <span>{file.why}</span>
                  </div>
                ))
              ) : (
                <p className="muted">{t("Файлы не указаны.")}</p>
              )}
            </div>
          ) : tab === "acceptance" ? (
            <ol className="board-acceptance">
              {card.criteria.map((criterion, index) => (
                <li key={index}>{criterion}</li>
              ))}
            </ol>
          ) : (
            <pre className="board-prompt">{card.prompt}</pre>
          )}
        </div>
      </div>
    </dialog>
  );
}
