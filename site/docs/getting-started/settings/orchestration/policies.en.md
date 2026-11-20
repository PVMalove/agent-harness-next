# Policies

Policies in `.harness/orchestration.json` control approval and the bounds of automatic
continuation: how many retries are allowed, when attention is required and which deadlines
apply. Executor assignments are covered in [roles](roles.md), resource permissions in
[access](access.md), and QA commands and plans in [verification](verification.md).

## Reading the values

Each field below includes its type, allowed values, default and effect. All policy groups
are optional; omitted nested parameters use built-in values. Exception: when the
`infrastructure_retry_policy` object is supplied, `enabled` is required within it.

Defaults come from the schema and are checked against the code. Where JSON Schema has no
`default` keyword, the value comes from its description and the loader. A value in the managed
example is a separate choice: it currently selects `auto`, 3 developer retries and 6
continuations, while the defaults are `manual_all`, `1` and `2`. Do not replace a whole config
with the example just to change one setting.

## Approval {#approval}

| Field | Contract |
| --- | --- |
| `approval_policy` | String: `manual_all`, `milestone`, `low_risk`, `auto`. Default: `manual_all`. Controls which steps require a human and which the policy approves. See each mode below. |
| `human_approval_gate` | String: `trusted`, `tty`. Default: `trusted`. `trusted` accepts CLI arguments `--approved-by` / `--approved-at`; `tty` requires interactive terminal confirmation. Only `trusted` is compatible with `auto`. |
| `approval_ttl_seconds` | Integer ≥ `1`. Optional. Without this field, explicit approval does not expire. Limits the age of `--approved-at`; `14400` in the managed example is a chosen lifetime, not a default. |
| `low_risk_paths` | Array of non-empty strings (at least one). Optional. Without allowed paths, nothing qualifies as low risk. Use repository-relative `dir/**`, `**` or an exact file, without a leading `/`, `.`, `..` or empty segments. All batch `allowed_paths` must fit these boundaries. |
| `worker_attestation_required` | Boolean: `true` / `false`. Default: `false`. `true` requires attestation for all roles. With `false`, it remains mandatory for `architect`, `developer`, `conflict-resolver`, `database-migrations`, `messaging-integration`, `code-review`. `auto` requires `true`. |

### approval_policy modes

| Value | Behavior |
| --- | --- |
| `manual_all` | Each step and report acceptance require manual approval. The built-in default. |
| `milestone` | Automatically accepts a clean `completed` report with no risks, blockers, risk triggers or failed checks. QA, publish and batches with matching risk triggers remain manual milestones. |
| `low_risk` | The same conditions for automatic acceptance, but only when the entire batch scope fits `low_risk_paths` or allowed legacy zones. Without matching paths, acceptance is not automatic. |
| `auto` | An automatic route from batch approval to accepted publish inside approved boundaries. Decisions are recorded as `policy:auto` with evidence. Integrity errors, exhausted budgets or a missing automatic route stop the path. Requires `trusted` and attestation for all roles. |

A fragment with manual approval:

```json
{
  "approval_policy": "manual_all",
  "human_approval_gate": "trusted"
}
```

`auto` requires a compatible combination of fields; the following fragment illustrates its
shape, not a recommendation to enable it:

```json
{
  "approval_policy": "auto",
  "human_approval_gate": "trusted",
  "worker_attestation_required": true
}
```

The policy is pinned when a batch is created. For `auto`, both project config and batch plan
must continue to select `auto`, with no `auto_stop` or manual recovery. `resume-stop` and
`rewind` preserve history and return subsequent steps to `manual_all`. Editing the file does
not resume a stopped automatic route. Auto policy does not open a PR: separate explicit human
confirmation is required; auto-merge is forbidden. See the
[backend guide](../../../backend-orchestration.md) for batches and approvals.

## Retries and attention {#retries}

| Field | Contract |
| --- | --- |
| `retry_policy.max_developer_retries` | Integer ≥ `0`. Default: `1`. Developer retry limit after review or QA findings; `0` disables these retries. These are not worker-session continuations. |
| `auto_retry_min_severity` | String: `info`, `warning`, `error`, `blocker`. Default: `info`. Minimum finding severity for automatic review-retry; pinned in the batch plan. This routes retries; it does not authorize ignoring findings. |
| `attention_policy.retry_queue_seconds` | Integer ≥ `1`. Default: `3600`. How long an accepted retry may wait for its dispatch before attention is required. |
| `attention_policy.max_infrastructure_retries` | Integer ≥ `0`. Default: `2`. Operational retry budget per candidate: infrastructure, transport and context pressure. `0` allows none. |
| `attention_policy.stale_dispatch_seconds` | Integer ≥ `1`. Default: `3600`. A live dispatch becomes stale after this period of silence and requires attention. This is not a process-stop command. |
| `attention_policy.heartbeat_interval_seconds` | Integer ≥ `1`. Default: `300`. Desired heartbeat interval in seconds. The brief pins `max(1, min(heartbeat_interval_seconds, stale_dispatch_seconds // 3))`. |
| `infrastructure_retry_policy.enabled` | Boolean: `true` / `false`. Default: `false`. The object is optional, but `enabled` is required within it. Enables bounded recovery inside approved boundaries using the attention budget; it grants no native permissions. |

