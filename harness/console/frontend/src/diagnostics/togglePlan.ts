/* What switching a feature changes: the state it takes and the state counts before and after.
   The state rule is the kernel's (harness/console/kernel/features.py `_state`): a disabled feature
   is `disabled`; an enabled one is `not_working` with an `err` requirement, `partial` with a `warn`
   one and `working` otherwise. Pure functions over the snapshot; nothing is sent from here. */
import { stateCounts } from "../ws/features";
import type { Feature, FeatureState } from "../ws/features";

/** The state `feature` takes when it is switched to `enabled`, from its current requirements. */
export function stateAfter(feature: Feature, enabled: boolean): FeatureState {
  if (!enabled) return "disabled";
  const levels = new Set(feature.requirements.map((item) => item.state));
  if (levels.has("err")) return "not_working";
  if (levels.has("warn")) return "partial";
  return "working";
}

/** The state counts of `features` once `feature` is switched to `enabled`. */
export function countsAfter(features: readonly Feature[], feature: Feature, enabled: boolean): Record<FeatureState, number> {
  return stateCounts(features.map((item) => (item.id === feature.id ? { ...item, state: stateAfter(item, enabled) } : item)));
}
