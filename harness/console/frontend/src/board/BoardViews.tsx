/* The blocks of the #board mockup over the snapshot: KPIs, the tracker banner, the filters, five
   columns with counters of the visible cards and the cards. Ticket text is untrusted: React text only. */
import { Icon } from "../icons";
import { useI18n } from "../i18n";
import { href } from "../navigation";
import { BOARD_COLUMNS } from "../ws/taskBoard";
import type { BoardCard, BoardStale, TaskBoard } from "../ws/taskBoard";
import { ageText, columnLabels, firstLine, priorityLabel, safeUrl, trackerReason, visible } from "./format";
import type { BoardFilters } from "./format";

export function BoardKpis({ board }: { board: TaskBoard }) {
  const { t } = useI18n();
  const { kpis } = board;
  return (
    <div className="board-kpis" id="board-kpis">
      <div>
        <span>{t("Открыто")}</span>
        <b className="cyan">{kpis.open}</b>
        <small>{t("из {total} задач", { total: kpis.total })}</small>
      </div>
      <div>
        <span>{t("С блокерами")}</span>
        <b className="lavender">{kpis.with_open_blockers}</b>
        <small>{t("нельзя перенести")}</small>
      </div>
      <div>
        <span>{t("Активный batch")}</span>
        <b className="violet">{board.ledger === "ok" ? kpis.active_batch : t("нет данных")}</b>
        <small>{t("занято")}</small>
      </div>
      <div>
        <span>{t("Снимок")}</span>
        <b className="blue" id="board-age">
          {ageText(t, board.age_seconds)}
        </b>
        <small>{board.stale ? t("трекер недоступен") : t("обновлено")}</small>
      </div>
    </div>
  );
}

export function BoardBanner({ stale, age }: { stale: BoardStale; age: number | null }) {
  const { t } = useI18n();
  return (
    <div className="board-banner down" role="alert" data-reason={stale.reason}>
      <Icon name="warning" />
      <span>
        <b>{t("Трекер недоступен.")}</b> {trackerReason(t, stale.reason)}
        {stale.message ? `: ${stale.message}` : ""}.{" "}
        {age === null ? t("Снимка доски ещё нет.") : t("Показан снимок {age} назад.", { age: ageText(t, age) })}
      </span>
    </div>
  );
}

export function BoardToolbar({ filters, onChange }: { filters: BoardFilters; onChange: (next: BoardFilters) => void }) {
  const { t } = useI18n();
  return (
    <div className="board-toolbar">
      <label className="board-search">
        <input
          id="board-search"
          type="search"
          value={filters.query}
          placeholder={t("Найти задачу")}
          aria-label={t("Поиск задач")}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
        />
      </label>
      <select
        id="board-priority"
        aria-label={t("Приоритет")}
        value={filters.priority}
        onChange={(event) => onChange({ ...filters, priority: event.target.value })}
      >
        <option value="all">{t("Все приоритеты")}</option>
        <option value="priority::p0">P0</option>
        <option value="priority::p1">P1</option>
        <option value="priority::p2">P2</option>
      </select>
      <label className="board-free">
        <input
          id="board-free"
          type="checkbox"
          checked={filters.free}
          onChange={(event) => onChange({ ...filters, free: event.target.checked })}
        />{" "}
        {t("Без блокеров")}
      </label>
      <button className="btn" type="button" id="board-reset" onClick={() => onChange({ query: "", priority: "all", free: false })}>
        {t("Сбросить")}
      </button>
    </div>
  );
}

