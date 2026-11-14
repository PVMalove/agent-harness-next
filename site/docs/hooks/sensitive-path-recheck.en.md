# sensitive-path-recheck.sh — recheck of a sensitive path

## 1. Name and localization

- **Source hook:** [`harness/project/hooks/sensitive-path-recheck.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/sensitive-path-recheck.sh)
  and the shared body [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Translation:** a warning about every new edit of a sensitive path with an evidence record.

## 2. Full description

An advisory hook `PreToolUse(Write|Edit)` of the `strict` profile from the matrix of ADR 0024, section 2a. It
warns about an edit of a sensitive path from ADR 0024, section 2. The set is defined by the fixed policy
constant `is_sensitive_path` in `harness/orchestration/hook_policy.py`; it has no configuration key. The set
contains:

- manifests and lock files by name at any depth: `pyproject.toml`, `uv.lock`, `poetry.lock`,
  `Pipfile`, `Pipfile.lock`, `setup.py`, `setup.cfg`, `requirements*.txt`, `constraints*.txt`,
  `package.json`, `package-lock.json`, `npm-shrinkwrap.json`, `yarn.lock`, `pnpm-lock.yaml`,
  `Cargo.toml`, `Cargo.lock`, `rust-toolchain`, `rust-toolchain.toml`, `go.mod`, `go.sum`, `Gemfile`,
  `Gemfile.lock`, `composer.json`, `composer.lock`;
- CI: `.github/*`;
- migrations, auth, and access rights: a path segment or a file stem, split by `.`, `_`, and `-`, contains
  a token from `migration`, `migrations`, `migrate`, `alembic`, `auth`, `authn`, `authz`, `oauth`,
  `oauth2`, `authentication`, `authorization`, `permission`, `permissions`, `acl`, `rbac`, and also the
  file `CODEOWNERS`. Tokens are compared, not substrings: `author.py` does not match `auth`;
- the hooks themselves: `.claude/settings*.json`, `.claude/hooks/*`, `.claude/agents/*`, `.codex/hooks.json`,
  `.codex/hooks/*`, `.codex/config.toml`;
- the project config `.harness/project.json`.

The hook keeps a copy of the set because it does not see the harness package; `tests/core/test_change_impact_hooks.py`
compares it with `is_sensitive_path`. The path is compared in the same way as in
[impact-first-touch.md](impact-first-touch.md): after `realpath` from the nearest directory with `.git`.

The model receives the text in `hookSpecificOutput.additionalContext` without `permissionDecision`; the hook
never blocks. An edit of `.claude/settings*.json`, `.claude/hooks/`, and `.harness/project.json` is
still blocked by the critical `protect-hook-policy`; this hook does not change the decision of the guard.

- **Profiles.** `minimal` and `standard` — the hook does not work (the body does not run). `strict` — `warn` with
  the code `sensitive-path-touched` and a mandatory `evidence_ref`.
- **Deduplication.** The subject of the notification is the path, `tool_name`, and `tool_input`: every new edit
  is checked again, and a repeat of the same edit in the same operation stays silent. A new operation (`session_id`
  or `agent_id`) gives a new notification.
- **Evidence.** The file `.harness/.sandboxes/hook-events/<operation_id>/n-<key>.json` contains `hook_id`,
  `event`, `path`, `subject_digest`, `operation_id`, `session_id`, `agent_id`, `profile`, and
  `recorded_at`; `evidence_ref` of the verdict is the path of this file from the project root.
- **Authoritative check.** The hook only warns. Under `strict`, the coordinator boundaries give the refusal:
  `dispatch propose` and `dispatch create` for code-review and QA, `qa run` and `dispatch publish` answer
  `strict_impact_unknown` until VerificationPlan proves the ImpactSet of the sensitive change
  (the section "Strict boundary" in [hook-response.md](hook-response.md)).
- **Remaining limitation.** A hardlink to a sensitive file bypasses only this warning:
  `realpath` does not resolve a hardlink. The critical `protect-hook-policy` and the diff check of
  the strict boundary, which sees the path from git, are authoritative.
- **Second runtime.** It is not connected until the `apply_patch` adapter; `harness health` names
  the check outside the hook — the strict boundary.

## 3. Contract

- **Input:** The JSON of the `PreToolUse` event in stdin, as in `impact-first-touch`; the profile is only
  `hook_policy` in `.harness/project.json`.
- **Output:** Code `0` always. A new edit of a sensitive path under `strict` — `additionalContext` in
  stdout, the first stderr line `[sensitive-path-touched] <text>`, the line `evidence_ref=<path>`, and
  the verdict `warn`. An internal error — `warn` `internal-error` with empty stdout.

## Source

[sensitive-path-recheck.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/sensitive-path-recheck.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py),
[hook_policy.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/hook_policy.py)
