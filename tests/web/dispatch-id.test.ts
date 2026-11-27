/* A dispatch UUID reads as `d` and its first eight hex digits across the web console, as in the
   TUI (`brand.short_dispatch`); an id of another form keeps its own. */
import { describe, expect, test } from "vitest";
import { shortDispatch } from "../../harness/console/frontend/src/dispatchId";

describe("shortDispatch", () => {
  test("cuts every dispatch UUID in a text", () => {
    expect(shortDispatch("dispatch-8e030c3f-336a-49db-b0a4-d8bc20022496")).toBe("d8e030c3f");
    expect(shortDispatch("architect: dispatch-b7fb27f0-e109-4359-a7d3-f9a12c2983ff, итог: reported")).toBe(
      "architect: db7fb27f0, итог: reported",
    );
  });

  test("keeps an id of another form", () => {
    expect(shortDispatch("dispatch-dev-887 · d-qa")).toBe("dispatch-dev-887 · d-qa");
  });
});
