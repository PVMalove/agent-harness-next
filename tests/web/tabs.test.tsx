/* WAI-ARIA Tabs pattern (WCAG 2.1 AA, 4.1.2): every tab controls an existing tabpanel, only the
 * selected tab is in the Tab order, arrow keys, Home and End move the selection. */
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, test } from "vitest";
import { TabList, TabPanel } from "../../harness/console/frontend/src/views/Tabs";

const TABS = [
  ["one", "Первая"],
  ["two", "Вторая"],
  ["three", "Третья"],
] as const;

function Harness() {
  const [tab, setTab] = useState<string>("one");
  return (
    <>
      <TabList id="demo" label="Демо" tabs={TABS} value={tab} onChange={setTab} />
      {TABS.map(([id, label]) => (
        <TabPanel key={id} id="demo" tab={id} value={tab}>
          <p>Панель {label}</p>
        </TabPanel>
      ))}
    </>
  );
}

describe("the shared Tabs component", () => {
  test("every tab names an existing tabpanel and the panel names its tab", () => {
    render(<Harness />);
    expect(screen.getByRole("tablist", { name: "Демо" })).toBeTruthy();
    for (const tab of screen.getAllByRole("tab")) {
      const panel = document.getElementById(tab.getAttribute("aria-controls") ?? "");
      expect(panel?.getAttribute("role")).toBe("tabpanel");
      expect(panel?.getAttribute("aria-labelledby")).toBe(tab.id);
    }
  });

  test("only the selected tab is focusable and only its panel is shown", () => {
    render(<Harness />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.getAttribute("tabindex"))).toEqual(["0", "-1", "-1"]);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Панель Первая")).toBeTruthy();
    expect(screen.queryByText("Панель Вторая")).toBeNull();
  });

  test("arrow keys, Home and End move focus and selection, wrapping at the ends", () => {
    render(<Harness />);
    const tab = (name: string) => screen.getByRole("tab", { name });
    fireEvent.keyDown(tab("Первая"), { key: "ArrowRight" });
    expect(tab("Вторая").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(tab("Вторая"));
    fireEvent.keyDown(tab("Вторая"), { key: "End" });
    expect(tab("Третья").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Третья"), { key: "ArrowRight" });
    expect(tab("Первая").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Первая"), { key: "ArrowLeft" });
    expect(tab("Третья").getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tab("Третья"), { key: "Home" });
    expect(tab("Первая").getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Панель Первая")).toBeTruthy();
  });
});
