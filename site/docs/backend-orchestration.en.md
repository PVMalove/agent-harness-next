# Backend orchestration guide

`backend-orchestration` is an opt-in capability for coordinated backend development by several
roles. It extends `engineering-suite`, but it is not an autonomous scheduler. The coordinator (a human or
a controlling session that the human designates) plans the batch and drives transitions under the configured
approval policy. Roles do not expand their scope, do not choose a model, and do not merge a pull request.

The [architecture](architecture/overview.md) page and ADR 0003 describe the capability's place in the system, its roles,
clean-room QA, and the local state store. This document
contains the detailed setup and launch procedure.

Use it when a task has independent backend boundaries or requires independent
verification. For an ordinary single task, the standard `engineering-suite` pipeline is enough.

## Rule ownership

`/implement` is a short coordinator contract, not a second copy of the procedure. It keeps the order of
the handoff `architect → developer → code-review → qa → publish`, approval by policy, model self-report,
and the watchdog.

The installed modules own the full rules: `playbook.md` owns lifecycle, authority,
the immutable brief, evidence, parallelism, and metrics; `roles/` owns the boundaries and proof of each role;
`coordinator.py` owns verifiable transitions and audit; the project adapter owns transport only. If they
conflict, this module-owned guidance and the immutable records take priority over the runtime adapter
or the short skill.

Tokens are only observable provider or runtime telemetry with a source and a missing-data note.
A role self-report, a completion report, and a coordinator estimate are not token telemetry. They must not
fill in a missing value.

## What gets installed

When you select the capability, the CLI copies these items into the project:

- `.harness/orchestration/roles/` — portable role manifests and the shared contract;
- `.harness/orchestration/playbook.md` — the full lifecycle, handoff, and parallelism rules;
- `.harness/orchestration/pilot.md` — the form for observing the first batches;
- `.harness/orchestration/coordinator.py` — a runtime-neutral CLI for batch, approval, dispatch, and report;
  the file itself is only a facade: argument parsing, routing, and JSON output. The lifecycle lives next to it in
  `core/` (constants, configuration, git, workspace), `ledger/` (persistence), and `workflow/`
  (one module per batch stage: planning, brief, delivery, decision, report);
- `.harness/orchestration.json` — project-owned configuration of assignments, the write ceiling, and checks.

Coordinator state, immutable briefs and reports, and sanitized QA artifacts are created locally in
`.harness/orchestration/state/`. The contents of this directory are gitignored and are not the project's
source code. They remain local evidence until the coordinator explicitly decides that cleanup is safe.
A role and an adapter do not delete batch history.

The internal protocol has fixed languages. Agent-to-agent handoff, checkpoint, state evidence, and
free text in `.harness/orchestration/state/` are written in English. The completion report for the
coordinator is written in Russian and contains `"report_language": "ru"`. Commands, paths, SHAs,
test names, and quotations of source requirements are not translated. This reduces ambiguity between
different runtimes and keeps the report readable for a human.

Before the first English handoff, the coordinator and workers must read the shared contract
[Technical English](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/technical-english.md). It is also available through the playbook and `roles/_common.md`.
The source itself describes its scope, language exceptions, and review examples. The current rules on
language, authority, scope, evidence binding to the candidate SHA, and human approval remain in force.

The manifest defines the role mode (`write` or `read-only`), the capability, and the risk triggers. The project
config selects the agent and fallback at the provider profile level. It selects `model` and `effort` separately
for each role in its assignment plan, together with the write ceiling, the parallelism budget, and the
verification commands. The config cannot weaken the manifest's boundaries. Secret values are stored neither in the config,
nor in a brief, nor in a report.

## 1. Enabling

For a new git repository, select only `backend-orchestration`. The CLI resolves the dependency on
`engineering-suite` automatically.

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --project-type software \
  --stack python \
  --capability backend-orchestration \
  --base-branch main \
  --language ru \
  --qa-gate-command "python -m pytest"
```

In PowerShell, replace `python3` with `python` and `\` with a backtick. Do not pass
`engineering-suite` separately: the capability already includes it through `extends`.

To enable it in an existing project that already has the harness, first inspect the local drift, then
update the selected capability set:

```bash
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository --capability backend-orchestration
```

`update` does not overwrite modified managed files without an explicit flag. `--force-managed-files`
updates only the managed snapshot and keeps seed documents, `--force-seed-files` overwrites
only the seed, and `--force` combines both actions. After any enabling or configuration change,
run:

```bash
python3 harness/bin/harness.py health /path/to/repository
```

## 2. Configuring `.harness/orchestration.json`
The config is **optional**. Without it, the coordinator works on defaults: the role write ceiling is the whole
repository (the batch `--allowed-path` provides the boundary), `verification_commands` come from
`qa_gate_commands` in `.harness/project.json`, `concurrency_budget` is 1, and the role `model`/`effort`
come from the calling session (`dispatch create --model <model> --effort <effort>`). In
this mode the transport is always `in-process`; there are no provider profiles, so there is nothing to start an external worker with.
`harness health` accepts such a project. You need the config when the project requires a narrower write
ceiling, different models per role, an external transport, or a parallelism budget above one. The reference
of all fields with their defaults is [`.harness/orchestration/README.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/README.md).

By default, start the coordinator session with `medium` effort, and also choose `medium` for the architect in the
assignment plan. A higher effort is not the default for every ticket: it requires an explicit decision by the
developer for a named question that is hard to reverse.

`init` creates the config as a copy of the managed example `.harness/orchestration.example.json`. The example
contains the provider profiles `claude-profile` and `codex-profile`, assignments of all eight roles to two
runtimes (`default_runtime: claude`, `transport: in-process`), a write ceiling for the whole repository,
`concurrency_budget: 5`, and `approval_policy: auto` with `human_approval_gate: trusted` and
`worker_attestation_required: true`. The models and efforts in the example are a guide; replace them with your own.
The check lists in the example are empty because the commands depend on the stack. Enter the real project
checks in `verification_commands`, `developer_verification_commands`, `review_verification_commands`
and, so that QA preparation and the bounded infrastructure retry work, in `qa_preparation`,
`qa_environment_probes`, and `qa_project_file_checks`. If you do not need the fully automatic
path, choose a different `approval_policy`. To choose a different runtime for a role, pass
`--runtime` to `dispatch create` or change `default_runtime`. The CLI updates the example
on every `update`/`adopt`, but it never updates your `.harness/orchestration.json`. Carry new fields and
values over from the example by hand. Adjust the provider profiles, the role `write_paths`, the assignment
for **every** role you use, and the project checks to fit your project. Always assign `code-review`.
The validator requires it when the config has assignments: it is a mandatory gate for high-risk work.

Below is a minimal complete example; the model and effort names belong to a specific project.
The fallback is set in the provider profile. The assignment plan of each role contains named
runtime sets (`codex`, `claude`, and so on), and each of them must have `profiles`, `model`, and
`effort`. The selected runtime is recorded in the immutable brief and does not change on profile failover.

If a role has several runtimes, set `default_runtime` in its assignment plan; otherwise every
`dispatch create` must pass `--runtime` explicitly: there is no hidden fallback to Codex. For example, if
a project always wants to run review through Claude, put
`"default_runtime": "claude"` next to `runtimes`. The example also enables `"worker_attestation_required": true`: before any
work, the worker confirms its actual Git worktree, branch, and SHA. Legacy projects may
enable this field gradually. `approval_policy: auto` requires `worker_attestation_required: true` and
`human_approval_gate: trusted`; config validation and `harness health` reject any other combination.

```json
{
  "$schema": "./orchestration/orchestration.schema.json",
  "provider_profiles": {
    "backend-primary": {
      "capabilities": [
        "backend-development",
        "architecture-analysis",
        "independent-verification",
        "database-migrations",
        "messaging-integration",
        "conflict-resolution",
        "code-review"
      ],
      "fallback": ["backend-fallback"],
      "known_limitations": ["Проект сам фиксирует доступные runtime limits"]
    },
    "backend-fallback": {
      "capabilities": [
        "backend-development",
        "architecture-analysis",
        "independent-verification",
        "database-migrations",
        "messaging-integration",
        "conflict-resolution",
        "code-review"
      ],
      "fallback": [],
      "known_limitations": ["Использовать только после безопасного отказа primary"]
    }
  },
  "assignment_plans": {
    "architect": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-architect-model", "effort": "medium"}, "claude": {"profiles": ["backend-claude"], "model": "project-architect-claude-model", "effort": "medium"}}},
    "developer": {"write_paths": ["services/payments/**"], "transport": "external", "runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-developer-model", "effort": "xhigh"}, "claude": {"profiles": ["backend-claude"], "model": "sonnet", "effort": "xhigh"}}},
    "database-migrations": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-migration-model", "effort": "xhigh"}, "claude": {"profiles": ["backend-claude"], "model": "project-migration-claude-model", "effort": "xhigh"}}},
    "messaging-integration": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-messaging-model", "effort": "high"}, "claude": {"profiles": ["backend-claude"], "model": "project-messaging-claude-model", "effort": "high"}}},
    "conflict-resolver": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-resolver-model", "effort": "high"}, "claude": {"profiles": ["backend-claude"], "model": "project-resolver-claude-model", "effort": "high"}}},
    "qa": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-qa-model", "effort": "medium"}, "claude": {"profiles": ["backend-claude"], "model": "project-qa-claude-model", "effort": "medium"}}},
    "code-review": {"runtimes": {"codex": {"profiles": ["backend-primary"], "model": "project-review-model", "effort": "high"}, "claude": {"profiles": ["backend-claude"], "model": "project-review-claude-model", "effort": "high"}}}
  },
  "concurrency_budget": 1,
  "developer_verification_commands": ["python -m pytest tests/unit"],
  "review_verification_commands": ["python -m pytest tests/unit"],
  "verification_commands": ["python -m pytest"]
}
```

`transport` is an optional assignment-plan field that you choose for each role separately.
`in-process` (the default) runs the role as a subagent of the current coordinator session in the worktree of the
same batch. Both variants receive the same immutable brief, must pass the model self-report, and
must return a completion report under the shared rules, so the coordinator logic does not depend on the transport.
`harness health` checks that the value is valid. For an external worker, set
`"transport": "external"` explicitly and provide the project adapter.

For `in-process`, `dispatch send` only records the handoff, and as its next action the coordinator
immediately starts the subagent against the already immutable brief — before any search for old reports, templates, or
configuration. The architect gathers only targeted evidence for the decision: its brief contains no verification
commands, and its report contains an empty `checks_run`. Clean-room QA runs the full set of
`verification_commands`, and the developer receives `developer_verification_commands`. This field is optional; without
it the compatible mode stays in effect, and the developer receives the full list. Put fast
task-scoped checks in it, and put the independent full gate in `verification_commands`. If
`developer_verification_commands` is not set, `harness health` warns that the developer will
run the full gate on every iteration. The optional `review_verification_commands` controls
only code-review; without it, review receives the full list. Code-review runs each
received command through `test_summary.py`; the report keeps the original command and a bounded summary, and
the sanitized full log is available only for a failed check.

The optional `verification_profiles` refines these two lists by batch area:

```json
"verification_profiles": [
  {
    "paths": ["harness/console/**", "tests/console/**"],
    "developer": ["make lint", "pytest -q -n 8 tests/console"],
    "review": ["make lint", "pytest -q -n 8 tests/console"]
  }
]
```

`batch create` takes the first profile whose `paths` cover all the batch `--allowed-path` values, and
freezes its `developer` and `review` lists in place of `developer_verification_commands` and
`review_verification_commands`. If no profile covers the whole batch, or the key is absent,
the batch receives the general lists. A brief is checked against the profile of its area, and clean-room QA always
runs `verification_commands`.

The optional `retry_verification` speeds up a developer retry:

```json
"retry_verification": {"lint": ["make lint"], "test_command": "pytest -q -n 8"}
```

A developer-retry brief receives the `lint` commands and a single `test_command`, to which the
`related_tests` paths of its Context Package are appended (`max_related_tests` limits their number). The first
developer dispatch, code-review, and QA do not change. If there are no related tests or the key is not set,
the retry runs the ordinary developer commands. The value is frozen in the batch at `batch create`, and
the retry report, like any other, must list exactly the brief's commands in `checks_run`. Test
paths are escaped under POSIX shell rules.

