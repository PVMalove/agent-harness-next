# Roles and transport

These groups in `.harness/orchestration.json` bind a role to a provider profile, runtime, model
and transport. A manifest defines the role's behavior and mode; configuration selects its
executor without overriding the manifest. Start with the [contract index](index.md) if the file
is not configured yet.

`<ключ>` in the paths below stands for a dictionary entry name, not a literal JSON key.
Every JSON block is a fragment to merge into the current file. Its model and effort come from
the managed example, not from defaults chosen for your project.

## Provider profiles: provider_profiles

Each named profile contains all three fields. Credentials are forbidden in profiles.

| Field | Contract |
| --- | --- |
| `provider_profiles.<ключ>.capabilities` | Required non-empty array of non-empty strings. Profile capabilities must be compatible with the role manifest's `required_capabilities`. |
| `provider_profiles.<ключ>.fallback` | Required array of fallback profile names in selection order. `[]` means no fallbacks. References must exist; cycles are rejected. |
| `provider_profiles.<ключ>.known_limitations` | Required array of non-empty strings describing known limitations. `[]` means none are listed. |

The schema documents these capabilities: `architecture-analysis`, `backend-development`,
`code-review`, `independent-verification`, `database-migrations`, `messaging-integration`,
`conflict-resolution`. This is a list in the schema description, not an `enum`: the validator
matches capabilities against manifests. Fallback does not change an approved brief's runtime.

```json
{
  "provider_profiles": {
    "claude-profile": {
      "capabilities": [
        "architecture-analysis",
        "backend-development",
        "code-review",
        "independent-verification"
      ],
      "fallback": [],
      "known_limitations": []
    }
  }
}
```

## Role assignments: assignment_plans

Keys are installed manifest names: `architect`, `developer`, `code-review`, `qa`,
`verification`, `database-migrations`, `messaging-integration`, `conflict-resolver`.
In the supplied set, `architect`, `code-review`, `qa` and `verification` use `read-only` mode;
the other four use `write`. Non-empty assignments must include `code-review`.
`test-author` is a developer helper, not a separate orchestration assignment; see the
[test-author guide](../../../agents/test-author.md).

