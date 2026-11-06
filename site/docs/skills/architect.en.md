# Architect — Architect

## Interactive skill architect { #architect_1 }

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/architect/SKILL.md).
It ships in `engineering-suite`, runs manually, and returns a decision brief in the chat:
the boundaries, the options, the recommendation, the trade-offs, the risks, the acceptance criteria,
and the first TDD seams.
The skill studies the evidence and does not change the repository files.

Before it compares the options, with memory enabled, it runs
`harness memory search . "<decision, boundary, and module>"`. It interprets the search status and the source status
according to the [shared contract](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/project-memory.md), which also defines
the installed entry point for a project without an external CLI. The returned pointers
give candidates for precedents; historical, unknown, and unconfirmed sources require
verification, and superseded sources are excluded. It opens a source only when necessary, checks the hash
and the applicability to the current requirements. When memory is unavailable, it works with the ordinary evidence.

## The `architect` orchestration role

This role uses its own manifest and Context Package. The interactive skill does not extend its
tool policy: a direct memory search call stays unavailable, and missing evidence is
escalated to the coordinator. The following contract applies to the role.

Source: [`harness/orchestration/roles/architect.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/architect.md) and the shared contract [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## 1. Name and localization

- **English name:** `Architect`
- **Russian translation:**

```text
Архитектор
```

## 2. Full translation of the role manifest

<div class="ah-skill-text" markdown="1">

```yaml
name: architect
mode: read-only
required_capabilities:
  - architecture-analysis
risk_triggers:
  - hard-to-reverse-decision
```

### Architect

Use this role before a significant boundary decision, especially when the decision is hard to reverse. It is read-only and does not change production code, tests, migrations, or configuration.

The result is one short architecture decision brief: the boundaries, the viable options, the chosen option, the trade-offs, the risks, the acceptance criteria, and the first TDD seams. Its proof is the targeted evidence from the repository and the requirements, sufficient for the coordinator to make the decision; an ADR is required only for a significant irreversible trade-off. The completion report refers to this brief and does not repeat its narrative.

Run only the checks that distinguish the architectural decision. The architect must not run the full batch verification set just to establish a baseline: that proof belongs to the developer and the independent QA gates. Escalate if a broad baseline is the only way to establish a material premise.

</div>

## 3. Contracts

- **Input (Input/Brief):** the immutable coordinator brief: the ticket, the explicit allowed paths, the acceptance criteria, the prohibitions, the issue branch, the worktree, and the required verification commands.
- **Process (Process):** select only the evidence that distinguishes the decision; prepare the decision brief; escalate an irreducible uncertainty or the need for a broad baseline check.
- **Output (Output/Report):** the decision brief and the completion report that refers to it; `changed files: none`, `commit SHA: not applicable — read-only role`.

## Source

[architect.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/architect.md)
