# project.json

`.harness/project.json` defines project conventions: report language, branches, QA commands,
tracker, test write zone, hook policy, and local memory. It does not replace
[`orchestration.json`](orchestration/index.md), which describes roles and task execution.

## Configure project.json with an agent {#agent-setup}

??? quote ah-skill-text "Agent prompt: basic fields and branches"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Configure only language, base_branch and branch_pattern from the installed schema.
    Read actual branch/CI conventions; ask for unresolved choices. Preserve the repository layout
    and existing branch policy. Do not create or switch branches as part of editing metadata.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: QA gate and shell"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Find real lint/build/test commands in manifests and CI. Ask which belong in qa_gate_commands
    and which shell is intended, including native Windows behavior. Do not invent a make target.
    Explain that configuration validation does not execute those checks; ask before actual QA.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: tracker and CI"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Derive tracker type/host/project from repository evidence, then ask about unresolved choices.
    Agree on ci_required_checks from actual workflow/check names, not guessed labels.
    Never request tokens; online checks/login/permission changes need separate authorization.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: tests and test-author"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether test-author is wanted. Read its dedicated guide before proposing test_paths,
    test_runner command/build/database or the optional short-route test_author profile.
    Use existing literal test directories and one separate {test_id} argument. Distinguish approved
    developer inheritance from the explicit short profile. Do not promise unsupported runtimes.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: hook policy"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read current hook_policy and installed profile rules. Ask about required warnings/escalation
    paths while preserving critical guards and user hooks. Never lower protection to hide failures.
    Explain how supported hook updates preserve managed fingerprints; do not hand-edit generated policy.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Agent prompt: story points and memory"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask separately whether story_points routing and memory/memory_policy are needed.
    Use only supported thresholds, runtime/model choices and allowlisted source types/paths.
    Explain retrieval limits and redaction before opting in; do not index private material by default.
    Preserve unresolved decisions instead of filling every optional field.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Location and creation

The file is created from a template during `harness init`, `adopt`, or `update` for a build that
includes project settings (`engineering-suite` and its extension `backend-orchestration`), if
the file does not already exist. The project maintains the values afterward. The installer also
provides `.harness/project.schema.json`; the editor reference is `"$schema": "./project.schema.json"`.

If the file is absent, `harness health` does not report a missing-file error. If present,
it must be a JSON object with required fields `language`, `base_branch`, `branch_pattern`, and
`qa_gate_commands`. Unknown keys are forbidden, including in nested objects.

## Reading this reference

Tables have two columns: the field and its contract — type, constraints, effect, and an example
where useful. A path such as `test_runner.database.ready_command` names a nested field; `[]`
denotes an array element.

The schema declares no `default` values. Values in the complete example and installer template
are chosen settings, not universal defaults. Behavior when optional fields are absent is
described separately.

## Top-level fields

| Field | Contract |
| --- | --- |
| `$schema` | Optional editor reference string, usually `./project.schema.json`. Harness code does not read this field. |
| `language` | Required string: `ru` or `en`. Language of code-review reports and the PR body template. |
| `base_branch` | Required non-empty string. Project release/base branch: `/to-spec` creates an epic's integration branch from it; without an epic, it is the fallback base. Example: `main`. |
| `branch_pattern` | Required non-empty string containing a valid regular expression for issue branch names. Enforced by branch hooks. Example: `^feature/issue-[0-9]+-.+`. |
| `qa_gate_commands` | Required array of strings; the schema requires each string to be non-empty. QA gate runs commands in order. An empty array is valid configuration, but qa-gate stops and asks you to supply checks. |
| `shell` | Optional string: `bash` or `powershell`. If absent, qa-gate uses `bash`. |
| `tracker` | Optional explicit tracker selection object. Requires `tracker.type`; GitHub/GitLab also require host and project. |
| `ci_required_checks` | Optional array of unique non-empty CI check names. All must pass to accept CI evidence through `integration collect-ci`. An empty or missing list keeps local QA as the fallback. |
| `test_paths` | Optional non-empty array of unique relative globs without `..` segments. The test-author write zone; activation also requires a runner and successful preflight. |
| `test_runner` | Optional isolated single-test runner object. Requires `test_runner.command`; build and database are separate opt-ins. |
| `test_author` | Optional executor object for the short `/fast-implement` route: runtime, model, and effort are explicit. The full route uses the approved developer brief's selection. |
| `hook_policy` | Optional object with required profile and optional escalations. If the entire object is absent, the profile resolves to `standard`. |
| `story_points` | Optional scoring scale and routing thresholds object. All four nested fields are required when present. Without it, story-point routing is not configured. |
| `memory` | Optional object containing only the required `memory.enabled` field. Without the object, memory is off. |
| `memory_policy` | Optional object selecting sources, redaction rules, and the memory budget. All six fields are required when present. |

`shell: bash` runs each QA command through `bash -lc`; `shell: powershell` uses
`powershell -NoProfile -NonInteractive -Command`. Select the appropriate shell explicitly on
native Windows: `bash` on `PATH` can be the WSL launcher. The test runner command below remains
an argv without a shell, regardless of `shell`.

