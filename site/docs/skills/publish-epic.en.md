# /publish-epic — Epic publication

Run `/publish-epic` explicitly (`$publish-epic` in Codex) after `/to-spec`, once the specification
is `Approved`. The skill publishes it as the epic and sets up the integration branch that
`/to-tickets` and the child tickets build on.

## Approval

Before any tracker or Git command, the skill shows a plan and waits for explicit approval:

- the epic title and the specification file that becomes its body;
- the labels `type::feature` or `type::bug`, `status::specs`, and `task-report::required` unless
  you ask to skip it;
- the `integration/<service-or-team>` branch, from the spec's `## Integration Branch` section or
  from explicit service or team naming;
- the grill docs (`CONTEXT.md`, `CONTEXT-MAP.md`, ADRs) changed by the current session or
  explicitly approved for the epic. Files with unrelated edits stay out of the commit.

## Output

The skill publishes the epic to GitHub, GitLab, or `.scratch/<feature-slug>/spec.md` of the local
tracker and renames the task folder after the epic number. It then creates the integration branch
from `base_branch`, commits the approved grill docs to it, and pushes it when the branch is absent
on the remote. It reuses an existing branch without a reset or force-push.

The grill docs are not always committed. When the branch already exists on the remote, the skill does
not commit to it or switch the worktree: the docs stay uncommitted, to be committed on the first child
ticket's issue branch and merged through its PR. With a local tracker, the skill commits the docs but
does not push. Without a remote, it only creates the local branch, and the docs stay uncommitted. On a
partial failure the
skill reports the state and the exact recovery action and never recreates the epic.

Finally, the skill offers to run `/to-tickets` manually. [Git and epic workflow](../agents/git-workflow.md)

[Source SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/publish-epic/SKILL.md)
