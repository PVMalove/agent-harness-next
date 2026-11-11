# Access and containers

The access plan describes worker permissions. A runtime or executor that proves support enforces it. Prepare the environment before approving a dispatch.

[Orchestration overview](../../backend-orchestration.md)

## Role access: `access_policy` and `runtime_access` {#role-access-access_policy-and-runtime_access}

The optional `access_policy` section sets the sandbox mode and the network and filesystem boundaries for the
worker. Without it, the brief keeps `inherit`, and `dispatch send` behaves as before. The section does not
require `assignment_plans`: the coordinator reads `access_policy` even in a config that contains only it.

```json
"access_policy": {
  "defaults": {"mode": "sandbox",
               "network": {"hosts": ["github.com"]},
               "filesystem": [{"resource": "checkout", "access": "write"},
                              {"resource": "git_common", "access": "write"},
                              {"resource": "cache", "access": "write", "path": "~/.cache/uv"}]},
  "roles": {"code-review": {"filesystem": [{"resource": "checkout", "access": "read"}]}},
  "operations": {"qa": {"network": {"hosts": []}}}
},
"extensions": {"runtime_access": "my_runtime:factory"}
```

- The components `mode` (`inherit`, `sandbox`, `unsandboxed`), `network.hosts`, and `filesystem`
  are selected independently of the role transport: `in-process` or `external`. The `container` component
  names the images of the built-in `docker` executor, and `environment` names the environment variables
  for its worker (see below). A plan without these components keeps its previous shape and its previous digest.
- A role override (`roles`) or an operation override (`operations`: `qa`, `git`, `publish`) replaces only the
  components it lists, and the rest come from `defaults`. The coordinator itself, not a worker, performs the operations `qa`, `git`, and
  `publish`, so only `defaults` and the
  operation's own override apply to them, and `roles` never does. The command itself selects the operation: `publish` for
  `--purpose publish`, `qa` for the `qa` role and `integration local-qa`, `git` for `integration refresh`
  and `integration resolve`. The section "QA, Git, and publish access" below describes what exactly is checked.
- `filesystem` names a resource: `checkout`, `git_common`, `shared_storage`, or `cache` (only `cache`
  requires `path`). The coordinator turns them into the real paths of the worktree, the shared Git directory, and the
  storage. A disk root and a whole home directory are rejected.
- Write permissions do not widen the brief's `write_paths`, the tool policy, or the native confirmations, and a
  read-only role gets no write access to `checkout`, `git_common`, or `shared_storage`.
- The coordinator records the resolved plan (`runtime_access`) in the brief, and its sha256 is part of the
  approval transition digest. Editing the config after `dispatch propose` does not widen the
  approved dispatch: new access requires a new `propose` and a new approval. Briefs without this
  field stay valid and are read as `inherit`.
- `dispatch preflight` shows the resolved plan and the reconciliation with `runtime_access`. User settings
  and the Git-checkout attestation do not count as proof of the current network and filesystem permissions.
- The `runtime_access` extension is a native implementation that observes the environment of this specific
  worker, applies the plan, and performs the handoff (`observe`, `apply`, `handoff`). The value `none` proves
  nothing, so without a native implementation the coordinator blocks `dispatch send` for a plan with
  `sandbox`, `unsandboxed`, hosts, or paths. The block happens before the work is handed over: there is no silent
  substitution or rollback to `inherit`, and nothing replaces the native confirmation. The harness
  ships one implementation, the built-in `docker` container executor (next section).
  Your project's module connects any other environment, like `my_runtime:factory` in the example above. While the
  project has not selected an implementation, any `access_policy`, even `mode: inherit`, blocks
  `dispatch send`. `dispatch status` keeps the worker status and evidence (`runtime_access`).

If `dispatch send` is stopped, the error names the cause. An implementation that names its own
blocker (as `docker` does) also passes its own remedy, and `dispatch preflight` shows its
observations in `runtime_access.verification.environment`. Otherwise the remedy is generic: prepare the named
hosts, paths, and mode in a new runtime session; connect a `runtime_access` implementation that
verifies the real worker launch; repeat `dispatch preflight`.

