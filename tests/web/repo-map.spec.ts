/* Manual mockup checklist is in docs/design/web-console-mockups/repo-map-acceptance.md.
   Synthetic facts are the TUI fixture; the real FastAPI process serves the production build. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import FACTS from "./fixtures/repo-map.json";

const base = () => process.env.CONSOLE_BASE_URL!;
const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures/home-snapshot.json"), "utf8")) as unknown;

async function open(page: Page, width: number) {
  const starts: Record<string, unknown>[] = [];
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((raw) => {
      const request = JSON.parse(String(raw)) as Record<string, unknown>;
      const reply = (body: Record<string, unknown>) => ws.send(JSON.stringify({ v: 1, id: request.id, type: request.type, ok: true, ...body }));
      if (request.type === "home.snapshot") reply({ cached: true, age_seconds: 0, snapshot: HOME });
      if (request.type === "repo_map.snapshot") reply({ cached: true, age_seconds: 0, snapshot_id: 1,
        text: JSON.stringify(FACTS), next: JSON.stringify(FACTS).length, done: true });
      if (request.type === "job.catalog") reply({ section: "repo-map", commands: [], cancel_reason: "Отмена останавливает команду; уже внесённые изменения не откатываются." });
      if (request.type === "job.list") reply({ jobs: [] });
      if (request.type === "job.start") {
        starts.push(request);
        reply({ job: { id: "map-1", command_id: "repo-map-build", mutating: true, phase: "completed", cursor: 1,
          done: true, truncated: false, returncode: 0, error: "", output: [{ channel: "stdout", text: JSON.stringify(FACTS.map) }] } });
      }
    });
  });
  await page.setViewportSize({ width, height: width > 600 ? 900 : 844 });
  await page.goto(`${base()}/#/repo-map`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  await expect(page.getByRole("button", { name: "pkg/core.py", exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready.then(() => undefined));
  return starts;
}

for (const width of [1440, 390]) {
  test(`Repo Map overview, tabs and confirmation at ${width} px`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const starts = await open(page, width);
    expect(await page.locator("#content").evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
    await page.getByRole("heading", { name: "Диагностики", exact: true }).scrollIntoViewIfNeeded();
    await page.getByRole("tab", { name: "Символы", exact: true }).click();
    await page.getByRole("searchbox", { name: "Поиск символа" }).fill("main");
    await expect(page.locator(".repo-symbol-row")).toHaveCount(1);
    await page.getByRole("tab", { name: "Связи", exact: true }).click();
    await expect(page.locator(".repo-link-row")).toHaveCount(4);
    await page.getByRole("tab", { name: "Настройки", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Память", exact: true })).toBeVisible();
    await page.getByRole("heading", { name: "Языки проекта", exact: true }).scrollIntoViewIfNeeded();
    await page.getByRole("button", { name: "Перестроить", exact: true }).first().click();
    await expect(page.getByRole("dialog")).toContainText("offline parser bundle");
    await page.getByRole("button", { name: "Отмена", exact: true }).click();
    expect(starts).toHaveLength(0);
    await page.getByRole("button", { name: "Перестроить", exact: true }).first().click();
    await page.getByRole("button", { name: "Собрать", exact: true }).click();
    await expect(page.locator(".command-output [role=status]")).toHaveText("Завершена");
    expect(starts).toHaveLength(1);
    expect(starts[0]).toMatchObject({ command_id: "repo-map-build", client: "browser", values: { commit: FACTS.head } });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("Repo Map switches ru/en in place and exports the actual map", async ({ page }) => {
  await open(page, 1440);
  await page.getByRole("button", { name: "EN · Английский язык" }).click();
  await expect(page.getByRole("tab")).toHaveText(["Browse", "Symbols", "Relations", "Settings"]);
  await page.getByRole("tab", { name: "Settings", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Memory", exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("repo-map-aaaaaaaaaaaa.json");
  const stream = await file.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  expect(JSON.parse(Buffer.concat(chunks).toString())).toEqual(FACTS.map);
});

test("the real server reports absent HEAD without offering a build", async ({ page }) => {
  await page.goto(`${base()}/?token=${process.env.CONSOLE_TOKEN!}`);
  await page.goto(`${base()}/#/repo-map`);
  await expect(page.getByText("HEAD не найден", { exact: true })).toBeVisible({ timeout: 60000 });
  await expect(page.getByRole("button", { name: "Перестроить", exact: true }).first()).toBeDisabled();
});
