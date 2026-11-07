/* Client state only: the server owns builds, output and the mutation slot. */
import { useEffect, useRef, useState } from "react";
import { useJobs } from "../commands/useJobs";
import { useConsole } from "../useConsole";
import { parseRepoMap } from "../ws/repoMap";
import type { RepoMap, RepoMapFacts } from "../ws/repoMap";

export function useRepoMap() {
  const { client, state } = useConsole();
  const jobs = useJobs("repo-map");
  const [facts, setFacts] = useState<RepoMapFacts | null>(null);
  const [built, setBuilt] = useState<RepoMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [buildError, setBuildError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const finished = useRef(new Set<string>());
  useEffect(() => {
    const stopMap = client.subscribeRepoMap((event) => {
      if (event.type === "facts") { setFacts(event.facts); setError(null); }
      else setError(event.code);
    });
    const stopOpen = client.subscribe((event) => {
      if (event.type === "open") client.requestRepoMap();
      if (event.type === "closed") setStarting(false);
    });
    client.requestRepoMap();
    return () => { stopMap(); stopOpen(); };
  }, [client]);
  useEffect(() => { if (jobs.refusal) setStarting(false); }, [jobs.refusal]);
  useEffect(() => {
    const job = jobs.shown;
    if (!job) return;
    setStarting(false);
    if (job.command_id !== "repo-map-build" || !job.done || finished.current.has(job.id)) return;
    finished.current.add(job.id);
    if (job.phase === "completed" && job.returncode === 0 && !job.truncated) {
      let map: RepoMap | null = null;
      try { map = parseRepoMap(JSON.parse(job.output.filter((f) => f.channel === "stdout").map((f) => f.text).join(""))); }
      catch { /* An invalid result cannot replace the last valid map. */ }
      if (map) setBuilt(map);
      else setBuildError("invalid_build");
    } else if (job.truncated) setBuildError("truncated");
    else if (job.phase === "failed" || (job.returncode !== null && job.returncode !== 0)) setBuildError("build_failed");
    client.requestRepoMap(true);
  }, [client, jobs.shown]);
  const start = (commit: string) => {
    if (state.status !== "connected" || facts?.head !== commit || starting || jobs.busy) return;
    setStarting(true); setError(null); setBuildError(null);
    jobs.start({ command_id: "repo-map-build", values: { commit } });
  };
  const map = facts?.map ?? (built?.commit === facts?.head ? built : null);
  return { client, state, jobs, facts, map, error: error ?? buildError, start, starting };
}
