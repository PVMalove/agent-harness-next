# Map of skills and roles

This directory is a short static memory of the harness. Each document records the localized name, triggers, responsibility, and the Input/Output contract; some pages also have an Archify PNG diagram. The detailed primary sources stay in `skills/first-party/engineering/`, `harness/orchestration/roles/`, `harness/orchestration/playbook.md`, and `harness/orchestration/pilot.md`.

## Command skills

- [ask-matt](ask-matt.md), [wayfinder](wayfinder.md), [triage](triage.md)
- [diagnosing-bugs](diagnosing-bugs.md), [tdd](tdd.md)
- [architect](architect.md#architect_1) — manual comparison of architectural options
- [grill-me](grill-me.md), [grilling](grilling.md), [grill-with-docs](grill-with-docs.md)
- [to-spec](to-spec.md), [to-tickets](to-tickets.md), [to-guide](to-guide.md)
- [implement](implement.md), [fast-implement](fast-implement.md), [code-review](code-review.md), [qa-gate](qa-gate.md), [to-pull-requests](to-pull-requests.md)
- [start-project](start-project.md), [integrate-project](integrate-project.md), [setup-labels](setup-labels.md), [delivery-stats](delivery-stats.md)

## Pipeline roles

- [Coordinator](coordinator.md), [Architect](architect.md), [Developer](developer.md)
- [Code Review](code-review-role.md), [QA](qa.md)
- [Messaging Integration](messaging-integration.md), [Database Migrations](database-migrations.md), [Conflict Resolver](conflict-resolver.md)
- [Playbook](playbook.md), [Pilot](pilot.md)

## Pinned upstream skills

The Russian descriptions of all 25 skills from `skills/vendor/mattpocock/` are in [vendor/](vendor/index.md).
Their original `SKILL.md` files are pinned in the upstream snapshot and are not edited by hand. First-party
overrides with matching names are described separately here, against the current `engineering-suite` version.

## Related documents

- Discovery Context (the list of paths that matter for the task) starts in `/grilling` through the
  opt-in `Live Artifact`, persisted in the spec's `artifacts/discovery-context.md`, and passes through
  the spec's `Relevant Files` and the ticket-specific Path inventory. The backend batch uses the LLM-free
  `Context Package` and checkpoint/continuation for the write role. The operating
  rules are collected in [backend-orchestration](../backend-orchestration.md); ADR 0003 describes the current
  design, and ADR 0005 describes the pipeline.
- Agents: [Agents](../agents/index.md)
- Hooks: [Hooks](../hooks/index.md)
- Diagrams of specific processes (`/implement`, `/to-spec`, `/wayfinder`, `/triage`, and others): [Diagrams](../diagrams/index.md)
