import { describe, expect, test } from "vitest";
import { screenKey } from "../../harness/console/frontend/src/ws/client";
import { BOARD_COLUMNS, parseBoard, parseSpecs } from "../../harness/console/frontend/src/ws/taskBoard";
import SPECS from "./fixtures/task-board-specs.json";
import STALE from "./fixtures/task-board-stale.json";
import BOARD from "./fixtures/task-board.json";

const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

describe("the task-board read models", () => {
  test("accept the snapshots the server builds", () => {
    expect(parseSpecs(SPECS)?.specs.map((spec) => spec.id)).toEqual(["#501", "#502"]);
    const board = parseBoard(BOARD);
    expect(board?.columns.map((column) => column.id)).toEqual([...BOARD_COLUMNS]);
    expect(board?.tickets).toHaveLength(7);
    const stale = parseBoard(STALE);
    expect(stale?.stale).toEqual({ reason: "auth", message: "tracker login required" });
    expect(stale?.age_seconds).toBe(95);
  });

  test("reject a payload with a missing key or a wrong type", () => {
    const noSpecs = copy(SPECS) as Record<string, unknown>;
    delete noSpecs.specs;
    expect(parseSpecs(noSpecs)).toBeNull();
    const badTotal = copy(SPECS);
    (badTotal.specs[0] as Record<string, unknown>).tickets_total = "7";
    expect(parseSpecs(badTotal)).toBeNull();
    expect(parseSpecs([])).toBeNull();

    const noKpis = copy(BOARD) as Record<string, unknown>;
    delete noKpis.kpis;
    expect(parseBoard(noKpis)).toBeNull();
    const badColumn = copy(BOARD);
    (badColumn.tickets[0] as Record<string, unknown>).column = "archive";
    expect(parseBoard(badColumn)).toBeNull();
    const badBlocker = copy(BOARD);
    (badBlocker.tickets[0]!.blockers[0] as Record<string, unknown>).state = "maybe";
    expect(parseBoard(badBlocker)).toBeNull();
    const reordered = copy(BOARD);
    reordered.columns.reverse();
    expect(parseBoard(reordered)).toBeNull();
    const badStale = copy(BOARD) as Record<string, unknown>;
    badStale.stale = { reason: "auth" };
    expect(parseBoard(badStale)).toBeNull();
    const badLedger = copy(BOARD) as Record<string, unknown>;
    badLedger.ledger = "maybe";
    expect(parseBoard(badLedger)).toBeNull();
  });

  test("a board request is keyed by its spec", () => {
    const one = screenKey({ type: "task_board.snapshot", params: { spec: "#501" } });
    const other = screenKey({ type: "task_board.snapshot", params: { spec: "#502" } });
    expect(one).not.toBe(other);
    expect(screenKey({ type: "task_board.specs" })).toBe("task_board.specs");
  });
});