| Field | Contract |
| --- | --- |
| `assignment_plans.<ключ>.zone` | Optional non-empty string. Legacy name of an existing `backend_zones` entry; use explicit `write_paths` for new plans. |
| `assignment_plans.<ключ>.write_paths` | Optional non-empty array of non-empty strings: the role's write ceiling. Without it, the whole repository or the selected legacy zone's paths apply. A batch's scope cannot exceed this ceiling; paths supplied alongside a zone must stay inside it. |
| `assignment_plans.<ключ>.transport` | `in-process` or `external`. Default: `in-process`, a subagent in the coordinator session. `external` uses the project's runtime adapter. |
| `assignment_plans.<ключ>.default_runtime` | Optional name of a runtime configured in this plan. With multiple runtimes and no default, select one via `--runtime`; a sole runtime needs no such field. |
| `assignment_plans.<ключ>.runtimes.<ключ>.profiles` | Required non-empty array of non-empty names from `provider_profiles`. Profiles are checked for existence and compatibility with the role. |
| `assignment_plans.<ключ>.runtimes.<ключ>.model` | Required non-empty string: a CLI model alias or ID without spaces. There is no universal default model; an ID in the example does not guarantee availability in your account. |
| `assignment_plans.<ключ>.runtimes.<ключ>.effort` | Required string: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra`. Support in the selected executor is checked separately. |

Each plan requires a non-empty `runtimes` object. The coordinator pins the selected runtime,
model, effort and transport in the brief. Adding `write_paths` to a read-only role does not
turn it into a writer. Transport, worktree and access restrictions are separate settings;
`external` alone does not mean a container. Resources are configured through
[access_policy](access.md).

The example assigns only `developer` and the mandatory `code-review`, using the profile above.
It is not a full pipeline: add plans for the other roles you use. `write_paths: ["**"]` means
the whole repository; choose an appropriate ceiling for your project during configuration.

```json
{
  "assignment_plans": {
    "developer": {
      "write_paths": [
        "**"
      ],
      "transport": "in-process",
      "default_runtime": "claude",
      "runtimes": {
        "claude": {
          "profiles": [
            "claude-profile"
          ],
          "model": "claude-opus-5-5",
          "effort": "xhigh"
        }
      }
    },
    "code-review": {
      "transport": "in-process",
      "default_runtime": "claude",
      "runtimes": {
        "claude": {
          "profiles": [
            "claude-profile"
          ],
          "model": "claude-opus-5-5",
          "effort": "xhigh"
        }
      }
    }
  }
}
```

## Languages: communication_policy

The object is optional; without it, agents communicate in `en` and coordinator reports use
`ru`. When the object is supplied, both fields are required. The site's language does not
change this contract.

| Field | Contract |
| --- | --- |
| `communication_policy.agent_to_agent_language` | Only `en` (`const`): the language of technical exchange between agents. |
| `communication_policy.coordinator_report_language` | Only `ru` (`const`): the language of coordinator reports for the user. |

```json
{
  "communication_policy": {
    "agent_to_agent_language": "en",
    "coordinator_report_language": "ru"
  }
}
```

## Working tool sets: tool_policy

The object is optional. The coordinator chooses a **complete list** in this order: the role
entry, otherwise the mode entry, otherwise the manifest mode's built-in set. Lists are not merged.

| Field | Contract |
| --- | --- |
| `tool_policy.modes` | Optional dictionary with `read-only` and `write` keys. Each entry is a non-empty array of unique, non-empty tool names. |
| `tool_policy.roles` | Optional dictionary: each installed role maps to a non-empty array of unique, non-empty tool names. Replaces the mode set entirely. Role names are the same as in `assignment_plans`. |

The built-in `read-only` set is `Read`, `Grep`, `Glob`, `Bash`; `write` additionally includes
`Edit`, `Write`. With an active test-author, the built-in developer set may also include
`Agent(test-author)`; explicit sets are not extended automatically.

```json
{
  "tool_policy": {
    "modes": {
      "read-only": [
        "Read",
        "Grep",
        "Glob"
      ],
      "write": [
        "Read",
        "Grep",
        "Glob",
        "Bash",
        "Edit",
        "Write"
      ]
    },
    "roles": {
      "code-review": [
        "Read",
        "Grep",
        "Glob",
        "Bash"
      ]
    }
  }
}
```

In this example, `code-review` gets `Bash` from its own entry although the shared `read-only`
set omits it. `allowed_tools` is a working set pinned in the brief, not a ban on global runtime
tools or a replacement for `access_policy`. Configuration changes affect subsequent briefs
without rewriting approved ones. See the
[guide](../../../backend-orchestration.md).

## Configure assignments with an agent {#agent-assignments}

This prompt helps select executors for installed orchestration. It must not infer the desired
model from the current agent's identity or change approval and access alongside assignments.
Questions and user-facing summaries stay in Russian, following the agreed interaction format.

??? quote ah-skill-text "Agent prompt: provider profiles and role assignments"

    ```text
    Configure role assignments in this project's .harness/orchestration.json.
    Follow repository instructions. Use English for technical instructions and Russian
    for all questions, choices and user-facing summaries.

    Read current project and orchestration configs, the installed schema, the managed
    example and role manifests. Run read-only health/config validation if available.
    Do not read credentials or authentication files. Preserve existing assignments
    unless I request a change; ask only for facts not established by the repository.

    Work through missing decisions one question at a time:
    - Which roles are needed: keep session-based assignments or configure explicit ones?
    - Which configured runtimes, available model IDs/aliases and effort levels should
      each role use? For multiple runtimes, which is the default?
    - Which write ceiling does each writer need, and which transport is intended?
    - Are fallback profiles, known limitations or tool overrides needed?
    Do not assume your own model or the managed example is the desired choice.

    Offer 2-4 concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; ask for missing
    facts when a recommendation is not possible. Example question:
    «Как запускать роль?» — «in-process: подагент текущей сессии»,
    «external: проектный runtime adapter», «Другое».
    Explain that external transport does not itself provide container isolation.

    Build only supported provider_profiles, assignment_plans, communication_policy
    and tool_policy fields. Reuse real profile/runtime IDs; ask for unknown model IDs
    and effort rather than guessing. Include code-review for non-empty assignments.
    Check capabilities against manifests, fallback references/cycles, runtime defaults,
    write ceilings and complete tool-list overrides. Keep communication languages en/ru.
    Do not alter manifests, approvals, access, execution policy, unrelated settings
    or existing dispatches. Never request token/key values or put them in configuration.

    Show the exact diff and explain choices, defaults and unresolved facts.
    Wait for my approval before applying it with Edit/Write. Validate the approved file
    with config validate --canonical --json and harness health through installed entry
    points. Report failures and unverified runtime/model availability separately.
    Do not run workers, change Git state, commit or open a PR.
    ```

## Validation and next step

Run the commands in the [index](index.md#config-validation). Then continue to
[policies](policies.md), [access](access.md) or [verification](verification.md).
The [backend guide](../../../backend-orchestration.md) explains role lifecycle and handoffs.
