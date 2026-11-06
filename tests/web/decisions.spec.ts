/* Browser decisions from the real server read-model/catalog fixture. Mutations stay on the
   mocked WebSocket: no native approval reaches the host. */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import fixture from "./fixtures/decisions.json";
import home from "./fixtures/home-snapshot.json";

type Body = Record<string, unknown>;

async function open(page: Page, route: string, width: number) {
  const starts: Body[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    const reply = (request: Body, payload: Body) => ws.send(JSON.stringify({ v: 1, id: request.id, type: request.type, ok: true, ...payload }));
    ws.onMessage((message) => {
      const request = JSON.parse(String(message)) as Body;
      if (request.type === "home.snapshot") reply(request, { snapshot: home, cached: false, age_seconds: 0 });
      else if (request.type === "decisions.snapshot") reply(request, { snapshot: fixture.snapshot });
      else if (request.type === "job.catalog") reply(request, { commands: fixture.commands, cancel_reason: "Отмена останавливает команду; уже внесённые изменения не откатываются." });
      else if (request.type === "job.list") reply(request, { jobs: [] });
      else if (request.type === "job.start") starts.push(request);
    });
  });
  await page.setViewportSize({ width, height: width === 1440 ? 900 : 844 });
  await page.goto(`${process.env.CONSOLE_BASE_URL}/#/${route}`);
  await expect(page.getByRole("heading", { name: "Ожидающие решения" })).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return starts;
}

for (const width of [1440, 390]) {
  test(`pending decisions and native confirmation at ${width} px`, async ({ page }) => {
    const starts = await open(page, "orchestration", width);
    await expect(page.getByRole("heading", { name: "Решение по отчёту" })).toBeVisible();
    await expect(page.getByText("dispatch-aaaa")).toBeVisible();
    await expect(page.getByText('{"file_path": "example.py"}')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole("button", { name: "Разрешить запрос native permission" }).click();
    await expect(page.getByRole("dialog")).toContainText("request_sha256");
    expect(starts).toEqual([]);
    await page.getByRole("dialog").getByRole("button", { name: "Отмена", exact: true }).click();
    expect(starts).toEqual([]);
    await page.getByRole("button", { name: "Отклонить запрос native permission" }).click();
    await page.getByRole("dialog").getByRole("button", { name: "Подтвердить", exact: true }).click();
    expect(starts).toHaveLength(1);
    const native = fixture.snapshot.items.find((item) => item.kind === "native-permission")!;
    expect(starts[0]).toMatchObject({ command_id: "native-permission-deny", confirmed: true, values: native.values });
  });
}

test("publication requests the human choice and translates its confirmation", async ({ page }) => {
  const starts = await open(page, "publish", 1440);
  await page.getByRole("button", { name: "Английский язык" }).click();
  await expect(page.getByRole("heading", { name: "Pending decisions" })).toBeVisible();
  await page.getByLabel("batch-decide decision", { exact: true }).selectOption("fail");
  await page.getByLabel("batch-decide approved_by").fill("operator");
  await page.getByLabel("batch-decide approved_at").fill("2026-11-06T12:00:00Z");
  await page.getByRole("button", { name: "Batch decision", exact: true }).click();
  await expect(page.getByRole("dialog")).toContainText("Confirm decision");
  expect(starts).toEqual([]);
});
