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
import HOME from "./fixtures/home-snapshot.json";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { CAPABILITY_TEXT } from "../../harness/console/frontend/src/project/format";

function renderPage(value: unknown = OPEN, home: unknown = HOME) {
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
  if (home) {
    const asked = socket.request("home.snapshot");
    act(() => socket.reply({ v: 1, id: asked.id, type: "home.snapshot", ok: true, cached: false, age_seconds: 0, snapshot: home }));
  }
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
    // A TUI status glyph is an icon on the page, so the words are compared without it.
    const missing = (FACTS as string[]).filter((fact) => !content().includes(fact.replace(/^[✔⚠✖○] /, "")));
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
    expect(within(document.querySelector("#open-project-plan") as HTMLElement).getAllByText("Не Git-проект").length).toBeGreaterThan(0);
    expect((document.querySelector("#open-project-install") as HTMLButtonElement).disabled).toBe(true);
  });

  test("the title and the current project follow the mockup: one action, name · branch · version and four KPIs", () => {
    renderPage();
    expect([...document.querySelectorAll(".project-title .actions > *")].map((item) => item.textContent?.trim())).toEqual(["Диагностика"]);
    expect([...document.querySelectorAll(".project-title .home-facts span")].map((item) => item.textContent)).toEqual(["claude-agent-harness", "feature/issue-7", "1.5.1"]);
    const steps = [...document.querySelectorAll("#open-project-steps .install-step")];
    expect(steps.map((step) => step.querySelector("svg")?.getAttribute("data-icon"))).toEqual(["check", "play", "clock", "clock", "clock"]);
    expect(steps.map((step) => step.textContent).join("")).not.toMatch(/[✔▶○]/);
    const current = document.querySelector("#open-project-current") as HTMLElement;
    expect([...current.querySelectorAll(".current-project-meta svg")].map((icon) => icon.getAttribute("data-icon"))).toEqual(["branch", "github-mark"]);
    expect(current.querySelector(".current-project-meta")?.textContent).toContain("feature/issue-7");
    expect([...current.querySelectorAll(".current-project-stats > div")].map((kpi) => [kpi.querySelector("span")?.textContent, kpi.querySelector("b")?.textContent])).toEqual([
      ["Harness", "1.5.1"],
      ["Скиллов", "32"],
      ["Managed", "232"],
      ["Health", "42/56"],
    ]);
  });

  test("the project list has its count head and foot; a typed path is checked locally with «Проверить путь»", () => {
    const { socket } = renderPage();
    expect(document.querySelector("#open-project-list .panel-head .small")?.textContent).toBe("3 найдено");
    expect(document.querySelector("#open-project-list .project-list-foot")?.textContent).toBe("Выберите проект, чтобы увидеть проверки справа.");
    const before = socket.sent.length;
    act(() => fireEvent.change(screen.getByLabelText("Путь к локальному Git-проекту"), { target: { value: "relative/path" } }));
    act(() => fireEvent.click(screen.getByRole("button", { name: "Проверить путь" })));
    expect(document.querySelector("#open-project-path-status")?.textContent).toBe("Нужен абсолютный путь");
    act(() => fireEvent.change(screen.getByLabelText("Путь к локальному Git-проекту"), { target: { value: "/srv/other" } }));
    act(() => fireEvent.click(screen.getByRole("button", { name: "Проверить путь" })));
    expect(document.querySelector("#open-project-path-status")?.textContent).toBe("Путь выглядит корректно · откройте его своей командой");
    expect(socket.sent.length).toBe(before);
  });

  test("the details of the served project show its tracker, facts and five checks; another one says what is not read", () => {
    renderPage();
    const detail = () => document.querySelector("#open-project-detail") as HTMLElement;
    expect(detail().querySelector(".project-provider svg")?.getAttribute("data-icon")).toBe("github-mark");
    expect(detail().querySelector(".project-meta")?.textContent).toContain("feature/issue-7");
    expect(detail().querySelector(".project-meta")?.textContent).toContain("2 ошибки · 1 внимание");
    const checks = () => [...detail().querySelectorAll(".project-check")].map((row) => [row.querySelector("b")?.textContent, row.querySelector(".project-check-state")?.className.split(" ")[1]]);
    expect(checks()).toEqual([
      ["Git repository", "ok"],
      ["Harness config", "ok"],
      ["Capability", "ok"],
      ["Skills snapshot", "warn"],
      ["Локальные правки управляемых файлов", "ok"],
    ]);
    expect((within(detail()).getByRole("button", { name: "Уже открыт" }) as HTMLButtonElement).disabled).toBe(true);
    act(() => fireEvent.click(document.querySelector('[data-path="/work/billing"]') as HTMLElement));
    expect(checks().map(([, state]) => state)).toEqual(["skip", "ok", "skip", "skip", "skip"]);
    expect(detail().textContent).toContain("снимок читает только проект этого сервера");
  });

  test("the rollout scheme reads runtime and health from Home; capabilities carry descriptions and a footer", () => {
    renderPage();
    const nodes = [...document.querySelectorAll("#open-project-flow .install-flow-node")].map((node) => [node.querySelector(".install-flow-value")?.textContent, node.querySelector("small")?.textContent]);
    expect(nodes[1]).toEqual(["1.5.1 → 1.5.1", "обновление"]);
    expect(nodes[3]).toEqual(["schema 3", "generation-1a2b3c4d · audit 1240"]);
    expect(nodes[4]).toEqual(["42/56 пройдено", "проверки — на странице «Диагностика»"]);
    const rows = [...document.querySelectorAll("#open-project-capability .cap-row")];
    expect(rows.every((row) => (row.querySelector("small")?.textContent ?? "").length > 0)).toBe(true);
    expect(document.querySelector("#open-project-capability .cap-footer")?.textContent).toBe(CAPABILITY_TEXT["engineering-suite"]![2]);
    const catalog = JSON.parse(readFileSync(resolve(__dirname, "../../harness/CAPABILITIES.json"), "utf-8")) as Record<string, unknown>;
    expect(Object.keys(catalog).filter((id) => !(id in CAPABILITY_TEXT))).toEqual([]);
  });

  test("the checks panel shows the Home health counts, the mode chips and the fix links", () => {
    renderPage();
    const checks = document.querySelector("#open-project-checks") as HTMLElement;
    expect(checks.querySelector(".panel-head .small")?.textContent).toBe("45 из 56 проверено");
    expect([...checks.querySelectorAll(".install-check-actions .chip")].map((chip) => chip.textContent)).toEqual(["Офлайн", "Онлайн"]);
    expect(checks.querySelector('a[href="#/diagnostics"]')?.textContent?.trim()).toBe("Исправить");
    expect(checks.querySelector('a[href="#/configuration"]')?.textContent?.trim()).toBe("Настройка");
    expect([...checks.querySelectorAll(".install-health > span")].map((item) => item.textContent?.trim())).toEqual(["42 пройдено", "1 внимание", "2 ошибки", "11 не проверено"]);
    expect(checks.querySelectorAll(".install-health-bar span").length).toBe(4);
  });
});
