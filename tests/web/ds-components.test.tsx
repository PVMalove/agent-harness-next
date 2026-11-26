import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import { Drawer, PageHeader, Panel, PipeTabs, RelatedTiles, StatusIcon, Summary, Switch } from "../../harness/console/frontend/src/ds";

describe("Switch", () => {
  test("is a role=switch button that toggles and reports the next value", () => {
    const onChange = vi.fn();
    const { rerender } = render(<Switch checked={false} onChange={onChange} label="Контейнеры" />);
    const sw = screen.getByRole("switch", { name: "Контейнеры" });
    expect(sw.tagName).toBe("BUTTON"); // Space and Enter come with a native button
    expect(sw.getAttribute("aria-checked")).toBe("false");
    fireEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
    rerender(<Switch checked onChange={onChange} label="Контейнеры" />);
    expect(screen.getByRole("switch").getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenLastCalledWith(false);
  });

  test("a disabled switch does not toggle, stays in the Tab order and names its reason", () => {
    const onChange = vi.fn();
    render(
      <>
        <Switch checked={false} onChange={onChange} label="x" disabled describedBy="why" />
        <p id="why">Недоступно в режиме seed</p>
      </>,
    );
    const sw = screen.getByRole("switch", { name: "x" }) as HTMLButtonElement;
    fireEvent.click(sw);
    expect(onChange).not.toHaveBeenCalled();
    expect(sw.disabled).toBe(false);
    expect(sw.getAttribute("aria-disabled")).toBe("true");
    expect(sw.getAttribute("aria-describedby")).toBe("why");
    sw.focus();
    expect(document.activeElement).toBe(sw);
  });
});

describe("StatusIcon", () => {
  test("each tone has its own shape and a hidden text: colour is not the only carrier", () => {
    const tones = ["ok", "warn", "err", "info", "wait", "off"] as const;
    render(<div>{tones.map((tone) => <StatusIcon key={tone} tone={tone} label={`состояние ${tone}`} />)}</div>);
    const shapes = tones.map((tone) => {
      const node = screen.getByText(`состояние ${tone}`).parentElement!;
      expect(node.className).toContain(`ds-status-${tone}`);
      return node.querySelector("svg")!.getAttribute("data-icon");
    });
    expect(new Set(shapes).size).toBe(6);
    expect(screen.getByText("состояние ok").className).toBe("ds-sr");
  });

  test("without a label the icon is decorative and the visible word is read once", () => {
    const { container } = render(<p><StatusIcon tone="ok" /> работает</p>);
    const icon = container.querySelector(".ds-status")!;
    expect(icon.getAttribute("aria-hidden")).toBe("true");
    expect(icon.querySelector(".ds-sr")).toBeNull();
    expect(container.textContent).toBe(" работает");
  });
});

describe("RelatedTiles", () => {
  test("link tiles carry href, button tiles call onSelect, and the panel counts them", () => {
    const onSelect = vi.fn();
    render(
      <>
        <RelatedTiles title="Связанные разделы" tiles={[{ key: "d", icon: "pulse", title: "Диагностика", count: 3, text: "Отчёт", href: "#/diagnostics" }]} />
        <RelatedTiles title="Читать дальше" onSelect={onSelect} tiles={[{ key: "keys", icon: "terminal", title: "Клавиши", text: "Переходы" }]} />
      </>,
    );
    expect(screen.getByRole("link", { name: /Диагностика/ }).getAttribute("href")).toBe("#/diagnostics");
    fireEvent.click(screen.getByRole("button", { name: /Клавиши/ }));
    expect(onSelect).toHaveBeenCalledWith("keys");
    expect(within(screen.getByText("Читать дальше").closest("section")!).getByText("1")).not.toBeNull();
  });
});

describe("PipeTabs", () => {
  function Harness() {
    const [value, setValue] = useState("a");
    return <PipeTabs id="t" label="Вкладки" value={value} onChange={setValue}
      tabs={[{ id: "a", label: "Первая" }, { id: "b", label: "Вторая", count: 7 }, { id: "c", label: "Третья" }]} />;
  }

  test("numbers the steps, shows a count as the badge beside the step number and moves with the arrow keys", () => {
    render(<Harness />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual(["1Первая", "2Вторая7", "3Третья"]);
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(tabs[0], { key: "ArrowRight" });
    expect(screen.getAllByRole("tab")[1].getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(screen.getAllByRole("tab")[1], { key: "End" });
    expect(screen.getAllByRole("tab")[2].getAttribute("aria-selected")).toBe("true");
    expect(screen.getAllByRole("tab")[0].getAttribute("tabindex")).toBe("-1");
  });
});

describe("Panel, PageHeader and Summary", () => {
  test("the panel has one header: title, count, meta and actions", () => {
    render(<Panel title="Файлы" count={5} meta="в снимке" actions={<button type="button">Сброс</button>}>тело</Panel>);
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Файлы");
    expect(screen.getByText("5").className).toBe("ds-chip");
    expect(screen.getByText("в снимке")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Сброс" })).not.toBeNull();
    expect(screen.getByText("тело")).not.toBeNull();
  });

  test("only a panel marked scroll tells the fit spec that its body may scroll", () => {
    render(<><Panel title="Список" scroll="list">а</Panel><Panel title="Факты">б</Panel></>);
    expect(screen.getByText("а").getAttribute("data-scroll")).toBe("list");
    expect(screen.getByText("б").hasAttribute("data-scroll")).toBe(false);
  });

  test("the summary shows the figures and a caption only when there is one", () => {
    render(
      <>
        <PageHeader title="Harness" subtitle="Установка" actions={<button type="button">Проверить</button>} />
        <Summary label="Сводка" stats={[{ label: "Версия", value: "1.5.1", caption: "Схема 6" }, { label: "Навыки", value: "—" }]}
          facts={<span>3 ошибки</span>} snapshot="Снимок 22:01" />
      </>,
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Harness");
    const summary = screen.getByLabelText("Сводка");
    expect(within(summary).getByText("1.5.1")).not.toBeNull();
    expect(within(summary).getByText("Схема 6")).not.toBeNull();
    expect(summary.querySelectorAll(".ds-stat-caption")).toHaveLength(1);
    expect(within(summary).getByText("Снимок 22:01")).not.toBeNull();
  });
});

describe("Drawer", () => {
  test("is a labelled dialog docked right with a close button, body and footer", () => {
    const onClose = vi.fn();
    render(
      <Drawer title="Кандидат" closeLabel="Закрыть" onClose={onClose} footer={<button type="button">Действие</button>}>
        <p>Содержимое</p>
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog", { name: "Кандидат" });
    expect(dialog.tagName).toBe("DIALOG");
    expect(dialog.className).toContain("ds-drawer");
    expect(dialog.hasAttribute("open")).toBe(true);
    expect(within(dialog).getByText("Содержимое").closest(".ds-drawer-body")).not.toBeNull();
    expect(within(dialog).getByRole("button", { name: "Действие" }).closest(".ds-drawer-foot")).not.toBeNull();
    fireEvent.click(within(dialog).getByRole("button", { name: "Закрыть" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("Escape closes it and the opener gets the focus back on unmount", () => {
    function Host() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Открыть
          </button>
          {open && (
            <Drawer title="Ящик" closeLabel="Закрыть" onClose={() => setOpen(false)}>
              <p>x</p>
            </Drawer>
          )}
        </>
      );
    }
    render(<Host />);
    const opener = screen.getByRole("button", { name: "Открыть" });
    opener.focus();
    fireEvent.click(opener);
    const dialog = screen.getByRole("dialog", { name: "Ящик" });
    // happy-dom's showModal() does not move the focus: move it into the dialog by hand, or the
    // focus would never leave the opener and the restore would go unchecked (review of PR #1186).
    within(dialog).getByRole("button", { name: "Закрыть" }).focus();
    expect(document.activeElement).not.toBe(opener);
    fireEvent(dialog, new Event("cancel", { cancelable: true }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  test("a click on the backdrop closes it: closedby=any, with a fallback where it is missing", () => {
    const onClose = vi.fn();
    render(
      <Drawer title="Ящик" closeLabel="Закрыть" onClose={onClose}>
        <p>Содержимое</p>
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog", { name: "Ящик" });
    expect(dialog.getAttribute("closedby")).toBe("any");
    // A click inside the panel keeps it open.
    fireEvent.click(screen.getByText("Содержимое"));
    expect(onClose).not.toHaveBeenCalled();
    // jsdom has no closedBy: the fallback reads a click on the dialog outside its box as the backdrop.
    const box = { top: 0, left: 600, width: 400, height: 800, right: 1000, bottom: 800, x: 600, y: 0, toJSON: () => ({}) };
    dialog.getBoundingClientRect = () => box as DOMRect;
    fireEvent.click(dialog, { clientX: 700, clientY: 100 });
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(dialog, { clientX: 100, clientY: 100 });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