## Built-in `docker` container executor {#built-in-docker-container-executor}

The value `extensions.runtime_access: "docker"` selects the executor that ships with the harness:
`harness-runtime` starts each approved external dispatch in a separate Docker or
Podman container, and, when `access_policy.operations.qa.container` is set, also each QA command. The
executor contract is described in ADR 0025 and ADR 0022 (the "Implementation decisions" sections); this section
describes the shipped behavior. The English-language guide
[`harness/docs/container-executor.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/container-executor.md), which
`backend-orchestration` installs as `.harness/docs/container-executor.md`, gives the step-by-step target-project setup: prerequisites, building
images, caches, the allowlist, blockers, cleanup, and an example project adapter. Project implementations of
`module:factory` work as before, and a host process cannot register another implementation
under the name `docker`.

```json
"access_policy": {
  "defaults": {
    "mode": "sandbox",
    "container": {"worker_image": "harness-worker:local", "proxy_image": "harness-proxy:local"},
    "environment": ["LLM_API_KEY"],
    "network": {"hosts": ["llm-api.example.com"]}
  },
  "roles": {"developer": {"container": {"worker_image": "harness-worker:dev",
                                        "proxy_image": "harness-proxy:local"}}},
  "operations": {"qa": {"container": {"worker_image": "harness-worker:local"},
                        "network": {"hosts": []}}}
},
"extensions": {"runtime_access": "docker"}
```

- The `container` component contains `worker_image` (required), an optional `proxy_image`, and an
  optional `engine` (`docker` by default, or `podman`). A tag is a single image reference without
  spaces and without a leading `-`. A role or operation override replaces the whole component. The resolver
  takes tags only from the config and does not query the engine, the network, or the images. If `docker` is selected,
  `harness health` and the schema require `access_policy.defaults.container`; if there is no `defaults`, they require
  `access_policy.operations.qa.container`: otherwise the executor has nothing to run.
- The `environment` component is a list of unique environment variable names (`[A-Za-z_][A-Za-z0-9_]*`),
  never values. A role or operation override replaces the whole list. The plan stores the names in
  sorted order, so they are part of `plan_digest` and are pinned in the brief at approval:
  a name added to the config after `dispatch propose` is not given to that dispatch. The engine
  takes the values from the environment of `harness-runtime serve`, so after changing them you must restart the runtime.
  The values do not reach the config, brief, digest, argv, evidence, logs, error texts, or image layers.
  The agent's auth files are not mounted.
- A role named by `access_policy.defaults` or by its own `access_policy.roles.<role>` must have
  `transport: external` in `assignment_plans`: the executor wraps the external adapter's command and does not know
  the specific agent. The configuration loader reports such an in-process role as a warning, and
  `dispatch preflight` blocks it. A role that `access_policy` does not name keeps the legacy-inherit plan and
  still runs in-process, so container QA can be enabled with a single `operations.qa`. Without `defaults`, a role
  override must carry `container` itself; otherwise the loader reports that as well.
- A container worker cannot run `dispatch self-report` and `dispatch heartbeat`: the coordinator records
  them on the host from the container's stdout snapshot and the approved plan (ADR 0025, "Implementation
  decisions").
- The executor works only in the runtime store epoch and only on Linux: on the file ledger and outside
  Linux, `dispatch preflight` blocks it with a remedy (`harness-runtime migrate`, then
  `harness-runtime serve`).
- `dispatch preflight` asks the runtime (`container.observe`), and the runtime queries the engine read-only:
  `<engine> info` determines the mode (`rootful`, `rootless`, `unknown`, or `unavailable`),
  SELinux, and the daemon ID, and `<engine> image inspect` finds the local id of each image. On success,
  the evidence contains the engine, the mode, and the image ids. These cases give an explicit blocker with its own remedy: an unavailable
  engine, an engine whose mode cannot be determined from `info` (for example, a docker-compatible wrapper
  around another engine), a remote Podman, Docker with userns-remap, a missing image, the `in-process`
  transport, the `unsandboxed` mode, a non-empty `network.hosts` without `proxy_image`, a plan root
  that opens the engine socket or the runtime directory, contains a comma, a quote, or a newline,
  or overlaps `/harness-home`, an `environment` variable missing from the environment of `harness-runtime serve`,
  and a name that the executor sets itself (`HOME`, `GIT_CONFIG_COUNT`,
  `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`, and, with a non-empty `network.hosts`, also
  `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, and their lowercase variants). A blocker names only
  variable names. Preflight lists all blockers at once, and none of them creates a container.
  The runtime checks the variables once more before the launch: a variable that disappeared after approval rejects
  the send, and the dispatch stays `approved`.
