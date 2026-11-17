/* The screens that are not moved to the design system v3 keep the look of the old stylesheet
   (#1091 review): the shared base rules of the new sheets must not reach them. Measured on Home
   (the fixture of the fit spec) against the values the old sheet declares: `.btn` and `.chip` are
   var(--fs-1) = 11px, `.btn` is var(--fg), `.chip` is var(--muted), links in a button keep their
   hover underline. Fixtures only, over a mocked socket. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { WebSocketRoute } from "@playwright/test";

const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures", "home-snapshot.json"), "utf-8")) as Record<string, unknown>;

const send = (ws: WebSocketRoute, body: Record<string, unknown>) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

test("Home keeps the size and colour of buttons, chips and links of the old stylesheet", async ({ page }) => {
  await page.routeWebSocket("**/ws", (ws) => {
    ws.onMessage((message) => {
      const { id, type } = JSON.parse(String(message)) as Record<string, unknown>;
      if (type === "home.snapshot") send(ws, { id, type, cached: true, age_seconds: 3, snapshot: HOME });
      else if (type === "job.catalog" || type === "job.list") send(ws, { id, type, jobs: [] });
    });
  });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${process.env.CONSOLE_BASE_URL}/#/`);
  await expect(page.locator("#connection-state")).toHaveAttribute("data-status", "connected");
  const buttons = page.locator("main#content .btn");
  await expect(buttons.first()).toBeVisible({ timeout: 20000 });
  const look = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    const colour = (name: string) => {
      const probe = document.createElement("i");
      probe.style.color = root.getPropertyValue(name);
      document.body.append(probe);
      const value = getComputedStyle(probe).color;
      probe.remove();
      return value;
    };
    const read = (selector: string) =>
      [...document.querySelectorAll<HTMLElement>(`main#content ${selector}`)].map((element) => {
        const style = getComputedStyle(element);
        return { tag: element.tagName.toLowerCase(), size: style.fontSize, colour: style.color, margin: style.marginTop };
      });
    return { btn: read(".btn:not(.primary)"), chip: read(".chip:not(.on)"), fg: colour("--fg"), muted: colour("--muted"), fs1: root.getPropertyValue("--fs-1").trim() };
  });
  expect(look.btn.length).toBeGreaterThan(0);
  for (const item of look.btn) {
    expect(item.size, `${item.tag}.btn font size`).toBe(look.fs1);
    expect(item.colour, `${item.tag}.btn colour`).toBe(look.fg);
  }
  for (const item of look.chip) {
    expect(item.size, `${item.tag}.chip font size`).toBe(look.fs1);
    expect(item.colour, `${item.tag}.chip colour`).toBe(look.muted);
  }
});
