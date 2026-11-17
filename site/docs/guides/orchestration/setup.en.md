# Enable and configure

Enable the capability, validate configuration and assess task scope before creating a batch. Field definitions belong in [Settings](../../getting-started/settings/orchestration/index.md).

[Orchestration overview](../../backend-orchestration.md)

## Enabling {#1-enabling}

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

## Configuring `.harness/orchestration.json` {#2-configuring-harnessorchestrationjson}

Use the [field reference](../../getting-started/settings/orchestration/index.md) to choose role assignments, verification commands and policies. An absent or empty seed configuration uses in-process defaults; authored policy-only configuration is merged with defaults even without `assignment_plans`. Validate before dispatch.

### Configuration normalization and validation {#configuration-normalization-and-validation}

The coordinator normalizes supported enum values in memory (`normalization.v1`), trimming spaces,
normalizing case and resolving documented aliases. Each correction emits a warning; the file stays
unchanged. IDs, models, paths and commands are not normalized. Invalid JSON, duplicate keys,
secrets and ambiguous values are errors. A duplicate key never silently keeps the last value.

- `config validate --json` reports the file, JSON pointer, diagnostic code and allowed values.
  An invalid configuration exits with code 2.
- `config validate --canonical --json` also rejects values that require normalization
  (`config-noncanonical`).
- `config validate --fix --dry-run --json` previews safe normalization.
  `config validate --fix --json` writes it transactionally with a backup.

### Context budget and preflight {#context-budget-and-preflight}

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

### Tool policy and context budget in the brief {#tool-policy-and-context-budget-in-the-brief}

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

### Operating-loop policy: attention, approval TTL, and extensions {#operating-loop-policy-attention-approval-ttl-and-extensions}

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

- `attention_policy` — the thresholds of the `needs_attention` flag (see [Attention state](decisions.md#attention-state)): how long an accepted retry may wait
  for its dispatch, how many operational retries (`verification-infrastructure`, `transport`,
  `context-pressure`) are allowed per candidate (`0` means none), and after how much silence a live
  dispatch counts as stale. `heartbeat_interval_seconds` (default 300) sets how often a worker sends a
  heartbeat; the brief records an interval no longer than a third of `stale_dispatch_seconds`.
- `approval_ttl_seconds` — the lifetime of an explicit `--approved-at`. The coordinator rejects an older
  approval (or one dated in the future) and does not reuse it. Without the field, approval does not expire.
  The `orchestration.example.json` example sets `14400`; `harness init` creates the config from it.
- `extensions` — pluggable interfaces outside the coordinator core: `transport_health`,
  `verification_environment_health`, `retry_reason_classifier`, `context_telemetry_provider`,
  `human_notifier`, `runtime_access`. The value is `none` (the inert default), a name registered by the
  host process, or `module:factory` (a factory callable without arguments in an importable module).
  An unknown name fails closed. No extension adds a model tool or changes the system prompt.

`harness health` checks the shape of all three sections. The coordinator reads authored policies without `assignment_plans` and merges them with defaults.
