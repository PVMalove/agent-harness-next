/* The activity of Home as it is now: the console counts it once per reply, so the ages of the
   last events are advanced by the time since that reply and the contour stops by itself. */
import { useEffect, useMemo, useState } from "react";
import type { HomeActivity } from "../ws/types";
import { ageActivity } from "./homeActivity";

/** How often the ages are advanced. */
export const AGING_TICK_MS = 5000;

export function useAgedActivity(activity: HomeActivity | null): HomeActivity | null {
  const [, setTick] = useState(0);
  const receivedAt = useMemo(() => Date.now(), [activity]);
  useEffect(() => {
    if (activity === null) return;
    const timer = window.setInterval(() => setTick((count) => count + 1), AGING_TICK_MS);
    return () => window.clearInterval(timer);
  }, [activity]);
  return activity && ageActivity(activity, (Date.now() - receivedAt) / 1000);
}
