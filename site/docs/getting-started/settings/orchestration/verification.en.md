# Verification

`.harness/orchestration.json` defines verification commands, test selection rules and context
limits for roles. Start with full QA, then identify focused developer and review checks.
Configure Repo Map and Context Package for the project's size and the model's available context.

Here, “default” means behavior when a field is omitted. The managed
`.harness/orchestration.example.json` contains separate example values: check its commands and
limits against your project. The JSON fragments below extend an existing configuration.

## Full gate {#full-gate}

| Field | Contract |
| --- | --- |
| `verification_commands` | Array of non-empty strings: shell commands for full QA. The managed example uses `[]`; project commands must be configured explicitly. An empty list is valid configuration, but `qa run` refuses to run without checks. |

Ordinary clean-room QA runs the full list in a separate checkout at `candidate_sha`.
A passing developer or review run does not replace that evidence. A changed SHA needs new QA;
the full gate required before publish is described in [QA gate](../../../guides/qa-gate.md).
The exception for ticket plans targeting `integration/*` is covered [below](#verification-plans).

## Focused role checks {#role-checks}

| Field | Contract |
| --- | --- |
| `developer_verification_commands` | Array of non-empty strings. When omitted, uses `verification_commands`. Explicit `[]` is allowed but defines no developer checks. |
| `review_verification_commands` | The same array type for independent code-review checks on the candidate. When omitted, uses `verification_commands`; explicit `[]` is allowed. |

The managed example contains empty general lists. Their presence alone does not configure tests.
Find working project commands first, then choose narrower commands for fast iterations.
A role's report must list exactly the commands from its brief, rather than substitute its own.

## QA preparation and diagnosis {#qa-preparation}

| Field | Contract |
| --- | --- |
| `qa_preparation` | Array of shell commands, default `[]`. Runs in the candidate checkout before the gate; stops at the first failure. An empty list starts checks immediately. |
| `qa_environment_probes` | Array of shell commands, default `[]`. Independent environment probes in the same checkout, only after preparation fails. For example, checking access to a required registry. |
| `qa_project_file_checks` | Array of shell commands, default `[]`. Independent offline project-file checks in the same checkout, only after preparation fails. For example, manifest/lock-file consistency. |

Every array element is a non-empty string. Choose commands from the project's actual toolchain:
there is no universal network or lock-file check here.

- A project-file check fails → a project defect is confirmed.
- An environment probe fails while project-file checks pass → an infrastructure cause is confirmed.
- Required probes/checks are absent or results provide no proof → diagnosis is needed;
  a dependency installation failure alone does not prove an infrastructure problem.

## Verification profiles and plans {#verification-plans}

### Scope profiles

`verification_profiles` is an optional array. At `batch create`, the **first** profile whose
patterns cover every batch `allowed_paths` entry supplies the frozen developer and review
commands. Without whole-scope coverage, the general lists apply; an empty scope selects no
profile. A profile does not replace the full QA list.

| Field | Contract |
| --- | --- |
| `verification_profiles[].paths` | Required non-empty array of repository-relative paths/globs. No leading `/`, backslash, empty segment, `.` or `..`. |
| `verification_profiles[].developer` | Required array of developer shell commands; `[]` is allowed. |
| `verification_profiles[].review` | Required array of code-review shell commands; `[]` is allowed. |

Example **for this repository**: the profile comes from the managed example; `make verify` is
the full gate in its Makefile. `pytest -n 8` requires pytest-xdist. Do not copy these paths and
commands to a different project without checking them.

```json {.ah-code-wrap}
{
  "verification_commands": ["make verify"],
  "developer_verification_commands": ["make lint"],
  "review_verification_commands": ["make lint"],
  "verification_profiles": [
    {
      "paths": ["harness/console/**", "tests/console/**"],
      "developer": ["make lint", "pytest -q -n 8 tests/console"],
      "review": ["make lint", "pytest -q -n 8 tests/console"]
    }
  ]
}
```

### Change-impact plan

Optional `verification_plan_policy` is frozen when a batch is created. At `dispatch propose`,
it produces a plan for developer-retry, code-review and QA. The first developer dispatch has
no such plan. Without this policy, the frozen command lists remain in use.

| Field | Contract |
| --- | --- |
| `verification_plan_policy.max_related_tests` | Required integer ≥ 1. ChangeImpact test-count threshold: exceeding it widens pytest selection to `full`. No default; the managed example uses `200`. |
| `verification_plan_policy.ticket_diff_selection` | Boolean, default `false`. When `true` **and** the target is `integration/*`, enables the ticket-diff selection described below. |
| `verification_plan_policy.stages[].stage_id` | Required non-empty string, unique among stages. |
| `verification_plan_policy.stages[].kind` | Required: `lint`, `typecheck`, `pytest`, `clean-room` or `custom`. Related-test selection applies to `pytest`. |
| `verification_plan_policy.stages[].argv` | Required non-empty array of non-empty strings: program and arguments, rather than a shell string. Selected nodeids are appended for `focused` pytest. |
| `verification_plan_policy.stages[].timeout_seconds` | Required integer ≥ 1: stage timeout in seconds. No shared default. |

`stages` must contain at least one stage and **must include a `pytest` stage**. Otherwise the
policy is rejected: the plan cannot cover related tests at review/QA (`impact_not_covered`).
An ordinary plan selects related tests for retry/review; unknown impact widens selection to
`full`, and QA receives `full`. An empty `focused` selection means `not_run`, not a passing run.

**Ticket-diff selection.** With `ticket_diff_selection` enabled for `integration/*`, retry,
review **and QA** plans select tests from `base..candidate` (`ticket-diff`), without widening
to `full`. Added/modified Python tests and corresponding Rust test targets are included.
If the diff contains no tests, static stages remain and the test stage is `not_run`.
Commands for these briefs are derived from the plan. This diagnoses the ticket branch; publish
still requires the full gate on the final SHA. With `false` or a default-branch target, ordinary
planning applies. The detailed contract is in
[ADR 0023](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0023-incremental-verification.md).

The next fragment is the template from the managed example, with its threshold and timeouts,
**not defaults**. Use it only after checking commands and run times in your project.

```json {.ah-code-wrap}
{
  "verification_plan_policy": {
    "max_related_tests": 200,
    "ticket_diff_selection": false,
    "stages": [
      {"stage_id": "lint", "kind": "lint", "argv": ["make", "lint"], "timeout_seconds": 900},
      {"stage_id": "tests", "kind": "pytest", "argv": ["pytest", "-q", "-n", "8"], "timeout_seconds": 1800}
    ]
  }
}
```

## Related tests {#related-tests}

| Field | Contract |
| --- | --- |
| `retry_verification.lint` | Required array of shell commands inside an authored `retry_verification`; may be `[]`. Runs before the selected developer-retry tests. |
| `retry_verification.test_command` | Required non-empty shell string inside `retry_verification`. Shell-quoted `related_tests` paths from Context Package are appended as one command. |
| `test_path_patterns` | Array of non-empty glob strings identifying test paths in delta-review. When omitted or `[]`, uses `tests/**`, `**/tests/**`, `**/test_*.py`, `**/*_test.py`. |

Without `retry_verification` or related tests, retry keeps the ordinary developer commands.
This mechanism alone does not change the first developer dispatch, review or full QA.
A verification plan, if configured, additionally defines ChangeImpact or ticket-diff selection.

`test_path_patterns` does not grant test-author write access. Its `test_paths` zones and runner
are in [project.json](../project.md); execution rules are in the
[test-author guide](../../../agents/test-author.md).

## Repo Map and Context Package {#context}

Repo Map summarizes tracked files at a pinned commit: paths and, when a parser bundle is
available, signatures and relationships. It is neither the full repository text nor an exact
call graph. Context Package assembles the diff, starting files/pointers, dependencies, related
tests and reference context within a budget. The map's cache is not a source of truth.

### Repo Map filters and limits

Optional `repo_map_policy` supplements built-in exclusions for secrets, dependencies,
generated files and binary files. An empty allow-list does not remove those exclusions.

| Field | Contract |
| --- | --- |
| `repo_map_policy.allow_paths` | Array of glob strings, default `[]`: no additional allow-list restriction. A non-empty list admits only matching paths. |
| `repo_map_policy.deny_paths` | Array of glob strings, default `[]`: additional path exclusions. |
| `repo_map_policy.redact_paths` | Array of glob strings, default `[]`. The current filter excludes the entire matching path from the map, rather than just the file body. |
| `repo_map_policy.redact_symbols` | Array of symbol-name glob strings, default `[]`: hides matching functions/classes from the map. |
| `repo_map_policy.max_files` | Integer ≥ 1, default `10000`: file-count limit. |
| `repo_map_policy.max_file_bytes` | Integer ≥ 1, default `2000000`: file-processing size limit in bytes. |
| `repo_map_policy.max_path_length` | Integer ≥ 1, default `4096`: maximum path length in characters. |
| `repo_map_policy.max_symbol_length` | Integer ≥ 1, default `256`: maximum symbol-name length. |
| `repo_map_policy.max_signature_length` | Integer ≥ 1, default `2048`: maximum signature length. |
| `repo_map_policy.timeout_seconds` | Integer ≥ 1, default `10`: Git-call timeout in seconds. |
| `repo_map_policy.max_tokens` | Integer ≥ 1. Budget for the final map JSON: `4000` without an explicit CLI/policy budget. An explicit CLI budget cannot exceed an authored policy ceiling. |

Array elements are non-empty strings; glob matching is case-sensitive. The managed example's
`timeout_seconds: 30` and `max_tokens: 8000` are chosen values, not defaults.

### Map tier and parser bundle

| Field | Contract |
| --- | --- |
| `repo_map_policy.tier` | `full` or `minimal`, default `full`: attempt semantic parsing or produce only a path inventory. An unavailable/unverified bundle can degrade the result to `minimal` with a reason. |
| `repo_map_policy.min_tier` | `full` or `minimal`. Omitted means no tier admission gate. Sets the minimum tier for dispatch admission. |
| `repo_map_policy.min_tier_by_role.architect` | `full` or `minimal`: overrides the global minimum for architect. When omitted, uses `min_tier` if set. |
| `repo_map_policy.min_tier_by_role.developer` | The same override for developer. |
| `repo_map_policy.min_tier_by_role.code-review` | The same override for code-review. |
| `repo_map_policy.parser_bundle_registry_paths` | Array of non-empty strings, default `[]`: additional local bundle search directories; relative paths resolve from the repository. The built-in local registry is searched first. |
| `repo_map_policy.parser_bundle_timeout_seconds` | Integer ≥ 1, default `30`: parser subprocess timeout in seconds. |
| `repo_map_policy.parser_bundle_max_output_bytes` | Integer ≥ 1, default `10000000`: parser subprocess output limit in bytes. |

Only the three listed roles are allowed in `repo_map_policy.min_tier_by_role`. Other roles use
the global minimum, or have no tier gate if it is absent. `tier: full` alone does not guarantee
full parsing; `min_tier: full` blocks dispatch with a degraded map. Do not lower this minimum
automatically to bypass an error. Bundle lock and hashes are verified; dispatch does not install
it from the network. See
[ADR 0008](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0008-repo-map.md).

### Context Package budget

Every value in optional `context_package_policy` is an integer ≥ 1.

| Field | Contract |
| --- | --- |
| `context_package_policy.max_tokens` | Default `200000`: token-estimate ceiling for the entire package. |
| `context_package_policy.context_window_tokens` | Default `250000`: configured target-model context window; the field itself does not verify the provider limit. |
| `context_package_policy.reserved_prompt_tokens` | Default `20000`: headroom for instructions and the system prompt. |
| `context_package_policy.symbol_graph_depth` | Default `2`: symbol/import graph traversal depth during assembly. |
| `context_package_policy.max_related_tests` | Default `25`: related-test limit. Exceeding it fails package assembly, without silently truncating tests. |
| `context_package_policy.min_starting_files` | Default `5`: minimum starting-file count for manual registration. |
| `context_package_policy.max_starting_files` | Default `10`: maximum starting-file count. |
| `context_package_policy.section_index_min_tokens` | Default `20000`: threshold at which a large Markdown/Python file may enter as a section/symbol index with line ranges. |

Constraints: `min_starting_files ≤ max_starting_files`, headroom is below the window, and
`max_tokens ≤ context_window_tokens − reserved_prompt_tokens`. If the package still does not
fit, assembly fails. An index is used where one can be built and reduces size; this does not
permit silently losing context.

Check these constraints with defaults applied: current canonical validation compares the budget
only when all three numbers are explicit. For example, `max_tokens: 240000` alone passes that
check but exceeds the available `230000` under the default window and headroom; Context Package
preparation rejects it. Validating a partial object does not replace checking effective limits.

These are separate budgets: the **plan's** test-count threshold widens the run; the **package's**
test-count cap limits assembly. Dispatch also enforces `adaptive_continuation_policy.context_limit`
from [policies](policies.md#continuation): increasing the package window does
not raise the role budget.

This fragment uses defaults; check the window against the chosen model before applying it.
The managed example uses higher `max_tokens: 260000` and `context_window_tokens: 300000`.

```json {.ah-code-wrap}
{
  "context_package_policy": {
    "max_tokens": 200000,
    "context_window_tokens": 250000,
    "reserved_prompt_tokens": 20000,
    "symbol_graph_depth": 2,
    "max_related_tests": 25,
    "min_starting_files": 5,
    "max_starting_files": 10,
    "section_index_min_tokens": 20000
  }
}
```

## Configure with an agent {#agent-setup}

The prompts inspect current configuration first and ask about unresolved facts. Full QA,
dependency installation and parser bundle builds are separate actions; they are not run
automatically just to configure settings.

??? quote ah-skill-text "Agent prompt: QA commands, profiles and plans"

    ```text
    Help me configure verification for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema and managed
    example, build/test manifests, CI configuration and existing verification scripts.
    Inspect existing read-only health/config checks. Do not run arbitrary project commands yet.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Establish the full clean-room QA command list first. Then ask which focused developer
    and independent review commands are acceptable. Explain missing-field fallback to the
    full list and that explicit empty lists provide no role checks; never silently empty a gate.
    Ask whether QA preparation is needed. Separate environment probes from offline project-file
    checks; neither a preparation error alone nor missing probes proves an infrastructure cause.
    Ask whether path profiles are useful. Explain first whole-scope match and batch freezing.
    Use only commands and paths found in this repository or explicitly supplied by me.
    Ask whether verification_plan_policy is needed. If yes, agree on max_related_tests,
    stage argv and measured/justified timeouts. Require unique stage IDs and a pytest stage;
    explain how this requirement fits the project's actual test runner before proposing a plan.
    Explain ordinary full/focused selection, unknown impact and empty-selection not_run.
    Ask separately before enabling ticket_diff_selection: it changes retry, review AND QA
    for integration/* to tests in the ticket diff, without widening to full. It does not
    replace the final full release gate. Leave it false unless I explicitly choose it.
    Ask whether retry_verification and test_path_patterns need changes. Distinguish retry's
    Context Package tests from plan ChangeImpact and from test-author write zones in project.json.

    Preserve unrelated settings. Show the exact proposed diff, command provenance, fallbacks,
    empty lists and which settings need a new batch. Wait for approval, then apply only that
    diff with Edit/Write. Run installed config validate --canonical --json and harness health.
    Report checks and remaining gaps. Ask separately before running the actual full QA,
    preparation or network probes. Do not create batches, send workers, install dependencies,
    weaken release checks, migrate state, change Git, commit or open a PR.
    ```

??? quote ah-skill-text "Agent prompt: Repo Map and context budget"

    ```text
    Help me configure repo_map_policy and context_package_policy for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema and managed
    example, Repo Map documentation, existing parser bundle metadata and model assignments.
    Use tracked path metadata to understand languages and scope; do not read authentication
    files, excluded secret files or token/key values. Do not install or fetch a bundle.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Ask which source paths should be included/excluded and which symbols should be hidden.
    Explain built-in exclusions, case-sensitive globs and that redact_paths excludes whole
    paths in the current implementation. Preserve existing privacy restrictions.
    Ask whether path-only minimal is sufficient or parser-backed full is needed, then agree
    separately on global/per-role minimum tiers. Only architect, developer and code-review
    have role overrides. Full generation can degrade; a required full tier blocks dispatch.
    Check local bundle provenance/availability without changing it. Explain blockers instead
    of lowering minimum tiers or inventing registry paths. Agree on justified size/time limits.
    Ask for the chosen model's supported context window if local evidence is insufficient.
    Agree on reserved prompt headroom and package/role budgets; validate max_tokens fits
    context_window_tokens minus reserved_prompt_tokens and does not ignore the role budget.
    Resolve omitted values to defaults yourself: canonical validation currently misses an
    over-budget partial object when window or reserve is omitted; package preparation rejects it.
    Agree on graph depth, starting-file bounds and the section-index threshold.
    Explain that the package's related-test cap fails on overflow, while the plan's cap widens
    test selection. Never silently truncate tests or raise caps merely to hide a failure.

    Use only supported fields and evidence or my answers. Show the exact proposed diff,
    effective defaults, tier admission consequences and assumptions. Wait for approval,
    then apply only that diff with Edit/Write. Run installed config validate --canonical --json
    and harness health. Report checks and remaining gaps, including parser execution or model
    limits not verified. Do not register packages, create batches, send workers, install/build
    bundles, change privacy policy, migrate state, change Git, commit or open a PR.
    ```

## Validate configuration {#config-validation}

After editing, run [canonical validation and health](index.md#config-validation).
They check the contract but do not prove commands work in clean-room, an image is ready,
a bundle is available or a package fits the model's real window. Run those checks separately
on a suitable candidate; a saved passing run for another SHA does not replace new QA.
