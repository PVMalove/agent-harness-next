import { describe, expect, test } from "vitest";
import {
  diffPaths,
  parseConfiguration,
  parseHelp,
  parseOpenProject,
  parseUpdateDiff,
  parseUpdateHarness,
} from "../../harness/console/frontend/src/ws/projectScreens";

const OPEN = {
  repo: "/work/project",
  target: { repo: "/work/project", action: "adopt", capabilities: [], conflicts: ["AGENTS.md"], found: ["AGENTS.md"] },
  error: "",
  blockers: { "engineering-suite": [], "backend-orchestration": ["AGENTS.md"] },
  candidates: [{ path: "/work/project", installed: false, current: true, command: "harness console --web /work/project" }],
};
const STATE = {
  installed: true,
  installed_version: "2.0.0",
  capabilities: ["engineering-suite"],
  skills: 32,
  managed_files: 259,
  updated_at: "2026-11-05 10:00 UTC",
  orchestration: true,
};
const DOCUMENT = { tracker: { token: "••••••" } };
const CONFIGURATION = {
  schema_installed: true,
  orchestration_installed: false,
  transaction_pending: false,
  store_root: "/work/project/.harness/config_versions",
  files: {
    "project.json": { exists: true, digest: "d".repeat(64), document: DOCUMENT, error: "" },
    "orchestration.json": { exists: false, digest: "", document: {}, error: "" },
  },
  adapters: {
    preview: {
      adapters: [{ path: ".claude/settings.json", status: "outdated", problem: null }],
      capabilities: ["engineering-suite"],
      fingerprint: "f".repeat(64),
      text: "План",
      blocked: false,
      reason: "",
    },
    error: "",
  },
};

describe("the Open Project, Update Harness, Configuration and Help parsers", () => {
  test("Open Project accepts the server shape and refuses an extra key or a bad action", () => {
    expect(parseOpenProject(OPEN)).toEqual(OPEN);
    expect(parseOpenProject({ ...OPEN, target: null, error: "не Git-проект" })).toMatchObject({ target: null });
    expect(parseOpenProject({ ...OPEN, project: "/other" })).toBeNull();
    expect(parseOpenProject({ ...OPEN, target: { ...OPEN.target, action: "switch" } })).toBeNull();
    expect(parseOpenProject({ ...OPEN, candidates: [{ ...OPEN.candidates[0], command: 1 }] })).toBeNull();
    expect(parseOpenProject({ ...OPEN, blockers: { x: [1] } })).toBeNull();
  });

  test("Update Harness keeps the drift report as the server sent it; a diff is a path and its text", () => {
    const drift = { state: "drift", conflict: ["AGENTS.md"], seed_differing: [".harness/project.json"], added: 2 };
    const store = { authority: "file-ledger", schema: 3, generation: "g-1", audit_records: 4, cutover_at: null, reason: "", start_command: "" };
    const facts = { state: STATE, package_version: "2.0.1", drift, store, store_target_schema: 4 };
    expect(parseUpdateHarness(facts)).toEqual(facts);
    expect(parseUpdateHarness({ ...facts, store: null, store_target_schema: null })).toMatchObject({ store: null });
    expect(parseUpdateHarness({ ...facts, store: { ...store, schema: "3" } })).toBeNull();
    expect(parseUpdateHarness({ state: STATE, package_version: "2.0.1", drift })).toBeNull();
    expect(parseUpdateHarness({ ...facts, drift: null })).toMatchObject({ drift: null });
    expect(parseUpdateHarness({ ...facts, drift: [] })).toBeNull();
    expect(parseUpdateHarness({ ...facts, state: { ...STATE, skills: -1 } })).toBeNull();
    expect(diffPaths(drift)).toEqual(new Set(["AGENTS.md", ".harness/project.json"]));
    expect(diffPaths(null)).toEqual(new Set());
    expect(parseUpdateDiff({ path: "AGENTS.md", text: "+x" })).toEqual({ path: "AGENTS.md", text: "+x" });
    expect(parseUpdateDiff({ path: "AGENTS.md" })).toBeNull();
  });

  test("Configuration needs exactly the two configuration files", () => {
    expect(parseConfiguration(CONFIGURATION)).toEqual(CONFIGURATION);
    expect(parseConfiguration({ ...CONFIGURATION, adapters: { preview: null, error: "нет" } })).toMatchObject({
      adapters: { preview: null },
    });
    const { "orchestration.json": _dropped, ...one } = CONFIGURATION.files;
    expect(parseConfiguration({ ...CONFIGURATION, files: one })).toBeNull();
    expect(parseConfiguration({ ...CONFIGURATION, files: { ...CONFIGURATION.files, "x.json": CONFIGURATION.files["project.json"] } })).toBeNull();
    expect(parseConfiguration({ ...CONFIGURATION, transaction_pending: "no" })).toBeNull();
  });

  test("Help is a language, an intro and titled Markdown sections", () => {
    const help = { language: "ru", intro: "# Справка", sections: [{ title: "Разделы", markdown: "## Разделы" }] };
    expect(parseHelp(help)).toEqual(help);
    expect(parseHelp({ ...help, language: "de" })).toBeNull();
    expect(parseHelp({ ...help, sections: [{ title: "x" }] })).toBeNull();
  });
});
