/* The features.snapshot reply of Diagnostics: the Harness feature registry
   (harness/console/kernel/features.py) with the configuration digests a toggle writes against.
   The types are those of protocol.gen.ts; the parser checks the shape the screen relies on and
   never recomputes a state: the state after a switch is the kernel's `toggle.state_after`. */
import type { FeaturePayload } from "./protocol.gen";

export type Feature = FeaturePayload;
export type FeatureState = Feature["state"];
export type FeatureCategory = Feature["category"];

export interface FeaturesSnapshot {
  features: Feature[];
  /** File name -> SHA-256 of the file the registry was read from; empty for a missing file. */
  config_digests: Readonly<Record<string, string>>;
  transaction_pending: boolean;
}

export const FEATURE_STATES: readonly FeatureState[] = ["working", "partial", "not_working", "disabled"];
export const FEATURE_CATEGORIES: readonly FeatureCategory[] = [
  "execution",
  "roles",
  "hooks",
  "context",
  "process",
  "publication",
  "capabilities",
  "platform",
];
const LEVELS = new Set(["ok", "warn", "err"]);
const FILES = new Set(["project.json", "orchestration.json"]);

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
const strings = (value: unknown): value is string[] =>
  Array.isArray(value) && value.every((item) => typeof item === "string");

const requirementList = (value: unknown): boolean =>
  Array.isArray(value) &&
  value.every((item) => isObject(item) && typeof item.title === "string" && LEVELS.has(String(item.state)) && typeof item.detail === "string");

function feature(value: unknown): value is Feature {
  if (!isObject(value)) return false;
  const { id, name, category, state, description, off_effect, depends_on, required_by, sources, requirements, settings, toggle } = value;
  if (![id, name, description, off_effect].every((item) => typeof item === "string")) return false;
  if (!FEATURE_CATEGORIES.includes(category as FeatureCategory) || !FEATURE_STATES.includes(state as FeatureState)) return false;
  if (!strings(depends_on) || !strings(required_by)) return false;
  if (!Array.isArray(sources) || !sources.every((item) => isObject(item) && typeof item.kind === "string" && typeof item.path === "string")) return false;
  if (!requirementList(requirements)) return false;
  if (
    !Array.isArray(settings) ||
    !settings.every(
      (item) =>
        isObject(item) &&
        FILES.has(String(item.file)) &&
        strings(item.path) &&
        typeof item.present === "boolean" &&
        (item.value === null || typeof item.value === "string"),
    )
  ) {
    return false;
  }
  return (
    toggle === null ||
    (isObject(toggle) &&
      FILES.has(String(toggle.file)) &&
      strings(toggle.path) &&
      typeof toggle.enabled === "boolean" &&
      FEATURE_STATES.includes(toggle.state_after as FeatureState) &&
      requirementList(toggle.requirements_after))
  );
}

/** The snapshot of a features.snapshot reply without its envelope, or null off the shape. */
export function parseFeatures(value: unknown): FeaturesSnapshot | null {
  if (!isObject(value)) return null;
  const { features, config_digests, transaction_pending } = value;
  if (!Array.isArray(features) || !features.every(feature)) return null;
  if (!isObject(config_digests) || !Object.values(config_digests).every((item) => typeof item === "string")) return null;
  if (typeof transaction_pending !== "boolean") return null;
  return {
    features,
    config_digests: config_digests as Record<string, string>,
    transaction_pending,
  };
}

/** The count of each state among `features` once `feature` takes the state the kernel forecast
    for its switch (`toggle.state_after`); the other states stay as the server reported them. */
export function countsAfterToggle(features: readonly Feature[], feature: Feature): Record<FeatureState, number> {
  const after = feature.toggle?.state_after ?? feature.state;
  return stateCounts(features.map((item) => (item.id === feature.id ? { ...item, state: after } : item)));
}

/** The count of each state among `features`. */
export function stateCounts(features: readonly Feature[]): Record<FeatureState, number> {
  const counts: Record<FeatureState, number> = { working: 0, partial: 0, not_working: 0, disabled: 0 };
  for (const item of features) counts[item.state] += 1;
  return counts;
}
