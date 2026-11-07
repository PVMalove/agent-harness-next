/* The shell fills the browser window at every width: no margin, frame, rounding, shadow or width
   cap around it, and only the page area scrolls (#985). */
import { expect, test } from "@playwright/test";

const base = () => process.env.CONSOLE_BASE_URL!;

for (const [width, height] of [
  [1440, 900],
  [1920, 1080],
  [390, 844],
] as const) {
  test(`shell fills the window at ${width} px`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await page.goto(`${base()}/#/diagnostics`);
    const app = page.locator("#app");
    await expect(app).toBeVisible();

    const box = await app.boundingBox();
    expect(box).toEqual({ x: 0, y: 0, width, height });

    const style = await app.evaluate((element) => {
      const css = getComputedStyle(element);
      return { border: css.borderTopWidth, radius: css.borderTopLeftRadius, shadow: css.boxShadow };
    });
    expect(style).toEqual({ border: "0px", radius: "0px", shadow: "none" });

    const scroll = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }));
    expect(scroll).toEqual({ width, height });
  });
}
