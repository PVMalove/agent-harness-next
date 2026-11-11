/* Home against the real console server: launch URL, cookie, CSP and the live WebSocket. */
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;
const token = () => process.env.CONSOLE_TOKEN!;

const RU_BLOCKS = [/^Требует внимания$/, /^Контекст$/, /^Последние задачи \d+$/, /^Здоровье$/, /^Контур Harness$/];
const EN_BLOCKS = [/^Requires attention$/, /^Context$/, /^Recent tasks \d+$/, /^Health$/, /^Harness outline$/];

async function watch(page: Page) {
  const errors: string[] = [];
  const requests: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => requests.push(request.url()));
  await page.addInitScript(() => {
    const violations: string[] = [];
    (window as unknown as { __csp: string[] }).__csp = violations;
    document.addEventListener("securitypolicyviolation", (event) =>
      violations.push(`${event.violatedDirective} ${event.blockedURI}`),
    );
  });
  return { errors, requests };
}

const blocks = (page: Page) => page.locator("#home h2");

test("the launch URL opens Home over the cookie and switches language in place", async ({ page, context }) => {
  const seen = await watch(page);
  await page.goto(`${base()}/?token=${token()}`);
  await expect(page).toHaveURL(`${base()}/#/?lang=ru`);
  const cookies = await context.cookies(base());
  const port = new URL(base()).port;
  expect(cookies.map(({ name, httpOnly, sameSite, path }) => ({ name, httpOnly, sameSite, path }))).toEqual([
    { name: `console_token_${port}`, httpOnly: true, sameSite: "Strict", path: "/" },
  ]);

  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected", { timeout: 60000 });
  await expect(blocks(page)).toHaveText(RU_BLOCKS);
  await expect(page.locator("#home h1")).toHaveText("Состояние харнесса");
  await expect(page.locator("#home-context h3")).toHaveText([/Проект/, /Harness/, /Runtime store/, /Repo Map/, /Память/]);
  await expect(page.locator("#home-health h3")).toHaveText(["По областям", "Проверки"]);
  await expect(page.locator("#home")).not.toContainText("Контур Harness 2.0.0");
  await expect(page.locator("#health-ok")).toHaveText(/^\d+$/);
  await expect(page.locator("#problems-limit")).toContainText("Показано");
  await expect(page.locator("html")).toHaveAttribute("lang", "ru");

  await page.evaluate(() => {
    (window as unknown as { __marker: number }).__marker = 1;
  });
  await page.getByRole("button", { name: "EN · Английский язык" }).click();
  await expect(blocks(page)).toHaveText(EN_BLOCKS);
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.getByRole("navigation", { name: "Console sections" })).toBeVisible();
  await page.getByRole("button", { name: "Russian language" }).click();
  await expect(blocks(page)).toHaveText(RU_BLOCKS);
  expect(await page.evaluate(() => (window as unknown as { __marker?: number }).__marker)).toBe(1);

  expect(await page.evaluate(() => (window as unknown as { __csp: string[] }).__csp)).toEqual([]);
  expect(seen.errors).toEqual([]);
  expect(seen.requests.filter((url) => !url.startsWith(`${base()}/`))).toEqual([]);
  expect(page.url()).not.toContain(token());
});

test("a wrong token answers 401 and sets no cookie", async ({ page, context }) => {
  const response = await page.goto(`${base()}/?token=wrong`);
  expect(response?.status()).toBe(401);
  expect(await context.cookies(base())).toEqual([]);
});

for (const width of [1440, 390]) {
  test(`Home and its recent tasks fit ${width} px without horizontal overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${base()}/?token=${token()}`);
    await expect(blocks(page)).toHaveCount(5);
    const overflow = await page.evaluate(() => {
      const main = document.querySelector("main") as HTMLElement;
      const rows = [...document.querySelectorAll<HTMLElement>("#home-tasks .task-row")];
      return {
        page: document.documentElement.scrollWidth - window.innerWidth,
        main: main.scrollWidth - main.clientWidth,
        rows: rows.filter((row) => row.scrollWidth > row.clientWidth + 1).length,
      };
    });
    expect(overflow).toEqual({ page: 0, main: 0, rows: 0 });
  });

  test(`Home health areas stay inside their frame at ${width} px with a small bar`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${base()}/?token=${token()}`);
    await expect(page.locator("#home-areas .health-row").first()).toBeVisible();
    const fit = await page.evaluate(() => {
      const boxes = [".health-panel", ".health-areas-grid", ".health-row"].flatMap((selector) => [
        ...document.querySelectorAll<HTMLElement>(selector),
      ]);
      const panel = document.querySelector(".health-panel") as HTMLElement;
      const right = panel.getBoundingClientRect().right;
      const counts = [...document.querySelectorAll<HTMLElement>("#home-areas .health-count")];
      const bars = [...document.querySelectorAll<HTMLElement>("#home-areas .health-bar")];
      return {
        overflowing: boxes.filter((box) => box.scrollWidth > box.clientWidth + 1).length,
        outside: counts.filter((count) => count.getBoundingClientRect().right > right + 0.5).length,
        widest: Math.max(...bars.map((bar) => bar.getBoundingClientRect().width)),
        tallest: Math.max(...bars.map((bar) => bar.getBoundingClientRect().height)),
        compact: counts.every((count) => /^\d+✓ \d+⚠ \d+✖ \d+–$/.test(count.textContent ?? "")),
      };
    });
    expect(fit.overflowing).toBe(0);
    expect(fit.outside).toBe(0);
    expect(fit.widest).toBeLessThanOrEqual(240);
    expect(fit.tallest).toBeLessThanOrEqual(6);
    expect(fit.compact).toBe(true);
  });
}
