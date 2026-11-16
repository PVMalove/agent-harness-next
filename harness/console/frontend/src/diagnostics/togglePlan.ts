/* What switching a feature changes: the state it takes, the state counts before and after and the
   `configuration-apply` request of the switch. The state rule is the kernel's
   (harness/console/kernel/features.py `_state`): a disabled feature is `disabled`; an enabled one
   is `not_working` with an `err` requirement, `partial` with a `warn` one and `working` otherwise.
   Pure functions over the snapshot; nothing is sent from here: the page hands the request to the
   configuration command panel, whose confirmation starts the existing confirmed write. */
import { draftRequest } from "../configuration/changes";
import type { Change } from "../configuration/changes";
import { stateCounts } from "../ws/features";
import type { Feature, FeatureState, FeaturesSnapshot } from "../ws/features";

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

/** A feature switch as the confirmed configuration write sends it: the one boolean change, the
    `configuration-apply` request built with the digests of the snapshot the user saw, what the
    confirmation says will happen and the before/after lines it shows. */
export interface TogglePlan {
  changes: Change[];
  request: string;
  reason: string;
  context: string;
}

type Translate = (text: string, values?: Readonly<Record<string, string | number>>) => string;

export const STATE_WORD: Readonly<Record<FeatureState, string>> = {
  working: "Работает",
  partial: "Частично",
  not_working: "Не работает",
  disabled: "Выключена",
};

/** The plan of switching `feature` to `enabled`; null for a feature without a boolean key. */
export function togglePlan(
  snapshot: FeaturesSnapshot,
  feature: Feature,
  enabled: boolean,
  t: Translate,
): TogglePlan | null {
  const toggle = feature.toggle;
  if (toggle === null) return null;
  const changes: Change[] = [{ file: toggle.file, path: [...toggle.path], value: enabled }];
  const name = t(feature.name);
  const byId = new Map(snapshot.features.map((item) => [item.id, item]));
  let reason: string;
  if (enabled) {
    const blockers = feature.requirements.filter((item) => item.state === "err");
    reason = blockers.length
      ? t("Включить «{name}». Заработает не сразу: {blockers}", {
          name,
          blockers: blockers.map((item) => (item.detail ? `${t(item.title)} (${item.detail})` : t(item.title))).join("; "),
        })
      : t("Включить «{name}». Функция начнёт использоваться при следующем запуске.", { name });
  } else {
    const dependents = feature.required_by
      .map((id) => byId.get(id))
      .filter((item): item is Feature => item !== undefined && item.state !== "disabled")
      .map((item) => t(item.name));
    reason = t("Выключить «{name}». {effect}", { name, effect: t(feature.off_effect) });
    if (dependents.length) reason += ` ${t("Перестанут работать: {names}", { names: dependents.join(", ") })}`;
  }
  const context = [
    `${toggle.file} › ${toggle.path.join(".")}: ${JSON.stringify(toggle.enabled)} → ${JSON.stringify(enabled)}`,
    `${name}: ${t(STATE_WORD[feature.state])} → ${t(STATE_WORD[stateAfter(feature, enabled)])}`,
  ].join("\n");
  const description = t(enabled ? "Включить функцию «{name}»" : "Выключить функцию «{name}»", { name });
  return { changes, request: draftRequest(changes, snapshot.config_digests, description), reason, context };
}
