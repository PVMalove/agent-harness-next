# Hooks and profiles

You can write some process rules in words, but words do not execute. Hooks turn such
rules into checks that fire before the action: the agent cannot "forget" the rule, because the
tool returns a refusal before the command runs.

## Why

**Forbidding dangerous operations.** A direct commit or push to a protected branch, a pull request merge, a
destructive history operation — all of these lead to a state that one command cannot roll back. A hook checks the command before
it runs and refuses.

**Protecting the process.** Publishing a PR without a passed QA makes the check worthless: the PR looks ready, but
in fact it was not verified. A hook does not let you open a PR until the quality run for the current tree passes.

**Protecting metadata.** Traces of an automated executor in the commit history and in the change description
stay forever and change the authorship of the work. A hook blocks them before publication.

## Three profiles

A profile sets the behavioral strictness: how many warnings, repeated checks, and refusals
the work gets.

- `minimal` — critical guards only. It suits quick edits in a personal project.
- `standard` — the default base mode: critical guards, a bounded run of checks, and
  reminders.
- `strict` — adds a repeated check of sensitive paths and a refusal at high-risk boundaries.

No profile weakens the critical guards, including `minimal`. Strictness changes the number of
hints and repeated checks, not whether a dangerous action is forbidden.

## The second runtime

Hooks ship for both supported runtimes from one set of scripts, and the critical guards
are equal in both. The second runtime sends file edits as a patch, so the guards are connected as a group
that covers both the patch and an ordinary write: the decision does not depend on which tool edited the file.

If the hooks of this runtime are unavailable, the runtime and coordinator process checks provide the critical protection,
and `harness health` reports this with a warning — so the absence of hooks is visible and
not masked.

## Policy as a contract

- The profile is read only from `.harness/project.json`. Environment variables and tool parameters
  do not change it.
- The agent cannot change the hook settings or the policy key: these edits are blocked in all
  profiles. A human changes the policy.
- You can raise the profile for individual paths and roles by escalation; you cannot lower it.
- The hook response is structured: an identifier, the profile, the decision `allow`/`warn`/`block`, a reason
  code, a ready recommendation, and a link to the evidence. A critical hook blocks on an internal error;
  a behavioral hook allows and writes diagnostics.

At approval, the policy digest is pinned. So a profile change does not pass unnoticed: the plan was
agreed under one policy, and execution runs under another, and this is visible before publication.

## Next

- [Hooks reference](../reference/hooks.md)
- [Architecture overview](../architecture/overview.md)
