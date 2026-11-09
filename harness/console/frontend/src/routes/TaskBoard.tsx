/* Task Board: the #913 snapshot laid out as the mockup's #board. One board per spec; the columns,
   the card order and the prompt are the server's. Read-only: moving a ticket belongs to #915. */
import { useMemo, useState } from "react";
import { BoardBanner, BoardColumns, BoardKpis, BoardStatePanel, BoardToolbar } from "../board/BoardViews";
import { NO_FILTERS } from "../board/format";
import type { BoardFilters } from "../board/format";
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
  const board = screen.data;
  const refreshAll = () => {
    onRefreshSpecs();
    refresh();
  };
  const unavailable = board?.stale && board.tickets.length === 0;
  return (
    <>
      <Title board={board} onRefresh={refreshAll} />
      <SpecBar specs={specs} spec={spec} board={board} onChoose={onChoose} />
      <ScreenRefusal screen={screen} />
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
                <BoardColumns board={board} filters={filters} />
              </>
            )}
          </>
        )
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
