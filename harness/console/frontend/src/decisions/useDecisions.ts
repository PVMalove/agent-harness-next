import { useEffect, useState } from "react";
import { useConsole } from "../useConsole";
import type { DecisionsSnapshot } from "../ws/decisions";

/** Refresh reads on reconnect, lifecycle events, completed jobs and while native requests wait. */
export function useDecisions() {
  const { client } = useConsole();
  const [snapshot, setSnapshot] = useState<DecisionsSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [fresh, setFresh] = useState(false);
  useEffect(() => {
    const seen = new Set<string>();
    const stop = client.subscribeDecisions((event) => {
      if (event.type === "decisions") { setSnapshot(event.snapshot); setFresh(!event.snapshot.unavailable); setError(event.snapshot.error_code ?? null); }
      else { setError(event.code); setFresh(false); }
    });
    const stopConnection = client.subscribe((event) => {
      if (event.type === "open" || event.type === "events") client.requestDecisions();
      if (event.type === "closed") setFresh(false);
    });
    const stopJobs = client.subscribeJobs((event) => {
      if (event.type === "job" && event.job.done && !seen.has(event.job.id)) {
        seen.add(event.job.id);
        setFresh(false);
        client.requestDecisions();
      }
    });
    client.requestDecisions();
    const timer = window.setInterval(() => client.requestDecisions(), 5000);
    return () => { stop(); stopConnection(); stopJobs(); window.clearInterval(timer); };
  }, [client]);
  return { snapshot, error, fresh, refresh: () => client.requestDecisions() };
}
