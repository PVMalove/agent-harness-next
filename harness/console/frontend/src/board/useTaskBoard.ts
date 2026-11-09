/* The Task Board data: the open specs, the selected spec remembered in this browser, and the board
   of that spec. A ledger event naming a ticket or a batch of the open board asks for the board with
   force; without events the board is asked again when its snapshot outlives the server's TTL. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useScreen } from "../screens/useScreen";
import type { Screen } from "../screens/useScreen";
import { useConsole } from "../useConsole";
import { BOARD_TTL_MS, parseBoard, parseSpecs } from "../ws/taskBoard";
import type { BoardSpecs, TaskBoard } from "../ws/taskBoard";
import { SPEC_KEY } from "./format";

/** A TTL re-ask never comes sooner than this, so a snapshot at the TTL edge cannot spin. */
const MIN_REASK_MS = 1000;

const readSpec = (): string | null => {
  try {
    return window.localStorage.getItem(SPEC_KEY);
  } catch {
    return null;
  }
};

const storeSpec = (spec: string) => {
  try {
    window.localStorage.setItem(SPEC_KEY, spec);
  } catch {
    // Storage may be blocked; the choice then lasts for this page only.
  }
};

export interface BoardSpecsState {
  specs: Screen<BoardSpecs>;
  /** The selected spec: the remembered one while the tracker lists it, else the first. */
  spec: string | null;
  choose(spec: string): void;
}

export function useBoardSpecs(): BoardSpecsState {
  const specs = useScreen({ type: "task_board.specs" }, parseSpecs);
  const [chosen, setChosen] = useState<string | null>(readSpec);
  const list = specs.data?.specs ?? [];
  const spec = list.find((item) => item.id === chosen)?.id ?? list[0]?.id ?? null;
  const choose = useCallback((next: string) => {
    storeSpec(next);
    setChosen(next);
  }, []);
  return { specs, spec, choose };
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

/** Whether a ledger event names a ticket or a batch of the board's cards. */
export function touchesBoard(board: TaskBoard, events: readonly unknown[]): boolean {
  const tickets = new Set(board.tickets.map((card) => card.id));
  const batches = new Set(board.tickets.flatMap((card) => (card.batch === null ? [] : [card.batch])));
  return events.some(
    (event) =>
      isObject(event) &&
      ((typeof event.ticket === "string" && tickets.has(event.ticket)) ||
        (typeof event.batch_id === "string" && batches.has(event.batch_id))),
  );
}

export interface BoardState {
  board: Screen<TaskBoard>;
  /** The refreshing panel shows on the first read and after a manual refresh only. */
  refreshing: boolean;
  refresh(): void;
}

export function useBoard(spec: string): BoardState {
  const { client } = useConsole();
  const board = useScreen({ type: "task_board.snapshot", params: { spec } }, parseBoard);
  const [manual, setManual] = useState(false);
  const data = useRef(board.data);
  data.current = board.data;
  const { refresh: ask, loading } = board;

  useEffect(
    () =>
      client.subscribe((event) => {
        if (event.type !== "events" || !data.current) return;
        if (touchesBoard(data.current, event.events)) ask(true);
      }),
    [client, ask],
  );

  useEffect(() => {
    if (!board.data || loading) return;
    const age = (board.data.age_seconds ?? 0) * 1000;
    // A stale board is the server's failure answer, held for one TTL from the failure.
    const delay = board.data.stale ? BOARD_TTL_MS : Math.max(MIN_REASK_MS, BOARD_TTL_MS - age);
    const handle = window.setTimeout(() => ask(false), delay);
    return () => window.clearTimeout(handle);
  }, [board.data, loading, ask]);

  useEffect(() => {
    if (!loading) setManual(false);
  }, [loading]);

  const refresh = useCallback(() => {
    setManual(true);
    ask(true);
  }, [ask]);

  return { board, refreshing: loading && (board.data === null || manual), refresh };
}
