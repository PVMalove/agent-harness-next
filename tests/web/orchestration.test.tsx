import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { lockLines } from "../../harness/console/frontend/src/orchestration/format";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { CANCEL_REASON, FakeSocket, ManualClock, screenPage } from "./fake-socket";
import FACTS from "./fixtures/orchestration-facts.json";
import ORCHESTRATION from "./fixtures/orchestration.json";
import TIMELINE from "./fixtures/reports-timeline.json";

function renderOrchestration(language = "") {
  window.location.hash = `#/orchestration${language}`;
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: new ManualClock(),
    probeHealth: async () => false,
  });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  const socket = FakeSocket.last;
  act(() => socket.open());
  const snapshot = socket.request("orchestration.snapshot");
  act(() => socket.reply(screenPage(snapshot.id, "orchestration.snapshot", JSON.stringify(ORCHESTRATION), { cached: true, age: 4 })));
  act(() =>
    socket.reply({
      v: 1,
      id: socket.request("decisions.snapshot").id,
      type: "decisions.snapshot",
      ok: true,
      snapshot: { version: 1, items: [], total: 0, unavailable: false },
    }),
  );
  act(() =>
    socket.reply({ v: 1, id: socket.request("job.catalog").id, type: "job.catalog", ok: true, commands: [], cancel_reason: CANCEL_REASON }),
  );
  return socket;
}

function openBatch(socket: FakeSocket, batch: string) {
  act(() => fireEvent.click(document.querySelector(`#batch-history [data-batch="${batch}"]`) as HTMLElement));
  const request = socket.request("reports.timeline");
  expect(request).toMatchObject({ batch_id: batch });
  const page = screenPage(request.id, "reports.timeline", JSON.stringify(TIMELINE));
  delete page.cached;
  delete page.age_seconds;
  act(() => socket.reply(page));
}

const content = () => document.querySelector("main#content")?.textContent ?? "";

describe("the Orchestration route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows every fact the TUI shows for the same snapshot and keeps the decisions", () => {
    const socket = renderOrchestration();
    expect(socket.request("orchestration.snapshot")).toMatchObject({ force: false });
    const shown = content();
    expect((FACTS as string[]).filter((fact) => !shown.includes(fact))).toEqual([]);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Оркестрация");
    expect(screen.getByRole("heading", { name: "Решения" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Ожидающие решения" })).toBeTruthy();
  });

  test("a chosen batch opens its chronology and is carried to Recovery and Container route", () => {
    const socket = renderOrchestration();
    expect(document.querySelector("#open-recovery")?.getAttribute("href")).toBe("#/recovery");
    openBatch(socket, "b-887");
    expect(content()).toContain("developer → review → qa → developer");
    expect(document.querySelector("#open-recovery")?.getAttribute("href")).toBe("#/recovery?batch=b-887");
    expect(document.querySelector("#open-container-route")?.getAttribute("href")).toBe("#/container-route?batch=b-887");
  });

  test("the state filter narrows the history; analytics tabs only switch the rows", () => {
    renderOrchestration();
    const history = () => [...document.querySelectorAll("#batch-history [data-batch]")].map((row) => row.getAttribute("data-batch"));
    expect(history()).toEqual(["b-887", "b-886"]);
    act(() => fireEvent.change(document.querySelector("#state-filter") as HTMLElement, { target: { value: "completed" } }));
    expect(history()).toEqual(["b-886"]);
    const analytics = document.querySelector("#orch-analytics") as HTMLElement;
    act(() => fireEvent.click(within(analytics).getByRole("tab", { name: "Гейты" })));
    expect(analytics.querySelector('[data-tab="gates"]')?.hasAttribute("hidden")).toBe(false);
    expect(analytics.querySelector('[data-tab="flow"]')?.hasAttribute("hidden")).toBe(true);
  });

  test("the lock panel words a free, an unreadable and a held lock as the TUI does", () => {
    expect(lockLines({ locked: false }, null, "ru")).toEqual(["Lock ledger свободен."]);
    expect(lockLines(null, "boom", "en")).toEqual(["Ledger lock: state unavailable: boom"]);
    expect(lockLines({ locked: false, qa_lease: null }, null, "en")).toEqual(["The ledger lock is free.", "The QA lease is free."]);
    expect(lockLines({ ...ORCHESTRATION.lock.lock, release_available: true }, null, "ru")[2]).toBe(
      "Держится: 1 мин 15 с · до снятия по таймауту: доступно",
    );
  });

  test("English labels come from the catalog", () => {
    renderOrchestration("?lang=en");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Orchestration");
    expect(content()).toContain("Ledger lock held: report submit");
    expect(content()).toContain("Pipeline state, batch history and human decisions.");
    expect(content()).toContain("in progress (1)");
  });
});