If `project.json` is entirely absent, branch hooks use their built-in pattern
`^feature/issue-[0-9]+-.+`. An empty `branch_pattern` in an existing file does not enable this fallback.

## Tracker: tracker

| Field | Contract |
| --- | --- |
| `tracker.type` | Required string within the object: `github`, `gitlab`, or `local`. `local` selects the markdown tracker without online checks. |
| `tracker.host` | String required for `github` and `gitlab`: hostname with an optional port. No URL scheme, path, or userinfo. Example: `gitlab.example.test:4443`. |
| `tracker.project` | String required for `github` and `gitlab`: full path with at least two segments, without a leading or trailing `/`. Segments allow ASCII letters, digits, `_`, `.`, and `-`. Example: `group/sub/project`. |

A valid explicit `tracker` determines the tracker used by health. Without the object, the tracker
is derived from `origin`, and health warns with suggested configuration. Certificates, proxies,
and credentials stay in the tracker CLI's personal settings.

## Test write zone and runner

`test_paths` accepts, for example, `tests/**`. Activating test-author requires more: the isolated
runner accepts only existing `<directory>/**` zones with literal segments, no symlinks, no
overlapping nested zones, and no forbidden service directories. A glob such as `tests/*.py` can
pass configuration health but receive `write_zone_rejected` in preflight. See the
[test-author guide](../../agents/test-author.md) for the complete conditions.

| Field | Contract |
| --- | --- |
| `test_runner.command` | Array of at least two non-empty strings: program and arguments. Exactly one element equals `{test_id}`, and it is not the first. The runner replaces it with the selected ID as one argument; no shell expansion occurs. Example: `["python3", "-m", "unittest", "{test_id}"]`. |

Without `test_paths` or `test_runner`, test-author is not activated; the absence of these optional
fields does not itself invalidate the config. Successful health does not replace isolation preflight.

### Build before a test: test_runner.build

Both fields are required inside this optional object:

| Field | Contract |
| --- | --- |
| `test_runner.build.command` | Non-empty argv of non-empty strings, without NUL or `{test_id}` even within an argument. Builds without a shell inside the sandbox. |
| `test_runner.build.artifact_paths` | Non-empty array of unique relative `<directory>/**` paths. Segments before the final `/**` are literal: no glob metacharacters, `.`/`..`, backslashes, or control characters. |

Artifact directories must already exist and be empty. The runner mounts fresh run-owned backing
directories: writable during the build, read-only during the test. Sources and the test write
zone are read-only during the build. The runner rejects non-empty directories rather than cleaning them.

### Test database: test_runner.database

All four fields are required inside this optional object:

| Field | Contract |
| --- | --- |
| `test_runner.database.engine` | String matching `[a-z][a-z0-9_-]{0,63}`: the production engine name. This is an identifier, not a closed enum of database names. |
| `test_runner.database.test_ids` | Non-empty array of unique non-empty `fnmatchcase` selectors without NUL; whitespace-only strings are invalid. Only matching tests receive the database. |
| `test_runner.database.command` | Non-empty argv of non-empty strings, without NUL or `{test_id}`. Starts a foreground server inside the sandbox. |
| `test_runner.database.ready_command` | Non-empty argv with the same constraints; checks the private database's readiness before the test. |

The server and readiness check receive `HARNESS_TEST_DATABASE_DIR` and
`HARNESS_TEST_DATABASE_SOCKET_DIR`. A project wrapper reads them; no shell expansion occurs in
argv. See [build and test database](../../hooks/run-test.md) for details.

## Short-route executor: test_author

All three fields are required inside the object; there is no implicit runtime, model, or effort.

| Field | Contract |
| --- | --- |
| `test_author.runtime` | String matching `[A-Za-z0-9][A-Za-z0-9_-]*`. Selected runtime ID; an unavailable protected adapter causes a refusal rather than a fallback to another CLI. |
| `test_author.model` | String matching `[A-Za-z0-9][A-Za-z0-9._:-]*`. Explicit CLI model ID or alias without spaces. |
| `test_author.effort` | String: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, or `ultra`. A contract-accepted value does not itself prove support by the selected CLI. |

The short `/fast-implement` route reads this profile. Full `/implement` inherits
`resolved_runtime`, `resolved_model`, and `resolved_effort` from the approved developer brief;
an invalid brief does not fall back to the project profile. The example below is an explicit
choice, not a model recommendation or defaults. Do not put secrets in the profile.

## Hook policy: hook_policy

| Field | Contract |
| --- | --- |
| `hook_policy.profile` | Required string within the object: `minimal`, `standard`, or `strict`. The base hook profile. |
| `hook_policy.escalations[].paths` | Non-empty array of unique relative globs without `..`. A matching touched path activates escalation; `*` and `?` can cross `/` under fnmatch semantics. |
| `hook_policy.escalations[].roles` | Non-empty array of unique roles: `developer`, `review`, `qa`, `coordinator`. Restricts escalation to these roles. |
| `hook_policy.escalations[].profile` | Required string for each escalation: `minimal`, `standard`, or `strict`. Cannot be weaker than the base profile; health checks this additional rule. |