Attention thresholds and infrastructure recovery permission are pinned in the immutable brief.
Editing configuration during a dispatch does not expand its approved permissions or budget.
Enabled recovery does not bypass `needs_attention`: resolve the stop reason first. The default
infrastructure budget is `2`, but automatic recovery via
`infrastructure_retry_policy.enabled` is disabled.

## Session continuation {#continuation}

A developer retry and a worker-session continuation are distinct mechanisms with separate
limits. Reaching an adaptive threshold is a reason to consider continuation, not permission
to spawn sessions indefinitely. Checkpoint/resume eligibility depends on the role and dispatch
state; see the [backend guide](../../../backend-orchestration.md) for the procedure.

| Field | Contract |
| --- | --- |
| `continuation_policy.max_continuations` | Integer ≥ `1`. Default: `2`. Worker-session continuation limit per dispatch. |
| `continuation_policy.max_rate_limit_resumes` | Integer ≥ `1`. Default: `1`. Automatic resume limit after a rate limit. A separate counter within continuation limits. |
| `adaptive_continuation_policy.context_limit` | Integer ≥ `1`. Default: `150000`. Context threshold for considering continuation; also supplies the brief context budget. This is not a task-wide billed-token limit. |
| `adaptive_continuation_policy.tdd_cycle_count` | Integer ≥ `1`. Default: `3`. TDD-cycle threshold for planned continuation. |
| `adaptive_continuation_policy.failure_log_bytes` | Integer ≥ `1`. Default: `20000`. Failure-log size threshold in bytes for planned continuation. |
| `adaptive_continuation_policy.context_warn_ratio` | Number: `0 < value ≤ 1`. Default: `0.8`. Fraction of the context limit that triggers a warning. At defaults: `150000 × 0.8 = 120000`. The advisory itself authorizes no checkpoint and changes no state. |

## Timeouts and preflight {#timeouts-preflight}

### Execution

All durations and intervals in this table are seconds. Waiting for a coordinator response is
not the same as a process lifetime: a startup/wait timeout alone does not prove it stopped.

| Field | Contract |
| --- | --- |
| `execution_policy.worker_startup_timeout_seconds` | Integer ≥ `1`. Default: `120`. Wait for the first self-report. Expiry does not prove that the worker stopped or authorize a duplicate launch. |
| `execution_policy.dispatch_wait_timeout_seconds` | Integer ≥ `1`. Default: `60`. Duration of one dispatch wait in seconds; not the worker execution deadline. |
| `execution_policy.dispatch_poll_interval_seconds` | Integer ≥ `1`. Default: `5`. Dispatch polling interval in seconds. |
| `execution_policy.rate_limit_retry_seconds` | Integer ≥ `1`. Default: `60`. Delay before retrying a rate limit when the provider supplied no deadline. |
| `execution_policy.worker_execution_timeout_seconds` | Integer ≥ `1`. Default: `14400`. Worker execution deadline under the runtime supervisor. On expiry, the runtime stops the process group. |
| `execution_policy.stop_grace_seconds` | Integer ≥ `1`. Default: `30`. Grace between SIGTERM and SIGKILL when stopping a process group at its deadline; also applies to stopping a QA command container. |
| `execution_policy.qa_command_timeout_seconds` | Integer ≥ `1`. Default: `3600`. Deadline for one containerized QA command under the runtime; its container is then stopped with the configured stop grace. |

### Task scope before starting

Preflight checks expected scope before creating a batch. If a limit is exceeded, first refine
the estimate or split the ticket; do not raise the limit automatically. The factors below
estimate context, not guaranteed cost or actual token usage.
The admission estimate is the maximum of the supplied number and the sum of line/file
estimates. A smaller `--expected-context-tokens` cannot reduce that computed floor.

| Field | Contract |
| --- | --- |
| `preflight_policy.require_estimates` | Boolean: `true` / `false`. Default: `true`. Requires scope estimates before starting. `false` disables that requirement, not the other limits. |
| `preflight_policy.max_definition_of_done_items` | Integer ≥ `1`. Default: `5`. Maximum number of Definition of Done items. |
| `preflight_policy.max_dependencies` | Integer ≥ `1`. Default: `3`. Maximum number of dependencies on other tickets. |
| `preflight_policy.max_expected_files` | Integer ≥ `1`. Default: `12`. Maximum expected changed files. |
| `preflight_policy.max_expected_services` | Integer ≥ `1`. Default: `1`. Maximum affected services. |
| `preflight_policy.max_expected_changed_lines` | Integer ≥ `1`. Default: `800`. Maximum expected changed lines. |
| `preflight_policy.max_expected_context_tokens` | Integer ≥ `1`. Default: `80000`. Maximum estimated context before starting; not a meter of billed tokens. |
| `preflight_policy.estimated_tokens_per_changed_line` | Integer ≥ `1`. Default: `20`. Estimation factor: tokens per changed line. |
| `preflight_policy.estimated_tokens_per_file` | Integer ≥ `1`. Default: `2000`. Estimation factor: tokens per affected file. |

