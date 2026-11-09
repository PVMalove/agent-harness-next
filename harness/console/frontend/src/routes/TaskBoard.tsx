/* Task Board: the #913 snapshot laid out as the mockup's #board. One board per spec; the columns,
   the card order, the prompt and the allowed moves are the server's. A card moves by drag and drop
   or by the status select of its modal, after a confirmation, through the server's mutating job. */
import { useMemo, useState } from "react";
import { BoardBanner, BoardColumns, BoardKpis, BoardStatePanel, BoardToolbar } from "../board/BoardViews";
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
  return (
    <div className="board-specbar">
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
  specs: BoardSpecs;
  spec: string;
  onChoose: (spec: string) => void;
  onRefreshSpecs: () => void;
}) {
  const { board: screen, refreshing, refresh } = useBoard(spec);
  const [filters, setFilters] = useState<BoardFilters>(NO_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);
  const board = screen.data;
  const open = board?.tickets.find((card) => card.id === selected) ?? null;
  const refreshAll = () => {
    onRefreshSpecs();
    refresh();
  };
  const change = useStatusChange(spec, refresh);
  const unavailable = board?.stale && board.tickets.length === 0;
  return (
    <>
      <Title board={board} onRefresh={refreshAll} />
      <SpecBar specs={specs} spec={spec} board={board} onChoose={onChoose} />
      <ScreenRefusal screen={screen} />
      <StatusNoticeLine notice={change.notice} running={change.running} />
      {refreshing ? (
        <BoardStatePanel kind="loading" onRefresh={refreshAll} />
      ) : (
        board && (
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
              </>
            )}
          </>
        )
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
      {specs && spec ? (
        <SpecBoard key={spec} specs={specs} spec={spec} onChoose={choose} onRefreshSpecs={refreshSpecs} />
      ) : (
        <>
          <Title board={null} onRefresh={refreshSpecs} />
          <ScreenRefusal screen={screen} />
          {specs?.stale && <BoardBanner stale={specs.stale} age={null} />}
          {!specs ? (
            screen.loading && <BoardStatePanel kind="loading" onRefresh={refreshSpecs} />
          ) : (
            <BoardStatePanel kind={specs.stale ? "nosnapshot" : "nospecs"} onRefresh={refreshSpecs} />
          )}
        </>
      )}
    </div>
  );
}
