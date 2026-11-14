/* The five connection states in the real build: mocked WebSocket replies for connected,
   reconnecting, error and empty; the real server's 401 for a rejected session and no server. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page, WebSocketRoute } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const FIXTURE = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf-8")) as Record<
  string,
  unknown
>;

type Body = Record<string, unknown>;

/** Mocks /ws: `onRequest` answers each request of one connection (its index is `connection`). */
async function mockSocket(page: Page, onRequest: (ws: WebSocketRoute, request: Body, connection: number) => void) {
  let connections = 0;
  await page.routeWebSocket("**/ws", (ws) => {
    const connection = connections++;
    ws.onMessage((message) => onRequest(ws, JSON.parse(String(message)) as Body, connection));
  });
}

const snapshot = (ws: WebSocketRoute, request: Body, body: unknown = FIXTURE) =>
  ws.send(JSON.stringify({ v: 1, id: request.id, type: "home.snapshot", ok: true, cached: false, age_seconds: 0, snapshot: body }));

const chip = (page: Page) => page.locator("#connection-state");

test("connected: chip online, Home from the snapshot", async ({ page }) => {
  await mockSocket(page, (ws, request) => {
    if (request.type === "home.snapshot") snapshot(ws, request);
  });
  await page.goto(`${base()}/#/`);
  await expect(chip(page)).toHaveAttribute("data-status", "connected");
  await expect(page.locator("#health-ok")).toHaveText("42");
  await expect(page.locator("#connection-banner")).toHaveCount(0);
});

test("reconnecting: banner, stale snapshot, resubscribe from the last cursor", async ({ page }) => {
  const subscriptions: Body[] = [];
  let hold: (() => void) | null = null;
  let drop: (() => void) | null = null;
  await mockSocket(page, (ws, request, connection) => {
    if (request.type === "orchestration.subscribe") {
      subscriptions.push(request);
      if (connection === 0) {
        ws.send(JSON.stringify({ v: 1, id: request.id, type: "orchestration.subscribe", ok: true, kind: "events", cursor: "j-5", events: [{}] }));
      }
    }
    if (request.type === "home.snapshot") {
      if (connection === 0) {
        snapshot(ws, request);
        drop = () => void ws.close();
      } else {
        hold = () => snapshot(ws, request);
      }
    }
  });
  await page.goto(`${base()}/#/`);
  await expect(page.locator("#health-ok")).toHaveText("42");
  await expect.poll(() => drop !== null).toBe(true);
  drop!();
  await expect(chip(page)).toHaveAttribute("data-status", "reconnecting");
  const banner = page.locator("#connection-banner");
  await expect(banner).toContainText("Переподключение к серверу консоли");
  await expect.poll(() => subscriptions.length).toBe(2);
  expect(subscriptions[0]).not.toHaveProperty("cursor");
  expect(subscriptions[1]).toMatchObject({ cursor: "j-5" });
  await expect(banner).toContainText("Последний снимок устарел");
  await expect(page.locator("#health-ok")).toHaveText("42");
  await expect.poll(() => hold !== null).toBe(true);
  hold!();
  await expect(chip(page)).toHaveAttribute("data-status", "connected");
  await expect(banner).toHaveCount(0);
});

test("no server: the socket never opens and /health/live is unreachable", async ({ page }) => {
  await page.route("**/health/live", (route) => route.abort("connectionrefused"));
  await page.goto(`${base()}/#/`);
  await expect(chip(page)).toHaveAttribute("data-status", "no_server");
  await expect(page.locator("h1")).toHaveText("Нет связи с сервером консоли");
  await expect(page.getByRole("button", { name: "Повторить подключение" })).toBeVisible();
});

test("error: the server rejects a session without the cookie", async ({ page }) => {
  await page.goto(`${base()}/#/`);
  await expect(chip(page)).toHaveAttribute("data-status", "error");
  await expect(page.locator(".connection-page")).toContainText("Сервер отклонил сессию");
});

test("error: an ok:false reply, then an invalid snapshot", async ({ page }) => {
  let invalid = false;
  await mockSocket(page, (ws, request) => {
    if (request.type !== "home.snapshot") return;
    if (invalid) snapshot(ws, request, { ...FIXTURE, active_batches: "0" });
    else ws.send(JSON.stringify({ v: 1, id: request.id, type: "home.snapshot", ok: false, error: { code: "busy", message: "later" } }));
  });
  await page.goto(`${base()}/#/`);
  await expect(chip(page)).toHaveAttribute("data-status", "error");
  await expect(page.locator(".connection-page")).toContainText("busy");
  invalid = true;
  await page.getByRole("button", { name: "Загрузить заново" }).click();
  await expect(page.locator(".connection-page")).toContainText("снимок не прошёл проверку");
});

test("empty: a valid snapshot without checks", async ({ page }) => {
  await mockSocket(page, (ws, request) => {
    if (request.type === "home.snapshot") {
      snapshot(ws, request, { ...FIXTURE, health: { ok: 0, warn: 0, fail: 0, skipped: 0 }, problems: [], problems_total: 0 });
    }
  });
  await page.goto(`${base()}/#/`);
  await expect(chip(page)).toHaveAttribute("data-status", "empty");
  await expect(page.locator("h1")).toHaveText("Данных пока нет");
});
