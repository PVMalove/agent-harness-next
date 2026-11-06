/* The jobs of a command panel: the section's catalog commands, the job list, the shown job and
   the last refusal. The server decides; this hook only forwards and remembers what it said. */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useConsole } from "../useConsole";
import type { JobCatalogRequest } from "../ws/protocol.gen";
import type { StartJob } from "../ws/client";
import type { CommandDescriptor, JobSummary, LocalJob } from "../ws/jobs";

export type Section = JobCatalogRequest["section"];

export interface JobRefusal {
  request: string;
  code: string;
  message: string;
}

export interface Jobs {
  /** null until the catalog reply arrives. */
  commands: CommandDescriptor[] | null;
  /** The running job that holds the mutation slot, if any. */
  busy: JobSummary | null;
  /** The job whose output the panel shows. */
  shown: LocalJob | null;
  refusal: JobRefusal | null;
  start(request: StartJob): void;
  cancel(jobId: string): void;
  show(jobId: string): void;
}

export function useJobs(section: Section): Jobs {
  const { client } = useConsole();
  const [commands, setCommands] = useState<CommandDescriptor[] | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [shown, setShown] = useState<LocalJob | null>(null);
  const [refusal, setRefusal] = useState<JobRefusal | null>(null);
  // The id of the shown job; "start" until the reply of a start names it.
  const shownId = useRef<string | null>(null);

  useEffect(() => {
    const stopJobs = client.subscribeJobs((event) => {
      if (event.type === "commands") {
        if (event.section === section) setCommands(event.commands);
      } else if (event.type === "jobs") {
        setJobs(event.jobs);
        const active = event.jobs.find((job) => job.mutating && job.phase === "running");
        if (active && shownId.current === null) {
          shownId.current = active.id;
          client.followJob(active.id);
        }
      } else if (event.type === "job") {
        const { job } = event;
        if (shownId.current === "start") shownId.current = job.id;
        if (job.id === shownId.current) setShown(job);
        setJobs((known) => {
          const { output: _output, ...summary } = job;
          return known.some((item) => item.id === job.id)
            ? known.map((item) => (item.id === job.id ? summary : item))
            : [...known, summary];
        });
      } else {
        if (event.request === "job.start" && shownId.current === "start") shownId.current = null;
        setRefusal({ request: event.request, code: event.code, message: event.message });
        if (event.code === "busy" && event.jobId) {
          // The console is busy with another mutation: show that job instead.
          shownId.current = event.jobId;
          client.followJob(event.jobId);
        }
      }
    });
    const stopOpen = client.subscribe((event) => {
      if (event.type === "open") client.requestCommands(section);
    });
    client.requestCommands(section);
    client.listJobs();
    return () => {
      stopJobs();
      stopOpen();
    };
  }, [client, section]);

  const start = useCallback(
    (request: StartJob) => {
      setRefusal(null);
      shownId.current = "start";
      client.startJob(request);
    },
    [client],
  );
  const cancel = useCallback(
    (jobId: string) => {
      setRefusal(null);
      client.cancelJob(jobId, true);
    },
    [client],
  );
  const show = useCallback(
    (jobId: string) => {
      shownId.current = jobId;
      const held = client.job(jobId);
      if (held) setShown(held);
      client.followJob(jobId);
    },
    [client],
  );

  const busy = useMemo(
    () => jobs.find((job) => job.mutating && job.phase === "running") ?? null,
    [jobs],
  );
  return { commands, busy, shown, refusal, start, cancel, show };
}