The write boundary is not a hint. A write role changes only the paths explicitly pinned to the batch
(`--allowed-path`, which go into the brief's `write_paths`), and only inside the role ceiling that the role's
`write_paths` in the assignment plan sets (by default the whole repository). The coordinator does not create a batch
wider than the ceiling, and it checks the brief and the completion report against the batch scope. The model must be a CLI alias
or an ID without spaces (for example, `sonnet`), not a display name.

Each batch has its own issue branch and worktree, and `concurrency_budget` limits the number of
simultaneously active batches. Raise it only after an
explicit coordinator decision. Run `harness health` first: it checks the JSON, that the profiles exist, capability compatibility, the fallback, and the
`code-review` mode.

### Context budget and preflight

A new batch is not created until `batch preflight` confirms a bounded scope. `batch create`
calls it automatically. Specify the expected changed paths, one bounded context or service, and a
conservative diff size. Split values above the project policy first through `/to-tickets`;
do not pass them to the architect as a discovery task:

```bash
python .harness/orchestration/coordinator.py --repo . batch preflight \
  --ticket '#123' --allowed-path 'services/payments/**' \
  --definition-of-done 'Добавить валидацию платежа' \
  --expected-file services/payments/validation.py \
  --expected-service payments --expected-changed-lines 120
```

Without `preflight_policy`, the coordinator limits the DoD (5), dependencies (3), files (12), services (1),
diff (800 lines), and expected context (80k tokens). The `orchestration.example.json` example sets
8/5/25/2/2000/150k. The project tunes these values through `preflight_policy`.
`context_package_policy` uses a conservative token estimate and reserves room for the system
instructions. The byte limit remains only for diagnostic compatibility. `symbol_graph_depth`
(2 by default) in this policy controls the import-graph depth for *every* automatic
Context Package. This also covers the packages that the coordinator builds itself at `dispatch create` for
the architect, developer, and code-review, not only a manual `context-package register`.
`--max-package-tokens` on `context-package register` is only a stricter ceiling for a single
package. The coordinator rejects a value above the configured `context_package_policy.max_tokens`
with an error and does not apply it silently. Only an edit to `context_package_policy.max_tokens`
in the project config raises the limit, and it must be deliberate and must pass `harness health`. `max_related_tests` (25 by default)
is a separate fail-loud safeguard. If the import graph of the starting files touches more
related_tests than this limit, the package build ends with `ContextPackageError`. It does not silently
drag half of the test suite into the token estimate. `--max-related-tests` overrides the limit for
a single manual `context-package register`. All role sessions on the same base/candidate
reuse one immutable shared Context Package. A new package is built only for a new
candidate. `continuation_policy` (2 continuations, at most one of them an automatic 429 resume) and
`retry_policy` (one developer retry) keep the loops finite. `harness health` checks all the fields.
Effort accepts only the documented levels (`none`…`ultra`).

### Tool policy and context budget in the brief

Besides model/effort and `verification_commands`, every immutable brief explicitly records two values
selected from `.harness/orchestration.json`, not from chat:

- `allowed_tools` — the working tool set of this specific role. Without `tool_policy`, the default comes from the
  manifest mode: `read-only` (architect, code-review, qa) gets `Read`, `Grep`, `Glob`, `Bash`, without
  `Edit`/`Write`; `write` gets the same plus `Edit` and `Write`. A read-only role works from the Context Package,
  does not scan the whole repository, and does not load irrelevant tools. The list is the role's working set,
  not a deny-list: the brief does not disable the runtime's global tools.
- `context_budget` — tokens from `adaptive_continuation_policy.context_limit` (150000 by default):
  the same threshold from which `context_advisory` is computed. `dispatch create` (and `--propose`)
  rejects an automatic Context Package if its `estimated_tokens` is above this budget. This holds
  even if the estimate fits within `context_package_policy.max_tokens`. The package ceiling may be
  higher than the role budget, but the role must receive a package that fits in its context.

The project overrides the set with the optional `tool_policy`. A role entry takes priority over a mode entry, and a mode
entry takes priority over the built-in default:

```json
"tool_policy": {
  "modes": {"read-only": ["Read", "Grep", "Glob"]},
  "roles": {"qa": ["Read", "Grep", "Glob", "Bash"]}
}
```

`harness health` accepts only the keys `modes` (`read-only`/`write`) and `roles` (names from the role
manifests), and the value must be a non-empty list of unique strings. A brief without these two fields (created before
they appeared) stays valid. A brief with only one of the two fields, or with an incorrect value shape, is
rejected. A brief is an immutable record of the choice at the time of approval. So a late edit to
`tool_policy` or `context_limit` does not make an already created dispatch invalid. The new values
apply only to the next briefs.

### Operating-loop policy: attention, approval TTL, and extensions

Three optional sections of `.harness/orchestration.json` control how the coordinator stops
looping retries and how it checks approval. A missing field takes its default, and the coordinator writes the resolved values
into every brief as `orchestration_policy`, so editing the file in the middle of a
dispatch does not change the conditions under which the dispatch was approved:

```json
"attention_policy": {"retry_queue_seconds": 3600, "max_infrastructure_retries": 2, "stale_dispatch_seconds": 3600},
"approval_ttl_seconds": 3600,
"extensions": {"transport_health": "none", "verification_environment_health": "none",
               "retry_reason_classifier": "none", "context_telemetry_provider": "none", "human_notifier": "none",
               "runtime_access": "none"}
```

- `attention_policy` — the thresholds of the `needs_attention` flag (see below): how long an accepted retry may wait
  for its dispatch, how many operational retries (`verification-infrastructure`, `transport`,
  `context-pressure`) are allowed per candidate (`0` means none), and after how much silence a live
  dispatch counts as stale.
- `approval_ttl_seconds` — the lifetime of an explicit `--approved-at`. The coordinator rejects an older
  approval (or one dated in the future) and does not reuse it. Without the field, approval does not expire.
  The `orchestration.example.json` example sets `14400`; `harness init` creates the config from it.
- `extensions` — pluggable interfaces outside the coordinator core: `transport_health`,
  `verification_environment_health`, `retry_reason_classifier`, `context_telemetry_provider`,
  `human_notifier`, `runtime_access`. The value is `none` (the inert default), a name registered by the
  host process, or `module:factory` (a factory callable without arguments in an importable module).
  An unknown name fails closed. No extension adds a model tool or changes the system prompt.

`harness health` checks the shape of all three sections. While the project has no
`assignment_plans`, the coordinator works on built-in defaults and does not read these values.

### Role access: `access_policy` and `runtime_access`

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

### Built-in `docker` container executor

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
  takes tags only from the config and does not query the engine, the network, or the images. `harness health` and the schema
  require `access_policy.defaults.container` if `docker` is selected: without it, a role would be left without an
  image.
- The `environment` component is a list of unique environment variable names (`[A-Za-z_][A-Za-z0-9_]*`),
  never values. A role or operation override replaces the whole list. The plan stores the names in
  sorted order, so they are part of `plan_digest` and are pinned in the brief at approval:
  a name added to the config after `dispatch propose` is not given to that dispatch. The engine
  takes the values from the environment of `harness-runtime serve`, so after changing them you must restart the runtime.
  The values do not reach the config, brief, digest, argv, evidence, logs, error texts, or image layers.
  The agent's auth files are not mounted.
- Every role that `dispatch send` sends must have `transport: external` in
  `assignment_plans`. The executor wraps the external adapter's command and does not know the specific
  agent.
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

### Container worker status and cleanup

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

### QA, Git, and publish access

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
the rollback waits for the lock for up to 30 seconds (see "Busy ledger, `report complete`, and `ledger release-lock`"). A denial before `refresh`, `resolve`, and
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

### Discovery Context and Context Package

The Discovery Pipeline carries verified context from design to dispatch. `/grilling` maintains a
`Live Artifact` with candidate paths, but adds a path only after the user explicitly agrees.
`/to-spec` saves the approved list in the epic under `## Relevant Files (Discovery Context)`.
`/to-tickets` assigns each path to a suitable tracer-bullet ticket and builds the Path inventory. A single
cheap advisory call may add only exact dependencies from this Path inventory. Its output is
neither evidence nor authority.

Before the first dispatch, the coordinator may register a deterministic Context Package in the
ledger:

```bash
python .harness/orchestration/coordinator.py --repo . context-package register \
  --batch <batch-id> --candidate-commit <candidate-sha> \
  --symbol-graph-depth 1 --min-starting-files 5 --max-starting-files 10 \
  --max-package-tokens 60000
```

`context_builder.py` does not call an LLM and works from pinned base/candidate commits. The package contains
the exact diff, 5–10 starting files with reasons, a bounded symbol/dependency graph, related tests,
short ADR/precedent cards, the SHA-256 of each included file, the byte size, and a conservative token
estimate. Byte-for-byte identical files (for example, the mirror `docs/agents/*` ↔
`harness/project/docs-agents/*`) stay starting files, but the estimate counts their content once;
the reason for the second copy names the original and requires keeping the copies identical. A Markdown file
enters the package as a table of contents if its estimate is not less than
`context_package_policy.section_index_min_tokens` (20000 by default). `sections` lists the
headings of levels 1–3 (outside fenced code) with `start_line`/`end_line`; the estimate counts only this
table of contents, and the role reads only the line ranges it needs. A file without headings is counted whole.

A Python file enters as a symbol index at the same threshold. It consists of top-level functions,
classes, and class methods; anything nested inside functions and methods is not listed. The rest of the file's code
is covered by the pointers `module header` (before the first definition) and `module code` (between definitions,
after the last one, and blocks such as `if TYPE_CHECKING:`), so the index hides nothing. Symbols hidden by
`repo_map_policy.redact_symbols` stay in the headings as the marker `[REDACTED-SYMBOL]`. The index
applies only if it is cheaper than the file. A file without definitions, with a syntax error, or of another
format is counted whole. If the package does not fit the limit, the heaviest starting files for
which an index can be built are replaced by the index one at a time until the package fits the limit.
An added file cannot be shortened this way: its text already lies in the diff, and the related tests and ADRs stay in the
package whole.

For Python, the AST extracts the signatures of direct local dependencies, and the current
Discovery contract limits the expansion to one level. An unsupported format gets its first
30 lines as a deterministic fallback. If the package does not fit
the token limit even after replacing files with indexes, the build ends with an error and does not silently truncate the package. You may set the legacy `--max-package-size-bytes` as an additional diagnostic,
but it does not replace the token limit.

The package record is immutable, versioned, and hash-verifiable. It is shared within the batch. The same
base/candidate reuses one package ID across the architect, developer, and continuation sessions.
A new package is created only after a new candidate. The coordinator does not reuse a package if
its frozen source from `memory.pointers` changed after registration, became unavailable, or was revoked.
Then the next dispatch registers a new package with current pointers. The old package
stays unchanged for the briefs already issued. The coordinator checks freshness before handoff and does not create a
brief with a stale package. If the new package is not fresh by memory either, the error names the path and the expected and
actual `source_hash`. The remedy suggests `harness memory rebuild .` from the main checkout or
`--no-memory`. The brief passes a compact summary (starting files, related tests, precedents, and pinned
commits). The full diff stays in the package once. The package does not replace the immutable brief and does not
cancel the mandatory self-report, heartbeat, review, or QA.

## Observing a launch and a ready unsubmitted report

The shipped example is `.harness/orchestration/adapters/claude_code.py`; `claude` or `codex`
by themselves are not adapters. From the Harness console, the selected session opens first,
then the confirmed send runs. For an intentionally hidden launch, pass
`--adapter-arg=--visibility=background`. The example keeps native permissions and hooks.
A check of the parent does not confirm access of the Bash tools inside the worker: the native probe must
pass before implementation. A permanent access denial requires preparing the environment, not identical retries.
Change the sandbox profile before propose/approval; global settings are not disabled.

`dispatch observe --dispatch <id> --offset <next_offset>` reads the existing events locally.
Opening the panel, refreshing, and reconnecting do not call the model; you can close the window without stopping the
worker. A human confirms a native-permission request; it does not give dispatch approval.
By default, the first self-report is awaited for 120 seconds, regardless of heartbeat stale. For a proven
early completion: auto-report → auto-decide → human resume-stop --restart. A repeated
launch keeps the original contract; on drift, a new proposal is needed.

For a ready report that the worker could not submit, the coordinator uses the original staging file:
`report submit --file <path> --relayed-by <sender> --relay-reason <exact-error>
--source-sha256 <hash-original-bytes>`. The worker JSON is not edited, and provenance is written separately.
Fail/not_run stay as they are; make lint does not replace make verify. If the report is already recorded,
use report complete when the submit result points to that route. Comparing a failure
with the base SHA is separate evidence, not a retroactive fix of the original report.

## 3. Choosing roles and planning a batch

The base set has four write roles and three read-only roles.

| Role | Mode | When to assign |
| --- | --- | --- |
| `developer` | write | An ordinary backend change inside a service or bounded context. |
| `database-migrations` | write | A schema/data migration and its rollout/rollback. |
| `messaging-integration` | write | Outbox, routing, message schema, retry, or DLQ. |
| `conflict-resolver` | write | A text conflict between the ticket branch and a shifted integration SHA; assigned only by the `integration resolve` route. |
| `architect` | read-only | A boundary decision that is hard to reverse. |
| `qa` | read-only | Independent verification through a project-facing interface is needed. |
| `code-review` | read-only | Mandatory for the listed high-risk triggers; produces separate Standards and Spec reports. |

One task may pass through several roles. But the handoff inside one batch is always sequential, and
a batch has only one active writer. Batches with overlapping files may run in parallel,
each in its own issue branch and worktree, as long as `concurrency_budget` allows. Overlaps are resolved
at integration and do not block the launch. The coordinator rejects two batches for the same
unfinished ticket, branch, or worktree. Heavy integration/quality checks go through one
serialized quality-gate lane.

For API/public contract, schema/data migration, outbox/queues, transactions,
authorization/security, and concurrency/retry, completion is impossible until the coordinator has received both
independent `code-review` reports: Standards and Spec.

After a developer dispatch, the candidate commit gets a deterministic risk assessment from the DoD, the changed
files, and the developer-reported triggers. The assessment decides when the composite read-only `code-review` is
**mandatory**, but not when it is *allowed*. You can create a review for any candidate, and the
`/implement` pipeline always does. The Standards and Spec axes stay separate evidence. A separate QA
dispatch is created only after an accepted review (if one is mandatory): the mandatory full QA gate
in a clean room cannot be replaced by the developer's local check. Any new candidate commit after a
finding or a failed QA goes through the risk assessment again.
## 4. Coordinator CLI and lifecycle

Runtime-neutral mode has no "start everyone" command. The coordinator CLI manages records through
`planned → awaiting-approval ↔ active → completed`, with the recoverable states `paused`,
`blocked`, `failed` and the final rejection `abandoned`. After a manual recovery, the effective
policy is `manual_all`. Under `manual_all`, every
report leaves its dispatch in `reported` until a human decides. Under `low_risk`, the coordinator
automatically accepts a clean completed report batch if the whole batch scope lies inside
`low_risk_paths`. The coordinator records the decision in the ledger. Blockers, failed checks, disclosed risks, risk
triggers, and findings from any review axis keep the manual gate. Publish also needs a separate
approval. Under `milestone`, the coordinator also automatically accepts a clean report of an ordinary role. But
QA, publish, and risky transitions remain manual milestones. Under `auto`, the coordinator walks the path
from `batch approve` to an accepted publish without a human. The policy approves each step, and
`batch auto-decide` decides on the reports (see "Automatic path `approval_policy: auto`"
below). Opening a PR and the merge remain manual.

1. Create a planned batch, then approve it separately:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch create \
     --ticket '#123' --branch feature/issue-123-payment-validation \
     --worktree issue-123-payment-validation \
     --allowed-path 'services/payments/**' \
     --definition-of-done 'Добавить валидацию платежа' \
     --prohibited-change 'Не менять migration или публичный API' \
     --required-gate review --required-gate qa
   python .harness/orchestration/coordinator.py --repo . batch approve \
     --batch <batch-id> --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:00:00Z
   ```

   `batch create` first runs `git fetch origin <ref>`. The ref is `--integration-ref` if it is passed,
   otherwise the project `base_branch` (for epic-less tasks). The command records the fetched tip as
   `base_commit`/`integration_base_commit`; a stale local HEAD never replaces it.
   The full `/implement` route requires an explicit `--required-gate review --required-gate qa`
   (independent Standards/Spec review and full clean-room QA), and the coordinator checks that they are present in
   `required_gates` before it sends the write-role (`developer`) worker. In the allowed direct CLI scenarios,
   you may omit `--required-gate` (the default is `["none"]`). After that, review, QA, and publish check the
   pinned candidate even if `origin/<ref>` has moved forward. There is no mandatory base freshness check
   and no forced developer restart, and other batches do not stop on this. The final
   base update is done by `integration refresh` when the PR is prepared (section "Integration accounting
   after publish").
2. Check the active batches, `concurrency_budget`, the writer lane, and the quality-gate lane. An overlap of files
   with another batch is no reason to delay the start, and a busy serialized quality-gate lane does not block
   parallel implementation. If a batch hits the budget, wait for an active batch to finish or
   raise `concurrency_budget`.
3. Create and separately approve an architect dispatch, accept its report, and only then create the
   developer dispatch. The order is strict: the coordinator rejects `dispatch create --role developer`
   until the same batch has an architect report accepted through `batch decide --decision accept`.
   The rule lives in `coordinator.py`, so it applies to both the manual CLI and `/implement`. The CLI
   saves the immutable brief before the handoff:

   ```bash
   # dry run first: shows the canonical transition and its digest, does not write the brief
   python .harness/orchestration/coordinator.py --repo . dispatch propose \
     --batch <batch-id> --role developer --runtime codex
   # the approval is valid only for the digest shown
   python .harness/orchestration/coordinator.py --repo . dispatch create \
    --batch <batch-id> --role developer --runtime codex --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:01:00Z --transition-digest <transition_digest>
   python .harness/orchestration/coordinator.py --repo . dispatch send \
     --dispatch <dispatch-id> --adapter <project-runtime-adapter>
   ```

   For a role with `transport: "in-process"`, you do not pass an adapter at all. `dispatch send --dispatch <id>`
   returns the path to the brief. After that, the coordinator **immediately** starts the role as a subagent
   of the current session. Between these actions, there are no reads of earlier dispatches, reports, or templates. Without
   `.harness/orchestration.json`, add the `--model` and `--effort` of the calling session to `dispatch create`.
   For the coordinator and architect, choose `medium` unless the developer explicitly approved otherwise.

   Accepting the architect report may pin the commit plan the architect proposed instead of the default plan:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:00:30Z --commit-plan-file .harness/.sandboxes/scratch/commit-plan.json
   ```

   The file lies in the repository or one of its worktrees and contains exactly one key,
   `{"commit_plan": [...]}`. Each entry contains exactly four fields: a unique `id`
   (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`), a non-empty `summary`, a non-empty list `expected_paths`
   (relative paths or globs without a leading `/` and without a `..` segment), and `covers`, the numbers of the DoD items
   `1..n` that the entry implements. The order of entries is the order of commits. Accept is rejected with a
   remedy if any DoD item is covered by no entry, if an entry names a nonexistent item,
   or if the flag is not passed with `--decision accept` on an architect report. Then the report stays waiting for a
   decision, and the batch does not change. The coordinator saves the verified plan in the batch as `commit_plan`.
   The architect decision receives `commit_plan_sha256`. This plan becomes the `commit_plan` of every
   developer brief of the batch, including `developer-retry`. If the plan in the batch does not match the digest of the
   accepted decision, the developer brief is not created. Without the file, the brief contains one `step-N` entry
   per DoD item with `covers: [N]`. Under `low_risk` and `milestone`, the coordinator automatically accepts a
   clean architect report with the default plan. Therefore an architect who proposes a different plan
   states this in `risks`, and the report waits for a manual decision.

   `dispatch send --role code-review` is the only case that needs one more mandatory flag:
   `--checkout <path>`. It points to a worktree that is actually checked out at the `candidate_commit` of the
   dispatch (see the clean-room QA lane below: review needs the same isolation). All other roles
   do not pass `--checkout`. Without it, the coordinator rejects `dispatch send` and shows the exact text of the
   expected flag.
4. Accept one schema-validated completion report with evidence. The coordinator saves it as
   canonical JSON and a deterministic Markdown projection. After that, the dispatch stays `reported`, and the
   batch waits for the next decision:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report submit \
     --file developer-report.json
   ```
   In `checks_run[*].result`, the canonical values are `pass`, `fail`, and `not_run`; only the architect
   may use `not_run_architect_read_only`, for compatibility with old briefs.
   Architect work without a verification gate keeps `checks_run` empty.
   `pass` and `passed` are equivalent; the old `not-run` is equivalent to `not_run`. New reports
   are saved with the canonical values; old immutable reports are read without being rewritten.
   Unknown results are rejected with a `remedy` before the canonical report is written. Fix the
   staging file according to the evidence and repeat the submission for the same dispatch: `pass` means a
   successful command, `fail` means an unsuccessful one, and `not_run` means a command that did not run. Automatic acceptance
   treats `pass` and `passed` the same.
   A result that is admissible as evidence does not mean the report is accepted automatically.
   Before the decision, the coordinator checks the report again, so an old recorded report
   with an unknown result is also refused. Do not edit an immutable report;
   for an already recorded report or a stopped batch, the operator chooses an existing
   recovery route separately. After `resume-stop`, the `auto` policy does not return.

   Before the next dispatch, the coordinator records a separate decision. Under `manual_all` or with an unclean
   report, a human accepts the report, overrides the warning, or requires a retry. Under `low_risk` and with a clean
   report, the coordinator itself records `accept` with the rationale
   `Auto-accepted due to low_risk policy and clean report`, computes `next_action`, and prepares the
   next admissible dispatch. Under `milestone`, a clean report outside a milestone also receives `accept`.
   After the developer, the coordinator assesses risk, and the QA dispatch waits for a separate approval. A clean
   QA report under `milestone` waits for a human decision.

   The policy chain (`policy-decide`, `risk-assess`, `next-dispatch`) runs as separate commands after
   the report is recorded. Each command may stop: the ledger is busy, `needs_attention` is raised,
   or the batch state changed. Then `report submit` still exits with code 0. The report
   is recorded, and the response names it (`report`, `report_sha256`) and carries a `completion` object. The object
   contains `route: "report-completion"`, `failed_step`, the state of each step (`done`,
   `already-done`, `not-applicable`, `failed`, `not-run`), `error`, `remedy`, and the exact command
   `command`. The coordinator itself runs it (`run_by: "coordinator"`), not the worker:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report complete --dispatch <dispatch-id>
   ```

   `report complete` is idempotent: each step is derived from the ledger, so an already recorded decision,
   risk assessment, or next dispatch is not repeated, and a repeated run writes nothing.
   The command repeats only the policy recorded at `report submit` (`auto_accept_policy` in the dispatch
   status). It never records the report again and never creates a dispatch for the role that submitted the report.
   The `risk-assess` step assesses the candidate of the report: for the developer, these are its `commit_sha` and
   `changed_files`; for read-only verification, it is the candidate pinned in its dispatch, with the files from the
   diff against the batch base, as `risk assess` counts them. A step that needs a human stops with the
   remedy of that step. For a report left to a human, all steps are `not-applicable`. Do not
   submit the report again: it is already recorded.

   A manual decision looks like this:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:02:00Z
   ```

   A developer report against a brief with a `commit_plan` carries `commit_map`. These are the pairs
   `{commit_sha, plan_entry_id}` for every commit after `snapshot_commit` (for a rebase, after
   `rebase_target`). In an initial and a rebase report, this is a relation. A commit that closes several
   entries yields one pair for each entry. An entry closed by several commits yields one pair for
   each commit. A mapping that is not one-to-one (a merged commit, a split or unclosed entry) is a
   divergence. Then the report must carry `dod_coverage`, exactly one record for each DoD item:
   `{"dod_item": <n>, "commits": [<sha>, ...]}` with commits of this dispatch, or
   `{"dod_item": <n>, "not_covered": "<reason>"}`. The report must also carry a non-empty
   `divergence_justification`: what was merged, split, or added, and why. For a one-to-one mapping,
   `dod_coverage` is optional (the coordinator derives the coverage from the `covers` of the plan), and
   `divergence_justification` is rejected.
   `report submit` and `batch decide` reject structural errors, each with a remedy:
   an unmapped created commit, a commit not from this dispatch, an unknown entry, a repeated pair,
   a divergence without `dod_coverage` or without a justification, coverage without an item, with another item, or
   another commit, `not_covered` without a reason. In `developer-retry` and in reports of other roles, these two
   fields are rejected.

   `report submit` also checks `dod_coverage` against `commit_map` and the `covers` of the plan. The command rejects
   a DoD item that is declared covered by a set of commits if `commit_map` maps none of
   them to an entry that has this item in `covers`. The remedy names the item, the declared commits, and the
   plan entries that cover this item. The reverse direction is admissible. `not_covered` with a reason
   is also valid for an item that the mapping formally covers. Like any `not_covered`, it
   requires a manual decision. A one-to-one report without `dod_coverage` gets its coverage from `covers` and does not
   need this check.

   A justified divergence with full coverage does not by itself make a report unclean. Under
   `low_risk` and `milestone`, the coordinator automatically accepts a report that is clean in other respects. The decision
   record receives `commit_plan_divergence` (`developer_dispatch_id`, `justification`,
   `merged_commits`, `split_entries`, `unclosed_entries`). A manual acceptance receives the same record.
   Any `not_covered` item makes the report unclean under any policy. Auto-accept does not fire,
   and `--decision accept` is rejected. You can accept the report only through `--decision override-warning` with
   a `--note` other than `none` (the decision receives `dod_not_covered` with the reasons). Otherwise, you can
   return the report through `retry`. Going outside the scope is a warning, not a refusal. For a completed developer
   report with `changed_files` outside `write_paths`, `report submit` records it. `batch decision-packet`
   shows these paths in `scope_warnings`. Such a report is not accepted automatically under any
   policy, and `--decision accept` is rejected. You can accept it only through
   `--decision override-warning` with a `--note` other than `none` and an explicit `--approved-by`. The decision
   receives `scope_warnings`, and the override adds a coordinator finding. The next code-review brief
   carries these paths as an item that the review must close. Accepting an architect report with
   `--commit-plan-file` succeeds if the `expected_paths` of the plan go beyond the `allowed_paths` of the batch.
   Then the packet (with the same `--commit-plan-file`) and the decision contain the same `scope_warnings`. The ban
   on writing outside `write_paths` for the worker itself, the `changed_files` check in the checkpoint, and the reports of
   other write roles remain strict.
   `batch decision-packet` shows `dod_coverage`, `dod_coverage_source` (`report` or
   `derived`), and `commit_plan_divergence`. The code-review brief carries the `commit_plan_divergence` of the
   latest accepted initial or rebase developer report (for other roles, the field is `null`). With
   it, the reviewer checks that the commit boundaries stayed reviewable.

   A defect that the coordinator found in a clean developer report does not spend a developer-retry before review
   (the `carry-over` route). Retrying a developer report without accept is an exception only for an unfulfilled
   DoD item or a change outside the scope. In other cases, the report is accepted with findings:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:02:00Z --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   The file lies in the repository or one of its worktrees and contains exactly one key,
   `{"findings": [...]}`. Each finding contains exactly three fields: a non-empty `summary`, `files`, a
   non-empty list of unique paths from the repository root in POSIX form (without a leading `/`, backslash,
   or `..` segment), and a non-empty `expected_evidence`: what the review uses to confirm the closure.
   The text of a finding is passed to a role, so it is in English. The flag is admissible only with `accept` or
   `override-warning` on a completed developer work report. Otherwise, the decision is rejected with a remedy, and the
   batch does not change. The coordinator records each finding in the batch append-only as a
   `carried_items` record: `item_id` `coordinator-finding-<n>` (the sequence number in the batch), `source` (`kind`,
   `dispatch_id` and `report_sha256` of the accepted report, `candidate_commit`), `summary`, `files`,
   `expected_evidence`, `attached_at`, `attached_by`, and `record_sha256`. The coordinator checks
   this hash on every read of the batch.

   The auto-accept policy does not take a findings file. After it, `batch carry-over` adds the findings:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch carry-over \
     --batch <batch-id> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   The command creates no dispatch and does not change the candidate, so a human does not approve it. It
   records the coordinator decision `carry-over` with `approved_by: policy:carry-over`. It attaches the findings
   to the latest accepted developer work report. A batch with `next_action: qa` moves to
   `code-review`. The command is rejected with a remedy: while any report waits for a decision; if the batch has no
   accepted developer work report; if a dispatch was already created after it that was not cancelled and not
   moved to `abandoned` by `batch resume`. For an unsent code-review (or a qa created by the
   low_risk chain), the remedy is `dispatch cancel` and a repeat of `batch carry-over`. For a sent one, the remedy is to
   report the defect when deciding its report. For an already decided report, attach the finding through
   `batch decide --findings-file` when accepting the next developer report.

   While a finding is open, the risk assessment sends the candidate to `code-review`, even if no trigger
   matched (the `review_required` of the assessment record does not change). A finding is closed when a code-review
   whose brief carried it is accepted (`accept` or `override-warning`). A review retry leaves it open.

   Every brief carries a `carried_items` section, the shared channel for carried items. It is an object: the key is
   the source kind (`coordinator-finding`, `review-finding`, `incomplete-item`), and the value is a list of
   `{item_id, source, summary, files, expected_evidence}`. An empty channel is `{}`. The code-review and
   developer work briefs carry all open `coordinator-finding` items. A developer brief that answers a `retry`
   of a code-review with the `fix-forward` route also carries the Standards and Spec axis findings of that review
   as `review-finding` (`item_id` `review-finding-<n>`; `source` is `dispatch_id`, `report_sha256`,
   `axis`, `severity`; `files: []`; `expected_evidence` is the evidence of the finding). Therefore the single
   developer-retry closes both groups and spends `retry_policy.max_developer_retries` once.
   Accept with findings and `batch carry-over` do not spend the budget. A non-empty section enters the transition as
   `carried_items_sha256`. Therefore a finding added after `dispatch propose` needs a new
   approval.

   The code-review report accounts for each brief item in the optional `review.carried_items`:
   `[{"item_id": ..., "status": "closed" | "open" | "unverified", "evidence": ...}]`. `report submit`
   rejects an item that the brief did not carry, a repeated item, an unknown status, and empty evidence.
   Omitting an item is structurally admissible, but an omission, like `unverified` and `open`, is a carried gap, and
   such a report is not clean: the policy does not accept it automatically, and `--decision accept` is rejected.
   `override-warning` requires a `--note` other than `none` and records `carried_items_gap`
   in the decision. You can also return the report through `retry`. The blocker and warning rules keep
   their priority. An `open` item is structural evidence of the `code` category, so such a retry leads to a
   developer-retry by the `fix-forward` route. `batch decision-packet` shows `carried_items`
   (each item with `source`, `summary`, `status` — for a code-review report, `omitted` for an omitted
   item — and `evidence`) and `carried_items_gap`.

   A read-only role (architect, verification, code-review, or qa) that did not complete part of the brief
   lists the unfinished items in the optional report field `incomplete_items`:
   `[{"brief_item": ..., "reason": ..., "target_role": ...}]`. The text is written in English because the
   item goes into the brief of the next role as agent-to-agent text. Each string is non-empty and at most
   1600 characters long. `target_role` is the report role itself (for a narrowed retry) or a later role:
   architect → architect, developer, code-review, or qa; verification → verification, code-review,
   or qa; code-review → code-review or qa; qa → qa. An item that a tool prevented from running
   (for example, a safety classifier) carries its own `tooling_blocker` of the same shape as the one in the
   report, under any outcome. `report submit` rejects, with a remedy, the field on a write role, an item without
   `reason`, an unknown or inadmissible `target_role`, Cyrillic, and an invalid `tooling_blocker`.

   A report with a non-empty `incomplete_items` is not accepted automatically under any `approval_policy`, and
   a plain `accept` or `override-warning` is rejected. A human chooses one of two decisions:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:02:00Z --carry-incomplete
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision retry --approved-by 'имя утверждающего' \
     --approved-at 2026-09-09T12:02:00Z --narrowed
   ```

   `--carry-incomplete` (with `accept` or `override-warning`) records a `carry-over` routing record with
   `carried_item_ids` (`incomplete-item-<n>`, numbered continuously across the batch). `next_action` changes as
   for any accept of this stage. The batch does not store the items. The work brief of the target role reads them from the
   immutable report and carries them in `carried_items` as `incomplete-item`. This continues until a
   dispatch of this role whose brief carried them is accepted (`accept` or `override-warning`). A retry leaves the
   item open. For code-review, an open item sends the candidate to code-review, even if the risk
   assessment found no triggers. The flag is rejected without items, with another decision, and when at least
   one item targets the report role itself. Only a narrowed retry closes such an item.

   `--narrowed` (only with `retry`) repeats the same stage on the same SHA. The brief of the new dispatch carries
   only the items of the report. The Definition of Done in the brief stays the full DoD of the batch. The route is
   `narrowed-retry` with `reason_category: null`. If at least one item carries a `tooling_blocker`, the route is
   `tooling-retry` with the category `tooling` (confirm the false positive and open a bug ticket against the
   tool; the attention `tooling-retry-repeated` limits a series). The budget
   `retry_policy.max_developer_retries` is not spent, and the new dispatch is approved according to
   `approval_policy`. `--narrowed` is rejected: for developer and publish; for a report without items;
   together with `--reason-category` or `--retry-role developer`; and with structural evidence of another
   route. Such evidence is a finding or a warning/blocker severity on an axis, an open carried item, a
   failed check, or a shifted candidate. A retry without `--narrowed` ignores the items and is routed as
   before.

   The `source` of an `incomplete-item` item contains the `dispatch_id` and `report_sha256` of the report, its `role`,
   `target_role` (the role whose brief carries the item), `route` (`carry-over`, `narrowed-retry`, or
   `tooling-retry`), `reason`, and `reason_category` (`tooling` for an item with `tooling_blocker`, otherwise
   `null`). `summary` is the `brief_item`, and `files` is empty. `batch decision-packet` shows the
   `incomplete_items` of the report; without `--findings-file`, it adds `route_preview["carry-over"]`,
   the record that `--carry-incomplete` will make, or a refusal. `batch decision-packet --narrowed`
   shows the route of the narrowed retry.

A minimal manual brief stores the ticket and dispatch ID, the role and its access, the selected
profile/model/effort, the allowed paths (write scope), the issue branch/worktree, the DoD, the prohibitions, the commands,
the dependencies, and the approval. For a write role, the completion report must include the commit SHA, the exact changed
files, the results of all checks, the risks, the blockers, and the next coordinator decision. A write role may
stop before any changes (for example, because of a risk trigger when a required gate is missing). Then the
coordinator accepts an honest report with `outcome: blocked`, empty `changed_files`, and a `commit_sha`
bound to the verified checkout (`snapshot_commit`). The coordinator registers the report and
returns a `decision_packet` with a `recovery_route` (`retry`, `block`, `abandon`). It does not register an unfinished
candidate. For a read-only role, the report states
`not applicable — read-only role` instead of a SHA.

New facts do not change a sent brief: the coordinator adds a separate decision with evidence. If the
scope, DoD, assignment, or proof changed, the current dispatch ends and a new one is created.
A repeat after `blocked` or `failed` is also a new dispatch with a new ID and brief.

### `retry` routing and the `abandon` decision

`batch decide --decision retry` no longer means "developer again". The coordinator stores a routing record on the
decision: `route`, `previous_role`, `reason_category`, `next_role`, `next_action`,
`rationale`, and `candidate_commit` (while it has not changed). The coordinator determines the cause only from the
structured data of the report: outcome, findings, the severity of the Standards/Spec axes, failed checks, and
whether the candidate changed. Free text in `blockers`/`output` is not classified. You can pass an explicit cause
through `--reason-category` (`code`, `requirements`, `candidate-change`,
`verification-infrastructure`, `transport`, `context-pressure`, `tooling`, `block-bypass`,
`unknown`). But it does not override a finding that was found. A rate limit, an unavailable Bash/WSL wrapper, and
a transport failure are operational evidence (`verification-infrastructure` or `transport`), not a
code finding. A context limit gives `context-pressure` only if a `critical` observation `context_pressure`
is recorded for the reporting dispatch (see below). A bare claim gives `unknown`.

**Failure domains.** Each routing record carries `failure`: exactly one ADR 0019 domain
(`environment_preparation`, `infrastructure`, `policy`, `tooling`, `code_test`, `timeout`,
`cancelled`, `unknown`) with the evidence that shows this domain: `domain`, `method`,
`matched`, and `source`. `method` is `structured` (a report, stage, or runtime field), `heuristic`
(a text pattern, which never proves `code_test`), `approver` (a human or a policy named the domain),
or `fallback`, and `fallback` always means `unknown`.

The `code_test` domain is proven by a finding in a review, a warning/blocker severity on an axis, an explicit retry that
the reviewer assigned, a failed check, an open carried item, a confirmed project defect during
QA preparation, a conflict-resolver report with `resolver.cause: task-defect`, and a shifted candidate (it
changed after the dispatch was pinned). The coordinator treats a shifted candidate as `code_test`
on purpose: the ledger proves that the work itself changed, so the route stays a developer retry
and spends the budget, as it did before the domains appeared. A `retry_reason_classifier` hint is not proof:
it does not replace a structured fact of the report, and without such a fact the domain stays `unknown`.

The other domains follow from facts. A structured `tooling_blocker` gives `tooling`,
a confirmed QA environment failure gives `environment_preparation`, a recorded `critical` observation
`context_pressure` gives `infrastructure`, and `block-bypass` gives `policy`. Anything that no
structured fact confirms is `unknown`, but never `code_test`.

Only a retry with the `code_test` domain spends `retry_policy.max_developer_retries`.
`infrastructure`, `environment_preparation`, `policy`, `tooling`, `timeout`, `cancelled`, and `unknown`
never spend it. When developer retries are counted for the `budget-exhausted` stop,
only such records are counted.

The coordinator refuses a developer retry on a code-review, qa, verification, or publish report if the
domain is not `code_test`. The refusal is typed as `UnprovenFailureError` and carries `failure`; `batch decide
--decision retry` returns `failure` and a remedy and writes nothing. Under `approval_policy: auto`, the same
refusal becomes the stop `no-automatic-route`/`unknown-reason`, and its evidence keeps `failure`.
The same stop ends an automatic developer retry with the `unknown` domain, because such a
retry would not spend the budget and would remain without a limit.

The approver proves the `code_test` domain with the categories `--reason-category code`, `requirements`, or
`candidate-change`. The approver may also request a developer retry through `--retry-role developer`, including
for a code-review, qa, or verification report that a tool blocked. Both variants prove the
`code_test` domain as `approver` and spend the budget. The exception is `tooling-retry`: with
`--retry-role developer`, such a retry of the developer stage keeps the `tooling` domain and spends nothing;
the other `tooling-retry` routes do not spend it either. A decision recorded before the domains appeared
does not carry `failure`, and the previous rule applies to it.

| Report stage | `accept` | `retry` | `block` / `fail` | `abandon` |
| --- | --- | --- | --- | --- |
| architect | developer | new architect | terminal | `abandoned` |
| developer | risk assessment | `developer-retry` continues the unaccepted candidate of this report (`snapshot_commit` is its `commit_sha`); the retry creates a new candidate, and that candidate gets a new risk assessment; the budget is spent only for the `code_test` domain; with a non-empty closed list of carried items, the route is `fix-forward` | terminal | `abandoned` |
| verification | risk assessment | `developer-retry` for the `code_test` domain, otherwise a refusal | terminal | `abandoned` |
| code-review | qa | new code-review on the same `candidate_commit` if the report is `blocked`, the cause is `verification-infrastructure`/`transport`/`context-pressure`, findings are empty, both axes have no findings, there is no failed check, and the candidate did not change; in other cases `developer-retry` for the `code_test` domain (with a non-empty closed list of carried items, `fix-forward`), and a refusal for another domain | terminal | `abandoned` |
| qa | publish | new qa on the same SHA under the same condition (QA stays read-only); a defect or a new candidate is a `developer-retry` for the `code_test` domain, otherwise a refusal | terminal | `abandoned` |
| publish | `completed` | new publish on the same accepted SHA for `verification-infrastructure`/`transport`/`context-pressure`; `developer-retry` for the `code_test` domain if the candidate must change; otherwise a refusal | terminal | `abandoned` |

`code`, `requirements`, and `candidate-change` lead to `developer-retry` when the `code_test` domain is
proven. `unknown`, or a contradictory or unconfirmed cause, does not prove a code defect: on the
manual path, the developer stage repeats through `developer-retry` without spending the budget, and on the
automatic path, the policy stops such a retry. The code-review, qa, verification, and publish stages
get a refusal (see "Failure domains"). Only the three operational categories can repeat a read-only stage
on the same SHA, and only with empty findings, an unchanged candidate, and no
scope/requirement blocker. A repeat on the same SHA is a new immutable dispatch: a new
dispatch ID, a repeated Context Package freshness check, and its own explicit approval under
`manual_all`, while the earlier brief, report, and blocker remain audit evidence. Fictitious and empty commits
are not used, and a new candidate always needs a new risk assessment. `block` and `fail` do not start a retry
themselves. `--retry-role developer` forcibly selects a developer retry where the coordinator
would otherwise repeat the same role on the same SHA.

`tooling` is a separate operational category: a hook, a safety classifier, or the ledger
blocked a legitimate action of the role. The coordinator assigns it only from the structured field
`tooling_blocker` (`tool`, the exact `command`, `message`) in a report with `outcome: blocked`. A finding,
a failed check, a shifted candidate, or a developer category must not override the category. An explicit
`--reason-category tooling` without this field gives `unknown`. Another named operational category
follows its previous route. The `tooling` route at any stage is `tooling-retry`: a new dispatch of the same
stage on the same SHA (architect, verification, code-review, qa, or publish). For the developer, this is
a `developer-retry` that continues its latest commit. This commit is recorded in the
`candidate_commit` of the routing record. In the table above, "three operational categories" still mean
`verification-infrastructure`, `transport`, and `context-pressure`.

If a hook blocked exactly the developer's `git commit`, the developer reverts nothing and adds to the
`tooling_blocker` the field `uncommitted_files`: a non-empty list without repeats, where each path is written
as Git prints it and lies inside the write zone. `commit_sha` then points to the developer's latest
commit, and the `tooling-retry` restart inherits these changes. `dispatch preflight`
pins HEAD to the developer's latest commit and allows a dirty worktree only if its
uncommitted paths (excluding coordinator state and tool sandboxes) exactly match the
list from the report and lie in the batch zone. Preflight rejects an extra file, a missing file, or a file
outside the zone, and the message and remedy name each mismatch. A clean worktree without a list passes, as
before, and for other dispatches preflight does not check the worktree for uncommitted changes.

`block-bypass` means that a read-only role (code-review, qa, or verification) bypassed a hook or tool
block instead of stopping with a `tooling_blocker`. Only the approver names this category. A report with the
violation is not evidence: its findings, failed checks, and outcome do not affect the
route, and only a shifted candidate still leads to `developer-retry`. The route is
`bypass-rerun`: a new dispatch of the same stage on the same SHA (for verification, on its
registered candidate) without a new candidate commit. `batch decide` requires a `--note` that
describes the violation, and the report itself is not accepted and is not closed through override-warning. The new
dispatch always requires an explicit approval (`--approved-by`) under any `approval_policy` except `auto`,
and `bypass-rerun` does not spend `retry_policy.max_developer_retries`. For architect, developer, and
publish, `block-bypass` is rejected: such a report still gets a `retry` with a developer category
(`code`, `requirements`, `candidate-change`) or `block`.

A retry of an unaccepted developer report continues its history. While the batch waits for this `developer-retry`,
the coordinator takes the candidate from the immutable report (`commit_sha`, verified by hash) and pins the
`snapshot_commit` of the new developer dispatch to it. The worktree is rolled back neither to the base nor to an older
accepted candidate. The `commit_map` of a retry counts only commits on top of `snapshot_commit`. Each
new commit closes exactly one distinct entry of the plan, and `dod_coverage` and
`divergence_justification` in a retry report are rejected. The default path is
`dispatch propose`/`create` without `--candidate-commit`. Then the brief gets `candidate_commit: null`
and needs no risk assessment, like a developer retry after code-review. To bind this SHA to the
transition digest, pass `--candidate-commit <commit_sha>`. Then, before
`dispatch propose`/`create`, while the batch is in `awaiting-approval`, a `risk assess` for the same SHA is needed.
Such an assessment is only evidence. `next_action` stays `developer-retry`, `required_next_role` and
the requirement of a new candidate are kept, and code-review and QA do not open. A `risk assess` for
another SHA is rejected. A retry report with the same SHA is not accepted. A retry after code-review, qa, or
publish still pins `snapshot_commit` to the latest accepted developer candidate.

Fix-forward is a route of the existing developer-retry, not a new transition. A `retry` decision
that leads to `developer-retry` records in the routing record `retry_item_ids`, a closed, possibly
empty list of carried items that the developer-retry brief will carry. For a code-review retry, it
includes the open `coordinator-finding` items, the Standards and Spec axis findings of this review
(`review-finding`), and the open `incomplete-item` items for the developer. For a qa, publish, or
verification retry, it includes the same items without review findings, and for a developer work report retry, it includes the items of its
own brief, none of which was accepted. A non-empty list makes the route `fix-forward`;
a developer `tooling-retry` keeps its route and writes the same list. The developer-retry brief carries
exactly these items, and a mismatch with `retry_item_ids` is rejected as an invariant violation.

The developer continues from `snapshot_commit` with new commits on top of it and reports in the completion report
with the field `carried_item_closure`, one record for each brief item:
`{"item_id": <id>, "commits": [<sha>, ...]}` with the commits of the retry chain that close the item,
or `{"item_id": <id>, "not_closed": "<reason>"}`. The retry chain is this dispatch and the earlier
attempts that passed the same closed list to it. A developer report retry and a developer `tooling-retry`
pass the items of their brief to the next attempt, and the `snapshot_commit` of the next attempt is the HEAD
of the previous one. Commits are counted from the `snapshot_commit` of the first attempt of the chain, from which the
`snapshot_commit` of this dispatch still descends; with an approved rebase target, counting starts from it, and
after a not-yet-accepted `rebase-fix-forward` attempt in the chain, from its target. Therefore an item closed by an
earlier attempt cites its commit, and after a rebase, its carried-over copy.

After a `rebase-fix-forward` attempt, commits of two kinds belong to the chain: the new commits of its attempts
and the carried-over copies whose `rebased_from` in the `commit_map` of the attempt report points to a commit
of the chain. An earlier rebase is taken into account: a copy of a copy leads to the original commit. A carried-over copy
of a commit that existed before the chain (it lies in the `snapshot_commit` of the first attempt or below)
is rejected with the same remedy as the original. There is one exception: an old stale-base rebase does not write
`rebased_from`, and its closure still counts all commits above the batch target. A completed report
of such a brief must carry the field, a blocked or failed report may carry it, and reports of other briefs
must not. `report submit` rejects, with a remedy, a missing, unknown, or repeated item, an empty
reason, an empty list of commits, an unresolvable SHA, and a commit that the retry chain did not create;
the commits are checked against Git, including for a brief without `commit_plan`. A `not_closed` item is a carried gap, and
such a report is not clean: the policy does not accept it automatically, and `--decision accept` is rejected.
`override-warning` requires a `--note` other than `none` and records
`carried_items_gap` in the decision. The `commit_map` of a retry report keeps the strict rule of checking against the commit plan, and
`batch decision-packet` shows, for the developer-retry items, the status `closed` with the commit SHAs or
`open` with the reason.

Without an approved rebase target, the `commit_sha` of a retry report must be a descendant of `snapshot_commit`.
A report after an amend, squash, or reset is rejected with the message `developer-retry candidate <sha> does
not descend from snapshot_commit <snapshot>: the retry rewrote the history it continues (amend,
squash or reset)`. Remedy: restore the rewritten commits from `git reflog`, repeat the fix
with new commits without amend and squash, and report the new HEAD. The retry of a rebase report of a legacy
stale-base record (`base_rebase_required`, recorded before ADR 0014) is still checked against its rebase
target.

Rebase-fix-forward is also a route of the existing developer-retry, not a new transition. A `retry`
decision that leads to `developer-retry` or `fix-forward` (a retry of a developer, verification,
code-review, qa, or publish report; not `tooling-retry` and not `bypass-rerun`) runs `git fetch` for
`origin/<integration_ref>`. The route becomes `rebase-fix-forward` if both conditions are met: the tip
moved forward from the pinned `integration_base_commit`; and the candidate that the retry will continue
(the retry's own candidate for a developer report, otherwise the latest accepted one) does not contain this tip yet. The routing
record additionally names `rebase_target_commit` (the new tip) and `integration_base_commit` (the base
it moved away from) and keeps `retry_item_ids`. `next_action` stays `developer-retry`, and such a
retry spends one `retry_policy.max_developer_retries` when its failure domain is `code_test`.
A fetch error rejects `batch decide --decision retry` with a remedy. `decision-packet` shows it
in `route_preview.retry`.
The decision only proposes the target: the `integration_base_commit` of the batch does not change before accept.

The target enters a brief only through a dispatch with an explicit approval under any `approval_policy` except
`auto`. The approval of another policy is rejected for it. `dispatch propose` shows the transition with the field
`rebase_target_sha`, and the brief gets `rebase_target_commit`. Besides this, the brief field is filled
only for the developer-retry of a superseding batch (see "Superseding batch" below). In all other briefs, it
is `null`, including the developer dispatch of a legacy stale-base record:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet --batch <batch-id>
python .harness/orchestration/coordinator.py --repo . batch decide --batch <batch-id> \
  --decision retry --reason-category code --approved-by 'имя утверждающего' \
  --approved-at 2026-10-07T09:00:00Z
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch <batch-id> --role developer --runtime claude
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch <batch-id> --role developer --runtime claude --approved-by 'имя утверждающего' \
  --approved-at 2026-10-07T09:05:00Z --transition-digest <transition_digest>
```

The developer moves the commits over the old base exactly onto this target
(`git rebase --onto <rebase_target_commit> $(git merge-base <snapshot_commit> <rebase_target_commit>)`),
resolves the conflicts, and adds fix commits in the same dispatch. Its `commit_map` lists each
commit of the previous candidate (after the `git merge-base` of `snapshot_commit` and the target up to
`snapshot_commit`) exactly once: `{"commit_sha": <copy>, "rebased_from": <original>}`, where the
carried-over copy inherits the plan item of the original, or `{"rebased_from": <original>, "dropped":
"<reason>"}` for a commit that the rebase did not carry over. Each commit after the target appears exactly
once: as a carried-over copy or as a new commit `{commit_sha, plan_entry_id}` under the strict
retry rule. `changed_files` and `carried_item_closure` are counted from the target. The check "the candidate is a
descendant of `snapshot_commit`" does not apply to such a brief. `report submit` rejects, with a remedy,
a missing, repeated, or unknown commit of the previous candidate, a copy that is identical to its
original (a merge of the target instead of a rebase), an empty `dropped` reason, a commit that the dispatch did not
create, and `rebased_from`/`dropped` in the report of a brief without a target.

`report submit`, `batch decision-packet`, and the `accept`/`override-warning` decision return
`rebase_check`: `rebase_target_commit`, `previous_base_commit`, `rebased` pairs with `patch_id_match`
(a `git patch-id --stable` comparison), `dropped`, and `patch_id_mismatches`. A patch-id mismatch
means a conflict that was resolved with changes: the report is not rejected and does not lose its clean status, and the pair
is shown for delta-review. Accepting such a report pins `integration_base_commit` = target,
and accepting a later retry whose candidate already stands on this target acts the same way. A retry of a not-yet-accepted
rebase report, like its `tooling-retry`, counts both `changed_files` and the commits of
`carried_item_closure` from the target. If the tip moves again, review and QA check the pinned candidate, and the branch
is updated by `integration refresh` when the PR is prepared (ADR 0014).

A batch created on a branch with commits of an earlier batch of the same ticket (its `branch_start_commit`
is a strict descendant of `integration_base_commit`) counts its changes from `branch_start_commit`. The
`changed_files` and `commit_map` of the developer and publish reports, their `scope_warnings`, the
checkpoint, and `risk assess` (`--base-commit`, `review_scope`) are counted from it. A superseding batch counts from
`integration_base_commit`; a batch whose start is not a descendant of this base (after an accepted
rebase and for a resolver batch) counts the same way. The brief and the Context Package (`--base-commit`) stay on
`integration_base_commit`. The rule does not distinguish accepted commits from unverified ones: the new batch does not review the commits
of an abandoned (`abandon`) batch.

Delta-review after fix-forward is also not a new transition and not a new decision. The coordinator itself
chooses the scope of the next code-review in `dispatch propose` and `dispatch create --role code-review`
without `--delta-review-of`. The coordinator makes the choice when all conditions are met: the candidate is the
`commit_sha` of the latest accepted developer work report of the batch; this report is a developer-retry; the
route `fix-forward` or `rebase-fix-forward` opened its chain of consecutively repeated developer-retry attempts;
the latest code-review before the chain finished its report on the `snapshot_commit` of the chain's first
attempt and was accepted or repeated in a developer. This code-review is the prior review. The brief
gets the field `delta_review_scope`: `mode` (`delta` or
`full`), `route`, `prior_review` (dispatch ID, `report_sha256`, the verified candidate,
`review_base`, `risk_assessment_id`), `developer_dispatch_id`, `delta_base`, `delta_commits`,
`reviewed_copies`, `closure` (the `carried_item_closure` of the accepted report), and `escalations`. The transition
binds the section with the field `delta_review_sha256`. `dispatch propose` shows it as
`delta_review_scope`. In all other briefs, the field is `null`, including with an explicit
`--delta-review-of`: a test-only delta-review works as before.

The delta is `git diff <delta_base> <candidate_commit>`. Without a rebase, `delta_base` is the candidate of the prior
review, and after a rebase in the chain, the commits after the last rebase target are taken. The leading
carried-over copies count as verified (`reviewed_copies`) if, by the `rebased_from` pairs from the
`rebase_check` of the chain reports, they lead to a commit from the range of the prior review and `git patch-id`
matches at every step; `delta_base` is the parent of the first other commit. The coordinator selects the mode
`full` automatically, without a manual choice, if at least one escalation `{reason, evidence}` is found:

- `new-risk-trigger` — a trigger of the risk assessment of the candidate (together with the developer triggers) or
  of the commits and files of the delta that was not in the assessment of the prior review;
- `file-outside-carried-items` — a delta file outside the files of the carried developer-retry items (for a
  `review-finding`, this is the `review_scope` of its review);
- `patch-id-mismatch` — a pair from `patch_id_mismatches` of any report of the chain;
- `dropped-commit` — a `dropped` record from the `rebase_check` of any report of the chain: the candidate lost
  a change that the prior review verified, and the delta of the remaining commits does not show this;
- `no-new-commits` — there are no new commits to check.

In this case, the brief is an ordinary full review, and the section remains audit evidence. In `delta` mode,
the `carried_items` of the brief additionally carries the `review-finding` and `incomplete-item` items for the developer from the
brief of the accepted developer-retry. The reviewer checks both axes only on the delta, and for the rest of the
candidate relies on the report of the prior review; the reviewer accounts for each item in `review.carried_items`, and
an omission, `open`, or `unverified` is a carried gap. `review_scope` and `review.scope` stay
full. Accepting any review, delta or full, leads to `qa`, and the clean-room QA runs on the new SHA with the
full `verification_commands`. A delta-review retry passes to the next developer-retry
the carried items that the review did not mark `closed`, and the review's own findings
get the next numbers `review-finding-N`.

A code-review `blocker` is never accepted. While `retry_policy.max_developer_retries` still allows a
developer retry, `retry` or `abandon` is available for it. After the budget is exhausted, `retry`
is rejected, and the blocker is closed through `block`, `fail`, or `abandon`. Then the work is split
or re-planned in a new batch. `tooling-retry` does not spend this budget and is not rejected when it is
exhausted. A human still decides each such retry, and the attention `tooling-retry-repeated` limits
a series. `--retry-role developer` on a read-only stage still gives a
`developer-retry` that spends the budget.

The `abandon` decision is available after any completion report. It requires an explicit approval and a non-empty
`--reason`, moves the batch to the terminal `abandoned`, and marks unclosed dispatches as
`abandoned`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide \
  --batch <batch-id> --decision abandon --approved-by 'имя утверждающего' \
  --approved-at 2026-09-20T09:00:00Z --reason 'план заменён, начинаем новый batch'
```

`abandon` does not delete the worktree, candidate, brief, report, Context Package, or audit evidence, does not
close the issue, and does not create a PR. Only what does not belong to evidence is removed: staged copies of
reports in the agent inbox and QA-queue records of dispatches that will no longer run (a live QA lease
is still released only by `qa clear-stale-lease`). The batch records `abandoned.last_accepted`, the
latest accepted stage and its candidate. From it, you can create a fresh batch on the same branch and the same
candidate. `abandon` never serves as an automatic fallback for `block`, `fail`, or `retry`.
The `batch abandon` command for a batch that will never have a report stays as before. It
ends such a batch in `failed`.

#### Superseding batch: `batch create --supersedes`

If a batch is closed by the `batch decide --decision abandon` decision after a dead end (for example, a code-review
blocker with an exhausted retry budget), a superseding batch continues the work. It is created for
the same ticket and the same issue branch and starts from `abandoned.last_accepted`, not from a new architect
and a manual cherry-pick of the accepted commits:

```bash
python .harness/orchestration/coordinator.py --repo . batch create \
  --ticket '#443' --branch feature/issue-443-<slug> --worktree <тот же worktree> \
  --allowed-path '<scope>' --definition-of-done '<item>' --prohibited-change '<rule>' \
  --supersedes <abandoned-batch-id> --approved-by 'имя утверждающего' \
  --approved-at 2026-09-20T09:00:00Z
```

`--supersedes` requires human approval. `--approved-by` and `--approved-at` are checked the same way as
for `batch abandon`: the approval TTL and the terminal confirmation when `human_approval_gate: tty`.
An approver with the `policy:` prefix is rejected. Approval flags without `--supersedes` are also rejected:
an ordinary batch is approved through `batch approve`. A superseding batch also goes through
`batch approve` after creation. The command names a remedy and writes nothing in these cases: the source is not in the current
generation of the ledger; its state is not `abandoned`; `abandoned.last_accepted` is `null`; the ticket or
issue branch differs; the latest accepted candidate does not resolve to a commit. A batch closed by
`batch abandon` stays in `failed` without `last_accepted`. With `null`, nothing was accepted. In both
cases, an ordinary batch is needed. The exception is a source with `null` that itself superseded a batch. Then the
remedy suggests passing that batch (the `supersedes.batch_id` of the source) to `--supersedes` again, because its
`last_accepted` is still the latest. An abandoned batch does not hold the ticket, branch, or worktree. But
another unfinished batch with the same ticket, branch, or worktree still blocks creation.

The new batch and its immutable plan carry the same immutable `supersedes` reference: `batch_id`,
`approved_by`, `approved_at`, a copy of `last_accepted`, `definition_of_done_matches`, `architect`,
`start_commit`, and `rebase_target_commit`. A batch whose reference diverges from the plan fails the
integrity check. The `coordinator_decisions` of the new batch contain one `supersede` record. Its routing record
of the `supersede` route names `previous_role`, `next_role`, `next_action`, `candidate_commit`
(`start_commit`), `rebase_target_commit`, `superseded_batch_id`, `rationale`, and `decided_at`.

What is carried over:

- with the same Definition of Done (the lists match item by item): the accepted architect of the source by
  the reference `supersedes.architect` (`batch_id`, `dispatch_id`, `report`, `report_sha256`,
  `commit_plan_sha256`) and the commit plan pinned at its accept through `--commit-plan-file`.
  If the source itself carried over an architect, the same reference is passed. The batch starts with
  `next_action: developer`: the developer dispatch is created at once, and an architect dispatch is not allowed.
  With a different Definition of Done, nothing is carried over, and the architect stage runs again;
- `start_commit` is the candidate from `last_accepted` (`null` if only an architect was accepted). For a
  superseding batch without an accepted developer, this candidate is its own `start_commit`.
  Therefore the next superseding batch in the chain does not lose the accepted candidate. The first developer
  dispatch takes it as `snapshot_commit`. The brief, the preflight, and the Context Package freshness check
  see the same SHA. If `start_commit` is a descendant of the integration base pinned at create,
  this is an ordinary initial developer: its `commit_map` covers all commits after the base, including the
  `start_commit` commits;
- `rebase_target_commit` is this base, if `start_commit` does not contain it. Then the first developer is a
  developer-retry of the rebase route inside the retry. It rebases the commits onto the target, fixes
  on top, and submits the `rebased_from` pairs. `report submit` returns `rebase_check`. Such a dispatch
  requires an explicit approval with a transition digest under any `approval_policy` except `auto`. The target
  stays in the brief until the snapshot being continued contains it. This happens, for example, after a retry of
  a report that was not yet rebased.

What is never carried over: the risk assessment, code-review, QA, carried items, candidate registrations,
and operator decisions. They stay evidence of the abandoned batch and are available only through
`supersedes.batch_id`. The risk assessment, review, and QA run again on the new candidate. The `supersede`
record is not a retry and does not spend `retry_policy.max_developer_retries`: the superseding batch has its
own budget. The abandoned batch is only read. The worktree must stand on `start_commit`. If
the dead-end attempt left unaccepted commits above it, the runtime attestation rejects the developer with a
remedy. A human decides to move the branch back. The coordinator looks for the source only in the current generation of the
ledger.

#### The `route` field: routing record, decision packet, and audit

Every `retry` and `abandon` decision in `batch decide` records the selected recovery route in
`routing.route`, one value of the closed set `RECOVERY_ROUTES`: `developer-retry`,
`same-candidate-rerun` (a new code-review, qa, or publish on the same SHA), `verification`,
`architect-retry`, and `abandon`. `batch decide` either records the other values under special
conditions or does not record them at all:

- `batch decide` does not record `report-completion`. It is named by `completion` in `report submit`
  when the policy chain stopped after the recorded report (see step 4 above and "Busy ledger"
  below).
- `carry-over` is recorded by `accept` or `override-warning` with `--findings-file` and by `batch carry-over`
  (see step 4). This is a routing record with `previous_role: developer`, `next_role` and `next_action`
  `code-review`, `candidate_commit`, `carried_item_ids`, and `rationale`, without `reason_category` and
  `decided_at`; it does not apply to `next_action`, and the next step goes through the risk assessment, as with
  any developer accept. The same route is recorded by `accept` or `override-warning` of a read-only
  report with `--carry-incomplete` (see step 4): then `previous_role` is the stage of the report, and `next_role` and
  `next_action` are the ordinary next step of its accept.
- `tooling-retry` is recorded by `retry` with the category `tooling` (see above), and also by `retry --narrowed`
  if an item carries a `tooling_blocker`.
- `bypass-rerun` is recorded by `retry` with the category `block-bypass` (see above).
- `narrowed-retry` is recorded by `retry --narrowed` for the unfinished items of a read-only report (see
  step 4); its routing record additionally names `carried_item_ids`.
- `fix-forward` is recorded by a `retry` that leads to `developer-retry` with a non-empty closed list
  of carried items (see above).
- `rebase-fix-forward` is recorded by a `retry` that leads to `developer-retry` while the integration base
  has moved forward (see above); its routing record additionally names `rebase_target_commit` and
  `integration_base_commit`.
- `batch decide` does not record `supersede`: `batch create --supersedes` records it in the
  `coordinator_decisions` of the new batch (see "Superseding batch" above).

Every routing record with `next_action: developer-retry` (`developer-retry`, `fix-forward`,
`rebase-fix-forward`, and the developer `tooling-retry`) additionally names `retry_item_ids`. The route
is set in the same place as `next_action`, from the same structured data and never from free
text. The `abandon` routing record has the same shape, but `reason_category`, `next_role`, `next_action`, and
`candidate_commit` are `null`, and `rationale` contains only structural facts (`--reason`
stays in `note`). The normative table "situation → route → who approves → evidence" is the section
"Recovery route table" in `.harness/orchestration/playbook.md`.

`batch decision-packet` shows the route before the decision is recorded: the field `route_preview` contains
`retry`, the routing record computed the same way as in `batch decide` (without `decided_at`), and `abandon`,
`{"route": "abandon"}`. The packet accepts the same `--reason-category`, `--retry-role developer`, and
`--narrowed` as `batch decide`, and writes nothing. For an already decided report and for the packet of the
next dispatch, `route_preview` is `null`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet \
  --batch <batch-id> --reason-category verification-infrastructure
```
### Automatic path `approval_policy: auto`

The `auto` policy applies while the project configuration and the batch plan select `auto` and the batch has no
`auto_stop`. The session does not pass `--approved-by` or `--approved-at`. The policy approves:

- `batch approve`: `coordinator_approval.approved_by` equals `policy:auto`;
- `dispatch create`, including the milestones `publish`, `risk-trigger`, `risk-reassessment-required`,
  `bypass-rerun`, `rebase-fix-forward`, and `rebase-target`;
- `dispatch resume --trigger` for a planned continuation, except `human-decision`;
- `batch carry-over`: the decision is written as `policy:auto`, not as `policy:carry-over`.

An explicit `--approved-by` under `auto` remains a human approval. Each policy approval is one hashable record
in `batch.auto_decisions` (`sequence`, `kind`, `dispatch_id`, `approved_by`, `approved_at`, `rationale`,
`evidence`). Ledger validation recomputes `record_sha256` and checks the record against the approval it names.

The `report submit` or `qa run` chain accepts a clean report as before. For all other reports, including the publish
report, the session runs:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-decide --batch <batch-id>
```

The command computes the decision from the ledger facts, passes it through the `batch decide` checks, and writes it
as `policy:auto` with the route, the reason, and the evidence. The session passes only the inputs that require
judgment:

- `--commit-plan-file` is the architect's plan. The policy pins the plan if it lies inside `allowed_paths` and
  covers all DoD items. Otherwise the path stops. If the command cannot read the file as a JSON object, it refuses
  and writes nothing.
- `--findings-file` holds the coordinator's findings for an accepted developer report.
- `--bug-ticket` is the tooling bug ticket for `tooling-retry`. Without it, the command refuses and writes
  nothing.
- `--block-bypass --note` applies when a role bypassed a hook or tool block.

The policy accepts a clean report and records its risks as `accepted_risks`. A review report in which the Standards
or Spec axis names `blockers` is not clean. For all other reports, the policy selects `retry` according to
`route_preview`. The policy never selects `override-warning`, `block`, `fail`, or `abandon`. A conflict-resolver
report is outside the automatic path: a human decides it.

The closed list of stops:

| `category` | `reason` |
| --- | --- |
| `integrity-failure` | `stale`, `model-mismatch`, `worktree-mismatch`, `harness-snapshot-changed`, `deterministic-gate-failed`, `ledger-validation-failed`, `operational-hold` |
| `budget-exhausted` | `retry_policy.max_developer_retries`, `continuation_policy.max_continuations`, `continuation_policy.max_rate_limit_resumes`, `attention_policy.max_infrastructure_retries`, `tooling-retry-repeated` |
| `no-automatic-route` | `unknown-reason`, `abandon-dead-end`, `supersede-dead-end`, `qa-environment-failure` |

`batch auto-decide` and `batch auto-report` find a stop in this order: integrity, budget, route.
The coordinator writes the stop once in `batch.auto_stop`, together with the final report.
The command only prints `ledger-validation-failed`: the ledger is untrustworthy. The policy writes the
`operational-hold` stop when the runtime store holds the batch: the policy does not decide the report and does not
abandon, and only `recovery resume` releases the hold (section "Batch hold and the `recovery` commands").
A stop creates no decision and does not weaken validation. After a stop, every batch step requires `--approved-by`,
and the batch cannot return to `auto`.

The policy also writes the `no-automatic-route`/`unknown-reason` stop when a read-only stage or publish fails with
`UnprovenFailureError` (see "Failure domains"): the decision is not written, and the stop evidence keeps `failure`.

The coordinator writes the final report once in `batch.auto_report`: when the publish report is accepted or at a
stop.
The report lists the `policy:auto` decisions, the accepted risks, the findings, the retries and the spent budget,
the DoD coverage by commit plan, the review and QA results, and the stop. The command prints the report:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-report --batch <batch-id>
```

If no report is recorded, the command records the stop that the ledger shows, or prints a live report with
`recorded: false`. The policy does not open or merge a PR: a PR opens only after explicit human confirmation, and
auto-merge is prohibited.

### Approval bound to the transition digest

`dispatch propose` takes the same arguments as `dispatch create`, but does not write a brief. It registers the
shared Context Package that the brief will pin. Then it returns the canonical transition and its
`transition_digest`. This is the SHA-256 of the batch ID, the ID and role of the previous dispatch, the reason
category, the next role/action and purpose, the candidate SHA, the base SHA, the review scope, the verification
commands, the Context Package ID, and the required gates. `dispatch create` with an explicit approval must receive
this digest in `--transition-digest`. The coordinator recomputes the transition from the ledger and rejects any
mismatch. So a change of scope, candidate, role, verification command, reason category, or Context Package
requires a new `propose` and a new approval. The coordinator stores the digest in the approval and in the
immutable brief, together with the transition itself. Ledger validation recomputes it. A policy approval
(`milestone`, `low_risk`) is derived from the transition being created and is bound to its own digest.
With `human_approval_gate: "tty"`, the confirmation prompt shows the digest.

If the Repo Map of the pinned package has a tier other than `full`, the `dispatch propose` result also contains
`context_package_quality_warning`: the tier, the reason for the degradation, and the parser provenance. This is a
warning for the approving human, not a dispatch block. For `full`, the field is absent.

Without `repo_map_policy.min_tier`/`min_tier_by_role`, Repo Map degradation never blocks a dispatch. Only the
non-blocking warning described above remains. `repo_map_policy` may contain `min_tier` (a common minimum for the
repository) and/or `min_tier_by_role` (a per-role override; the keys are exactly
`architect`/`developer`/`code-review`). The resolution order is then: the role override, then `min_tier`, then no
gate. If a minimum is set for the role and the actual tier of the pinned Context Package is worse than required
(the tier order follows ADR 0008: `minimal` < `full`), the coordinator rejects both `dispatch propose` and
`dispatch create` before any approval. The reason names the role and the actual and required tier. This check runs
in the shared path before the `propose`/`create` branch. So a ready `--transition-digest` does not bypass it. A
role that is not listed in `min_tier_by_role` keeps the default behavior (no block) when there is no common
`min_tier`.

An expired (`approval_ttl_seconds`) or terminal-rejected approval is fail-closed: the coordinator does not repeat
the call itself and does not substitute an older approval.

### Idempotency of a read-only retry

The brief of the roles `architect`, `code-review`, `qa`, and publish stores
`retry_idempotency_key = sha256(role + candidate SHA + base SHA + review scope + reason category +
digest verification commands)`. While the open batch has an active dispatch (not decided, not cancelled, not
abandoned) with the same key, a new dispatch is rejected. A finished retry does not block a new dispatch on the
same candidate: it gets a new immutable ID. A change of candidate always changes the key. A repeated review/QA never
edits the earlier report and brief.

### Context pressure

`dispatch context-pressure --dispatch <id> --observed-tokens <N> --source probe|provider-usage|
runtime-adapter` writes an observation with `observed_tokens`, `context_limit`, `warning_threshold`, `level`
(`ok`/`warning`/`critical`), and `recorded_at`. Without `--observed-tokens`, the configured
`context_telemetry_provider` supplies the number. The source is only the provider/runtime: a model self-report is
rejected. The limit and the warning share are values pinned in the brief. The record is a pure observation: it does
not change `next_action`, does not create a retry, and does not remove an approval. At `critical`, it states the
worker's obligation. A write role creates a checkpoint at the nearest green TDD boundary or returns a structured
blocker. A read-only role returns a blocker. A continuation is created only from a checkpoint and only with a new
model self-report. A retry with the category `context-pressure` requires such a `critical` record for the reporting
dispatch.

### Attention state

`needs_attention` is a batch flag, not a lifecycle state: it does not change `state`, `next_action`, the candidate,
or the evidence, but it prohibits the creation of the next dispatch. The fields `needs_attention`,
`attention_reason`, `attention_since`, `last_safe_action`, and `recommended_human_action` describe the flag. The
reasons:

| `attention_reason` | When |
| --- | --- |
| `operational-hold` | the runtime store holds the batch with the record `recovery/hold/<batch_id>.json`; after the cause is removed, a human resolves the attention, then `recovery resume` releases the hold |
| `unknown-reason` | a retry with the reason `unknown` |
| `infrastructure-retry-repeated` | operational retries of one candidate exceed `max_infrastructure_retries` |
| `tooling-retry-repeated` | the third consecutive `tooling-retry` on one candidate; cleared after the tool is fixed |
| `retry-queued-too-long` | an accepted retry waits for a dispatch longer than `retry_queue_seconds` |
| `stale-evidence` | the Context Package pinned in an unfinished dispatch diverges from the base or from the current developer candidate (the same one that `snapshot_commit` selects) |
| `stale-dispatch` | a live dispatch is silent longer than `stale_dispatch_seconds` |

`batch decide --decision retry`, `dispatch wait` (the `stale` event), and `batch attention check --batch <id>` set
the flag. The last command simply evaluates the batch now. Only a human clears the flag:
`batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …` acknowledges the open findings
(the same event is not raised again) and writes an event to `attention_events`. If `human_notifier` is configured,
it is called when the flag is set. An adapter failure is recorded as `failed` and does not cancel the flag.

### Compatibility and migration

All new batch fields and the four brief fields (`transition`, `transition_digest`, `retry_idempotency_key`,
`orchestration_policy`; either all or none) are optional. Records created earlier remain valid, the ledger version
does not change, and `ledger migrate` is not needed. New records pass the same integrity check (`context_pressure`
with a hash, the shape of the attention fields, brief consistency). The CLI behavior changed: `dispatch create` with
`--approved-by` now requires `--transition-digest`. A brief without the field `commit_plan_divergence` and a batch
without `commit_plan` also remain valid. A plan entry without `covers` covers the DoD item by its position. A brief
without `carried_items`, a transition without `carried_items_sha256`, a batch without `carried_items`, and a
code-review report without `review.carried_items` are also valid. An empty channel adds nothing to the transition,
so earlier digests do not change. A report without `incomplete_items` and a brief without the kind
`incomplete-item` are also valid. The new source kind, the report field, and the route value `narrowed-retry` were
introduced without a ledger version change and without a migration. A routing record without `retry_item_ids`, the
report field `carried_item_closure`, and the route value `fix-forward` were also introduced without a ledger
version change and without a migration. A developer-retry brief for a decision recorded before them gets a section
without a check against `retry_item_ids`. A completed developer-retry report that was recorded before the
`fix-forward` route appeared, without `carried_item_closure` for a brief with carried items, is still decided
through `batch decide`. Each item gets the status `omitted` and enters `carried_items_gap`. So `accept` and the
policy auto-accept are rejected, and `override-warning` requires a `--note` other than `none`. `retry`, `block`,
`fail`, and `abandon` are available. `report submit` rejects a new report of this kind. A brief without
`rebase_target_commit`, a transition without `rebase_target_sha`, and the route value `rebase-fix-forward` were also
introduced without a ledger version change and without a migration: a transition without a target keeps its
earlier digest. A brief without `delta_review_scope` and a transition without `delta_review_sha256` are also valid
and were introduced without a ledger version change and without a migration: a code-review transition without the
section keeps its earlier digest. The `supersedes` reference in a batch and plan and the route value `supersede`
were also introduced without a ledger version change and without a migration: a batch and plan without the
reference are read as before.

The `route` field in a routing record and the `decision` detail in the transition audit record of a batch are also
optional and were introduced without a ledger version change (it stays 3). A decision recorded before them is read
as is and remains valid. `ledger migrate` does not add or derive a route for it. Only a new `batch decide` decision
writes a route. A recorded `route` outside the closed set of routes is rejected when the batch is read.

### Inventory and closing a dead-end batch

To see what exists and what is not closed:

```bash
python .harness/orchestration/coordinator.py --repo . batch list --open
python .harness/orchestration/coordinator.py --repo . batch list --ticket '#123'
```

The normal path to a terminal state is `batch decide`, but it requires exactly one report awaiting a decision, and a
report requires a live dispatch with a confirmed model. A worker that died before its self-report never reports, and
neither `fail` nor `block` can close such a batch. A separate command exists for this case:

```bash
python .harness/orchestration/coordinator.py --repo . batch abandon \
  --batch <batch-id> --approved-by 'approver name' --approved-at 2026-09-11T06:00:00Z \
  --reason 'worker died before the model self-report, the decision is unreachable'
```

It requires an explicit approval and a non-empty reason, moves the batch to `abandoned`, keeps `last_accepted`,
marks all unclosed dispatches as `abandoned`, and writes the decision next to the others. **It deletes nothing**: the
immutable brief, the reports, and the QA artifacts stay in place. You cannot apply it again to a batch that is
already terminal.

After a confirmed launch failure, continue the same batch after you remove the cause:

```bash
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <batch-id> --approved-by 'operator name' --approved-at <current-UTC-time> \
  --note 'fixed the worker launch directory'
```

The command keeps the accepted reports, the original stop, and `next_action`, marks the failed dispatch as
`abandoned`, and moves the batch to `awaiting-approval`. The next `dispatch create` requires a new approval and keeps
the contract of the interrupted role. The detailed limits are described in the section "Manual recovery and stage
retry". For an unknown reason, or to return to an earlier gate, use `batch rewind`. `completed` and `abandoned` are
final.

Before sending, `dispatch send` checks the `--adapter-arg` flags against the adapter's `dispatch --help` and rejects
an unsupported flag before it passes the brief: the dispatch stays approved and unsent. If `--help` does not
respond, the result goes to `adapter_preflight` as a `limitation`.
`dispatch runtime-probe --dispatch <id> --runtime-command <runtime> --runtime-arg=app-server` checks the app-server
runtime without a worker: `model/list`, the `thread/start` fields, and one `turn/start` on an ephemeral read-only
thread without tools. A capacity, rate-limit, or unavailability error after `thread/start` gives a classified
failure, not READY. The probe writes nothing to the ledger and does not replace the model self-report.

The `stale` watchdog does not prove that the process ended. First stop the worker through its runtime, then record
`dispatch cancel --runtime-stopped` with a human approval and run a rewind.
The compatible command `batch resume` applies only to the earlier manual path without auto/recovery.
For a stale dispatch, it also requires `--runtime-stopped`, `--approved-by`, and `--approved-at`.

For an unfinished initial developer, pin the saved HEAD through `--candidate-commit` at the next
`dispatch preflight`, `dispatch propose`, and approved `dispatch create`. This is a startup snapshot, not an
accepted completed candidate: the risk assessment and the later gates follow the acceptance of the final report.
The commit map of the initial work covers the whole original plan from the batch base, including the commits saved
before the failure. Earlier risks stay in the report. `developer-retry` keeps a separate contract: only new commits
after the snapshot.

A batch is pinned to the runtime under which it was planned. `batch create` records the hash of the whole runtime
package in `.harness/`: the top-level modules and all subpackages (`orchestration/`, `gate_runner/`,
`context_builder/`, and others). It also stores an immutable snapshot of this package in
`.harness/orchestration/state/runtimes/`. If the runtime is reinstalled after that (for example, by
`harness update` from the branch of another task), the commands of this batch (`--batch`, `--dispatch`, or
`dispatch_id` in the `--file` file of `report submit`, `dispatch checkpoint`, and `dispatch telemetry`) run
automatically from the snapshot code. The role descriptions also come from the snapshot. New batches get the new
runtime. So tasks run in parallel and do not block each other. A snapshot that was changed by hand is rejected. For
a batch created before snapshots existed, the hash covers only `orchestration/`, and there is no snapshot. Restore
it from the package of the revision on which the batch was planned: a `.harness` from a temporary worktree where
`harness update` has run, or the `harness/` directory from `git archive <revision> harness`, will do:

```bash
python .harness/orchestration/coordinator.py --repo . batch restore-runtime \
  --batch <batch-id> --from <path to the package of the pinned revision>
```

The command accepts a directory only if its hash matches the pinned one. The snapshot and the new runtime work with
one ledger. So `ledger migrate` to a new schema version refuses to run while unfinished batches pinned to another
runtime exist. First finish them or cancel them on their own runtime.

If the pinned snapshot already satisfies all DoD items, do not create a fictitious commit for a write-role report
and do not use `abandon`. Record a separate terminal decision:

```bash
python .harness/orchestration/coordinator.py --repo . batch not-required \
  --batch <batch-id> --approved-by 'approver name' --approved-at 2026-09-11T06:00:00Z \
  --reason 'pinned snapshot already satisfies every definition-of-done item'
```

The command leaves audit evidence, cancels unclosed dispatches, moves the batch to `completed` with
`completion_kind: no-implementation`, and returns a recommendation to close the linked issue with the label
`resolution::wontfix`. An ordinary write-role report must still contain a real commit and the exact changed files.

If you find an error **before** the brief is passed to the runtime, do not abandon the batch. Cancel only this
unsent dispatch: the immutable brief stays in the audit trail, and the batch returns to `awaiting-approval` and can
get a corrected dispatch.

```bash
python .harness/orchestration/coordinator.py --repo . dispatch cancel \
  --dispatch <dispatch-id> --approved-by 'approver name' \
  --approved-at 2026-09-11T06:00:00Z --reason 'fix the assignment before the worker starts'
```

Never edit the files in `.harness/orchestration/state/` by hand. These records are the evidence for which the whole
route exists. If there is no standard command for your case, that is a tool defect, not a reason to open an editor.

### Model self-report and dispatch watchdog

A sent dispatch is not considered live by itself. As its first action after it receives the brief, the role
confirms the model that is really active:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch self-report \
  --dispatch <dispatch-id> --model <actual model> \
  --worktree "$(git rev-parse --show-toplevel)"
```

A match with the `resolved_model` of the immutable brief moves the dispatch to `working`. If
`worker_attestation_required` is on, the coordinator also checks the passed Git top-level, the issue branch of a
write role, or the pinned SHA of a review role. A mismatch immediately moves the dispatch to `blocked`, marks the
batch `blocked`, and ends the command with an error. After that, the coordinator does not accept `report submit` for
this dispatch. The fix is a new dispatch with a new brief, not an edit of the sent one. Without a successful
self-report, a completion report is not accepted at all. So a substituted or wrongly configured model is visible
immediately, not after the window is spent.

For architect/developer, `worker_attestation_required` also requires that the Git worktree HEAD at the moment of the
first `self-report` literally equals the immutable `snapshot_commit` from the brief. For an allowed
`dispatch resume` of a write role, the fresh self-report checks the exact `commit_sha` of the last registered
checkpoint. The original brief and the boundary of the commit-plan evidence stay unchanged. For architect,
developer, verification, and code-review, `dispatch create` selects `snapshot_commit` in this order:

1. an explicit `--candidate-commit`;
2. the `commit_sha` of an unaccepted developer report, while the batch waits for its `developer-retry`;
3. the last accepted developer candidate, for example `developer-retry` after a code-review blocker, qa, or publish
   (a repeat on the same SHA does not create a developer dispatch);
4. otherwise `base_commit`.

`dispatch preflight` and the freshness check of the Context Package use the same rule. A retry continues the
history of this candidate and adds separate logical commits according to the immutable commit plan. The coordinator
does not run or suggest `git reset --soft`. If the worktree HEAD does not match the pinned snapshot, fix the
configuration of the new dispatch or choose a worktree at this commit, without rewriting the existing history.

For `developer-retry`, `dispatch preflight` additionally returns `retry_start`: the handoff from which the new
developer session starts, its starting files, `context_estimate` (the threshold, and the estimate before and after
compaction), and `warning`. `decision_packet` repeats the estimate and the warning as `retry_context_estimate` and
`retry_context_warning`. The handoff content, the smart-zone threshold, and the compaction rules are in the section
"Developer-retry handoff" of `playbook.md`.

Before it writes the brief, `dispatch create` runs the same check on it as `dispatch send`. A brief that send would
reject is not created: neither the brief nor its status appears in the ledger. An example is `--candidate-commit`
without a linked immutable risk assessment. The remedy names
`risk assess --batch <batch-id> --candidate-commit <sha> --changed-file <path>...`. After it, a new
`dispatch propose` and `create` are needed (first cancel the unsent brief through `dispatch cancel`). The check at
`dispatch send` stays in place.

While the role works, it sends a heartbeat, and the coordinator session polls the state. By default, a dispatch
allows up to an hour of silence for a long build or test. But the immutable brief requires a heartbeat right after
the self-report and then at least once every five minutes. This keeps a fast signal about a live worker, and a
working developer does not become stale because of one long tool call:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch heartbeat --dispatch <dispatch-id>
python .harness/orchestration/coordinator.py --repo . dispatch status \
  --batch <batch-id> --stale-after 3600
```

For each dispatch, `dispatch status` shows the role, the transport, `resolved_model`, the self-report result, the
`startup` estimate (the worker state, the failure classification, the unknowns), the time of the last heartbeat,
`silent_seconds`, and the `stale` flag. This generalizes the QA lease expiry to any dispatch, not only to the
clean-room QA lane. Stale is a blocker that the coordinator escalates to a human; the coordinator does not change
the state on timeout by itself.

`dispatch heartbeat` takes an optional pair `--context-tokens <N> --context-source probe`. This is the number of
tokens that the coordinator measured in a live context probe (see "Reporting and token monitoring" below), not a
role self-report. This keeps the rule from the beginning of the document ("Tokens are only observable provider or
runtime telemetry", lines 27-29): the role itself does not supply this value. The value goes into the open `extra`
field of the dispatch status. The ledger schema does not change, and no new event is introduced in `dispatch wait`.

For each dispatch, `dispatch status` additionally returns the last `telemetry` record (`dispatch telemetry`, see
below) and `context_advisory`. This is a pure read, and missing telemetry is not an error: `telemetry` and
`context_advisory.observed` are then `null`, and `context_advisory.level` stays `"ok"`.

### Busy ledger, `report complete`, and `ledger release-lock`

Each coordinator command takes an exclusive ledger lock (`.coordinator.lock` in the state directory). The lock
records its owner: `pid`, `host`, and `acquired_at`. On a platform with `/proc`, the record is extended with
`pid_namespace` (the `/proc/self/ns/pid` link) and `boot_id`, and also with `operation`, the coordinator command
that took the lock. Old records without these fields are read as before. The lock is held by whoever first created
this record exclusively. A process gets a refusal and does not write into a foreign lock if its still empty lock
directory was removed and taken again. While another operation holds the lock, a write command ends with the error
`ledger is locked by another operation`. Its remedy suggests repeating the command and names `ledger release-lock`,
not a manual delete.

Coordinator polling survives a busy lock:

- `dispatch wait` counts a busy lock as a skipped poll and keeps polling until its `--timeout`. The report is
  returned as soon as the lock is free. If the lock stays busy until the end of the wait, the result is the ordinary
  `{"dispatch_id": ..., "event": "timeout"}`;
- `dispatch status` with a busy lock ends with exit code 0 and answers in a structured way:
  `{"ledger_busy": true, "retry_after_seconds": ..., "lock": {...}, "remedy": ...}`. Here `lock` contains the owner
  and `held_seconds`. This is not an unavailable coordinator: repeat `dispatch status` after
  `retry_after_seconds`.

The tolerance applies only to these two polling commands, `report complete`, and the release of the QA lane in
`qa run`. No write goes without the lock. For the other commands, a busy lock remains an error. With a busy lock,
`report complete` stops at the step that could not read the state. It writes nothing, and its remedy names itself
for the repeat.

`qa run` releases the QA lane after a failure and after the report is written. If the lock is busy, the release
waits for it for up to 30 seconds and retries every 0.25 seconds. When the lock is free, `qa run` removes only the
lease and the queue record of its own dispatch. After a failure, it also returns the dispatch to `approved`, and the
same dispatch can be started again right away. If the lock is busy for all 30 seconds, the error
`QA dispatch <id> was not released` names the dispatch, the lease owner, and the time the lease expires. The
dispatch then stays `working`. After the lease expires, the coordinator runs `qa clear-stale-lease`. The command
removes the lease and the queue record and returns the dispatch to `approved` if it has no recorded report. After
that, the same dispatch is started again. The command response and the record `qa-lane/recoveries/*.json` contain
`restored_dispatch_state`: `approved` or `null`. The rollback of a run that outlived its lease does not remove the
lease of a new run of the same dispatch and does not change its state.

A read-only command shows the lock state. It does not take the lock, so it works when the ledger is busy:

```bash
python .harness/orchestration/coordinator.py --repo . ledger lock-status
```

The response is `{"locked": false}` or an object with the fields `acquired_at`, `held_seconds`, `owner`,
`operation`, `verdict` (a verdict from the table below), `stale_after_seconds`, `remaining_seconds` (how long until
the timeout release, not less than zero), and `release_available` (whether the ordinary `release-lock` would release
the lock right now). The "Lock ledger" panel in the orchestration section of the Harness console shows the same
information; the hold time and the remainder update on the live screen.

Only a command with an owner check releases a lock that stays busy:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock
```

The verdict depends on the owner:

| Lock owner | Verdict |
| --- | --- |
| The owner process is alive (on this host, in the same PID namespace and boot) | refusal `owner-alive`, at any lock age |
| The owner is on another host | refusal `owner-on-another-host`: run the command on that host |
| The owner is from another PID namespace or another boot, the lock is younger than `LEDGER_LOCK_STALE_SECONDS` | refusal `owner-in-other-environment`: the pid of a worker from a sandbox (`--unshare-pid`) points to a foreign process, so it cannot be checked |
| The owner is from another PID namespace or another boot, the lock is older than `LEDGER_LOCK_STALE_SECONDS` | released, `owner-unknown-stale` |
| The owner process has ended (on this host) | released, `owner-dead` |
| There is no readable owner record, the lock is younger than `LEDGER_LOCK_STALE_SECONDS` (3600 s) | refusal `owner-unknown-recent`; the remedy names how many seconds until the lock can be released |
| There is no readable owner record, the lock is older than `LEDGER_LOCK_STALE_SECONDS` | released, `owner-unknown-stale` |

A readable owner record is missing in two cases. First: the lock was taken by an old runtime, and there is no record
at all. Second: the owner died after it created `owner.json` but before it wrote it; the record is empty or
unreadable. The age of an unreadable record counts from the mtime of `owner.json`, and without a record, from the
mtime of the lock directory. While the lock is younger than the threshold, the owner may still be writing itself, so
the command refuses. An owner that has not written the created record within `LEDGER_LOCK_STALE_SECONDS` is
considered ended.

Success returns `{"released": true, "reason": ..., "lock": {...}}`, and if there is no lock,
`{"released": false, "lock": null}`. A refusal is an error with the reason, the owner, and `held_seconds`, and the
lock is not touched. The `lock` object describes the released lock:

| Field | Meaning |
| --- | --- |
| `path` | the lock directory |
| `owner` | the owner record (`pid`, `host`, `acquired_at`), or `null` if there is no readable record |
| `owner_record` | `readable`: the record was read; `unreadable`: `owner.json` exists but is empty or unreadable; `absent`: there is no record |
| `acquired_at` | `acquired_at` from the record, otherwise the mtime of `owner.json` for an unreadable record, or of the lock directory |
| `held_seconds` | how many seconds the lock has been held at the time of the check |

In the runtime store epoch (store schema 3), `ledger lock-status` keeps the fields of the file lock and their
verdicts and adds the `qa_lease` object: the owner of the QA-lane lease, the identity of its process,
`fencing_token`, `expires_at`, `stale_heartbeat`, the runtime verdict, and `release_available`. If the file lock is
not busy, `ledger release-lock` without `--force` releases an expired lease only with the verdict `owner-dead`. The
command rejects a live owner with exit code 2 and the line `REMEDY: [lease_held] stale_heartbeat=… verdict=…`.
`--force` with an approval and a reason releases the lease at any verdict through `lease_clear`, and the runtime
writes the decision to the audit.

#### Parallel writes, read snapshots, and the QA-lane lease

Commands of different batches write in parallel. A command reads the store from one snapshot (`state.read` with
`snapshot`): a commit of another batch between its two reads gives neither a refusal nor half of two states. Read
commands (`dispatch status`, `batch auto-report`, `batch decision-packet`, `qa status`) do not wait for a writer.
A write to one batch is still serialized by the `revision` of the row. A decision across all batches
(`concurrency_budget` in `dispatch create`, a duplicate ticket, branch, or worktree in `batch create`) is protected
by the revision of the `generation` row from the snapshot of this decision. Of two commands that decided from one
state, one commits, and the other gets `revision_conflict` on `generation`
and retries.

The QA lane in the store is a singleton lease with a `fencing_token`. `qa run` and `integration local-qa` take it
with the `lease_acquire` operation. The runtime records the identity of the owner process from the kernel: host,
boot, PID namespace, pid, and the process start time. Each new lease increases `fencing_token`. The owner extends
the lease by heartbeat every third of `lease_ttl_seconds` (300 s by default; `--lease-seconds` overrides the term).
A release or heartbeat with a foreign owner or token gets `fencing_mismatch`. After `expires_at`, the runtime checks
the owner by identity only:

| Verdict | Meaning | Lease |
| --- | --- | --- |
| `owner-dead` | the same host, boot, and PID namespace, and no process with this pid | released without `--force` |
| `owner-alive` | the pid is taken by a process with the recorded start time | stays |
| `owner-pid-reused` | the pid is taken by a process with a different start time | stays: this does not prove death |
| `owner-in-other-environment` | another boot or PID namespace | stays |
| `owner-on-another-host` | another host | stays |
| `owner-unknown` | there is no identity (a schema 2 lease, a client outside the runtime's view) | stays |

The next `qa run`, `integration local-qa`, or `ledger release-lock` releases the lease of a dead owner. The audit
record contains the owner, the identity, the observation, the verdict, and the time. Like `qa clear-stale-lease`,
the release deletes the owner's queue record, returns its QA dispatch to `approved`, and writes `qa-lane/recoveries`.
With any other verdict, the request ends with exit code 2 with `[lease_held]` and `stale_heartbeat`. `qa status`
shows `stale_heartbeat`, and `dispatch status` shows the lane in the top-level object `qa_lane`. Neither the
automation nor `ledger release-lock` without `--force` releases a live owner. The manual override remains
`ledger release-lock --force` or `qa clear-stale-lease`. Start `harness-runtime serve` in a PID namespace that the
coordinators can see (the host or an ancestor of their sandboxes). A runtime that does not see the client does not
record its identity, and such a lease is not released automatically.

The command releases only the lock that it checked: if the owner changed during the release, it refuses and asks
for a repeat. Runs of `ledger release-lock` do not overlap, because an OS file lock
(`.coordinator.lock.release` in the state directory) serializes them, and the system releases it itself when the
process exits. A second parallel run gets the refusal `another ledger release-lock is releasing the ledger lock`
and repeats after the first. You must not delete the lock or other state files by hand.

If a stopped worker left the lock and its pid matches a live process (an old record without `pid_namespace`, the
verdict `owner-alive`), or you cannot wait for the timeout, the operator releases the lock by force:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock --force \
  --approved-by "<operator>" --approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --reason "<why the owner will not finish the operation>"
```

Without `--approved-by`, `--approved-at`, or `--reason`, the command refuses; a `policy:...` approval is rejected,
and with `human_approval_gate: tty` it must be confirmed on the terminal. No policy, including `auto`, runs this
command. Before the release, the command writes an audit record with a checksum (`record_sha256`) to `lock-audit/`
in the state directory: who approved it and when, the reason, the verdict of the check, and the previous state of
the lock. If the lock could not be released after the record was written, a second record,
`ledger-lock-force-release-failed`, names the first. `ledger validate` checks the checksums of these records; it
does not detect a record replaced together with its checksum, or a deleted file. In the console, the same action is
the command "Release ledger lock" with a confirmation.

### Lifecycle writes in the runtime store epoch

After `harness-runtime migrate` (`ledger.json` version 4), the Rust runtime accepts every batch and dispatch
mutation, not a file write and not the `.coordinator.lock` lock (ADR 0020, ADR 0021, section 4). Python does not
open `runtime.db` and has no fallback write path: without a running runtime, a write command refuses with exit
code 2 and `[runtime_unavailable]`, and creates and changes nothing.

- **Write unit.** The `_ledger_lock` block of a command became its write unit. The ledger primitives
  (`write_immutable`, `write_artifact`, `replace`, `delete`) only accumulate mutations, and the command reads its
  own writes from its own view. On a clean exit from the block, the coordinator sends one `state.write` operation
  per batch; an exception inside the block sends nothing except the records that the failure saves itself (the
  attempt record on an access refusal of `qa run` and the `needs_attention` flag on a refusal of `dispatch create`:
  before the exception, they call `persist_writes`, as the file ledger held them). Each outer `_ledger_lock` block
  and each `read_state` reads a fresh store snapshot, so the `dispatch wait` poll sees a new `reported` and new
  heartbeats; reads of a command before the block see the snapshot of its start. A nested block joins the outer
  unit. If the mutations touch two batches, they go in two transactions: each is atomic, but not both together.
- **CAS by revision.** `state.read` returns the `revision` of each row (`batch`, `dispatch`, `dispatch-status`,
  `qa-lane`, the QA queue, the `record` row). The first touch of an existing row carries the revision that the
  command read; the request envelope carries the revision of the batch row (0 at creation). A committed transaction
  increases the revision of each affected row by exactly 1. A stale revision gives `revision_conflict`, and nothing
  is written.
- **Transaction.** `BEGIN IMMEDIATE`, then the rows in the order `batch` → `qa_lane` → `generation` (the batch rows,
  the QA-lane rows, then the audit and the `operations` row); one audit record per mutation in request order.
  Immutable records (plan, brief, report, checkpoint, evidence) are not replaced and not deleted
  (`invariant_violation`). SQLite checks the schema invariants: CHECK for the batch and CHECK for the execution
  state (`DispatchState` is terminal while the execution is `unknown`, `launching`, or `running`).
- **Idempotency.** The `operations` row (`intent`, `committed`, or `failed`) is written in the same transaction. A
  repeat with the same `operation_id` and the same request digest returns the stored result; the same
  `operation_id` with a different request gives `idempotency_conflict`. `operation_id` equals
  `sha256(batch_id, expected_revision, operation, payload_digest)` (ADR 0021, section 4). The payload contains
  times, so a command restarted after a SIGKILL of the coordinator builds a new key, and the CAS by `revision`
  answers `revision_conflict`, not the stored result: the command must be repeated.

| Code | When | Retry | REMEDY (first line) |
|---|---|---|---|
| `revision_conflict` | another command changed the row after the read | yes | `[revision_conflict]` repeat the command: it reads the store again and applies the policy to the current state |
| `store_busy` | the store is busy longer than 5 seconds | yes | `[store_busy]` repeat the command |
| `runtime_unavailable` | the runtime does not respond | yes | `[runtime_unavailable]` start `harness-runtime serve --repo <repo>` |
| `idempotency_conflict` | `operation_id` is already taken by another request | no | `[idempotency_conflict]` repeat the command: it derives a new id from the current revision |
| `invariant_violation` | the change breaks a store invariant or the audit chain does not converge | no | `[invariant_violation]` stop the writers and run `ledger validate --full` |

Each refusal ends the command with exit code 2 and starts the first `REMEDY:` line with the code in brackets.
Commands that waited for a busy ledger treat `store_busy` as a busy ledger: `dispatch status` answers
`ledger_busy`, and the `dispatch wait` poll skips the busy tick and repeats it. In the store epoch, the
`_ledger_lock` block does not wait for a lock: `store_busy` comes from `state.read` or from sending the write, that
is, already inside the block. So the release of the QA lane after `qa run` does not wait 30 seconds, as with a file
lock, but passes `store_busy` through at once; the lease and the queue record stay until the lease expires, and
`qa clear-stale-lease` releases them.

#### The audit chain and `ledger validate --full`

The audit chain is stored in the `audit` table: each record is linked by hash to the previous one, and the first
record is `legacy-import` with the anchor of the import manifest. The `audit_checkpoint` table remembers the last
checked record. An ordinary command (read and write) checks only the records after the checkpoint; a write moves
the checkpoint in its own transaction. A missing or damaged checkpoint means a full check, and the next write or
`ledger validate` rebuilds it without an error. A write builds the missing checkpoint before the `BEGIN IMMEDIATE`
transaction (the full check runs in a read snapshot that does not block writers), so inside the transaction only the
tail of the chain is checked (ADR 0020, section 3). An unreadable store gives `store_busy` (the lock is busy) or
`internal` during the check, not `invariant_violation`: send the operator to the snapshot recovery only when the
chain does not converge.

`coordinator.py ledger validate --full` does not use the checkpoint. It recomputes the chain from genesis (the `seq`
sequence, the hashes of the records and links, the closed vocabulary of actions), checks record 1 against
`store_meta` and `AUTHORITY.json`, recomputes the import manifest and the hashes of the legacy audit and the
generations, runs `PRAGMA integrity_check` and `foreign_key_check`, and checks each row written by a command against
the last audit record of its path. This finds a deleted, inserted, or reordered record and a row changed outside the
runtime. Rows that were imported and not rewritten after the import are checked only by the `migrate` parity. A
failure writes nothing; a success rebuilds the checkpoint. In the file ledger epoch, `--full` is accepted and equals
the ordinary check (there is no cache).

In the runtime store epoch, `ledger migrate`, `ledger clean`, and `ledger reset` refuse with exit code 2: the
history is already imported, the store holds no orphaned records, and the command cannot reset it.
`ledger status` shows the epoch and the number of audit records.

### Reporting and token monitoring: `dispatch telemetry`

```bash
python .harness/orchestration/coordinator.py --repo . dispatch telemetry --file telemetry.json
```

The command writes source-observed metrics (of a worker or coordinator session) to the audit trail of the batch:
`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `max_context_tokens`, `tool_calls`,
`tool_output_bytes`, `poll_turns`, `restart_reason`, `recorded_at`. A missing provider field stays `null`, not an
estimated zero. The command is **intentionally data-only**: it only writes a telemetry record and cannot change the
role state, the scheduling, the approvals, or the model routing.

In the **return value** (not in the stored ledger record), the command adds
`context_advisory: {"level": "ok"|"warn"|"over", "limit", "warn_at", "observed"}`. This is an advisory estimate of
`max_context_tokens` against the threshold `adaptive_continuation_policy.context_limit` in the project
`.harness/orchestration.json`. `adaptive_continuation_policy.context_warn_ratio` sets the share of the threshold
for the warning (a share of `context_limit`, `0.8` by default;
`warn_at = round(context_limit * context_warn_ratio)`). `level` is `"ok"` while `observed` (or its absence) is
below `warn_at`; `"warn"` in the range `[warn_at, context_limit)`; `"over"` at `context_limit` and above. This is a
pure estimate: it does not trigger a checkpoint automatically. The decision about a checkpoint stays with the
coordinator, as for any other signal, except the auto-resume on 429 (see the continuation section above). The
baseline from `playbook.md` ("Baseline metrics") stays, in the same way, a guideline and not a hidden limit.

### Checkpoint and a new worker session

A write role (developer, database-migrations, messaging-integration, conflict-resolver) may stretch one dispatch
over several worker sessions if the whole TDD cycle in one session inflates its context. A read-only role
(architect, qa, code-review) may not: a checkpoint attempt for it is rejected at once.

Instead of a completion report, the current worker session records a non-final checkpoint: a separate, hashed
ledger record that cannot be mistaken for a report:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch checkpoint \
  --file checkpoint.json
```

`checkpoint.json` must contain exactly: `dispatch_id`, `commit_sha`, `changed_files`,
`remaining_definition_of_done` (a subset of the DoD of the approved dispatch), `passing_checks` (in the
`checks_run` format of the completion report, with commands from the approved `verification_commands`), `risks`,
`blockers`, and `context_package_id`, a reference to the last Context Package registered for the batch, or the
literal `not applicable — no context package registered` if the batch has none yet. No foreign fields: no raw chat
history and no logs of earlier failed attempts. `checkpoint` requires an already confirmed self-report. The command
moves the dispatch status to `checkpointed` and does not touch the outcome enum (`completed`/`blocked`/`failed`).
This enum stays only with the completion report.

A new worker session for the same dispatch ID starts with the `dispatch resume` command. The authorization depends
on why the previous session ended:

```bash
# the runtime adapter reported a rate-limit termination: the authorization is automatic
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --termination-reason rate_limit

# a planned trigger (context limit / N TDD cycles / a large failure log / a finished vertical
# slice): an explicit coordinator decision is required
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --trigger context-limit --measured-value 162000 --file continuation-facts.json \
  --approved-by "project coordinator" --approved-at 2026-09-14T18:00:00Z
```

A `--termination-reason` recognized as a rate limit (`rate_limit`/`rate-limit`/`429`) authorizes the new session
automatically. No new human or coordinator decision is required. Any other reason, including a missing or
unrecognized one, is treated as a planned trigger. This is a safe default toward approval, not away from it:

- `--trigger` is required and must be one of `context-limit`, `tdd-cycles`, `failure-log`, `vertical-slice`.
- for `context-limit`/`tdd-cycles`/`failure-log`, `--measured-value` must be not less than its
  `adaptive_continuation_policy` threshold (`context_limit`/`tdd_cycle_count`/`failure_log_bytes`) from
  `.harness/orchestration.json`. Without an explicit configuration, the documented default values are used
  (150000 / 3 / 20000), not values hardcoded separately in each place.
- `--file` must contain JSON with `dispatch_id`, `remaining_definition_of_done`, `risks`, and `dependencies` that
  literally match the last checkpoint (the first two fields) and the dispatch (`dependencies`). `blockers` is not
  part of the comparison: their wording may change between sessions without a real drift of scope/DoD/risks/
  dependencies. A mismatch is a signal that they really changed. Then the coordinator must close the current
  dispatch and open a new one through the ordinary approval, not resume this one.
- the authorization is recorded in the same `coordinator_decisions` as accept/retry/block/fail/abandon/cancel: no
  new record type is introduced.

`resume` accepts only a `checkpointed` dispatch, returns it to `dispatched`, and discards the previous model
self-report. This means that the new session must go through `dispatch self-report` and `dispatch heartbeat` again,
exactly as at the first contact, before the next checkpoint or completion report is accepted. The circle closes with
the same dispatch ID: checkpoint → `dispatch resume` → a new self-report/heartbeat → finally one completion report.

Updating the installed runtime does not change the runtime snapshot of the active batch. If the old snapshot
contains a continuation error, keep the checkpoint and the Git history, then choose the standard recovery on the
fixed runtime with a new approval. The new batch must pin the original integration base, the full DoD/commit plan,
and the saved writer HEAD. Review and QA check the whole final candidate. The recorded briefs, reports, and runtime
snapshots of the old batch stay as audit evidence.
### Clean-room QA lane

The coordinator itself runs the approved `qa` dispatch in a separate temporary Git worktree,
detached exactly at `candidate_commit`. The commands come verbatim from `verification_commands` of the
immutable brief, and a HEAD mismatch or a dirty worktree stops the check. The run is not
passed to a runtime adapter:

```bash
python .harness/orchestration/coordinator.py --repo . qa run \
  --dispatch <qa-dispatch-id> --lease-seconds 1800
```

The repository has one FIFO lane for heavy checks. If the lane is busy, the command saves
the request and returns `state: queued` with a position. A repeated call for the same dispatch runs it
only when it becomes first in the queue. The state and the current owner are visible without running the gate:

```bash
python .harness/orchestration/coordinator.py --repo . qa status
```

The lease contains the dispatch ID, host, PID, acquisition time, and expiry. An expired lease is **not** released
automatically: the coordinator first checks the owner, then records its own decision with the same
host/PID/expiry, and only after that deletes the stale request:

```bash
python .harness/orchestration/coordinator.py --repo . qa clear-stale-lease \
  --expected-host <host> --expected-pid <pid> --expected-expiry <ISO-8601> \
  --approved-by 'имя coordinator-а' --approved-at 2026-09-10T12:00:00Z \
  --reason 'проверено, что владелец больше не выполняется'
```

If the lease belongs to a dispatch that stayed `working` with no recorded report, the command
returns that dispatch to `approved`. The `restored_dispatch_state` field in the response and in the recovery record
is `approved` or `null`.

#### Environment preparation and failure categories

The optional `qa_preparation` in `.harness/orchestration.json` sets the environment preparation commands
(for example, `uv sync --locked`). The optional `qa_environment_probes` (for example, a check that
the package registry is reachable) and `qa_project_file_checks` (for example, `uv lock --check`) set
independent facts. Their commands run in the same checkout only after a failed preparation.
`qa run` runs them and then `verification_commands` in one clean checkout of the exact
`candidate_commit`. It stops at the first failed command. Without `qa_preparation`
(configurations with only `verification_commands`), the behavior and the report shape do not change.

A report and an artifact with preparation carry `qa_stages`. For each executed command, it holds the stage
(`preparation`, `environment-probe`, `project-file-check`, or `gate`), the exact command, the result,
the exit code, and a sanitized diagnostic of the failed command. They also carry `failed_stage` and
`code_checks_started` (`started`, `not_started`, or `unknown`). The records are checked against the immutable
artifact: the commands and exit codes must match its blocks. If preparation failed, the gate commands
in `checks_run` are recorded as `not_run`. This is not an invented failed code check.

Independent facts confirm the cause of a preparation failure: neither an exit code nor a keyword in the log
decides alone, and the preparation stage itself does not prove an infrastructure cause. Log signatures
only support the diagnosis, and without configured probes and project file checks an infrastructure
cause is not confirmed. The failure then requires triage:

| Diagnosis | Confirmation | Report | Route of `batch decide --decision retry` |
| --- | --- | --- | --- |
| `infrastructure` | an environment probe failed, and all project file checks passed (and at least one is configured); the output has no project-defect signature; the code was not checked | `blocked`, "code not checked" | `same-candidate-rerun` without `--reason-category`: a new qa dispatch on the same SHA, the developer retry budget is not spent |
| `project-defect` | a project file check failed (and no probe failed), or a defect signature (for example, an incompatible lock file) that matches a tracked manifest or lock file named in the output; the project file checks do not refute it | `failed` | `developer-retry`, reason `code` |
| `unknown` | no probes and checks are configured, they do not confirm a cause, or they contradict each other (for example, both a probe and a check failed) | `blocked`, triage needed | `retry` without `--reason-category` is rejected; the coordinator names the reason or blocks the batch |

A failure of the gate itself remains an ordinary code-check failure and follows the existing
`developer-retry` route.

**Recovery on the same SHA.** After the environment is confirmed ready, the coordinator runs
`batch decide --decision retry`. Then it creates a new qa dispatch for the same `candidate_commit` with
the same commands and limits. The earlier brief, report, artifact, and approval stay as audit
evidence. A failure of preparation or of the report write leaves no lease, queue entry, or `working`
state: the same approved dispatch can be run again without editing the ledger and without a new batch.
The exception is a ledger held by another operation for more than 30 seconds (see "Busy ledger").

#### Bounded infrastructure retries

A project can separately allow a policy retry of a confirmed infrastructure failure:

```json
{
  "infrastructure_retry_policy": {"enabled": true},
  "attention_policy": {"max_infrastructure_retries": 2}
}
```

Without opt-in, the manual gates apply. The policy does not grant platform permissions, does not replace native
approval, and does not accept a failed QA. The budget uses the existing
`attention_policy.max_infrastructure_retries`: the default is 2, and `0` forbids retries.
The developer retry budget is not spent. The opt-in, the budget, and the preparation/probe/project-file-check commands
are saved in `orchestration_policy.infrastructure_retry` and are bound to the approval digest.
Historical briefs without this section stay in manual mode. Editing the live config does not enable
a retry for an old approval and does not change the commands of a new, already approved brief.

After a QA preparation failure, the policy continues only the `same-candidate-rerun` route with a
confirmed `infrastructure` diagnosis, `code_checks_started: not_started`, and an unchanged SHA. Before the
decision, the coordinator checks access and reruns the pinned independent environment probes and
project file checks in a clean checkout; if the environment is not ready yet, there is no new dispatch. After
the cause is removed, within the same limits, run:

```bash
python .harness/orchestration/coordinator.py --repo . report complete --dispatch <qa-dispatch-id>
```

Each retry that takes place gets a new immutable dispatch and the decision source
`policy:infrastructure-retry`, and the earlier brief/report/artifact are kept. A repeated `report complete`
returns the dispatch that was already created, and an interruption after the decision completes the missing step. The command
does not start a worker and does not open a PR.

An access denial before the QA or publish run does not create a report about a code check. For an opt-in dispatch,
the coordinator saves a structured access attempt and a checksum. When the same resource becomes available,
request the check and a new policy-approved assignment:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch retry-infrastructure --dispatch <dispatch-id>
```

This path is allowed only for a denial confirmed by a probe (`denied`), with a fresh confirmation of
readiness. The old unsent brief is cancelled with an audit of the reason, and the new one keeps the stage, SHA, commands,
runtime/model/effort, scope, and access; a repeated command returns the earlier result. The publish remote
must also stay the same. Then run `qa run` or `dispatch publish` with the new ID.
An unconfirmed network denial (`unverified`), an unsupported mode (`unsupported`), a denial by the plan itself,
and an arbitrary Git error require manual analysis. Git operations without an approved dispatch
keep the manual route: the opt-in does not allow an arbitrary Git command.

A change of candidate, commands, or access, an unknown cause, and an exhausted budget stop the
policy and raise `needs_attention`. A human clears the attention. This does not raise the budget
and does not allow a changed contract. New requirements go through the ordinary proposal and approval.
Do not edit the ledger and do not rewrite the candidate for the sake of infrastructure recovery.

**Native smoke.** The support check requires a real coding environment. Create a separate smoke project,
a local bare remote, and a new empty cache inside the allowed shared storage. Record the full
harness and candidate SHA, the checkout cleanliness, and the exact preparation/gate commands. Through the public CLI,
go through batch/dispatch approval, the native role handoff, preparation/clean-room QA, and publish of the
accepted SHA. Then confirm the access denial, the absence of a retry before readiness, the bounded
retry, and the preservation of evidence. Take dynamic IDs and the digest from the command JSON. Native approval accepts the
coding runtime according to the user's current policy, and the orchestration policy does not replace it.
Do not change machine/global profiles, do not clear the user's cache, do not create a PR, and do not
run a merge. An external push requires permission for the specific smoke remote, and a push to a local
bare remote checks Git/publish but not external Git access.

First steps from a source checkout (the paths and the actual model are set by a human):

```bash
python harness/bin/harness.py init "$SMOKE_REPO" --capability backend-orchestration \
  --base-branch integration/smoke --language ru --tracker-type local \
  --qa-gate-command "$SMOKE_GATE"
python "$SMOKE_REPO/.harness/orchestration/coordinator.py" --repo "$SMOKE_REPO" batch create \
  --ticket local:619 --branch feature/issue-619-native-smoke --worktree "$SMOKE_REPO" \
  --integration-ref integration/smoke --allowed-path smoke.py --expected-file smoke.py \
  --expected-service smoke --expected-changed-lines 2 \
  --goal 'Change answer to 42 and verify the native smoke' \
  --definition-of-done 'answer returns 42; exact candidate passes QA and local publish' \
  --prohibited-change 'global config, other projects, secrets, PR, merge'
```

Before this, the local `origin` must contain `integration/smoke`, and the checkout must be a clean issue branch.
Create a tracked `smoke.py`, a manifest/lock, and real project-owned commands for preparation, an independent
network/cache probe, and offline file checks. Configure the opt-in before the proposal, create a separate cache, and
record that it is empty. For QA, use, for example,
`UV_CACHE_DIR=<new-cache> UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`, and the developer
uses a different cache. The runner selects Python from `.harness/.venv` of the current clean-room checkout.
The gate command must check the actual change in `smoke.py`, and also the location of `sys.prefix`
and of the imported package in this checkout. Save the actual `executed_command` from the stage evidence.

Choose the transport before creating the batch. For a separate native CLI session, set
`assignment_plans.<role>.transport: "external"` and the real `runtimes`, `provider_profiles`, and check
commands. The authored assignment plan requires architect, developer, code-review, and qa, and health
checks this set. Prepare a project-owned adapter that receives `dispatch --repo --brief` and
actually starts the coding CLI in the approved worktree with the model and effort from the brief; it
returns after the worker starts and does not manage the ledger. For `in-process`, the role runs as a
subagent of the current coordinator session, and a separate CLI session must not be treated as such a subagent.

Take `batch_id` from the `batch create` JSON, after which a human, or a coordinator the human explicitly designates,
runs `batch approve` with `--approved-by` and the actual `--approved-at`. In the same smoke checkout:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT"
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT" \
  --transition-digest "$DIGEST" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"
python .harness/orchestration/coordinator.py --repo . dispatch send --dispatch "$DISPATCH"
```

For the chosen `external`, the last command contains the real adapter:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch "$DISPATCH" --adapter "$SMOKE_REPO/scripts/native_codex_adapter.py"
```

`DIGEST` comes from the reviewed proposal, and `DISPATCH` comes from create. The handoff prints the brief path, the
report staging path, and the expected model. With `external`, the adapter starts the role; with `in-process`, the
coordinator starts it in its own coding session. The role runs
`dispatch self-report --dispatch "$DISPATCH" --model "$ACTUAL_MODEL" --worktree "$SMOKE_REPO"`,
then `dispatch heartbeat --dispatch "$DISPATCH"` and a real `report submit --file <report>`.
The architect does not change code and does not run the full gate. After checking the report, the coordinator saves
its plan as `{"commit_plan": [...]}` in `$COMMIT_PLAN` and runs
`batch decide --batch "$BATCH" --decision accept --commit-plan-file "$COMMIT_PLAN" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"`.
Repeat proposal/create/send for the developer: its commit/report set the full candidate SHA.
`risk assess --batch "$BATCH" --candidate-commit "$SHA" --changed-file smoke.py` determines
whether a review is needed, and a required review cannot be skipped; its send uses a checkout of the exact SHA.

For a new qa proposal/create, add `--candidate-commit "$SHA"` and use `qa run`,
not `dispatch send`. Arrange a write denial only in the created cache (in a POSIX fixture,
`chmod u-w "$SMOKE_CACHE"`). Save `qa_stages` and the `report complete` denial before readiness.
Restore with `chmod u+w "$SMOKE_CACHE"`. `report complete` must return a new ID for the same SHA,
and a replay must return the same ID. Run `qa run` for the new ID and manually accept only a successful report.
The publish proposal/create sets `--role developer --purpose publish --candidate-commit "$SHA"`.
For a POSIX metadata fixture, restrict writes only in the smoke `.git`. Save the denial of
`dispatch publish --dispatch "$PUBLISH" --remote origin` and the denial of `dispatch retry-infrastructure`
before recovery. After recovery, get a new ID and repeat the publish to the same `origin`.
`git ls-remote --heads origin refs/heads/feature/issue-619-native-smoke` must return exactly `$SHA`.
If interrupted, restore the write bit of your own fixture only. An incomplete or different diagnosis is a blocker,
not permission to continue the scenario. An authorized inherit of coordinator operations does not prove
that the authored worker permissions are applied. Run only a mode confirmed by the current extension.

In the evidence, save the runtime, version, transport and mode, full SHAs, native parameters and proof
of actual access, commands with exit codes, readiness, dispatch IDs and checksums, after
removing secrets. The health config and the checkout attestation do not prove network permissions.

The checks of this implementation cover real Git/ledger, preparation/gate, same-SHA retry,
budget, attention, metadata refusal, and local publish. These are controlled checks: they do not
prove the native handoff and the whole runtime matrix. A native handoff with an authored access plan needs an
implementation of `extensions.runtime_access` that observes and applies the actual worker access;
`none` gives no such proof, and an explicitly chosen unverified mode is blocked. `legacy-inherit`
keeps the earlier assignment handoff but does not confirm worker permissions.

The native smoke verified on 2026-10-08 was installed from harness
`cca45e172c7b3685c012e7e6c077356d6cbd6722`: Linux, Codex CLI 0.160.1, a real project adapter, and
two separate roles `architect`/`developer`. The candidate `1dba1785bc809971981129c747e85bffd9b29c51`
passed preparation and the gate in a new clean-room checkout with an empty QA cache, a fresh `.harness/.venv`, and
downloaded dependencies, and was then published to a local bare remote. A cache denial and a `.git` write
denial stopped the continuation before readiness. Recovery spent the two shared infrastructure
retries, the replay kept the successor IDs, and the earlier records kept their checksums. The batch finished through
the public CLI. This confirms only the following limits:

| Runtime / transport / mode | Native smoke result | Evidence boundary |
| --- | --- | --- |
| Codex CLI 0.160.1 / `external` / worker `legacy-inherit` | PASS: real roles, self-report, heartbeat, commit, and report | The native CLI ran with `workspace-write`; the authored worker access plan is not verified |
| Coordinator / `inherit` / QA and publish | PASS: fresh dependencies, exact-SHA gate, cache/Git denial, readiness, budget, and replay | Actual operations in one allowed coordinator environment; publish only to a local bare remote |
| Worker with authored `inherit`, `sandbox`, or `unsandboxed` / `runtime_access: none` | Blocker | A current extension with proof of observing and applying the plan is needed; an attestation does not replace it |
| `in-process`, Claude and other runtimes, external Git push | Not verified | Each combination needs its own actual run |

CLI flags, the coordinator host execution, and the POSIX `chmod` fixture do not prove the whole permission matrix.
Another runtime, transport, or authored mode needs its own native evidence for support.

After the run, an immutable completion report is created with the commands, exit codes, and short
sanitized evidence. The full sanitized stdout/stderr is stored outside Git in
`.harness/orchestration/state/qa-artifacts/<sha256>.log`. The report refers to this path and checksum.
A gate failure remains a QA finding and requires a new approved developer dispatch. The runner does not edit
code and does not rerun the check on its own.

After accepted QA evidence, the coordinator creates, but does not start, a publish dispatch for the same
candidate SHA. Only the developer publish pushes this SHA, and neither QA, nor review, nor the adapter
creates or merges a PR. After publish, a human manually runs `/to-pull-requests <ticket>`: it
checks the accepted QA evidence of the current SHA and follows the ordinary manual PR workflow without a repeated
heavy gate. The `require-qa-gate.sh` hook accepts the same evidence itself, so a repeated gate and a
marker are not needed for a clean checkout whose `HEAD` equals the accepted `candidate_commit` and with `pass` for
each command of `qa_gate_commands`. Otherwise the earlier path with a marker remains.

The ordinary entry point is `/implement <ticket>`. This session becomes the coordinator itself and runs
the described cycle. It stops at five approval gates (architect, developer, code-review, qa,
publish) and watches the heartbeat of each dispatch. One ticket is brought to a terminal batch state
before the next one starts. A manual run following this guide stays fully valid. For
it, a ready request to the controlling session can be worded like this:

```text
Выступи coordinator-ом backend batch для issue #123. Прочитай .harness/orchestration/roles/
и .harness/orchestration/playbook.md. Не запускай роль до моего явного approval. Предложи
explicit allowed paths, последовательность ролей, immutable brief и требуемые risk gates;
не меняй protected или integration branch.
```

### Integration accounting after publish

A finished batch is history: it is not reopened and not rewritten. The link that the next integration
step needs (ticket, issue branch, source batch, published candidate SHA, and target SHA of the
integration ref) is recorded by a separate immutable record, the Integration record. The `integration`
group creates and reads it. None of the commands writes the batch, plan, dispatch, or reports. Only `refresh`
(below) changes Git:

```bash
python .harness/orchestration/coordinator.py --repo . integration prepare \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration status \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration link-evidence \
  --record <integration_record_id> --kind ci --result passed \
  --candidate-commit <sha> --target-commit <sha> --reference <run-url> [--artifact-sha256 <hex>]
```

Run `prepare` after an accepted publish and before a merge or branch deletion. It selects the only
finished batch with an accepted publish for the ticket+branch pair. It checks the published SHA in two
independent ways: by the accepted publish report (the report and brief digest) and by `ls-remote`
(the remote branch is exactly the candidate, and the integration ref is exactly the pinned target). The evidence
comes from the accepted green QA of the same SHA. The response contains `integration_record_id`, the
`candidate_sha`/`target_sha` pair, and digest links to the source QA and publish. A repeated `prepare` does not
create a second record and does not lose the first one (`created: false`). A refusal always contains a remedy. The refusal
cases are: no batch found for the ticket and branch; `--batch` belongs to another pair; the batch is not finished or not
published; several published batches without `--batch` (one batch is never substituted for another);
`--candidate-commit` is not equal to the published SHA; the remote branch is missing or different; there is no accepted
green QA; the integration ref has already moved forward and there is no record yet; the remote is unavailable; the batch history
was changed after the record.

The record lies in `reports/integration/`, and the evidence lies in `reports/integration-evidence/` inside the
already verified `reports` directory: the ledger schema version and `ledger migrate` do not change.

`status` is observation only, under the same read-only contract. It does not create a dispatch, writes nothing,
and gives the same answer on repetition. The states are: `current` (the integration ref is still at the
recorded target), `stale` (the ref has moved forward; `refresh_required: true`), and `unavailable` (the remote did not
respond; the pair cannot be confirmed). The source QA applies only to the recorded pair.
`source_evidence.applies_to_current_pair` is `false` when `stale`, and the old QA is not accepted for
a new candidate/target pair. `status` itself starts nothing. `integration refresh` (below) can update the pair
when it is `stale`. After a refresh, `status` shows the current pair (`candidate_sha`,
`target_sha`, the original values in `original_candidate_sha`/`original_target_sha`), the `refreshes` list,
and the `verification` block: `required: true` until there is a passed CI or local-QA of exactly this pair
(`resolver` does not count), and always `re_review_required: false`.

`refresh` is the PR preparation route instead of a mandatory developer rerun caused by a base shift:

```bash
python .harness/orchestration/coordinator.py --repo . integration refresh \
  --ticket '#123' --branch feature/issue-123-short-name
```

The command reads the current SHA of the integration ref. If it equals the pair's target, no rebase is run
(`state: unchanged`, nothing is written). Otherwise it rebases the issue branch in the worktree of its batch
onto this exact SHA and publishes the branch with `--force-with-lease` and the expected old SHA, so
another person's commit on the remote is not lost. The command refuses with a remedy if the worktree is not on the issue branch
at the recorded candidate, if the worktree has uncommitted changes or an operation in progress, or
if the remote branch no longer equals the recorded candidate. Stash, reset, and bypass are not applied, protected
and `integration/*` branches are never a write target, and other worktrees are not touched.

A clean rebase returns `state: rebased`, `new_candidate_sha`, and `verification_required: true`, does not
call the resolver, and does not spend its two cycles. A text conflict returns `state: conflict` and
`resolver` (`conflicting_files`, `candidate_sha`, `target_sha`, `worktree`, `cycles_spent: 0`);
the rebase is aborted, and the branch and the worktree stay as they were. A rebase writes an immutable
`IntegrationRefreshRecord` in `reports/integration-refresh/` (the earlier and the new candidate, the target,
the commits before and after). The old QA stays as historical evidence, and the new candidate is confirmed by CI
or local-QA of the pair through `link-evidence`; a repeated review because of a refresh is not needed. A conflict and work
that needs a developer follow the rebase route from ADR 0012, and `refresh` does not depend on it.

`resolve` is the text conflict route (the `conflict-resolver` role, ADR 0015). It writes nothing to
Git and rejects a clean rebase, because that is the work of `refresh`. A conflict becomes a new batch
of the `resolver` kind next to the ticket's finished batch, and the brief, reports, and history of the finished batch do not change:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolve \
  --ticket '#123' --branch feature/issue-123-short-name
```

The response contains `batch_id`, the conflicting files, the candidate and target SHA, the scope, and the remaining budget.
The `next_action` of the batch is `resolve-conflict`. Then the ordinary path follows: `batch approve`, then
`dispatch create --role conflict-resolver --purpose work` (first `--propose`). The brief carries an
immutable `resolver` section: the ticket, the requirements of both sides (`sides.candidate` is the DoD of the source
batch; `sides.target` is the plan records of the tickets `(#N)` from the subjects of the target commits, otherwise the subject and body
of the commit), the candidate and target SHA, the scope, the prohibitions, the commit plan, the checks, the remaining budget, and
`report_staging_path`. The role opens the skill `resolving-merge-conflicts`, preserves the requirements of both
sides, and does not add functionality outside them.

The budget is two automatic target SHAs, and a third needs a human decision. A cycle is spent only by
a recorded resolver report for a new target SHA, whereas a clean rebase, a human answer, and
a fix on the same target do not spend a cycle. Fixes on one target are limited by
`retry_policy.max_developer_retries`. The budget is derived from the append-only events of
`reports/resolver-events/` (`cycle-spent`, `same-target-fix`, `human-decision`, `scope-change`,
`exhausted`), so a lost session or a resume does not reset it.

The resolver does not guess incompatible requirements: it writes a checkpoint (`blockers` with a specific description
and the options) and ends the session. The human answer is recorded as a separate event before the resume:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolver-event \
  --record <id> --kind human-decision --dispatch <dispatch-id> \
  --decided-by <имя> --option <вариант> --note '<решение>' [--extends-budget]
python .harness/orchestration/coordinator.py --repo . dispatch resume \
  --dispatch <dispatch-id> --trigger human-decision --file <facts.json> \
  --approved-by <имя> --approved-at <время>
```

The same session continues the same dispatch: a new developer is not created, and neighboring batches are not
stopped. `--extends-budget` gives one more automatic target after two are spent.
A scope change is an ordinary approval of a new dispatch (`--kind scope-change` only records it).
The source brief is not rewritten. The existing check rejects a resume with changed facts.
A lost runtime session is resumed through the existing checkpoint/resume or
`batch resume`. The counters are taken from the events.

After the budget is exhausted (`exhausted`), only this task stops: the branch and the evidence
are kept. The same resolver continues an integration incompatibility after a human decision.
A defect in the ticket itself (`resolver.cause: task-defect`) is returned to the ordinary developer.

The resolver report carries a top-level `resolver` block: `preserved_requirements` (each requirement of
both sides verbatim from the brief), `human_decisions` (the ids of only those human-decision events that
answer a checkpoint of this dispatch), `target_sha`, `resolved_candidate_sha`, `cause`,
`changed_files`, and `commits` with a plan record for each commit. A standalone
`human-decision --extends-budget` without a checkpoint is recorded only as a ledger event and does not get into the report.
Besides one more automatic target cycle, it gives another `max_developer_retries`
attempts to fix the same target. An accepted resolution follows a narrow route: a repeated code-review
is skipped, but QA and CI or local-QA of the new candidate/target pair are required
(`integration status` keeps `verification.required`).

`collect-ci` collects CI proof for the combined result of the PR (ADR 0016):

```bash
python .harness/orchestration/coordinator.py --repo . integration collect-ci \
  --ticket '#123' --branch feature/issue-123-short-name --pull-request 45
```

The command works only with the `github` tracker and the `ci_required_checks` list from
`.harness/project.json`. CI is accepted if both conditions are met: the checks ran on the merge commit of the
PR whose parents are exactly the current candidate and target; and all required checks passed. Then the
command writes an immutable record with `verification: collector-accepted`. `integration status`
shows a `qa_replacement` block (the source, repository, PR, pair SHAs, merge commit, and check run id).
If the integration ref has moved forward, `qa_replacement.applies` becomes `false`, and
`re_refresh_required` becomes `true`: a new refresh and a new collection are needed. The fallback path is a full local
QA. It is needed on `fallback` with the reason `unsupported_tracker`, `not_configured`, `unavailable`,
`unknown_checkout`, `head_only`, `stale_candidate`, `stale_target`, `missing_check`, `pending_check`,
or `inconclusive_check`. In this case nothing is written. CI unavailability counts neither as a
code finding nor as a success. A completed `failure` on a confirmed pair is recorded as
`collector-failed`. A CI linked manually through `link-evidence` stays `unverified` and does not close the verification of
the pair. CI does not replace the source QA reports.

`local-qa` is the fallback path when the CI of the combined result is absent, unavailable, or
unusable (`--ci-condition absent|unavailable|unusable`, required `--reason` and `--record`):

```bash
python .harness/orchestration/coordinator.py --repo . integration local-qa \
  --record <integration-record-id> --ci-condition absent --reason 'CI не настроен для ветки'
```

The command pins an immutable request (the candidate/target pair, the reason, the full list of
`verification_commands`) and runs the existing gate runner in an isolated clean-room checkout
of the exact candidate. The task branch, the terminal source batch, and the accepted reports do not change, and
the code is not fixed. The run goes through the shared FIFO QA queue (`qa status`): two heavy QA runs do not work
at the same time, and the other batches continue implementation. The command writes the result as a separate immutable
record with the commands, a sanitized artifact, and a checksum, and links it as evidence
`kind: local-qa` with `verification: verified`, but only if the pair and the remote branch have not moved:
an earlier result does not confirm another SHA or a target movement. A check failure is a finding with
`state: failed`, which stays for the PR session to route. Infrastructure unavailability gives
a separate `state: unavailable` without findings. A retry is possible only with an explicit `--retry` and not more than
`max_infrastructure_retries`, after which `state: exhausted` occurs. A manually linked
`local-qa` stays `unverified` and does not close the verification of the pair.

`next` is the read-only PR continuation step (ADR 0017). It writes nothing to Git, the ledger, dispatch, or the PR and
does not contact the tracker. It classifies `status`, the evidence, open resolver batches, and the budget
events:

```bash
python .harness/orchestration/coordinator.py --repo . integration next \
  --ticket '#123' --branch feature/issue-123-short-name [--pull-request 45]
```

The steps (`step`) are: `unavailable` (the integration ref cannot be read: an operational stop, not a code defect),
`resolver-open` (a resolver batch is open; the PR session waits, no cycle is spent), `refresh`, `route-failure`
(a failed check of the current pair), `human-decision` (the resolver budget is exhausted), `confirm-pr` (before the PR),
`verify` (with `--pull-request`: the updated pair needs CI or local-QA), and `handoff` (the pair is current and
verified: `candidate_sha`, `target_sha`, `qa_source` `original-qa|ci|local-qa`, `reference`,
`refreshed`). Old evidence allows entering PR preparation (`confirm-pr`), but does not count as QA of
the new candidate: `verify` and `handoff` require verification of exactly the updated pair.

The failure routing rule: a failure is only a `collector-failed` CI or a `failed`
generated local-QA of the current pair that has no passed verified check. A passed, verified
check of the current pair clears the failure regardless of the write order. A failure recorded after it does not
open the route while the passed check still applies to the current pair. If the pair went through a refresh or
a resolver, the route is `resolver` (a behavioral incompatibility after a clean rebase, a consequence of a
resolver fix; the budget `cycles_total`/`cycles_spent`/`remaining`/`internal_fix_budget` and
`fixes_on_target` are in the response; on exhaustion, `human-decision` with
`integration resolver-event --extends-budget`). If the pair is the original one, the route is `developer`:
the task's own defect goes to the ordinary developer with review and QA (ADR 0012). The finished source
batch is terminal, and `batch decide` on it refuses. So the `next` hint names an executable
path: a new batch of the same ticket and issue branch through the ordinary `/implement` route
(`batch create --ticket T --branch B --worktree W --integration-ref I`, then architect, developer,
code-review, QA, and publish; a finished batch does not block a new one). The base of the new batch is the integration
tip. So the developer report shows in `commit_map` also the branch commits that are already published (with `dod_coverage` and
`divergence_justification`). After an accepted publish, `integration prepare --ticket T --branch B --batch
<new batch>` creates a new record, and `integration next --record <new record> --pull-request N`
continues the PR, while the failed evidence of the earlier record stays as history. One ticket and branch now has
two records, and `<ticket-branch>` is rejected with the refusal "several integration records match".
`--record <new record>` replaces `<ticket-branch>` in the `integration` commands of the `to-pull-requests` skill.
The operational CI fallback and `unavailable`/`exhausted` local-QA do not create failed evidence and do not
become a code failure. For a failure of the updated pair, `integration resolve` creates a resolver batch with
`resolver.trigger: verification-failure` (`failed_evidence_ids`, empty `conflicting_files`) even
when `tip == target`. The `target` side is taken from the commits that landed in the target after the source
target of the record (`identity.target_sha..tip`). The scope stays the task's own files (an edit of
other files is a new approved `scope-change` dispatch). The budget and the limit of fixes on the same target
are the same as for a conflict. A human answer and waiting for CI neither reset nor spend the budget.

The `next` hint in the result of `collect-ci`: `pending_check` is `{action: wait}`; `not_configured` and
`unsupported_tracker` are `{action: local-qa, ci_condition: absent}`; `unavailable` is `local-qa` with
`unavailable`; the other fallbacks are `local-qa` with `unusable`; `failed` is `{action: route}`. For `accepted`
there is no hint: the full local QA is skipped (`qa_replacement.applies`).

`/to-pull-requests` runs this process. Before the PR, a separate human confirmation is needed, bound
to the exact `candidate_sha`/`target_sha` pair. A change of the pair before opening makes it invalid.
After the PR is opened or updated, it waits for CI; if CI is unusable, the fallback `local-qa` runs, then
`handoff` for a manual merge. Before the merge, the verified SHA pairs and the QA source are shown. The handoff
does not promise immutability until the merge, and a new target repeats the refresh and verification.
Server branch
protection and the merge queue are not enabled automatically. The merge stays manual, and the ticket is closed
only after a confirmed merge.

`link-evidence` is the only public way to attach future CI, local-QA, or resolver results to a record
(`--kind ci|local-qa|resolver`). Each link is a separate immutable record with its own
`candidate_sha`/`target_sha` pair and `verification: unverified`; the source evidence of the record never
gets a new pair, and a check of a new pair does not replace the old one. A repeat of the same link is
idempotent (`linked: false`). This operation does not start CI, local-QA, or the resolver itself. In `status`,
each link shows whether its pair relates to the current tip
(`pair_checks[].applies_to_current_pair`).

### Advisory tool call

`.harness/orchestration/advisory.py` is a cheap non-role CLI for purely utility subtasks:
ranking files by keyword, a log summary, and a rough risk hint. It runs outside the
brief/report/self-report/heartbeat contract. It is not a dispatch: it writes no ledger record and does not
import `ledger/`/`contract.py`/`coordinator.py`. The output is ephemeral. It is printed to stdout and
recomputed on every call. It is not saved anywhere as ground truth for another
dispatch:

```bash
python .harness/orchestration/advisory.py rank-files --keyword payments -- services/payments/handler.py README.md
python .harness/orchestration/advisory.py summarize-log --file qa-output.log
python .harness/orchestration/advisory.py classify-risk --text "data migration for payments" --known-trigger data-migration
```

The advisory output is not an authorization: the coordinator/contract validation path does not accept it as a
basis to create a dispatch, lower a risk, accept QA, or change a scope. The only
authoritative source of risk stays `coordinator.py risk assess`.

## 5. Optional external adapter

The `backend-orchestration` capability ships two standard adapters:
`.harness/adapters/claude_worker.py` for Claude Code and `.harness/adapters/codex_worker.py` for Codex.
`harness init`/`adopt` install them, and an ordinary `harness update <repo>` restores
missing files and updates the managed versions. The console settings offer the states,
plan preview, and explicit confirmation; the current capability set is preserved.

For an already approved dispatch with `external` chosen, use the adapter of the assigned runtime:

```bash
python /path/to/project/.harness/orchestration/coordinator.py --repo /path/to/project dispatch send --dispatch <dispatch-id> --adapter /path/to/project/.harness/adapters/claude_worker.py
```

For Codex, replace the adapter path with `/path/to/project/.harness/adapters/codex_worker.py`.
The coordinator runs the `.py` file with its own Python in the worker checkout. The model and effort parameters
come from the immutable brief, and the lifecycle prompt is passed through stdin. Claude limits
additional access to the incoming reports directory and uses the native `allowed_tools`;
Codex passes this list in the prompt, and selects the sandbox by `access`: `read-only` or
`workspace-write`. This is not a native Codex tool filter.
Both adapters reject `qa`, `purpose: publish`, another transport, and a missing `allowed_tools`.
An early worker exit, even with code `0`, returns a launch error and the end of the log.
To check a command without a model, there is `dispatch --dry-run`; for a test executable,
`--claude-bin`/`--codex-bin`; for developer-retry lines, `--extra-prompt-file`.

For `transport: "external"`, the project passes `--adapter <path>` to `dispatch send`. This is a transport-only
boundary. The coordinator passes the approved immutable brief to this executable through `--repo` and
`--brief`.
The adapter is responsible for starting the worker in the chosen environment. It does not choose a scope, does not accept a report,
does not plan the next dispatch, and does not merge a PR. After starting, the worker returns a completion report
under the general rules of section 4. The access and launch environment checks belong to the project adapter.

## 6. First pilot and the source of rules

Do not set token limits or a "right" level of parallelism by eye. In the first pilot period,
record for each closed ticket agent starts, tokens per batch, quality-gate wall time, and
post-integration defects, including the source and the missing data. The form and the common counting rules
are in `.harness/orchestration/pilot.md`.

The full normative source is `.harness/orchestration/playbook.md`, and the boundaries of individual roles are
in `.harness/orchestration/roles/`. If the convenience of a specific runtime conflicts with this
contract, the manifest, the immutable brief, and the explicit approval take priority.

The architectural contract of the route is recorded in full in
[ADR 0003](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0003-orchestration-core.md): an opt-in capability, a separate
approval for dispatch, review and QA for one SHA, local sanitized evidence, and an adapter
only for transport. Turning `/implement` into a coordinator-driven pipeline by default, model
self-report, the dispatch watchdog, per-role transport, and zero-config defaults are recorded in
[ADR 0005](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0005-implement-pipeline.md).

## Manual recovery and stage repeat

`batch auto-report` only reads the state. The detected cause is in `observed_stop`.
To record a stop, call `batch auto-decide` explicitly: the batch moves to `paused`, even if the
worker did not manage to send a report. A repeated call in paused does not change the ledger.

```bash
python .harness/orchestration/coordinator.py --repo . ledger validate
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <id> --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'worker checkout fixed'
python .harness/orchestration/coordinator.py --repo . batch rewind \
  --batch <id> --to code-review --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'repeat review'
```

`resume-stop` fits a confirmed worktree/model mismatch or an OS refusal to start the adapter,
but it restarts only a worker with a known outcome: `absent`, `reported`, `rejected-at-startup`,
or `stopped`. For a rejected self-report, the contract is unchanged: a human approval takes the dispatch out of
circulation, and the ledger rejects its late records. If `dispatch status` shows `live` or
`unknown`, the command refuses and changes nothing: stop the worker through its runtime and repeat
the command with `--runtime-stopped`. A missing self-report is not confirmed by `resume-stop`: stop the worker
and record `dispatch cancel --runtime-stopped`. If there is no structural proof, a cautious text heuristic looks for an infrastructure cause
(rate limit, timeout, network, runtime crash, resources, unavailable service) in the `blockers` of a blocked
report and in the runtime error. A sign of a problem with tests, linter, types, conflict, scope, or
requirements outweighs it; unknown text stays unknown. The match is recorded in the
event as `classification` with `method: heuristic`; it only suggests a cause, and the
human approval decides. It keeps the role, scope, candidate, and fix-forward findings. The repeat gets a new dispatch ID,
context, and approval. An operational attempt does not spend a second developer retry. When paused because of the
budget or an unknown cause, a pending report can be returned for a manual decision. When the budget of
infrastructure retries is exhausted, `resume-stop` refuses, and the batch stays in the stopped state
until a human decides: wait, fix the launch, change the attention policy, run `rewind`, or
separately decide `batch abandon`; the counters are not reset. Dirty files, an unknown SHA, failed
checks, and new code findings require the ordinary fix route.

After recovery, `manual_all` applies, including a continuation after a 429. The source `auto_stop`
and `auto_report` stay as history. The new report shows the current progress and `historical_report`.
`blocked` and `failed` hold the ticket/branch/worktree; a repeated batch is forbidden until they are closed.
Both abandon paths record `abandoned` and `last_accepted`. An old `failed` can be superseded only
with a proven human abandon; an ordinary failed is not a refusal of the work.

Rewind selects a reached stage: `architect`, `developer`, `code-review`, `qa`, or `publish`.
`verification` requires a registered candidate, and `resolve-conflict` requires a resolver boundary.
Old dependent approvals/reports/risk/QA are excluded from the active chain, but not deleted.
HEAD and commit objects stay in place. After a return to architect, a new accepted plan is needed;
after a return to a writer, the new attempt spends the developer retry budget. No counter is
reset. The `batch approve` requirement is kept until the first accept.

If a stage report is `blocked` only because of an infrastructure failure, and the work in the report looks
finished (for example, the developer commits match the plan, but the handoff to review failed),
a human can accept the stage conditionally:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide --batch <id> \
  --decision accept-conditional --infrastructure-failure --note '<проверенная причина>' \
  --approved-by '<оператор>' --approved-at '<текущий UTC>'
```

The decision is recorded as `accept-conditional`, the pipeline goes on as after `accept`, and the stage
stays an open condition of the batch. An unconditional `accept` of a later gate independently closes the condition:
code-review or qa for architect, developer, and verification; qa for code-review and
qa. While the condition is open, publish and completion refuse. A conditional qa does not count as a green QA,
so publish still requires a real QA. A conditional publish is accepted only if the remote
branch already points to the candidate. The report must be `blocked` without failed checks, and the other
checks of an ordinary `accept` (commit plan, scope, DoD) are kept. Rewind lifts the conditions
of cancelled dispatches. If the stage can simply be restarted, `resume-stop` is preferable.

A live worker must first be stopped by the runtime means. Then the operator records
`dispatch cancel --runtime-stopped` with approved_by/approved_at/reason. A timeout does not prove a stop.
After that, a rewind can be run. The old dispatch no longer accepts a heartbeat/report/checkpoint.

For an old pinned batch, the new recovery commands use the installed runtime. An event with a
human approval links the source pin to the new control runtime and saves its snapshot.
The source immutable plan and the old brief/report do not change. `ledger validate` fixes nothing.

Before the handoff, pass one absolute `--worktree` to preflight and send. For a writer, the path must
match the issue worktree, branch, and startup SHA. The self-report checks the actual directory even
when two checkouts have the same SHA. The runtime must be able to select an existing directory; `isolation: worktree`
alone is not enough. The coordinator stays in the main checkout.

If the writer session ended before the first checkpoint, the operator can run
`dispatch resume --trigger startup-failure --runtime-stopped` with a new approval and `--note`.
The `--file` file contains exactly `dispatch_id`, `definition_of_done`, `dependencies`, `write_paths`,
`prohibited_changes` from the brief. A clean worktree must stay at the known startup SHA.
The command records separate startup evidence, spends the continuation budget, and requires a new
self-report/heartbeat. A changed scope, unknown commits, or a paused batch exclude this path.

### Batch hold and the `recovery` commands

Unknown, missing, or unreadable system data does not become a decision (ADR 0026).
If strict reading rejects a batch record, `recovery resume` holds the batch with the record
`recovery/hold/<batch_id>.json` of the `operationalHold.v1` contract: the state is `held`, and the refusal has the step
`hold:<reason>`, where the reason is `unknown-value`, `missing-value`, or `unreadable-record`. The hold
writes no lifecycle record, decision, or approval, and a terminal batch is never held.
A hold record that cannot be read also holds the batch, but no `recovery` command releases it:
the remedy names `ledger validate --full` and an escalation to a human.

While the hold is in effect, these commands refuse with code 2, write nothing, and name the recovery route in `REMEDY`:
`dispatch propose` and `dispatch create`, `dispatch send`,
`dispatch self-report`, `dispatch checkpoint`, `report submit`, `qa run`, `dispatch publish`,
`batch decide`, `batch resume`, `batch resume-stop`, and `batch rewind`. The reaction to a finished
execution of a supervised dispatch also waits: `dispatch status --dispatch` shows the refusal as
`reaction_error`, and the report stays in `pending_report`. With an active `auto` policy, `batch auto-decide`
records an `integrity-failure`/`operational-hold` stop and never decides a report and never
makes an abandon; without an active policy, the command refuses like `batch decide`. The commands that stay available are
`dispatch heartbeat`, `dispatch cancel`, `batch abandon`, `batch attention check` and `resolve`,
`batch decision-packet`, and the read commands. `batch attention check` raises the attention
`operational-hold`. The decision packet of a held batch shows the `operational_hold` field, and empty
`options` and `recovery_route.commands`: `recovery status`, `batch attention resolve` (if the attention
is raised), and `recovery resume`.

Recovery never resolves the attention, and `recovery resume` refuses with `attention-open` while the
attention is open. So the order is: read the diagnostics, remove the cause, resolve the
attention, then release the hold.

```bash
python .harness/orchestration/coordinator.py --repo . recovery status --batch <id> --json
python .harness/orchestration/coordinator.py --repo . recovery reload --batch <id>
python .harness/orchestration/coordinator.py --repo . batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …
python .harness/orchestration/coordinator.py --repo . recovery resume --batch <id>
```

The commands `recovery status|reload|resume|fix|abort --batch <id>` work only on the installed
runtime in the `runtime-store` epoch, do not read stdin, and need no TTY or Textual, so the console
calls them as a process:

| Code | stdout | When |
| --- | --- | --- |
| 0 | a `recoveryStatus.v1` document with `outcome: done` | the action is done |
| 2 | a `recoveryStatus.v1` document with `outcome: refused` | the policy refused; `refusals` and `diagnostics` name the reason |
| 2 | empty, `ERROR:` and `REMEDY:` in stderr | the command cannot run: the file ledger epoch (remedy `harness-runtime migrate`), a `runtime_client` refusal (`[runtime_unavailable]`, `[store_busy]`, `[revision_conflict]`), an incomplete approval, or an interruption |

The `recoveryStatus.v1` document is the console contract. It contains `contract`, `action`, `outcome`,
`batch_id`, `observed_at`, `resumable`, `lifecycle`, `hold`, `checks`, `diagnostics`,
`skipped_advisories`, `actions`, `intent`, and `next`. Each of the 13 checks (`config`, `store`,
`ledger`, `batch`, `lifecycle`, `runtime`, `snapshot`, `context`, `compatibility`, `operation`,
`liveness`, `attention`, `approval`) shows a status and diagnostics: the pointer, the redacted
expected and received values, a hint, and a remedy. Secrets do not get into the document.

- `status` only reads. `--skip <diagnostic-id>` (repeatable) hides an advisory from the
  closed list (`config-normalized`) for one call and writes nothing.
- `reload` rereads and checks the configuration and the runtime hello (protocol 1.5, `store_id`,
  features `state.read`, `state.write`, and `state.recovery`), returns this evidence under the key
  `runtime`, and does not start a worker.
- `resume` repeats the `status` checks in one write unit. A refusal of any check changes
  nothing, except the hold of a batch whose record strict reading rejects. Otherwise the command releases the
  hold and reacts to the observable execution of each open supervised dispatch:
  a finished execution gets a reaction (step `reconcile`), an `unknown` execution gives the refusal
  `ambiguous-effect`, and a live worker is not started a second time. A recorded stop continues
  only through the auditable `batch resume-stop`, for which `resume` accepts `--approved-by`,
  `--approved-at`, and `--note` (all three together or none); otherwise `batch rewind` is needed. The document
  adds `steps` (`hold`, `release`, `reconcile`, `resume-stop`), `refusals`,
  `dispatch_created: false`, `worker_started: false`, `status`, and `next`. `resume` does not create a
  dispatch, does not rewrite the brief, and does not change the attention, budgets, `auto_stop`, and terminal
  refusals; the next transition needs an approval with the current digest.
- `fix` shows a safe normalization of the configuration, and `fix --apply` applies it with a configuration
  transaction and resumes nothing.
- `abort` records an exit from recovery: it abandons nothing, stops nothing, and cleans nothing.

`reload`, `resume`, `fix`, and `abort` first write a durable intent
`recovery/intent/<batch_id>.json` (`recoveryIntent.v1`). After a cancel, EOF, or SIGINT, the intent
stays `interrupted`, and a repeat of the command completes the action. An internal exception gives the diagnostic
`internal-error` with a correlation ID, not a configuration error.

The Harness console (`harness console`, the Orchestration section) shows three catalog entries in the
`batch` group: `recovery status` and `recovery reload` run without confirmation, and `recovery resume` is a
terminal coordinator action and asks for confirmation. `recovery fix` and `recovery abort` are
available only from the CLI.

Recovery records follow the same authority as the lifecycle (ADR 0020, ADR 0021): Python
decides, the Rust store writes.

| Record | Decides | Writes | Write rules |
| --- | --- | --- | --- |
| `recovery/hold/<batch_id>.json`, `recovery/intent/<batch_id>.json` | Python: `operational_hold` and `recovery_api` in the command's write unit | Rust store, `state.write` (protocol 1.5, feature `state.recovery`) | only `create`, then `replace` by the row revision, `delete` refuses; the `batch_id` field equals the path id; the batch row exists in the same transaction; one audit record per mutation; no schema migration |
