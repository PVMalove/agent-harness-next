/* The Task Board status change at 1440 and 390 px over the production build and the real FastAPI
   process, the socket answered with the synthetic board fixture and scripted job replies: target
   highlighting while a card is dragged, the refusal captions, the confirmation dialog and the
   status select, without horizontal overflow. DOM assertions only (ADR 0029: no screenshot
   comparison); the visual check against the mockup is the manual checklist in
   docs/design/web-console-mockups/board-acceptance.md. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import SPECS from "./fixtures/task-board-specs.json";
import BOARD from "./fixtures/task-board.json";

const base = () => process.env.CONSOLE_BASE_URL!;
const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf8")) as unknown;

/** How the scripted server answers `job.start` of `board-status`. */
type Answer = "changed" | "busy" | "write_error";

const job = (stdout: string) => ({
  id: "job-9",
  command_id: "board-status",
  mutating: true,
  phase: "completed",
  cursor: 1,
  done: true,
  truncated: false,
  returncode: stdout.includes('"changed"') ? 0 : 1,
  error: "",
  output: [{ channel: "stdout", text: stdout }],
});

const result = (fields: Record<string, unknown>) =>
  JSON.stringify({ ticket: "#512", from: "ready", to: "progress", reason: null, blockers: [], batch: null, message: "", ...fields }) + "\n";

/** With `hold`, the forced snapshot read after a job start waits for `release(board)`. */
async function open(page: Page, width: number, answer: Answer = "changed", hold = false) {
  const asked: Record<string, unknown>[] = [];
  const started: Record<string, unknown>[] = [];
  let held: ((board: unknown) => void) | null = null;
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-09T10:41:00Z"));
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((raw) => {
      const request = JSON.parse(String(raw)) as Record<string, unknown>;
      const reply = (body: Record<string, unknown>) =>
        ws.send(JSON.stringify({ v: 1, id: request.id, type: request.type, ok: true, ...body }));
      const paged = (value: unknown) => {
        const text = JSON.stringify(value);
        reply({ cached: false, age_seconds: 0, snapshot_id: 1, text, next: text.length, done: true });
      };
      if (request.type === "home.snapshot") reply({ cached: true, age_seconds: 0, snapshot: HOME });
      if (request.type === "task_board.specs") paged(SPECS);
      if (request.type === "task_board.snapshot") {
        asked.push(request);
        if (hold && request.force === true && started.length) held = paged;
        else paged(BOARD);
      }
      if (request.type === "job.start") {
        started.push(request);
        if (answer === "busy") {
          ws.send(
            JSON.stringify({
              v: 1,
              id: request.id,
              type: "job.start",
              ok: false,
              error: { code: "busy", message: "Busy: job-7 (update)", job_id: "job-7" },
            }),
          );
        } else if (answer === "write_error") {
          reply({ job: job(result({ result: "write_error", reason: "write_failed", message: "gh: label not found" })) });
        } else {
          reply({ job: job(result({ result: "changed" })) });
        }
      }
    });
  });
  await page.goto(`${base()}/#/board`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.locator("[data-board-ticket]")).toHaveCount(7);
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return { asked, started, release: (board: unknown) => held?.(board) };
}

const noOverflow = (page: Page) =>
  page.evaluate(() => {
    const content = document.querySelector("#content")!;
    return document.documentElement.scrollWidth <= innerWidth && content.scrollWidth <= content.clientWidth;
  });

const card = (page: Page, id: string) => page.locator(`[data-board-ticket="${id}"]`);
const column = (page: Page, id: string) => page.locator(`[data-board-col="${id}"]`);

/** HTML5 drag events with one DataTransfer, as a browser drag sends them. */
async function dragStart(page: Page, id: string) {
  const data = await page.evaluateHandle(() => new DataTransfer());
  await card(page, id).dispatchEvent("dragstart", { dataTransfer: data });
  return data;
}

async function drop(page: Page, id: string, to: string) {
  const data = await dragStart(page, id);
  await column(page, to).dispatchEvent("dragover", { dataTransfer: data });
  await column(page, to).dispatchEvent("drop", { dataTransfer: data });
  await card(page, id).dispatchEvent("dragend", { dataTransfer: data });
}

function watch(page: Page) {
  const errors: string[] = [];
  const foreign: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => {
    if (!request.url().startsWith(base())) foreign.push(request.url());
  });
  return { errors, foreign };
}

