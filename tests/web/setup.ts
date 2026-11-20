import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  try {
    localStorage.clear();
  } catch {
    /* Storage is optional. */
  }
  document.body.className = "";
  window.location.hash = "";
});
