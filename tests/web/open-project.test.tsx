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

const stepTo = (index: number) => act(() => fireEvent.click(document.querySelector(`#open-project-step-tab-${index}-button`)!));

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
    const current = document.querySelector('#navigation a[aria-current="page"]');
    expect(current?.getAttribute("href")).toBe("#/open-project");
  });

  test("lays out the mockup blocks: folder rows, the rollout scheme and the install plan under it", () => {
    renderPage();
    const rows = [...document.querySelectorAll("#open-project-list [data-path]")];
    expect(rows.map((row) => [row.querySelector(".ds-project-icon svg")?.getAttribute("data-icon"), row.querySelector(".ds-row-title")?.textContent, row.querySelector(".ds-tag")?.textContent])).toEqual([
      ["folder", "project", "Открыт"],
      ["folder", "billing", "Не открыт"],
      ["folder", "new service", "Не открыт"],
    ]);
    expect(document.querySelector("#open-project-current .ds-project-icon svg")?.getAttribute("data-icon")).toBe("folder");
    const flow = document.querySelector("#open-project-flow") as HTMLElement;
    expect(flow.querySelector("h2")?.textContent).toBe("Схема внедрения");
    expect([...flow.querySelectorAll(".ds-loop-node b")].map((node) => node.textContent)).toEqual(["Проект", "Harness", "Capability", "Runtime", "Проверки"]);
    const capability = () => flow.querySelector("[data-flow-cap]")?.textContent;
    expect(capability()).toBe("engineering-suite");
    stepTo(2);
    act(() => fireEvent.click(screen.getByRole("radio", { name: /backend-orchestration/ })));
    expect(capability()).toBe("backend-orchestration");
    const bottom = document.querySelector(".ds-project-install") as HTMLElement;
    expect([...bottom.children].map((child) => child.id)).toEqual(["open-project-plan", "open-project-capability"]);
    expect(flow.compareDocumentPosition(bottom) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // The snapshot has no per-composition counts: they say so instead of a number.
    const counts = [...document.querySelectorAll("#open-project-composition-counts dd")].map((item) => item.textContent);
    expect(counts).toEqual(["нет данных", "нет данных", "нет данных"]);
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
    stepTo(2);
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

  test("the title and the current project follow the mockup: one action, name · branch · version and four KPIs shown once", () => {
    renderPage();
    expect([...document.querySelectorAll(".ds-page-head .ds-head-actions > *")].map((item) => item.textContent?.trim())).toEqual(["Диагностика"]);
    expect([...document.querySelectorAll("#open-project-facts .ds-facts-main span")].map((item) => item.textContent)).toEqual(["claude-agent-harness", "feature/issue-7", "1.5.1"]);
    const steps = [...document.querySelectorAll("#open-project-steps [role=tab]")];
    expect(steps.map((step) => step.textContent)).toEqual([
      "1Выбор проекта✓",
      "2Предварительные проверки",
      "3Установка / внедрение",
      "4Настройка",
      "5Итоговая диагностика",
    ]);
    expect(document.querySelector("#open-project-steps .ds-note")?.textContent).toBe("Этап проекта: 2 из 5");
    const current = document.querySelector("#open-project-current") as HTMLElement;
    expect([...current.querySelectorAll(".ds-project-meta svg")].map((icon) => icon.getAttribute("data-icon"))).toEqual(["branch", "github-mark"]);
    expect(current.querySelector(".ds-project-meta")?.textContent).toContain("feature/issue-7");
    // The four KPIs live in the summary only; the current project panel does not repeat them.
    const stats = [...document.querySelectorAll("#open-project-facts .ds-stat")].map((kpi) => [kpi.querySelector(".ds-stat-label")?.textContent, kpi.querySelector(".ds-stat-value")?.textContent]);
    expect(stats).toEqual([
      ["Harness", "1.5.1"],
      ["Скиллов", "32"],
      ["Управляемых файлов", "232"],
      ["Проверки", "42/56"],
    ]);
    expect(current.textContent).not.toContain("Управляемых файлов");
    expect(current.textContent).not.toContain("42/56");
    expect(document.querySelectorAll("main#content .ds-legacy-island")).toHaveLength(1);
    expect(document.querySelector("main#content .ds-legacy-island #open-project-steps, main#content .ds-legacy-island .ds-panel")).toBeNull();
  });

  test("the project list has its count head and foot; a typed path is checked locally with «Проверить путь»", () => {
    const { socket } = renderPage();
    expect(document.querySelector("#open-project-list .ds-panel-meta")?.textContent).toBe("3 найдено");
    expect(document.querySelector("#open-project-list #open-project-list-foot")?.textContent).toBe("Выберите проект, чтобы увидеть проверки справа.");
    expect(screen.getByLabelText("Путь к локальному Git-проекту").className).toBe("ds-input");
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
    expect(detail().querySelector(".ds-project-provider svg")?.getAttribute("data-icon")).toBe("github-mark");
    expect(detail().querySelector(".ds-project-meta")?.textContent).toContain("feature/issue-7");
    expect(detail().querySelector(".ds-project-meta")?.textContent).toContain("2 ошибки · 1 внимание");
    // Every check row is a StatusIcon (shape plus the spoken word), never a colour alone.
    const checks = () =>
      [...detail().querySelectorAll("#open-project-detail-checks .ds-row")].map((row) => [
        row.querySelector(".ds-row-title")?.textContent,
        row.querySelector(".ds-status")?.getAttribute("data-tone"),
        row.querySelector(".ds-status .ds-sr")?.textContent,
      ]);
    expect(checks()).toEqual([
      ["Git repository", "ok", "пройдено"],
      ["Harness config", "ok", "пройдено"],
      ["Capability", "ok", "пройдено"],
      ["Skills snapshot", "warn", "внимание"],
      ["Локальные правки управляемых файлов", "ok", "пройдено"],
    ]);
    expect((within(detail()).getByRole("button", { name: "Уже открыт" }) as HTMLButtonElement).disabled).toBe(true);
    act(() => fireEvent.click(document.querySelector('[data-path="/work/billing"]') as HTMLElement));
    expect(checks().map(([, tone]) => tone)).toEqual(["wait", "ok", "wait", "wait", "wait"]);
    expect(detail().textContent).toContain("снимок читает только проект этого сервера");
  });

  test("the rollout scheme reads runtime and health from Home; capabilities carry descriptions and a footer", () => {
    renderPage();
    const nodes = [...document.querySelectorAll("#open-project-flow .ds-loop-node")].map((node) => [node.querySelector(".ds-project-flow-value")?.textContent, node.querySelector("small:last-of-type")?.textContent]);
    expect(nodes[1]).toEqual(["1.5.1 → 1.5.1", "обновление"]);
    expect(nodes[3]).toEqual(["schema 3", "generation-1a2b3c4d · audit 1240"]);
    expect(nodes[4]).toEqual(["42/56 пройдено", "проверки — на странице «Диагностика»"]);
    const rows = [...document.querySelectorAll("#open-project-capability .ds-choice")];
    expect(rows.length).toBeGreaterThan(0);
    expect(rows.every((row) => (row.querySelector(".ds-row-sub")?.textContent ?? "").length > 0)).toBe(true);
    expect(document.querySelector("#open-project-capability-footer")?.textContent).toBe(CAPABILITY_TEXT["engineering-suite"]![2]);
    const catalog = JSON.parse(readFileSync(resolve(__dirname, "../../harness/CAPABILITIES.json"), "utf-8")) as Record<string, unknown>;
    expect(Object.keys(catalog).filter((id) => !(id in CAPABILITY_TEXT))).toEqual([]);
  });

  test("the checks panel shows the Home health counts, the mode filter and the fix links", () => {
    const { socket } = renderPage();
    stepTo(1);
    const checks = document.querySelector("#open-project-checks") as HTMLElement;
    expect(checks.querySelector(".ds-panel-meta")?.textContent).toBe("45 из 56 проверено");
    const modes = within(checks).getByRole("group", { name: "Режим проверки" });
    expect(modes.className).toBe("ds-filter");
    expect([...modes.querySelectorAll("button")].map((button) => [button.textContent, button.getAttribute("aria-pressed")])).toEqual([
      ["Офлайн", "true"],
      ["Онлайн", "false"],
    ]);
    act(() => fireEvent.click(within(modes).getByRole("button", { name: "Онлайн" })));
    expect(socket.sent.filter((body) => body.type === "home.snapshot").at(-1)).toMatchObject({ force: true, online: true });
    expect(within(modes).getByRole("button", { name: "Онлайн" }).getAttribute("aria-pressed")).toBe("true");
    expect(checks.querySelector('a[href="#/diagnostics"]')?.textContent?.trim()).toBe("Исправить");
    expect(checks.querySelector('a[href="#/configuration"]')?.textContent?.trim()).toBe("Настройка");
    const counters = [...checks.querySelectorAll("#open-project-health .ds-row")].map((row) => [row.querySelector(".ds-status")?.getAttribute("data-tone"), row.querySelector(".ds-row-main")?.textContent]);
    expect(counters).toEqual([
      ["ok", "42 пройдено"],
      ["warn", "1 внимание"],
      ["err", "2 ошибки"],
      ["wait", "11 не проверено"],
    ]);
    expect(checks.querySelectorAll(".ds-project-bar span").length).toBe(4);
  });

  test("the wizard steps are TabPanels that keep their content mounted while hidden", () => {
    renderPage();
    const panels = [...document.querySelectorAll('[id^="open-project-step-tab-"][role="tabpanel"]')];
    expect(panels.map((panel) => [panel.id, panel.hasAttribute("hidden")])).toEqual([
      ["open-project-step-tab-0", false],
      ["open-project-step-tab-1", true],
      ["open-project-step-tab-2", true],
      ["open-project-step-tab-3", true],
      ["open-project-step-tab-4", true],
    ]);
    expect(panels.every((panel) => panel.childElementCount > 0)).toBe(true);
    stepTo(4);
    expect(document.querySelector("#open-project-step-tab-4")?.hasAttribute("hidden")).toBe(false);
    expect(document.querySelector("#open-project-step-tab-0")?.hasAttribute("hidden")).toBe(true);
  });
});
