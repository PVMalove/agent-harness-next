/* The screens that are not moved to the design system v3 keep their markup. On a wide window their
   `.btn` and `.chip` take the design system's size and colours on purpose (UX review of #1296,
   item 18): var(--ds-fs-2), `.btn` var(--ds-fg), `.chip` var(--ds-muted). Measured on Home (the
   fixture of the fit spec). Fixtures only, over a mocked socket. */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { WebSocketRoute } from "@playwright/test";

const HOME = JSON.parse(readFileSync(resolve(__dirname, "fixtures", "home-snapshot.json"), "utf-8")) as Record<string, unknown>;

const send = (ws: WebSocketRoute, body: Record<string, unknown>) => ws.send(JSON.stringify({ v: 1, ok: true, ...body }));

test("Home buttons and chips take the size and colour of the design system", async ({ page }) => {
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
    const computed = (property: "color" | "fontSize", name: string) => {
      const probe = document.createElement("i");
      probe.style[property] = root.getPropertyValue(name);
      document.body.append(probe);
      const value = getComputedStyle(probe)[property];
      probe.remove();
      return value;
    };
    const read = (selector: string) =>
      [...document.querySelectorAll<HTMLElement>(`main#content ${selector}`)].map((element) => {
        const style = getComputedStyle(element);
        return { tag: element.tagName.toLowerCase(), size: style.fontSize, colour: style.color, margin: style.marginTop };
      });
    return {
      btn: read(".btn:not(.primary)"),
      chip: read(".chip:not(.on)"),
      fg: computed("color", "--ds-fg"),
      muted: computed("color", "--ds-muted"),
      size: computed("fontSize", "--ds-fs-2"),
    };
  });
  expect(look.btn.length).toBeGreaterThan(0);
  for (const item of look.btn) {
    expect(item.size, `${item.tag}.btn font size`).toBe(look.size);
    expect(item.colour, `${item.tag}.btn colour`).toBe(look.fg);
  }
  for (const item of look.chip) {
    expect(item.size, `${item.tag}.chip font size`).toBe(look.size);
    expect(item.colour, `${item.tag}.chip colour`).toBe(look.muted);
  }
});
