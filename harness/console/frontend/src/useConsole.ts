/* One console client per app: the connection state, the Home snapshot and the actions. */
import { createContext, createElement, useContext, useEffect, useMemo, useReducer, useState } from "react";
import type { ReactNode } from "react";
import { INITIAL, reduce } from "./connection";
import type { ConnectionState } from "./connection";
import { parseHomeEvents } from "./ws/homeEvents";
import type { HomeEvent, HomeSnapshot } from "./ws/types";
import { createConsoleClient } from "./ws/client";
import type { ConsoleClient, SocketFactory } from "./ws/client";

export interface ConsoleValue {
  state: ConnectionState;
  client: ConsoleClient;
  /** Grows with every Home snapshot reply, valid or not. */
  replies: number;
  /** Grows with every batch of orchestration events. */
  events: number;
  /** The last orchestration events seen since the console opened, newest first. */
  recentEvents: HomeEvent[];
  /** When the last valid Home snapshot arrived; null before the first one. */
  snapshotAt: Date | null;
  /** The last valid Home snapshot (kept while reconnecting); null before the first one. Other
      pages read its facts (project, harness, store, health) instead of asking again. */
  snapshot: HomeSnapshot | null;
}

/** How many orchestration events Home keeps for its list. */
const RECENT_EVENTS = 20;

const ConsoleContext = createContext<ConsoleValue | null>(null);

/** The client of the page's own server: ws://<host>/ws, probing /health/live on failure. */
export function browserClient(): ConsoleClient {
  return createConsoleClient({
    url: `ws://${window.location.host}/ws`,
    // The browser socket satisfies SocketLike; only its handler event types are wider.
    WebSocket: window.WebSocket as unknown as SocketFactory,
    timers: {
      setTimeout: (callback, ms) => window.setTimeout(callback, ms),
      clearTimeout: (handle) => window.clearTimeout(handle as number),
    },
    probeHealth: () =>
      fetch("/health/live", { cache: "no-store", credentials: "same-origin" }).then(
        () => true,
        () => false,
      ),
  });
}

export function ConsoleProvider({
  client: given,
  children,
}: {
  client?: ConsoleClient;
  children: ReactNode;
}) {
  const [client] = useState(() => given ?? browserClient());
  const [state, dispatch] = useReducer(reduce, INITIAL);
  const [replies, setReplies] = useState(0);
  const [events, setEvents] = useState(0);
  const [snapshotAt, setSnapshotAt] = useState<Date | null>(null);
  const [recentEvents, setRecentEvents] = useState<HomeEvent[]>([]);

  useEffect(() => {
    const unsubscribe = client.subscribe((event) => {
      dispatch(event);
      if (event.type === "snapshot") setSnapshotAt(new Date());
      if (event.type === "snapshot" || event.type === "invalid" || event.type === "error") {
        setReplies((count) => count + 1);
      }
      if (event.type === "events") {
        setEvents((count) => count + 1);
        const seen = parseHomeEvents(event.events);
        if (seen.length) setRecentEvents((kept) => [...seen.reverse(), ...kept].slice(0, RECENT_EVENTS));
      }
    });
    client.start();
    const stop = () => client.stop();
    window.addEventListener("pagehide", stop);
    return () => {
      window.removeEventListener("pagehide", stop);
      unsubscribe();
      client.stop();
    };
  }, [client]);

  const value = useMemo(
    () => ({ state, client, replies, events, recentEvents, snapshotAt, snapshot: state.snapshot }),
    [state, client, replies, events, recentEvents, snapshotAt],
  );
  return createElement(ConsoleContext.Provider, { value }, children);
}

export function useConsole(): ConsoleValue {
  const value = useContext(ConsoleContext);
  if (!value) throw new Error("useConsole outside ConsoleProvider");
  return value;
}
