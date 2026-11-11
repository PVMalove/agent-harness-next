/* Task Board: the #913 snapshot laid out as the mockup's #board. One board per spec; the columns,
   the card order, the prompt and the allowed moves are the server's. A card moves by drag and drop
   or by the status select of its modal, after a confirmation, through the server's mutating job.
   The frame of the five columns is drawn at once; the mascot jumps over it while a snapshot loads. */
import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  BoardBanner,
  BoardColumns,
  BoardFrame,
  BoardKpis,
  BoardStatePanel,
  BoardToolbar,
  BoardUpdating,
  specNumber,
} from "../board/BoardViews";
import { NO_FILTERS } from "../board/format";
import { StatusConfirm, StatusNoticeLine } from "../board/StatusConfirm";
import { TicketModal } from "../board/TicketModal";
import type { BoardFilters } from "../board/format";
import { useStatusChange } from "../board/useStatusChange";
import { useBoard, useBoardSpecs } from "../board/useTaskBoard";
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import type { Screen } from "../screens/useScreen";
import type { BoardSpecs, TaskBoard as Board } from "../ws/taskBoard";

const clock = (at: Date) => at.toTimeString().slice(0, 8);

function Title({ board, onRefresh }: { board: Board | null; onRefresh: () => void }) {
  const { t, section } = useI18n();
  const at = useMemo(
    () => (board && board.age_seconds !== null ? new Date(Date.now() - board.age_seconds * 1000) : null),
    [board],
  );
  return (
    <div className="page-title board-title">
      <div>
        <h1>{section("Доска задач")}</h1>
        <p>{t("Одна доска на спеку. Колонки, блокеры и переносы соответствуют трекеру.")}</p>
        {board && (
          <div className="home-facts" id="board-facts">
            <span>{board.spec.title || t("нет данных")}</span>
            <span>{board.spec.branch ?? t("нет данных")}</span>
            <span>{t("{count} задач", { count: board.kpis.total })}</span>
            <span id="board-snapshot">{at ? clock(at) : t("нет данных")}</span>
          </div>
        )}
      </div>
      <div className="actions">
        <button className="btn" type="button" id="board-refresh" onClick={onRefresh}>
          <Icon name="refresh" /> {t("Обновить")}
        </button>
        <a className="btn" href={href("orchestration")}>
          <Icon name="orchestration" /> {section("Orchestration")}
        </a>
      </div>
    </div>
  );
}

