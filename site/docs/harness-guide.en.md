# How Harness works

Harness installs skills, rules, hooks and documents for agent work into a project.
The CLI copies the chosen capability into the repository; the project then uses its own snapshot.
Updates are applied separately after reviewing changes.

This overview replaces the long document with a map. Detailed instructions live in topic chapters;
localized contracts belong in [Reference](reference/translations/index.md).

## What an installation contains

- **Skills** describe agent workflows and invocation conditions. The runtime discovers them through
  native project paths. A skill does not itself restrict process permissions.
- **Project rules** define branches, verification commands, tracker settings and other agreements.
  Engineering configuration lives in `.harness/project.json`.
- **Hooks** check tool events. Wiring depends on the runtime and trust in its settings;
  a hook entry in a file does not prove it actually ran.
- **Orchestration**, when selected, adds the coordinator, roles and checked transitions.
  `.harness/orchestration.json` defines policies and assignments.

`.harness/skills/` contains the installed set. `harness.lock` pins its contents;
`REGISTRY.md` helps locate a skill. `.claude/skills` and `.agents/skills` point to that set.
See [skill discovery](runtime-discovery.md) and [project structure](project/structure.md).

## Choose capabilities

| Capability | When to choose it |
| --- | --- |
| `project-foundation` | General skills for research, discussion, handoff and agent instructions |
| `mattpocock-suite` | The pinned upstream engineering and productivity collection |
| `engineering-suite` | Project rules, hooks and the engineering process with maintained overrides |
| `backend-orchestration` | Separate roles, approvals and independent verification; extends `engineering-suite` |

Without an explicit choice, the CLI uses `project-foundation`. Select the capability you need;
the CLI resolves its dependencies. Selection fields and prompts belong in [Quick start](getting-started/index.md).

## Install and maintain

1. Use [start-project](skills/start-project.md) for a new idea and
   [integrate-project](skills/integrate-project.md) for an existing project. The agent first inspects the task and asks questions.
2. Before writes, review the `init`, `adopt` or `update` command, target repository and capability.
3. Run `health` after installation. `--fix` and `--online` are separate actions.
4. Inspect `diff` before an update. Local managed-file edits require a separate decision.
5. Preview `cleanup` before removing temporary data. Deletion requires `--apply`.
   Full Harness removal uses the separate `uninstall` command, also with a preview.

Exact commands and conditions belong in the [CLI reference](reference/cli.md),
[update instructions](hooks/install-and-update.md) and [project settings](getting-started/settings/index.md).
Secret values do not belong in configuration or reports.

## Take a task through the workflow

The [workflow](guides/workflow.md) selects an entry point: exploring an idea, an approved specification
or an incoming ticket. `/fast-implement` handles a small `afk` ticket labeled `pipeline::fast`.
`/implement` uses `backend-orchestration` roles and gates. `/to-guide` prepares instructions
for a person implementing the task.

Development follows [TDD](guides/tdd.md), [review](guides/code-review.md) and [QA](guides/qa-gate.md)
under the chosen route. Opening a PR requires separate confirmation. A person performs the merge.
[Examples](guides/examples.md) show complete routes.

## Context and parallel work

A [worktree](concepts/worktrees.md) separates a task's branch and files. It does not isolate processes,
network access or credentials. Worker permissions are configured and checked separately.

[Session context](concepts/context.md) must be recorded in documents and the tracker so another session
can continue. In orchestration, a [Context Package](guides/orchestration/context.md) pins the role's
inputs. Repo Map provides a code map; optional project memory returns pointers to allowed sources.
Unavailable memory does not justify inventing past decisions.

## Find details

- [Labels](reference/labels.md) and [Git workflow](agents/git-workflow.md): task states, branches and PRs.
- [Hooks](reference/hooks.md): checks and reasons to stop.
- [Orchestration](backend-orchestration.md): roles, approvals, execution and recovery.
- [Architecture](architecture/overview.md): Python/Rust boundaries, state and execution.
- [Skill, hook and agent translations](reference/translations/index.md): individual contracts.

The original long [Harness reference](https://github.com/PVMalove/agent-harness-next/blob/0b4fccb8854c1aa7d6a9dc77369117acaa1e29be/docs/harness-guide.md)
records historical behavior. Capability names, commands and limits in this overview were checked
against the current worktree; the obsolete `pvmalove-suite` is replaced here with `engineering-suite`.
