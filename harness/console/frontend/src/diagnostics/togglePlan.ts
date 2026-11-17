/* What switching a feature changes: the `configuration-apply` request of the switch, what its
   confirmation says and the before/after lines it shows. The state and requirements after the
   switch are the kernel's forecast (`toggle.state_after` and `toggle.requirements_after` of
   features.snapshot, computed in harness/console/kernel/features.py with the key flipped); nothing
   here derives a state. Pure functions over the snapshot; nothing is sent from here: the page hands
   the request to the configuration command panel, whose confirmation starts the existing
   confirmed write. */
import { draftRequest } from "../configuration/changes";
import type { Change } from "../configuration/changes";
import type { Feature, FeatureState, FeaturesSnapshot } from "../ws/features";

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

/** The plan of switching `feature` to `enabled`, the opposite of the `toggle.enabled` the forecast
    was computed for; null for a feature without a boolean key or for no change. */
export function togglePlan(
  snapshot: FeaturesSnapshot,
  feature: Feature,
  enabled: boolean,
  t: Translate,
): TogglePlan | null {
  const toggle = feature.toggle;
  if (toggle === null || toggle.enabled === enabled) return null;
  const changes: Change[] = [{ file: toggle.file, path: [...toggle.path], value: enabled }];
  const name = t(feature.name);
  const byId = new Map(snapshot.features.map((item) => [item.id, item]));
  let reason: string;
  if (enabled) {
    const issues = (level: "err" | "warn") =>
      toggle.requirements_after
        .filter((item) => item.state === level)
        .map((item) => (item.detail ? `${t(item.title)} (${item.detail})` : t(item.title)))
        .join("; ");
    reason =
      toggle.state_after === "not_working"
        ? t("Включить «{name}». Заработает не сразу: {blockers}", { name, blockers: issues("err") })
        : toggle.state_after === "partial"
          ? t("Включить «{name}». Будет работать частично: {issues}", { name, issues: issues("warn") })
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
    `${name}: ${t(STATE_WORD[feature.state])} → ${t(STATE_WORD[toggle.state_after])}`,
  ].join("\n");
  const description = t(enabled ? "Включить функцию «{name}»" : "Выключить функцию «{name}»", { name });
  return { changes, request: draftRequest(changes, snapshot.config_digests, description), reason, context };
}
