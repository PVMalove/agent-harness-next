# Map of agents and guides

Harness Next operational guides and Russian descriptions of the project agents. The guides,
except `releases.md`, match the templates in `harness/project/docs-agents/`, and `harness init`
deploys these templates to `docs/agents/` of the target project. They are documents for agent work.
This overview and the agent descriptions do not reach the target project. The public guides on
workflow and the CLI ([guides](../guides/workflow.md),
[CLI reference](../reference/cli.md)) and the backend orchestration guide
([`backend-orchestration.md`](../backend-orchestration.md)) are meant for the developer.

## Subagents

Project subagents from `harness/project/agents/`. Each description contains the name and
localization, the full manifest, the contracts, and the diagram.

| Agent | Purpose |
| --- | --- |
| [code-review-standards](code-review-standards.md) | The Standards axis of the `code-review` skill: compliance with repository standards and Fowler smells. |
| [code-review-spec](code-review-spec.md) | The Spec axis of the `code-review` skill: completeness of the implementation and scope creep. |
| [pr-composer](pr-composer.md) | Fills in the PR body from the project template and returns the file path. |
| [test-author](test-author.md) | Writes one behavior Red test in the protected test zone and runs it through the isolated runner. |

## Process and Git

| Document | Contents |
| --- | --- |
| [git-workflow](git-workflow.md) | Branches, commits, PRs, and ticket closure. |
| [issue-tracker](issue-tracker.md) | Working with the issue tracker. |
| [triage-labels](triage-labels.md) | Triage labels and their colors. |
| [worktrees](worktrees.md) | Parallel work in Git worktrees. |

## Artifacts and releases

| Document | Contents |
| --- | --- |
| [artifacts](artifacts.md) | Temporary artifacts and where to put them. |
| [releases](releases.md) | Version release and GitHub Release. |

## Acceptance

| Document | Contents |
| --- | --- |
| [console-web-home-checklist](console-web-home-checklist.md) | Manual acceptance of the Home page of the web console SPA. |

## Related documents

- Skills and pipeline roles: [skills map](../skills/index.md)
- Hooks: [hooks map](../hooks/index.md)
