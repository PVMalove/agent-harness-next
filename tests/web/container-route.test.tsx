import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, test } from "vitest";
import { App } from "../../harness/console/frontend/src/App";
import { LanguageProvider } from "../../harness/console/frontend/src/i18n";
import { TUI_ONLY } from "../../harness/console/frontend/src/routes/ContainerRoute";
import { createConsoleClient } from "../../harness/console/frontend/src/ws/client";
import { FakeSocket, ManualClock, screenPage } from "./fake-socket";
import FACTS from "./fixtures/container-route-facts.json";
import ROUTE from "./fixtures/container-route.json";

function answer(socket: FakeSocket) {
  const request = socket.request("container_route.view");
  act(() => socket.reply(screenPage(request.id, "container_route.view", JSON.stringify(ROUTE))));
  return request;
}

function renderRoute(route = "#/container-route?batch=b-887&role=developer") {
  window.location.hash = route;
  const client = createConsoleClient({
    url: "ws://127.0.0.1:1/ws",
    WebSocket: FakeSocket,
    timers: new ManualClock(),
    probeHealth: async () => false,
  });
  render(
    <LanguageProvider>
      <App client={client} />
    </LanguageProvider>,
  );
  const socket = FakeSocket.last;
  act(() => socket.open());
  return { socket, request: answer(socket) };
}

const content = () => document.querySelector("main#content")?.textContent ?? "";
const facts = FACTS as Record<string, string[]>;

describe("the Container route", () => {
  beforeEach(() => FakeSocket.reset());

  test("reads the view of the URL selection and shows the TUI facts on every tab", () => {
    const { request } = renderRoute();
    expect(request).toMatchObject({ batch: "b-887", role: "developer" });
    expect(request).not.toHaveProperty("force");
    expect(facts.common.filter((fact) => !content().includes(fact))).toEqual([]);
    for (const stage of ["setup", "preflight", "plan", "worker", "qa", "cleanup"]) {
      act(() => fireEvent.click(document.querySelector(`[role="tab"][data-stage="${stage}"]`) as HTMLElement));
      expect(document.querySelector('[role="tabpanel"]')?.getAttribute("data-stage")).toBe(stage);
      expect([stage, facts[stage].filter((fact) => !content().includes(fact))]).toEqual([stage, []]);
    }
    expect(document.querySelector('nav a[aria-current="page"]')?.getAttribute("href")).toBe("#/orchestration");
  });

  test("a tab only switches the pane; only the read is interactive and no command starts", () => {
    const { socket } = renderRoute();
    const sent = socket.sent.length;
    act(() => fireEvent.click(screen.getByRole("tab", { name: "✖ Plan / approval" })));
    expect(socket.sent).toHaveLength(sent);
    const propose = within(document.querySelector('#view-actions [data-action="propose"]') as HTMLElement);
    expect((propose.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
    expect(propose.getByText(TUI_ONLY)).toBeTruthy();
    act(() => fireEvent.click(screen.getByRole("tab", { name: "· Cleanup" })));
    const preview = document.querySelector('#view-actions [data-action="cleanup-preview"] button') as HTMLButtonElement;
    expect(preview.disabled).toBe(true);
    act(() => fireEvent.click(screen.getByRole("tab", { name: "✖ Preflight" })));
    const recheck = document.querySelector('#view-actions [data-action="recheck"] button') as HTMLButtonElement;
    expect(recheck.disabled).toBe(false);
    act(() => fireEvent.click(recheck));
    expect(socket.sent.filter((body) => body.type === "container_route.view")).toHaveLength(2);
    expect(socket.sent.filter((body) => body.type === "job.start" || body.type === "job.catalog")).toEqual([]);
  });

  test("a new selection is a new read of its own", () => {
    const { socket } = renderRoute("#/container-route");
    expect(socket.request("container_route.view")).toMatchObject({ batch: "", role: "developer", runtime: "" });
    act(() => fireEvent.change(screen.getByLabelText("batch"), { target: { value: "b-886" } }));
    act(() => fireEvent.change(screen.getByLabelText("role"), { target: { value: "qa" } }));
    act(() => fireEvent.click(screen.getByRole("button", { name: "Применить выбор" })));
    expect(socket.request("container_route.view")).toMatchObject({ batch: "b-886", role: "qa", runtime: "" });
    expect(window.location.hash).toBe("#/container-route?batch=b-886&role=qa");
  });
});
