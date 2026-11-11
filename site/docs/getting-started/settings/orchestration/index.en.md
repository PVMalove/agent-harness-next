# orchestration.json

`.harness/orchestration.json` defines role assignments, approval, access and checks for backend
orchestration. The coordinator reads it to prepare briefs and choose the next step;
`harness-runtime` uses the configuration for execution. Project conventions — language, branches,
tracker and the shared QA gate — remain in [project.json](../project.md).

## Location and creation

Installing the `backend-orchestration` capability creates a missing file from the managed
`.harness/orchestration.example.json`. The project then owns it: a normal `harness update`
refreshes the example and preserves the existing `orchestration.json`. Forcing a replacement
is a separate explicit action, not a way to change one setting.

The schema lives at `.harness/orchestration/orchestration.schema.json`. The optional string
field `$schema` points editors to `./orchestration/orchestration.schema.json`.

## Explicit assignments and the unconfigured mode

A configuration with explicit profiles or assignments needs four top-level keys:

| Field | Purpose |
| --- | --- |
| `provider_profiles` | Provider profiles: capabilities, fallback profiles and limitations. |
| `assignment_plans` | Assignments for the roles in use: runtime, model, effort, transport and write ceiling. A non-empty set must include `code-review`. |
| `concurrency_budget` | An integer of at least `1`: the limit on simultaneously active batches. See [policies](policies.md). |
| `verification_commands` | An array of strings defining the full independent QA gate. See [verification](verification.md). |

Optional policies use built-in values where the contract defines them. A value in the managed
example is not necessarily a default.

A missing file does not itself prevent work: the coordinator supports a mode without explicit
assignments, where the runtime comes from the invoking session and each batch states its scope.
An empty seed does not enable explicit assignments either:

```json
{
  "$schema": "./orchestration/orchestration.schema.json",
  "provider_profiles": {},
  "assignment_plans": {},
  "concurrency_budget": 1,
  "verification_commands": []
}
```

This is a recognized seed, not an example of a fully configured pipeline. In unconfigured mode,
QA commands come from `project.json.qa_gate_commands`; check that it defines real checks.
In an explicit configuration, populate `verification_commands` with your project's commands:
an empty list does not prove code quality. The schema separately permits configurations without
profiles, assignments and legacy zones, so the four-key rule has exceptions.

## Section map

| Page | Settings covered |
| --- | --- |
| [Roles and transport](roles.md) | `provider_profiles`, `assignment_plans`, `communication_policy`, `tool_policy`: executors, languages and working tool sets. |
| [Policies](policies.md) | Approval, retries, session continuation, preflight, concurrency and leases. |
| [Access and container](access.md) | `access_policy`, `extensions`, resource access, networking and the container executor. |
| [Verification](verification.md) | QA commands and plans, verification profiles, Repo Map and Context Package. |

The [backend orchestration guide](../../../backend-orchestration.md) explains batch execution,
approval and recovery. The [console wizard](../../../console-configuration.md) helps select
configuration and inspect diagnostics.

## Validation and normalization {#config-validation}

From the installed project's root, run:

```bash
python3 .harness/orchestration/coordinator.py --repo . config validate --json
python3 .harness/orchestration/coordinator.py --repo . config validate --canonical --json
harness health .
```

The first command validates the contract and prints diagnostics; an invalid configuration exits
with code `2`. The second also rejects spelling that needs normalization, with
`config-noncanonical`. `harness health` checks configuration alongside the project's other
surfaces. If the CLI is not installed as `harness`, use the available package entry point
from the [CLI reference](../../../reference/cli.md).

Unknown fields are rejected. On load, the coordinator normalizes only registered enum fields
in memory and warns about corrections; it does not normalize IDs, models, paths or commands.
Reading and ordinary validation do not rewrite the file. Invalid JSON, duplicate keys and
secrets need explicit correction. Writing normalization requires a separate `--fix`; first
inspect `config validate --fix --dry-run --json`, as explained in the
[guide](../../../backend-orchestration.md).

## Configure with an agent {#agent-setup}

Copy this prompt into an agent session opened in the target project. It inspects current state
before asking missing questions; writing requires your review and approval of the diff.
Questions and user-facing summaries stay in Russian, following the agreed interaction format.

??? quote ah-skill-text "Agent prompt: getting started"

    ```text
    Help me configure backend orchestration for this repository.
    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.

    1. Read .harness/project.json and .harness/orchestration.json if present,
       the installed orchestration schema, .harness/orchestration.example.json,
       and the role manifests. Do not read credentials or authentication files.
       Run the available read-only harness health and config validate commands.
       If backend-orchestration is not installed, explain what is missing first;
       do not invent a config layout or install anything implicitly.
    2. Summarize existing settings. Do not ask for known values or replace them
       with the managed example. Missing config and an empty seed can use the
       invoking session; do not call either case broken by default.
    3. Ask one unresolved question at a time. Start with whether to keep session-based
       assignments or configure explicit role assignments. Clarify the required roles,
       runtimes/models, write boundaries and full QA commands only where needed.
       Offer 2-4 concrete choices plus «Другое». Put an evidence-based recommendation
       first, mark it «Рекомендуется», and explain each consequence in one line.
       If no recommendation is justified, ask for the missing fact instead.
       Example: «Как выбирать исполнителей?» — «Из текущей сессии»,
       «Явные назначения по ролям», «Другое». Recommend only after inspecting context.
    4. Use only schema fields and values supported by the validator, repository
       evidence or my answers. Do not guess a model, effort, path or QA command.
       With non-empty assignments, include code-review and validate profile references.
       Do not widen permissions, enable auto approval or change unrelated policies.
       Never request, read, print or store token/key values.
    5. Show the proposed configuration diff, explain defaults versus chosen values,
       and list unanswered questions. Wait for my approval before writing.
       Apply only approved changes with Edit/Write; preserve unrelated settings.
       Run config validate --canonical --json and harness health again through the
       installed entry points. Report results and anything not checked. Do not commit,
       launch workers, start a batch or open a PR as part of configuration.
    ```