function Card({ card, onOpen }: { card: BoardCard; onOpen?: (card: BoardCard) => void }) {
  const { t } = useI18n();
  const prio = priorityLabel(card);
  const link = safeUrl(card.url);
  const what = firstLine(card.what);
  return (
    <article
      className="board-card"
      tabIndex={0}
      data-board-ticket={card.id}
      aria-label={`${card.id} ${card.title}`}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest("a")) return;
        onOpen?.(card);
      }}
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        onOpen?.(card);
      }}
    >
      <div className="board-card-meta">
        <span>{card.id}</span>
        {prio && <em className={`board-prio ${prio.toLowerCase()}`}>{prio}</em>}
      </div>
      <h3>{card.title}</h3>
      <p>{what || t("нет данных")}</p>
      <div className="board-card-chips">
        <span className="board-chip command">{card.command}</span>
        {card.dispatch && <span className="board-chip role">{t("dispatch: {role}", { role: card.dispatch })}</span>}
        {!card.closed &&
          (card.open_blockers > 0 ? (
            <span className="board-chip blocker">{t("блокеров: {count}", { count: card.open_blockers })}</span>
          ) : (
            <span className="board-chip free">{t("без блокеров")}</span>
          ))}
      </div>
      <div className="board-card-foot">
        <span>{t("критериев: {count}", { count: card.criteria.length })}</span>
        {link ? (
          <a href={link} target="_blank" rel="noopener noreferrer">
            {t("Открыть")}
          </a>
        ) : (
          <span>{t("нет данных")}</span>
        )}
      </div>
    </article>
  );
}

export function BoardColumns({
  board,
  filters,
  onOpen,
}: {
  board: TaskBoard;
  filters: BoardFilters;
  onOpen?: (card: BoardCard) => void;
}) {
  const { t } = useI18n();
  const labels = columnLabels(t);
  const shown = board.tickets.filter((card) => visible(card, filters));
  return (
    <>
      <div className="board-count" id="board-count">
        {t("{shown} из {total}", { shown: shown.length, total: board.tickets.length })}
      </div>
      <div id="board-columns">
        <div className="board-columns">
          {BOARD_COLUMNS.map((id) => {
            const items = shown.filter((card) => card.column === id);
            return (
              <section className="board-col" data-board-col={id} key={id}>
                <header>
                  <div>
                    <b>{labels[id].name}</b>
                    <small>{labels[id].hint}</small>
                  </div>
                  <span className="board-col-count">{items.length}</span>
                </header>
                <div className="board-cards">
                  {items.length ? (
                    items.map((card) => <Card key={card.id} card={card} onOpen={onOpen} />)
                  ) : (
                    <div className="board-empty">{t("пусто")}</div>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </>
  );
}

export type BoardStateKind = "nospecs" | "empty" | "loading" | "nosnapshot";

export function BoardStatePanel({ kind, onRefresh }: { kind: BoardStateKind; onRefresh: () => void }) {
  const { t, section } = useI18n();
  const [title, text] =
    kind === "nospecs"
      ? [t("Спек пока нет"), t("Спека появляется после /to-spec и /to-tickets. Доска покажет её после обновления.")]
      : kind === "loading"
        ? [
            t("Обновление доски"),
            t("Читаем трекер и статусы. Показан последний подтверждённый снимок; карточки временно недоступны."),
          ]
        : kind === "nosnapshot"
          ? [t("Снимка доски ещё нет"), t("Доска появится, когда трекер снова ответит.")]
          : [t("На доске нет задач"), t("В выбранной спеке пока нет тикетов. Разбейте спеку через /to-tickets.")];
  return (
    <section className="panel board-state" data-board-state={kind}>
      <div className="board-state-icon">
        <Icon name={kind === "loading" ? "refresh" : "board"} />
      </div>
      <span className="eyebrow">{kind === "loading" ? t("ДОСКА · LOADING") : t("ДОСКА · EMPTY")}</span>
      <h2>{title}</h2>
      <p>{text}</p>
      <div className="actions">
        <button className="btn primary" type="button" onClick={onRefresh}>
          <Icon name="refresh" /> {t("Обновить")}
        </button>
        <a className="btn" href={href("help")}>
          <Icon name="help" /> {section("Help")}
        </a>
      </div>
    </section>
  );
}
