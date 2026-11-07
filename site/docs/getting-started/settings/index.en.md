# Project settings

Two files in `.harness/` configure the project. `project.json` describes the project itself: language,
branches, QA gate commands, tracker, test zone, and memory. `orchestration.json` describes how the
coordinator and the runtime run roles, approval, and verification. The first file exists in every
project; the second appears with the `backend-orchestration` capability.

## The two files

| File | When it appears | Who writes it | Who reads it |
| --- | --- | --- | --- |
| `.harness/project.json` | `harness init`, `adopt`, or `update` when the file does not exist yet | the project after creation; the installer writes the file from a template | qa-gate, pr-composer, code-review, to-guide, test-author, and hooks |
| `.harness/orchestration.json` | installation of the `backend-orchestration` capability | the project; when absent it is copied from `.harness/orchestration.example.json` | the coordinator, `harness-runtime`, and the console setup wizard |

The installer does not overwrite existing values: `project.json` is created once, and
`orchestration.json` only when it is absent. `harness update` refreshes the managed
`.harness/orchestration.example.json`, but not the project config; overwriting the project file
requires an explicit `--force-seed-file`.

## Where the schemas live

- `.harness/project.schema.json` — the `project.json` schema; the file itself holds `"$schema": "./project.schema.json"`.
- `.harness/orchestration/orchestration.schema.json` — the `orchestration.json` schema; the file holds
  `"$schema": "./orchestration/orchestration.schema.json"`.
- `.harness/orchestration.example.json` — the managed example of a complete configuration; `harness diff`
  shows its drift.

Editors use the schemas for hints and checks. The schema and the `harness health` validator remain the
source of truth, not the example.

## How to edit safely

1. Edit the file with the Edit or Write tool, not with shell redirection or a heredoc. That keeps the
   change visible in the diff and does not bypass review.
2. Keep the JSON valid: UTF-8, no comments, no trailing commas, unique keys.
3. Change one logical group of fields at a time and verify the result before the next edit.
4. After an edit, run `python3 harness/bin/harness.py health <repo>` (or `harness health <repo>` when
   the CLI is installed). The check changes nothing; on `fail` it prints the cause and the fix command.
5. For `orchestration.json`, also run `config validate` (see below).
6. If a running runtime reads the configuration, restart `harness-runtime serve`: the process keeps
   the configuration in memory.

## Validating the configuration

```bash
python3 .harness/orchestration/coordinator.py --repo . config validate --json
python3 .harness/orchestration/coordinator.py --repo . config validate --canonical --json
python3 .harness/orchestration/coordinator.py --repo . config validate --fix --dry-run --json
```

| Command | What it does |
| --- | --- |
| `config validate --json` | Prints diagnostics: file, JSON pointer, code, allowed values, and the safe received value. Writes nothing. An invalid config exits with code 2. |
| `config validate --canonical --json` | Also rejects spelling that requires normalization, with the code `config-noncanonical`. |
| `config validate --fix --dry-run --json` | Shows the diff of safe enum normalization and does not write the file. |
| `config validate --fix --json` | Writes the normalization in a transaction with a backup copy. |

On load, the coordinator normalizes enum fields in memory only and warns about every correction; the
file does not change. IDs, models, paths, and commands are not normalized. A duplicate key, a secret,
and an ambiguous value are errors, not a reason to keep the last value. See the
[backend orchestration guide](../../backend-orchestration.md) for details.

## Pages in this section

- [project.json](project.md) — every field of `.harness/project.json`: language, branches, QA gate,
  tracker, test zone, hook policy, story points, memory.
- [orchestration.json](orchestration/index.md) — required fields, validation, and the map of the other pages.
- [Roles and transport](orchestration/roles.md) — provider profiles, assignment plans, communication
  languages, and tool policy.
- [Policies](orchestration/policies.md) — approval, retries, attention, session continuation,
  timeouts, and preflight.
- [Access and container](orchestration/access.md) — `access_policy`, `extensions`, and the link to the
  container executor.
- [Verification](orchestration/verification.md) — QA commands, verification profiles and plans,
  Repo Map, and Context Package.
- [Container executor](container.md) — host, images, network, token, checks, and common errors.
- [Test-author](test-author.md) — fields, activation conditions, refusal reasons, and the live check.

## Neighbouring guides

- [Backend orchestration](../../backend-orchestration.md) — launch, batch, approval, and recovery.
- [Project setup in the console](../../console-configuration.md) — the setup wizard and diagnostics.
- [Test-author: agent guide](../../agents/test-author.md) — the full role contract.
