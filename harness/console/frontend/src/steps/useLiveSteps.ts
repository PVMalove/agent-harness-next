/* The live step list of the console client. One store per client follows the feed for the
   client's lifetime, so leaving and reopening the route neither resubscribes nor loses steps. */
import { useEffect, useSyncExternalStore } from "react";
import { useConsole } from "../useConsole";
import type { ConsoleClient } from "../ws/client";
import { EMPTY_STEPS, reduceSteps } from "../ws/steps";
import type { StepsState } from "../ws/steps";

export interface LiveSteps extends StepsState {
  /** The code of the last refusal of the feed, if any. */
  error: string | null;
}

interface Store {
  get(): LiveSteps;
  subscribe(listener: () => void): () => void;
}

const stores = new WeakMap<ConsoleClient, Store>();

function storeOf(client: ConsoleClient): Store {
  const known = stores.get(client);
  if (known) return known;
  let value: LiveSteps = { ...EMPTY_STEPS, error: null };
  const listeners = new Set<() => void>();
  client.subscribeSteps((event) => {
    value =
      event.type === "steps-error"
        ? { ...value, error: event.code }
        : { ...reduceSteps(value, event), error: null };
    for (const listener of [...listeners]) listener();
  });
  const store: Store = {
    get: () => value,
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
  stores.set(client, store);
  return store;
}

export function useLiveSteps(): LiveSteps {
  const { client } = useConsole();
  const store = storeOf(client);
  useEffect(() => {
    client.followSteps();
  }, [client]);
  return useSyncExternalStore(store.subscribe, store.get);
}
