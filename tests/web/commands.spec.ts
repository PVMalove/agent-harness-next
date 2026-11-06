/* Harness · Commands (the «Команды» tab) in the real build over a mocked socket: a run streams its output, a dropped
   socket resumes it from the held cursor, and the panel and its confirmation dialog match the
   baselines at 1440 and 390 px. Update only these with
   `npm run test:e2e:update -- commands.spec.ts`. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const read = (name: string) => JSON.parse(readFileSync(resolve(__dirname, "fixtures", name), "utf-8")) as unknown;
const HOME = read("home-snapshot.json");
const CATALOG = read("job-catalog.json") as Body;
const OVERVIEW = read("harness-overview.json") as Body;
const MAINTENANCE = JSON.stringify(read("harness-maintenance.json"));

type Body = Record<string, unknown>;

const fragment = (n: number) => ({ channel: "stdout", text: `drift line ${n}\n` });
const lines = (from: number, to: number) => Array.from({ length: to - from }, (_, index) => fragment(from + index));

function job(output: Body[], cursor: number, done = false): Body {
  return {
    id: "job-1",
    command_id: "diff",
    mutating: false,
    phase: done ? "completed" : "running",
    cursor,
    done,
    truncated: false,
    returncode: done ? 0 : null,
    error: "",
    output,
  };
}

const send = (ws: WebSocketRoute, body: Body) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

/** Answers Home, the catalog and the job list; `onJob` answers the job requests. */
async function mockSocket(page: Page, onJob: (ws: WebSocketRoute, request: Body, connection: number) => void) {
  let connections = 0;
  await page.routeWebSocket("**/ws", (ws) => {
    const connection = connections++;
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      const id = request.id;
      if (request.type === "home.snapshot") {
        send(ws, { id, type: "home.snapshot", cached: true, age_seconds: 3, snapshot: HOME });
      } else if (request.type === "harness.overview") {
        send(ws, { id, type: "harness.overview", cached: true, age_seconds: 3, ...OVERVIEW });
      } else if (request.type === "harness.maintenance") {
        const text = MAINTENANCE;
        send(ws, { id, type: "harness.maintenance", snapshot_id: 2, text, next: text.length, done: true, cached: false, age_seconds: 0 });
      } else if (request.type === "job.catalog") {
        send(ws, { id, type: "job.catalog", ...CATALOG });
      } else if (request.type === "job.list") {
        send(ws, { id, type: "job.list", jobs: [] });
      } else if (String(request.type).startsWith("job.")) {
        onJob(ws, request, connection);
      }
    });
  });
}

async function open(page: Page, width: number) {
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.clock.setFixedTime(new Date("2026-11-05T10:41:00Z"));
  await page.goto(`${base()}/#/harness`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await page.getByRole("tab", { name: "Команды" }).click();
  await expect(page.locator('[data-command="diff"]')).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
}

const output = (page: Page) => page.locator(".command-output pre");

test("a run streams its output and a dropped socket resumes it without loss or repeats", async ({ page }) => {
  const subscriptions: Body[] = [];
  await mockSocket(page, (ws, request, connection) => {
    if (request.type === "job.start") {
      send(ws, { id: request.id, type: "job.start", job: job(lines(0, 2), 2) });
    } else if (request.type === "job.subscribe") {
      subscriptions.push(request);
      if (connection === 0) {
        send(ws, { id: request.id, type: "job.subscribe", job: job(lines(2, 4), 4) });
        // The connection drops in the middle of the output.
        setTimeout(() => void ws.close(), 50);
      } else {
        // The server replays from the cursor it is given, overlapping by one fragment.
        const cursor = Number(request.cursor);
        send(ws, { id: request.id, type: "job.subscribe", job: job(lines(cursor - 1, 6), 6) });
        send(ws, { id: request.id, type: "job.subscribe", job: job(lines(6, 7), 7, true) });
      }
    }
  });
  await open(page, 1440);
  await page.getByRole("button", { name: "Запустить diff" }).click();
  await expect(output(page)).toHaveText(lines(0, 7).map((line) => line.text).join(""));
  await expect(page.locator(".command-output [role=status]")).toHaveText("Завершена");
  expect(subscriptions.map((request) => request.cursor)).toEqual([2, 4]);
});

for (const width of [1440, 390]) {
  test(`commands at ${width} px`, async ({ page }) => {
    await mockSocket(page, (ws, request) => {
      if (request.type === "job.start") {
        send(ws, { id: request.id, type: "job.start", job: job(lines(0, 3), 3, true) });
      }
    });
    await open(page, width);
    await page.getByRole("button", { name: "Запустить diff" }).click();
    await expect(page.locator(".command-output [role=status]")).toHaveText("Завершена");
    await expect(page).toHaveScreenshot(`commands-${width}.png`, { fullPage: true });
  });

  test(`confirmation dialog at ${width} px`, async ({ page }) => {
    const starts: Body[] = [];
    await mockSocket(page, (_ws, request) => {
      if (request.type === "job.start") starts.push(request);
    });
    await open(page, width);
    await page.getByRole("button", { name: "Запустить uninstall-apply" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Введите UNINSTALL, чтобы подтвердить").fill("UNINST");
    await expect(dialog.getByRole("button", { name: "Запустить" })).toBeDisabled();
    await expect(page).toHaveScreenshot(`commands-confirm-${width}.png`);
    expect(starts).toEqual([]);
  });
}
