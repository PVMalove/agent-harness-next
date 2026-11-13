import { fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import { PageHeader, Panel, PipeTabs, RelatedTiles, StatusIcon, Summary, Switch } from "../../harness/console/frontend/src/ds";

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

  test("a disabled switch does not toggle", () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="x" disabled />);
    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe("StatusIcon", () => {
  test("each tone has its own shape and a hidden text: colour is not the only carrier", () => {
    const tones = ["ok", "warn", "err", "info", "wait"] as const;
    render(<div>{tones.map((tone) => <StatusIcon key={tone} tone={tone} label={`состояние ${tone}`} />)}</div>);
    const shapes = tones.map((tone) => {
      const node = screen.getByText(`состояние ${tone}`).parentElement!;
      expect(node.className).toContain(`ds-status-${tone}`);
      return node.querySelector("svg")!.getAttribute("data-icon");
    });
    expect(new Set(shapes).size).toBe(5);
    expect(screen.getByText("состояние ok").className).toBe("ds-sr");
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

  test("numbers the steps, keeps the number of a counted tab and moves with the arrow keys", () => {
    render(<Harness />);
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual(["1Первая", "7Вторая", "3Третья"]);
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
