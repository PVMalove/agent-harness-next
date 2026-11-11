import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { openCommand, shellQuote } from "../../harness/console/frontend/src/project/format";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import CATALOG from "./fixtures/setup-catalog.json";
import FACTS from "./fixtures/open-project-facts.json";
import OPEN from "./fixtures/open-project.json";

function renderPage(value: unknown = OPEN) {
  window.location.hash = "#/open-project";
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
  const request = socket.request("open_project.snapshot");
  act(() => socket.reply(screenPage(request.id, "open_project.snapshot", JSON.stringify(value), { cached: true, age: 2 })));
  const catalog = socket.sent.find((body) => body.type === "job.catalog");
  if (catalog) act(() => socket.reply({ v: 1, id: catalog.id, type: "job.catalog", ok: true, ...CATALOG }));
  return { socket, request };
}

const content = () => document.querySelector("main#content")?.textContent ?? "";
const starts = (socket: FakeSocket) => socket.sent.filter((body) => body.type === "job.start");
// The page's own requests and the shell's (its event feed and the context facts); no other type.
const SENT_TYPES = new Set([
  "open_project.snapshot",
  "job.catalog",
  "job.list",
  "job.start",
  "job.subscribe",
  "orchestration.subscribe",
  "home.snapshot",
]);

describe("the Open Project route", () => {
  beforeEach(() => FakeSocket.reset());

  test("shows every fact the TUI shows for the served project and its candidates", () => {
    const { request, socket } = renderPage();
    expect(request).toMatchObject({ type: "open_project.snapshot", force: false });
    expect(Object.keys(request).sort()).toEqual(["force", "id", "type"]);
    const missing = (FACTS as string[]).filter((fact) => !content().includes(fact));
    // Each candidate command is shown when its row is selected.
    const commands = OPEN.candidates.map((item) => item.command);
    expect(missing.filter((fact) => !commands.includes(fact))).toEqual([]);
    for (const item of OPEN.candidates) {
      act(() => fireEvent.click(document.querySelector(`[data-path="${item.path}"]`) as HTMLElement));
      expect(document.querySelector("#open-project-command")?.textContent).toBe(item.command);
    }
    expect(socket.sent.filter((body) => !SENT_TYPES.has(String(body.type)))).toEqual([]);
    const current = document.querySelector('nav a[aria-current="page"]');
    expect(current?.getAttribute("href")).toBe("#/open-project");
  });

  test("lays out the mockup blocks: folder rows, the rollout scheme and the install plan under it", () => {
    renderPage();
    const rows = [...document.querySelectorAll("#open-project-list .project-row")];
    expect(rows.map((row) => [row.querySelector(".project-row-icon svg")?.getAttribute("data-icon"), row.querySelector(".project-row-main b")?.textContent, row.querySelector(".project-pill")?.textContent])).toEqual([
      ["folder", "project", "Открыт"],
      ["folder", "billing", "Не открыт"],
      ["folder", "new service", "Не открыт"],
    ]);
    expect(document.querySelector("#open-project-current .current-project-icon svg")?.getAttribute("data-icon")).toBe("folder");
    const flow = document.querySelector("#open-project-flow") as HTMLElement;
    expect(flow.querySelector("h2")?.textContent).toBe("Схема внедрения");
    expect([...flow.querySelectorAll(".install-flow-node b")].map((node) => node.textContent)).toEqual(["Проект", "Harness", "Capability", "Runtime", "Health"]);
    const capability = () => flow.querySelector("[data-flow-cap]")?.textContent;
    expect(capability()).toBe("engineering-suite");
    act(() => fireEvent.click(screen.getByRole("radio", { name: /backend-orchestration/ })));
    expect(capability()).toBe("backend-orchestration");
    const bottom = document.querySelector(".install-bottom-grid") as HTMLElement;
    expect([...bottom.children].map((child) => child.id)).toEqual(["open-project-plan", "open-project-capability", "open-project-checks"]);
    expect(flow.compareDocumentPosition(bottom) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test("another path becomes a copyable command in the browser; nothing is sent", () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const { socket } = renderPage();
    const before = socket.sent.length;
    act(() => fireEvent.change(screen.getByLabelText("Путь к локальному Git-проекту"), { target: { value: "/srv/it's here" } }));
    expect(document.querySelector("#open-project-path-command")?.textContent).toBe("harness console --web '/srv/it'\"'\"'s here'");
    act(() => fireEvent.click(document.querySelector("#open-project-path-copy") as HTMLElement));
    expect(writeText).toHaveBeenCalledWith("harness console --web '/srv/it'\"'\"'s here'");
    expect(socket.sent.length).toBe(before);
    expect(shellQuote("")).toBe("''");
    expect(openCommand("/work/project")).toBe("harness console --web /work/project");
  });

  test("cancelling the install dialog starts nothing; confirming starts one confirmed setup job", () => {
    const { socket } = renderPage();
    expect(screen.queryByText("Команды")).toBeNull();
    const install = document.querySelector("#open-project-install") as HTMLButtonElement;
    act(() => fireEvent.click(install));
    let dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("setup-update")).toBeTruthy();
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Отмена" })));
    expect(starts(socket)).toEqual([]);
    act(() => fireEvent.click(install));
    dialog = screen.getByRole("dialog");
    act(() => fireEvent.click(within(dialog).getByRole("button", { name: "Запустить" })));
    expect(starts(socket)).toHaveLength(1);
    expect(starts(socket)[0]).toMatchObject({
      command_id: "setup-update",
      values: { capability: "engineering-suite" },
      confirmed: true,
    });
  });

  test("a blocked capability changes the plan and cannot be installed", () => {
    const { socket } = renderPage();
    act(() => fireEvent.click(screen.getByRole("radio", { name: /backend-orchestration/ })));
    expect(document.querySelector("#open-project-install-command")?.textContent).toBe(
      "harness update /work/project --capability backend-orchestration",
    );
    expect(content()).toContain(".harness/orchestration/roles/developer.md");
    const install = document.querySelector("#open-project-install") as HTMLButtonElement;
    expect(install.disabled).toBe(true);
    act(() => fireEvent.click(install));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(starts(socket)).toEqual([]);
  });

  test("a project that cannot be installed into shows the server's reason", () => {
    renderPage({ ...OPEN, target: null, error: "Не Git-проект" });
    expect(content()).toContain("Не Git-проект");
    expect((document.querySelector("#open-project-install") as HTMLButtonElement).disabled).toBe(true);
  });
});