## Concurrency and leases {#concurrency-lease}

| Field | Contract |
| --- | --- |
| `concurrency_budget` | Integer ≥ `1`. Default: `1`. Limit on simultaneously active batches. Unconfigured mode uses `1`; the key is required in an explicitly configured setup. Does not remove the single-writer limit inside a batch. |
| `lease_ttl_seconds` | Integer ≥ `1` and ≤ `86400`. Default: `300`. Runtime-store QA-lane lease in seconds. The owner renews it every third of its lifetime; the runtime checks owner liveness after expiry. |
| `execution_policy.qa_lease_seconds` | Integer ≥ `1`. Default: `1800`. File-based QA-lane lease in seconds. Does not replace the current runtime store’s `lease_ttl_seconds` or set a QA-command deadline. |

`lease_ttl_seconds`, the worker execution timeout and the lifetime of manual approval are
independent. None replaces the others or resets their restrictions.

## Deprecated fields {#legacy}

Existing zone-based configurations remain valid. `<ключ>` stands for a dictionary entry name,
not a literal JSON key. Use explicit paths for new configurations.

| Field | Contract |
| --- | --- |
| `backend_zones.<ключ>.paths` | Array of non-empty strings (at least one). Required within an existing zone. Legacy named boundaries; new batches use `allowed_paths` within the `assignment_plans.<ключ>.write_paths` ceiling. Zones no longer control admission of parallel batches. |
| `low_risk_zones` | Array of non-empty strings. Legacy names from `backend_zones`. Their paths contribute to allowed low-risk paths; use `low_risk_paths` in new configs. An older batch without explicit scope still uses its zone. |

For example, a legacy zone list:

```json
{
  "backend_zones": {
    "docs": {
      "paths": [
        "site/docs/**"
      ]
    }
  },
  "low_risk_zones": [
    "docs"
  ]
}
```

Its paths can be written explicitly for low-risk classification:

```json
{
  "low_risk_paths": [
    "site/docs/**"
  ]
}
```

Both blocks are fragments, not complete configs. Do not remove `backend_zones` while
`assignment_plans.<ключ>.zone` or older batches reference it. Preserve the existing scope when
migrating; changing path notation must not expand automatic approval.

## Configure with an agent {#agent-policy-setup}

Choose a prompt for the group you need. The agent reads existing values before asking only
for missing decisions. Instructions are in English; questions and summaries are in Russian.

??? quote ah-skill-text "Agent prompt: approval"

    ```text
    Help me configure approval policy for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask who should approve workflow steps: manual_all, milestone, low_risk or auto.
    For a new setup, explain the manual_all default; do not overwrite an existing
    choice automatically. For low_risk, ask for exact allowed paths and show the whole
    allowlist; never choose ** for convenience. Ask about trusted versus tty, whether
    explicit approvals should expire, and attestation for the remaining roles.
    Keep the six always-attested roles protected even when the flag is false.
    Do not enable auto without my explicit choice. Explain its trusted-gate and
    worker_attestation_required=true prerequisites, stop conditions and separate
    human confirmation for opening a PR. Changing config does not resume auto_stop.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

??? quote ah-skill-text "Agent prompt: retries and attention"

    ```text
    Help me configure bounded retries and attention thresholds for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask separately about developer retry count, review severity threshold,
    infrastructure/transport/context retry budget, stale-worker time and heartbeat,
    and how long accepted retries may queue. Use observed project facts, not guessed
    performance. Example: «Сколько повторов developer разрешить?» — a justified
    current/default value, another supported count, zero where supported, «Другое».
    Explain which fields allow zero and that zero is not a general disable value.
    Calculate the effective heartbeat cadence from the chosen stale interval.
    Ask whether infrastructure_retry_policy.enabled should be set: enabling it only
    permits recovery inside already-approved boundaries and the attention budget;
    it does not grant network, filesystem or native permissions. Do not widen them.
    Do not treat retries as a way to suppress findings or restart a live worker.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

??? quote ah-skill-text "Agent prompt: continuation and limits"

    ```text
    Help me configure continuation, execution and preflight limits for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask about total continuations and rate-limit resumes, then context/TDD/log
    thresholds. Explain that context warnings alone authorize no state transition.
    Ask about startup wait, one dispatch wait, execution deadline and stop grace
    separately; do not confuse them with each other or with QA-command timeouts.
    Ask for typical DoD size, dependencies, expected files/services/lines and context
    estimates. Derive proposed preflight limits from those answers; do not inflate
    limits just to pass a check or describe estimates as a billed-token spending cap.
    Ask whether concurrency and the runtime QA lease need to change. Distinguish
    lease_ttl_seconds from the legacy file-lane execution_policy.qa_lease_seconds.
    Do not migrate or delete backend_zones/low_risk_zones until all assignment and
    batch references have been inspected and I have reviewed the migration diff.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

## Validation and next steps

After editing, run the commands in the [index](index.md#config-validation).
Resource and container settings are in [access](access.md); verification commands and plans
are in [verification](verification.md). This page does not override them.
