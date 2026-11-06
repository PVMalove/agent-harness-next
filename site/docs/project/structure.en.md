# Project structure

`harness init` leaves a verifiable snapshot in the project: the set of skills, hooks, and contracts
that the project lives with on its own. The source harness repository is not needed after the install — you can delete it, and
updates come with a separate command.

## Project tree

```text
<repo>/
├── .harness/            # managed snapshot: lock, skill registry, configuration
│   ├── docs/            # contracts for agents: technical-english and project-memory
│   ├── skills/          # installed skills
│   ├── project.json     # language, branches, checks, hooks, memory
│   └── orchestration/   # appears with the backend-orchestration capability
├── .agents/             # skills visible through native skill discovery
├── .claude/             # runtime rules, agents, hooks, and local settings
├── docs/
│   ├── agents/          # operational guides for agents
│   └── adr/             # architectural decisions of the project
├── AGENTS.md            # cross-runtime contract of the project
├── CLAUDE.md            # entry point for Claude Code
└── CONTEXT.md           # glossary of terms and the domain model
```

The installer manages the content of `.harness/`: edits to managed files show up in `diff` and are not
silently overwritten. Seed files, which the project edits for itself, are kept during an update
until you explicitly request their replacement.

## Contracts for agents

The project receives the operational guides
`docs/agents/{artifacts,git-workflow,issue-tracker,test-author,triage-labels,worktrees}.md`. These are
the documents an agent follows to do the work: branches and commits, tracker work, labels, temporary
artifacts, worktrees, and the test zone.

The release guide and the subagent descriptions stay in the source harness repository: in the target
project, they are either not needed or depend on its own rules.

## What is not installed

| What | Where it lives | Why |
| --- | --- | --- |
| Architectural decisions | Source harness repository | Contracts of the tool itself, not of the project |
| Specifications and task archives | Project tracker | The live source of truth is not copied |
| Diagrams | Source harness repository | Illustrations for the tool developer |
| Skill descriptions in Russian | Source harness repository | Documentation for humans, not an instruction for an agent |
| Developer guides | Source harness repository | The public versions live on this site |

## Snapshot and update

The install copies the snapshot and writes a lock with the hashes of the files that harness manages. After that,
`diff` shows the differences from the locked snapshot, and `update` pulls in the new capability version and
keeps local edits until you ask to overwrite them.

An installed project lives independently of the tool clone: the hashes in the lock describe exactly what is
installed, not what currently lies in the source repository.

## Next

- [CLI](../reference/cli.md)
- [Workflow](../guides/workflow.md)
- [Architecture overview](../architecture/overview.md)