for (const width of [1440, 390]) {
  test(`dragging highlights the targets and a refused drop shows its reason at ${width} px`, async ({ page }) => {
    const seen = watch(page);
    const { started } = await open(page, width);
    await dragStart(page, "#512");
    await expect(column(page, "backlog")).toHaveClass(/drop-ok/);
    await expect(column(page, "progress")).toHaveClass(/drop-ok/);
    await expect(column(page, "ready")).not.toHaveClass(/drop-(ok|no)/);
    await expect(column(page, "review")).toHaveClass(/drop-no/);
    await expect(column(page, "done")).toHaveClass(/drop-no/);
    await expect(column(page, "review")).toHaveAttribute("data-reason", /Review \/ QA/);
    expect(await noOverflow(page)).toBe(true);
    await card(page, "#512").dispatchEvent("dragend");
    await expect(page.locator(".drop-ok, .drop-no")).toHaveCount(0);

    const notice = page.locator("#board-move-notice");
    await drop(page, "#511", "ready");
    await expect(notice).toHaveText("#511 → «Готово к работе»: Открыты блокеры: #512");
    await drop(page, "#513", "ready");
    await expect(notice).toHaveText("#513 → «Готово к работе»: Активный batch b-513");
    await drop(page, "#514", "ready");
    await expect(notice).toHaveText("#514 → «Готово к работе»: У тикета активный batch или PR");
    expect(await noOverflow(page)).toBe(true);
    expect(started).toEqual([]);
    expect(seen.errors).toEqual([]);
    expect(seen.foreign).toEqual([]);
  });

  test(`the confirmation dialog runs the change and refreshes the board at ${width} px`, async ({ page }) => {
    const seen = watch(page);
    const { asked, started } = await open(page, width);
    await drop(page, "#512", "progress");
    const dialog = page.locator("#board-confirm");
    await expect(dialog).toBeVisible();
    await expect(dialog.locator(".eyebrow")).toHaveText("СМЕНА СТАТУСА");
    await expect(dialog.locator("h2")).toHaveText("#512 → В работе");
    await expect(dialog.locator(".board-confirm-diff")).toHaveText("ready→progress");
    await expect(dialog.locator(".board-confirm-note")).toHaveText(
      "Сервер запустит смену метки в GitHub как мутирующий job и обновит доску.",
    );
    expect(await noOverflow(page)).toBe(true);
    await dialog.getByRole("button", { name: "Отмена" }).click();
    await expect(dialog).toHaveCount(0);
    expect(started).toEqual([]);

    await drop(page, "#512", "progress");
    await page.locator("#board-confirm-ok").click();
    await expect(page.locator("#board-move-notice")).toHaveText("#512: статус обновлён");
    expect(started[0]).toMatchObject({
      command_id: "board-status",
      values: { spec: "#501", ticket: "#512", to: "progress" },
      confirmed: true,
    });
    await expect.poll(() => asked.at(-1)).toMatchObject({ spec: "#501", force: true });
    expect(seen.errors).toEqual([]);
    expect(seen.foreign).toEqual([]);
  });

  test(`the board stays under the updating overlay until the new snapshot at ${width} px`, async ({ page }) => {
    const seen = watch(page);
    const { release } = await open(page, width, "changed", true);
    await drop(page, "#512", "progress");
    await page.locator("#board-confirm-ok").click();

    const overlay = page.locator("#board-updating");
    await expect(overlay).toBeVisible();
    await expect(overlay).toHaveAttribute("role", "status");
    await expect(overlay).toContainText("Идёт обновление…");
    await expect(page.locator("[data-board-col]")).toHaveCount(5);
    await expect(page.locator('[data-board-state="loading"]')).toHaveCount(0);
    const mascot = overlay.locator(".board-mascot");
    await expect.poll(() => mascot.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
    expect(await mascot.evaluate((el) => getComputedStyle(el).animationName)).toBe("board-mascot-jump");
    expect(await overlay.evaluate((el) => getComputedStyle(el).pointerEvents)).toBe("none");
    expect(await overlay.evaluate((el) => el.contains(document.activeElement))).toBe(false);
    expect(await noOverflow(page)).toBe(true);

    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(await mascot.evaluate((el) => getComputedStyle(el).animationName)).toBe("none");

    const moved = {
      ...BOARD,
      tickets: BOARD.tickets.map((ticket) => (ticket.id === "#512" ? { ...ticket, column: "progress" } : ticket)),
    };
    release(moved);
    await expect(overlay).toHaveCount(0);
    await expect(column(page, "progress").locator('[data-board-ticket="#512"]')).toHaveCount(1);
    expect(seen.errors).toEqual([]);
    expect(seen.foreign).toEqual([]);
  });

  test(`a busy server refuses the move with the running job at ${width} px`, async ({ page }) => {
    await open(page, width, "busy");
    await drop(page, "#512", "progress");
    await page.locator("#board-confirm-ok").click();
    await expect(page.locator("#board-move-notice")).toHaveText("#512 → «В работе»: Занято: update");
    expect(await noOverflow(page)).toBe(true);
  });

  test(`a tracker write error is shown and the board refreshed at ${width} px`, async ({ page }) => {
    const { asked } = await open(page, width, "write_error");
    await drop(page, "#512", "progress");
    await page.locator("#board-confirm-ok").click();
    await expect(page.locator("#board-move-notice")).toHaveText(
      "#512 → «В работе»: Ошибка записи в трекер: изменение не сохранено",
    );
    await expect.poll(() => asked.at(-1)).toMatchObject({ spec: "#501", force: true });
    expect(await noOverflow(page)).toBe(true);
  });

  test(`the status select of the modal works from the keyboard at ${width} px`, async ({ page }) => {
    const { started } = await open(page, width);
    await card(page, "#512").focus();
    await page.keyboard.press("Enter");
    const modal = page.locator("#board-ticket");
    await expect(modal).toBeVisible();
    const select = modal.locator("select#board-status");
    await expect(select).toHaveValue("ready");
    await select.focus();
    await expect(select).toBeFocused();
    await select.selectOption("review");
    await expect(modal.locator("#board-modal-notice")).toHaveAttribute("data-reason", "review_target");
    await expect(select).toHaveValue("ready");
    expect(await noOverflow(page)).toBe(true);
    await select.selectOption("progress");
    const dialog = page.locator("#board-confirm");
    await expect(dialog.locator("h2")).toHaveText("#512 → В работе");
    await dialog.locator("#board-confirm-ok").focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#board-move-notice")).toHaveText("#512: статус обновлён");
    expect(started).toHaveLength(1);
  });
}