Each escalation sets `paths`, `roles`, or both. The coordinator requires all specified conditions
to match and selects the strictest applicable profile. When forming advisory responses, hooks use
the strictest profile among the base and all escalations. Critical guards remain active in every
profile, including `minimal`. Neither the `HOOK_PROFILE` variable
nor tool parameters override this object; the `protect-hook-policy` hook prevents agent tools
from changing it. The project owner edits the policy. See
[hook installation and update](../../hooks/install-and-update.md).

## Task scoring: story_points

All fields are required when the object is present. It is available without the
`backend-orchestration` capability.

| Field | Contract |
| --- | --- |
| `story_points.scale` | Non-empty array of integers from 1. The scale for to-tickets; the template uses `[1, 2, 3, 5, 8, 13, 21]`. The validator does not require a strict Fibonacci sequence. |
| `story_points.fast_threshold` | Integer. Scores at or below this threshold suggest `pipeline::fast`; the template uses `3`. |
| `story_points.full_threshold` | Integer. Scores at or above this threshold suggest `pipeline::full`; the template uses `5`. |
| `story_points.gray_zone` | Integer for a second advisory scoring pass between the thresholds; the template uses `4`. |

Keep the scale and threshold ordering consistent yourself: the current schema and validator
check these numeric types but do not prove routing consistency.

## Local memory: memory and memory_policy

| Field | Contract |
| --- | --- |
| `memory.enabled` | Boolean: `true` or `false`. Enables memory; without the `memory` object, it resolves to `false`. `true` alone is insufficient without allowed sources and paths. |
| `memory_policy.source_types` | Array of strings: `adr`, `glossary`, `task_archive`, `qa_finding`, `completion_report`, `ledger`. An empty list permits no sources. |
| `memory_policy.allow_paths` | Array of non-empty relative POSIX patterns. No absolute paths, `:`, backslashes, empty segments, `.`/`..`, or trailing `/`. An empty list permits no paths. |
| `memory_policy.redact_rules` | Array of valid regular expressions, each 1–512 characters long. May be empty. |
| `memory_policy.min_similarity` | Finite number from 0 to 1. Reserved for cosine-vector search; currently does not filter FTS5 ranks. |
| `memory_policy.top_k` | Integer from 1: maximum number of returned memory pointers. |
| `memory_policy.max_tokens` | Integer from 1: memory budget in tokens. |

If the entire `memory_policy` object is absent, the parser uses empty `source_types`, `allow_paths`,
and `redact_rules`, `min_similarity: 0`, `top_k: 5`, and `max_tokens: 1000`. This is parser behavior,
not schema `default` values. If the object is present, all six fields are required. Memory is active
only with `memory.enabled: true` and non-empty `source_types` and `allow_paths` lists.

## Complete example

This complete example uses Russian report language, a local tracker, and a unittest runner.
It omits optional build/database settings and does not guarantee test-author readiness: the
`tests` directory must exist, and preflight must confirm the adapter and isolation. Replace the
branch, commands, and executor profile with your project's settings.

```json {.ah-code-wrap}
{
  "$schema": "./project.schema.json",
  "language": "ru",
  "base_branch": "main",
  "branch_pattern": "^feature/issue-[0-9]+-.+",
  "qa_gate_commands": ["python3 -m unittest discover"],
  "shell": "bash",
  "tracker": {"type": "local"},
  "ci_required_checks": [],
  "test_paths": ["tests/**"],
  "test_runner": {
    "command": ["python3", "-m", "unittest", "{test_id}"]
  },
  "test_author": {
    "runtime": "claude",
    "model": "sonnet",
    "effort": "high"
  },
  "hook_policy": {"profile": "standard"},
  "story_points": {
    "scale": [1, 2, 3, 5, 8, 13, 21],
    "fast_threshold": 3,
    "full_threshold": 5,
    "gray_zone": 4
  },
  "memory": {"enabled": false},
  "memory_policy": {
    "source_types": [],
    "allow_paths": [],
    "redact_rules": [],
    "min_similarity": 0,
    "top_k": 5,
    "max_tokens": 1000
  }
}
```

## Validation

After editing, run this from the project directory with the CLI installed:

```bash {.ah-code-wrap}
harness health .
harness health . --json
```

From the harness source checkout, use `python3 harness/bin/harness.py health <repo>`.
Without `--fix`, the command makes no repairs. `files.project_json` reports structural and
business-rule errors; JSON mode prints a machine-readable report. If the report contains `fail`,
the command exits with code 1. Fix the named field and repeat the check; do not substitute an
empty QA command list for passing checks. Test-author also needs the preflight from its role guide.

The schema supports the editor and console wizard; health adds business rules such as exactly
one `{test_id}` and no hook-profile downgrade.

## Next

- [All project settings](index.md)
- [Test-author settings](test-author.md)
- [Test-author guide](../../agents/test-author.md)
- [Backend orchestration](../../backend-orchestration.md)
