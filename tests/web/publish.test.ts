import { act, fireEvent, render, screen } from "@testing-library/react";
import { createElement } from "react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider, stateLabel } from "../../harness/console/frontend/src/i18n";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import REPORTS from "./fixtures/reports.json";
import { blockingReasons, preflightRows } from "../../harness/console/frontend/src/reports/preflight";
import { defaultBatch } from "../../harness/console/frontend/src/routes/Publish";
import type { PublishEntry } from "../../harness/console/frontend/src/ws/ledger";

const entry = (batch_id: string, reviewed: boolean): PublishEntry => ({
  batch_id,
  ticket: "#1",
  state: "open",
  branch: "feature/x",
  candidate: null,
  target: null,
  integration_ref: null,
  head: null,
  head_matches: null,
  target_in_history: null,
  refusals: [],
  review: reviewed ? { dispatch_id: `d-${batch_id}`, outcome: "completed", has_blockers: false } : null,
  qa: null,
  pr_url: "",
  pr_state: "",
  verdict: "unknown",
});

describe("the Publication batch selector", () => {
  test("defaults to the newest reviewed batch; entries come newest first", () => {
    expect(defaultBatch([entry("b-new", true), entry("b-old", true)])).toBe("b-new");
    expect(defaultBatch([entry("b-new", false), entry("b-mid", true), entry("b-old", true)])).toBe("b-mid");
  });

  test("falls back to the newest batch without a review report", () => {
    expect(defaultBatch([entry("b-new", false), entry("b-old", false)])).toBe("b-new");
    expect(defaultBatch([])).toBeNull();
  });
});

describe("the Publication preflight rows", () => {
  test("name the review and QA outcomes in the UI language, never the raw value", () => {
    const reviewed = { ...entry("b-1", true), qa: { dispatch_id: "d-qa", outcome: "failed", has_blockers: true } };
    const details = preflightRows(reviewed, (state) => stateLabel("ru", state)).map((row) => row.detail);
    expect(details).toContain("d-qa · Сбой");
    expect(details).toContain("d-b-1 · Завершено");
    expect(details.join(" ")).not.toMatch(/completed|failed/);
    const english = preflightRows(reviewed, (state) => stateLabel("en", state)).map((row) => row.detail);
    expect(english).toContain("d-b-1 · Completed");
  });
});

test("a ready verdict with every check ok leaves no reason; a refusal comes first", () => {
  const ok = { dispatch_id: "d", outcome: "completed", has_blockers: false };
  const ready: PublishEntry = { ...entry("b", true), qa: ok, head_matches: true, target_in_history: true, verdict: "ready" };
  expect(blockingReasons(ready)).toEqual([]);
  expect(blockingReasons({ ...ready, verdict: "blocked", refusals: ["tree differs"] })).toEqual(["tree differs", "Release Gate"]);
});

describe("the Publication page in the mockup's order", () => {
  beforeEach(() => FakeSocket.reset());

  function renderPublish() {
    window.location.hash = "#/publish";
    const client = createConsoleClient({ url: "ws://127.0.0.1:1/ws", WebSocket: FakeSocket, timers: new ManualClock(), probeHealth: async () => false });
    render(createElement(LanguageProvider, null, createElement(App, { client })));
    const socket = FakeSocket.last;
    act(() => socket.open());
    const body = socket.sent.find((sent) => sent.type === "reports.snapshot")!;
    act(() => socket.reply(screenPage(body.id, "reports.snapshot", JSON.stringify(REPORTS), { cached: false, age: 0 })));
  }

  test("the v3 page: header actions on the right, summary by verdict with the snapshot time, pipe tabs, candidate list and detail", () => {
    renderPublish();
    expect(document.querySelector(".ds-page.ds-fit.publish-page")).not.toBeNull();
    expect(document.querySelector("#publish-kpis")!.previousElementSibling?.classList.contains("ds-page-head")).toBe(true);
    const actions = [...document.querySelectorAll(".ds-page-head .ds-head-actions > *")];
    expect(actions.map((item) => item.getAttribute("aria-label") ?? item.textContent?.trim())).toEqual(["Проверить", "Отчёты", "Оркестрация"]);
    expect([...document.querySelectorAll("#publish-kpis .ds-stat-label")].map((item) => item.textContent)).toEqual(["Готово", "Заблокировано", "Неизвестно"]);
    expect(document.querySelector("#publish-updated")!.textContent).toMatch(/^\d{2}:\d{2}:\d{2}$/);
    expect([...document.querySelectorAll("#publish-tabs .ds-pipe-label")].map((item) => item.textContent)).toEqual(["Обзор", "Preflight", "PR / MR", "Evidence"]);
    expect(document.querySelector("main .orch-pill")).toBeNull();
    // The list selects the newest reviewed batch and words its verdict with a StatusIcon.
    const rows = [...document.querySelectorAll("#publish-candidates [data-batch]")];
    expect(rows.map((row) => [row.getAttribute("data-batch"), row.getAttribute("aria-pressed")])).toEqual([["b-887", "true"]]);
    expect(rows[0]!.querySelector(".ds-status")).not.toBeNull();
    expect(rows[0]!.querySelector(".ds-row-end")!.textContent).toMatch(/^\d \/ 5 пройдено$/);
  });

  test("Open candidate shows the shared drawer with Evidence, Quality and Readiness", () => {
    renderPublish();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Открыть кандидата" })));
    const drawer = screen.getByRole("dialog", { name: /Кандидат · #887/ });
    expect([...drawer.querySelectorAll("[role=tab]")].map((tab) => tab.textContent)).toEqual(["Evidence", "Качество", "Готовность"]);
  });

  test("Release candidate: ticket and branch, then branch icon, target and QA in that order", () => {
    renderPublish();
    expect(document.querySelector(".publish-candidate h3")!.textContent).toBe("#887 · feature/issue-887");
    const meta = [...document.querySelectorAll(".publish-candidate .publish-meta > span")];
    expect(meta[0]!.querySelector("svg")).not.toBeNull();
    expect(meta.map((item) => item.textContent)).toEqual(["feature/issue-887", "target нет данных", "QA Сбой"]);
    expect(document.querySelector(".publish-gate-facts")!.textContent).toContain("нет отказов");
  });

  test("Overview shows all five preflight rows and the human decision with its reasons", () => {
    renderPublish();
    expect(document.querySelectorAll("#publish-preflight-overview .publish-check")).toHaveLength(5);
    const decision = document.querySelector("#publish-decision")!;
    expect(decision.querySelector(".publish-decision-text b")!.textContent).toBe("PR не готов к созданию");
    expect(decision.querySelector(".publish-decision-text p")!.textContent).toBe("QA evidence · Release Gate · Target");
    const buttons = [...decision.querySelectorAll(".publish-decision-actions > *")].map((item) => item.textContent?.trim());
    expect(buttons).toEqual(["Подготовить PR", "Почему", "Отчёты"]);
    expect((decision.querySelector(".publish-decision-actions button") as HTMLButtonElement).disabled).toBe(true);
    expect(decision.querySelector("#publish-why")).toBeNull();
    act(() => fireEvent.click(screen.getByRole("button", { name: "Почему" })));
    expect(decision.querySelectorAll("#publish-why li")).toHaveLength(3);
    expect(decision.querySelector(".decision-panel, #decisions")).toBeNull();
  });
});