- The harness does not build, download, or publish images. The `.harness/container/` payload contains
  an optional worker base image `Dockerfile.sandbox` (Debian slim with `git`, `curl`, `jq`,
  Python with `uv`, and Node.js), `Dockerfile.proxy`, and the egress-proxy code. The guide gives the `docker build` and
  `podman build` commands for both images; build or download a missing image
  yourself, then repeat `dispatch preflight` and `dispatch propose`.
- `dispatch propose` queries the engine and pins the image ids in the brief field `runtime_images`
  (`{"worker": "sha256:…", "proxy": "sha256:…" | null}`) next to the plan. Its sha256 is part of the
  transition digest (`runtime_images_sha256`) but not of `plan_digest`: the plan stays a function of the
  config, while the image under the same tag may change. `dispatch create` queries the engine once more,
  so an image rebuilt after `propose` changes the digest, and an explicit approval with the old digest is
  rejected. The field exists on the brief that `dispatch send` sends and on the container QA brief;
  publish and host QA do not get it. A brief without the field stays valid.
- `dispatch send` launches only the pinned ids. If an image disappears or changes after
  `propose`, the runtime rejects the launch with `approval_mismatch`, and the dispatch stays `approved`.
  The remedy is to restore the image with the pinned id, or to rebuild or download the image, cancel the dispatch
  (`dispatch cancel`), and repeat `dispatch propose`: an approval for a different image is not
  reused.
