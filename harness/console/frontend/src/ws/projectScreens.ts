/* The Open Project, Update Harness, Configuration and Help snapshots. ws-schema.json types the
   paged snapshot text as a string, so the shapes follow the kernel wire codecs by hand:
   kernel/open_project_snapshot.py, kernel/update_harness_snapshot.py,
   kernel/configuration_snapshot.py and kernel/help_text.py (`to_payload`). The parsers only check
   shapes; a configuration document arrives with every secret already masked by the server. */
import { exact, flag, isObject, list, nullable, string } from "./ledger";
import type { Check } from "./ledger";
import { harnessState } from "./screens";
import type { HarnessOverview } from "./screens";

export type SetupAction = "init" | "adopt" | "update";
export const SETUP_ACTIONS: readonly SetupAction[] = ["init", "adopt", "update"];

export interface ProjectTarget {
  repo: string;
  action: SetupAction;
  capabilities: string[];
  conflicts: string[];
  found: string[];
}

export interface Candidate {
  path: string;
  installed: boolean;
  current: boolean;
  /** `harness console --web <path>`: the server's own command line. */
  command: string;
}

export interface OpenProjectFacts {
  repo: string;
  target: ProjectTarget | null;
  error: string;
  blockers: Record<string, string[]>;
  candidates: Candidate[];
}

export interface UpdateHarnessFacts {
  state: HarnessOverview["state"];
  package_version: string;
  /** The `harness diff --json` report, or null when the harness is not installed. */
  drift: Record<string, unknown> | null;
}

export interface UpdateDiff {
  path: string;
  text: string;
}

export type JsonObject = Record<string, unknown>;

export interface ConfigFile {
  exists: boolean;
  digest: string;
  document: JsonObject;
  error: string;
}

export interface AdapterStatus {
  path: string;
  status: string;
  problem: string | null;
}

export interface AdapterPreview {
  adapters: AdapterStatus[];
  capabilities: string[];
  fingerprint: string;
  text: string;
  blocked: boolean;
  reason: string;
}

export const CONFIG_NAMES = ["project.json", "orchestration.json"] as const;
export type ConfigName = (typeof CONFIG_NAMES)[number];

/** One parameter of the Settings wizard (kernel/configuration_wizard.py): a real schema path. */
export interface WizardParam {
  group: string;
  file: ConfigName;
  path: string[];
  label: string;
  type: string;
  choices: (string | number | boolean)[];
  default: unknown;
  minimum: number | null;
  description: string;
}

export interface ConfigurationFacts {
  schema_installed: boolean;
  orchestration_installed: boolean;
  transaction_pending: boolean;
  store_root: string;
  files: Record<ConfigName, ConfigFile>;
  adapters: { preview: AdapterPreview | null; error: string };
  /** The wizard parameter catalog; absent or null from a server without it. */
  wizard?: WizardParam[] | null;
}

export interface HelpSection {
  title: string;
  markdown: string;
}

export interface HelpSections {
  language: "ru" | "en";
  intro: string;
  sections: HelpSection[];
}

const strings = list(string);
const target = exact({
  repo: string,
  action: (value) => (SETUP_ACTIONS as readonly unknown[]).includes(value),
  capabilities: strings,
  conflicts: strings,
  found: strings,
});
const openProject = exact({
  repo: string,
  target: nullable(target),
  error: string,
  blockers: (value) => isObject(value) && Object.values(value).every(strings),
  candidates: list(exact({ path: string, installed: flag, current: flag, command: string })),
});
const updateHarness = exact({ state: harnessState, package_version: string, drift: nullable(isObject) });
const updateDiff = exact({ path: string, text: string });
const configFile = exact({ exists: flag, digest: string, document: isObject, error: string });
const preview = exact({
  adapters: list(exact({ path: string, status: string, problem: nullable(string) })),
  capabilities: strings,
  fingerprint: string,
  text: string,
  blocked: flag,
  reason: string,
});
const configuration = exact({
  schema_installed: flag,
  orchestration_installed: flag,
  transaction_pending: flag,
  store_root: string,
  files: exact(Object.fromEntries(CONFIG_NAMES.map((name) => [name, configFile])) as Record<string, Check>),
  adapters: exact({ preview: nullable(preview), error: string }),
});
const help = exact({
  language: (value) => value === "ru" || value === "en",
  intro: string,
  sections: list(exact({ title: string, markdown: string })),
});

/** The facts of an open_project.snapshot reply, or null for any other shape. */
export function parseOpenProject(value: unknown): OpenProjectFacts | null {
  return openProject(value) ? (value as OpenProjectFacts) : null;
}

/** The facts of an update_harness.snapshot reply, or null for any other shape. */
export function parseUpdateHarness(value: unknown): UpdateHarnessFacts | null {
  return updateHarness(value) ? (value as UpdateHarnessFacts) : null;
}

/** The file diff of an update_harness.diff reply, or null for any other shape. */
export function parseUpdateDiff(value: unknown): UpdateDiff | null {
  return updateDiff(value) ? (value as UpdateDiff) : null;
}

const wizardParam = exact({
  group: string,
  file: (value) => (CONFIG_NAMES as readonly unknown[]).includes(value),
  path: list(string),
  label: string,
  type: string,
  choices: list((value) => ["string", "number", "boolean"].includes(typeof value)),
  default: () => true,
  minimum: (value) => value === null || typeof value === "number",
  description: string,
});

/** The facts of a configuration.snapshot reply, or null for any other shape. */
export function parseConfiguration(value: unknown): ConfigurationFacts | null {
  if (value === null || typeof value !== "object" || Array.isArray(value)) return null;
  const { wizard, ...facts } = value as Record<string, unknown>;
  if (!configuration(facts)) return null;
  if (wizard !== undefined && wizard !== null && !list(wizardParam)(wizard)) return null;
  return wizard === undefined ? (facts as unknown as ConfigurationFacts) : ({ ...facts, wizard } as unknown as ConfigurationFacts);
}

/** The guide of a help.snapshot reply, or null for any other shape. */
export function parseHelp(value: unknown): HelpSections | null {
  return help(value) ? (value as HelpSections) : null;
}

/** The drift report fields that list files (update_harness_snapshot.DIFF_FIELDS). */
export const DIFF_FIELDS = [
  "conflict",
  "package_changed",
  "added",
  "missing",
  "retired",
  "local_changed",
  "seed_differing",
] as const;

/** Every file the drift report lists in `DIFF_FIELDS` (`diff_paths`): the only files the server
    answers an update_harness.diff for. A bare counter names no file. */
export function diffPaths(drift: Record<string, unknown> | null): Set<string> {
  const found = new Set<string>();
  for (const field of DIFF_FIELDS) {
    const value = drift?.[field];
    if (Array.isArray(value)) for (const item of value) if (typeof item === "string") found.add(item);
  }
  return found;
}
