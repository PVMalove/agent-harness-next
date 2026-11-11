/* One screen snapshot of a route: requested on mount and again after every reconnect, read to its
   end by the client and checked by `parse`. The last good value stays shown while a refresh runs. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useConsole } from "../useConsole";
import { screenKey } from "../ws/client";
import type { ScreenRequest } from "../ws/client";

export interface ScreenError {
  code: string;
  message: string;
}

export interface Screen<T> {
  data: T | null;
  cached: boolean;
  ageSeconds: number | null;
  error: ScreenError | null;
  loading: boolean;
  /** Ask again; `force` rebuilds the facts on the server instead of reading its cache. */
  refresh(force?: boolean): void;
}

export function useScreen<T>(request: ScreenRequest, parse: (value: unknown) => T | null): Screen<T> {
  const { client } = useConsole();
  const key = screenKey(request);
  // The request is rebuilt by every render; its key names it, so the latest one is kept.
  const latest = useRef(request);
  latest.current = request;
  const [data, setData] = useState<T | null>(null);
  const [cached, setCached] = useState(false);
  const [ageSeconds, setAge] = useState<number | null>(null);
  const [error, setError] = useState<ScreenError | null>(null);
  const [loading, setLoading] = useState(true);

  const ask = useCallback(
    (force: boolean) => {
      setLoading(true);
      client.requestScreen({ ...latest.current, force });
    },
    // The key changes exactly when the request does.
    [client, key],
  );

  useEffect(() => {
    setData(null);
    setError(null);
    const stopScreens = client.subscribeScreens((event) => {
      if (event.key !== key) return;
      setLoading(false);
      if (event.type === "screen-error") {
        setError({ code: event.code, message: event.message });
        return;
      }
      const parsed = parse(event.value);
      if (parsed === null) {
        setError({ code: "invalid", message: "" });
        return;
      }
      setError(null);
      setData(parsed);
      setCached(event.cached);
      setAge(event.ageSeconds);
    });
    const stopOpen = client.subscribe((event) => {
      if (event.type === "open") ask(false);
    });
    ask(false);
    return () => {
      stopScreens();
      stopOpen();
    };
    // `parse` is a module function of the route; the key names the request.
  }, [client, key, ask]);

  const refresh = useCallback((force = true) => ask(force), [ask]);
  return { data, cached, ageSeconds, error, loading, refresh };
}