- `dispatch send` hands the supervised docker dispatch to the runtime's `execution.launch`; Python does not build the engine
  argv. The runtime creates an `--internal` network and a sidecar proxy (if `network.hosts` is not
  empty), then the worker `harness-<dispatch_id>` with `<engine> create --pull never`, and starts
  it with `<engine> start` without waiting (detached). The worker gets `--network none` or the internal network of the
  dispatch, the host user (rootful: `--user <uid>:<gid>`, rootless Podman:
  `--userns=keep-id`, rootless Docker: `--user 0:0`; with SELinux also `label=disable`),
  `--cap-drop ALL`, `no-new-privileges`, HOME on the tmpfs `/harness-home`, `safe.directory=*` through
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`, and the marker `HARNESS_EXECUTOR=docker`.
  Each name from `environment` of the pinned plan is passed as `--env NAME` without a value. Each
  plan root is mounted at the same absolute path: `read` is read-only, `write` is read-write;
  there are no other mounts. The labels `harness.dispatch`, `harness.repository`, `harness.plan_digest`,
  `harness.operation`, and `harness.execution` tie the objects to the dispatch and the execution. The
  `dispatch send` receipt (the `execution` field) names the engine and the container id.
- With a non-empty `network.hosts`, the worker reaches the outside only through the sidecar from the pinned
  proxy image: the variables `HTTP_PROXY` and `HTTPS_PROXY` (and their lowercase variants) point to it, and
  `NO_PROXY` leaves only loopback. The proxy passes HTTP and `CONNECT` to an exactly matching
  plan host on ports 80 and 443, refuses IP literals and names with a loopback, link-local,
  unspecified, or multicast address, and answers `403` to everything else. You must list the model API host
  explicitly; ssh-remote Git does not work through the proxy.
- A failed staged launch is at-most-once: the runtime rolls back the created objects from newest to oldest,
  the execution becomes `lost`, the operation becomes `failed`, the dispatch becomes `blocked`, and there is no relaunch.
- The adapter must lie inside the plan mounts and run in the image: `--entrypoint` receives the
  adapter path. For a `.py` adapter, the coordinator passes the host interpreter, which the image
  usually does not have, so an executable adapter is required. The project adapter sets the agent flags for running in a container
  by the `HARNESS_EXECUTOR` marker.

Limitations: a worker role sees `shared_storage` read-only and writes to the storage only in
`.sandboxes/scratch`, and the runtime socket is not mounted into the container. So the coordinator
commands that change the ledger (`dispatch self-report`, `dispatch heartbeat`, `report submit`) do not
run from the container: the worker puts the report in `report_staging_path`, and after it exits, the report is
recorded on the host with `report submit --file <path>`. The separate `--checkout` of the `code-review` role
is not mounted into the container: only the plan roots are mounted. The real smoke test in CI (job
`docker-smoke`) checks only rootful Docker; Podman (rootful and rootless), rootless Docker, and
SELinux hosts are confirmed only by the argv matrix and the scripted engine and are not verified on a live engine.

Container QA is enabled only by a set `access_policy.operations.qa.container`: then each
QA command is a separate foreground container `--rm --init` from the image pinned in the brief of the
QA dispatch, and the sidecar and the network live for the whole QA run. The mounts are narrowed: the clean-room directory for writing,
`git_common` read-only, and the plan's `cache`. The command's exit code goes into its stage evidence, and
ADR 0022 (the "Implementation decisions" section) classifies how it ends. Without
`operations.qa.container`, QA stays on the host, and the coordinator always performs the `git` and `publish` operations
in its own environment (the section "QA, Git, and publish access" below).

## Container worker status and cleanup {#container-worker-status-and-cleanup}

`harness-runtime`, not the coordinator, observes the execution of a container worker. The runtime reconcile
at startup, before every operation on an execution, and once per `dispatch_poll_interval_seconds`
compares the container with its labels: a live object is `running`, an exit with a code is `exited`, proven
absence is `lost`, and no response is `unknown`. `dispatch status` and `dispatch wait`
show this execution from the runtime and do not query the engine themselves.

When the worker finishes, the runtime saves its streams (`executions/<id>/stdout.log` and
`stderr.log`), records the exit code in the execution, and removes the worker, the sidecar, and the network in that
order; reconcile repeats a removal that did not finish. When `worker_execution_timeout_seconds` expires,
the runtime stops the container (`stop --time <stop_grace_seconds>`, then `kill`) and records
`stopped_by: "deadline"`. A running worker is not stopped without an explicit command: you can stop it
with an engine command (`docker stop harness-<dispatch_id>`). The container does not write to the ledger, so it
usually finishes before the report is recorded: the prepared report lies in `report_staging_path`,
and you record it with `report submit --file <path>`.

`harness cleanup <repo>` lists the remaining containers and networks of this repository through the runtime
(`container.objects`: the runtime filters them by its own label `harness.repository` and knows
the execution state of each object) and removes them through `container.remove` with the engines from
`access_policy`. The command follows the general rules: a preview without `--apply`, and `--apply`
applies a fresh plan and refuses if the plan has changed. The section runs only when
`.harness/orchestration.json` selects `extensions.runtime_access: "docker"`, and it is the same for `soft`
and `hard`. Cleanup skips a worker that is not stopped (with the hint `<engine> stop <name>`), objects of a
live execution, and a runtime response that cannot be obtained or read. The runtime does not
list or remove volumes: anonymous volumes from the image's `VOLUME` are left to `rm`.

## QA, Git, and publish access {#qa-git-and-publish-access}

The coordinator itself performs `qa run`, `integration local-qa`, `integration refresh`, `integration resolve`, and `dispatch publish`
in its own process. If the project has no `access_policy`, they work as
before (`legacy-inherit`). An environment denial still stops them, but with the ordinary Git or checkout
error classification. If `access_policy` exists, the coordinator checks the plan before the action:

- Which plan. For `qa run` and `dispatch publish`, the plan pinned in the approved brief. Editing the
  config after `dispatch propose` does not widen it. A brief without a plan stays `legacy-inherit`. For
  `integration local-qa`, `integration refresh`, and `integration resolve`, the `defaults` and the operation override
  (`qa`, `git`) from the live config. A role override applies to none of them.
- What is required. Write access to the shared Git directory and the shared `.harness` storage; write access to the directory of the
  clean-room checkout (`qa`) or to the batch worktree (`git`); the `cache` paths from `filesystem`. For `git`
  and `publish`, the remote must also be reachable. The coordinator checks the remote host against `network.hosts`
  when the mode is `sandbox` or the host list is non-empty. The plan must allow these requirements. A brief
  pinned before this version, without write access to Git and the storage, needs a new `dispatch propose`.
  The "read-only" requirement on the QA role does not extend to the coordinator operation.
- How it is checked. The coordinator actually tries to write (it creates and immediately deletes a file with a unique
  name) and reads the remote through `git ls-remote`. The `inherit` mode claims nothing about the environment itself.
  It only means that the coordinator works in its own environment. The coordinator accepts `sandbox` and
  `unsandboxed` only if a connected `runtime_access` implementation confirms them for the coordinator
  process (`observe` with the `in-process` transport). Without it, the mode counts as unsupported.
  The harness does not ship such an implementation and does not claim native support: the built-in `docker`
  confirms only the external worker and the container QA commands (`operations.qa.container`, the section
  above), and for the coordinator process it gives a blocker. Your project defines what exactly your
  implementation confirms.
- The result. A confirmed denial (`denied`), an unsupported mode (`unsupported`), and an unverified
  requirement (`unverified`, for example the path does not exist or the remote is unreachable) stop the
  action before the first change. The error names the resource, the path, and the reason. Its remedy is a concrete
  environment action. The structured evidence (`operation`, `status`, `plan_digest`, `checks`) is available
  in the attempt record: `qa-lane/attempts/*.json` for `qa run` (stage `access`) and the attempt record of
  `integration local-qa` (stage `access`, fields `access` and `remedy`). `dispatch publish` returns the
  evidence of a successful check in the `access` field.

What stays untouched on a denial. A `qa run` denial happens before queueing. The lease and the
queue entry are not created, the dispatch stays `approved`, and the previous evidence and attempts
are kept. The next run after the environment is fixed goes through without manual cleanup. Any failure of
`qa run` after the lease is taken (checkout creation, state change, evidence write, unexpected
exception) releases the lease, the queue entry, and the dispatch state. If the ledger is busy at that moment,
the rollback waits for the lock for up to 30 seconds (see ["Busy ledger, `report complete`, and `ledger release-lock`"](operations.md#busy-ledger-report-complete-and-ledger-release-lock)). A denial before `refresh`, `resolve`, and
`publish` happens before fetch, rebase, batch creation, and push. The rollback of a denied rebase returns the
worktree to the issue branch. The coordinator classifies a metadata or remote write denial during rebase and push
as an access error (`metadata-write-denied`, `remote-access-denied`,
`remote-unreachable`), not as a conflict or an ordinary Git failure. For the classification, the coordinator
runs Git with `LC_ALL=C`.

Diagnosis by message:

| Message | What to do |
| --- | --- |
| `qa access is denied: shared Git metadata (write …)` | Grant the coordinator process write access to the named shared Git directory in the sandbox or in the filesystem permissions. |
| `… clean-room checkout (write …)` or `could not prepare clean QA checkout storage` | Grant write access to `.harness/.sandboxes/runs/qa` (or the storage directory named in the error). |
| `… is unsupported` / `mode … is not provable for the coordinator` | Connect a `runtime_access` that confirms the mode for the coordinator, or set `mode: inherit` for the operation in `access_policy.operations`. |
| `host … is not in the approved network hosts` | Add the host to the operation's `network.hosts` and, for an operation with a brief, run `dispatch propose` again. |
| `remote … ` is unavailable (`unverified`) | Restore the connection to the remote from the coordinator environment and repeat the command. |
| `remote-access-denied` on push | Grant the process credentials write access to the remote issue branch; then repeat the command. |

Bypassing a block with a tool or a hook is not allowed. When something is blocked, stop and report
it.