function SpecBar({
  specs,
  spec,
  board,
  onChoose,
}: {
  specs: BoardSpecs;
  spec: string;
  board: Board | null;
  onChoose: (spec: string) => void;
}) {
  const { t } = useI18n();
  const [number, setNumber] = useState("");
  // The number asked with Enter: typing "1066" never opens #1, #10 and #106 on the way.
  const [asked, setAsked] = useState<string | null>(null);
  const wanted = asked === null ? null : specNumber(asked);
  const missing = asked !== null && asked.trim() !== "" && (wanted === null || !specs.specs.some((item) => item.n === wanted));
  const find = (event: FormEvent) => {
    event.preventDefault();
    setAsked(number);
    const n = specNumber(number);
    const found = n === null ? undefined : specs.specs.find((item) => item.n === n);
    if (found && found.id !== spec) onChoose(found.id);
  };
  return (
    <div className="board-specbar">
      <form className="board-search board-spec-search" role="search" onSubmit={find}>
        <Icon name="search" />
        <input
          id="board-spec-number"
          type="search"
          inputMode="numeric"
          value={number}
          placeholder={t("Номер спеки")}
          aria-label={t("Найти спеку по номеру")}
          onChange={(event) => {
            setNumber(event.target.value);
            setAsked(null);
          }}
        />
      </form>
      {missing && (
        <span className="board-spec-missing" role="status">
          {t("Спека #{n} не найдена", { n: (asked ?? "").trim().replace(/^#/, "") })}
        </span>
      )}
      <label>
        {t("Спека")}
        <select id="board-spec" aria-label={t("Выбрать спеку")} value={spec} onChange={(event) => onChoose(event.target.value)}>
          {specs.specs.map((item) => (
            <option key={item.id} value={item.id}>
              {item.n === null ? item.id : `#${item.n}`} · {item.title} —{" "}
              {item.tickets_total === null ? t("нет данных") : t("{count} задач", { count: item.tickets_total })}
            </option>
          ))}
        </select>
      </label>
      {board && (
        <span className="board-spec-meta">
          {t("{total} задач · {open} открыто", { total: board.kpis.total, open: board.kpis.open })}
        </span>
      )}
    </div>
  );
}

function ScreenRefusal({ screen }: { screen: Screen<unknown> }) {
  const { t } = useI18n();
  if (!screen.error || screen.data) return null;
  return (
    <p className="command-refusal err" role="alert" data-code={screen.error.code}>
      {t("Доска не построена")}: {screen.error.message || screen.error.code}
    </p>
  );
}

function SpecBoard({
  specs,
  spec,
  onChoose,
  onRefreshSpecs,
}: {
  /** Null while the specs load: the remembered spec's board is read in parallel with them. */
  specs: BoardSpecs | null;
  spec: string;
  onChoose: (spec: string) => void;
  onRefreshSpecs: () => void;
}) {
  const { board: screen, refreshing, updating, refresh, reload } = useBoard(spec);
  const [filters, setFilters] = useState<BoardFilters>(NO_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const board = screen.data;
  const open = board?.tickets.find((card) => card.id === selected) ?? null;
  const refreshAll = () => {
    onRefreshSpecs();
    refresh();
  };
  const change = useStatusChange(spec, reload);
  const unavailable = board?.stale && board.tickets.length === 0;
  return (
    <>
      <Title board={board} onRefresh={refreshAll} />
      {specs && <SpecBar specs={specs} spec={spec} board={board} onChoose={onChoose} />}
      <ScreenRefusal screen={screen} />
      <StatusNoticeLine notice={change.notice} running={change.running} />
      {refreshing || !board ? (
        <>
          <BoardFrame />
          {screen.loading && <BoardUpdating />}
        </>
      ) : (
        <>
          {board.stale && <BoardBanner stale={board.stale} age={unavailable ? null : board.age_seconds} />}
          {unavailable ? (
            <BoardStatePanel kind="nosnapshot" onRefresh={refreshAll} />
          ) : board.tickets.length === 0 ? (
            <BoardStatePanel kind="empty" onRefresh={refreshAll} />
          ) : (
            <>
              <BoardKpis board={board} />
              <BoardToolbar filters={filters} onChange={setFilters} />
              <BoardColumns
                board={board}
                filters={filters}
                onOpen={(card) => setSelected(card.id)}
                onMove={change.request}
              />
              {(change.running || updating) && <BoardUpdating />}
            </>
          )}
        </>
      )}
      {board && open && (
        <TicketModal
          key={open.id}
          card={open}
          board={board}
          onClose={() => setSelected(null)}
          onMove={change.request}
          notice={change.notice}
          running={change.running}
        />
      )}
      {board && change.pending && (
        <StatusConfirm
          move={change.pending}
          tracker={board.tracker}
          onClose={change.cancel}
          onConfirm={() => {
            change.confirm();
            setSelected(null);
          }}
        />
      )}
    </>
  );
}

export function TaskBoard() {
  const { specs: screen, spec, choose } = useBoardSpecs();
  const specs = screen.data;
  const refreshSpecs = () => screen.refresh(true);
  return (
    <div className="board-page" data-section="Доска задач">
      {spec ? (
        <SpecBoard key={spec} specs={specs} spec={spec} onChoose={choose} onRefreshSpecs={refreshSpecs} />
      ) : (
        <>
          <Title board={null} onRefresh={refreshSpecs} />
          <ScreenRefusal screen={screen} />
          {specs?.stale && <BoardBanner stale={specs.stale} age={null} />}
          {!specs ? (
            <>
              <BoardFrame />
              {screen.loading && <BoardUpdating />}
            </>
          ) : (
            <BoardStatePanel kind={specs.stale ? "nosnapshot" : "nospecs"} onRefresh={refreshSpecs} />
          )}
        </>
      )}
    </div>
  );
}
