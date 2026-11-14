# Architect — Architect

## Interactive skill architect { #architect_1 }

Source: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/architect/SKILL.md).
It ships in `engineering-suite`, runs manually as `/architect`, and returns a decision brief in the chat:
the current boundary, the options, the recommendation, the trade-offs, the risks, the acceptance criteria,
and the first TDD seams.
The skill studies the evidence and does not change production code, tests, configuration, or repository files.
The brief does not authorize implementation, commit, push, or PR creation. If the developer wants a
durable ADR, the accepted decision goes through `domain-modeling`.

Before it compares the options, with memory enabled, it runs
`harness memory search . "<decision, boundary, and module>"` once. It interprets the search status and the source status
according to the [shared contract](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/instructions/project-memory.md), which also defines
the installed entry point for a project without an external CLI. The returned pointers
give candidates for precedents; `historical`, `unknown`, and unconfirmed sources require
verification, and superseded sources are excluded. It opens a source only when it helps distinguish an option, and checks its hash
and the applicability to the current requirements. When memory is unavailable, it works with the current repository evidence.

## The `architect` orchestration role

The interactive skill and the coordinator's `architect` role are separate. The role uses its own manifest and Context Package. The interactive skill does not extend its
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

Prescribe the shape of the change, not only its behaviour, and prefer an idiom that keeps the diff reviewable. Boilerplate repeated at every call site adds a nesting level in Python, so `git diff` records every line of every touched block as removed and re-added: a mechanical change can then exceed the batch's own line budget, while a centralised context manager or decorator expresses the same guarantee within it. When a brief rules such an idiom out, say why in the brief, so the developer escalates instead of discovering the cost after the fact.

The result is one short architecture decision brief: the boundaries, the viable options, the chosen option, the trade-offs, the risks, the acceptance criteria, and the first TDD seams. Its proof is the targeted evidence from the repository and the requirements, sufficient for the coordinator to make the decision; an ADR is required only for a significant irreversible trade-off. The completion report refers to this brief and does not repeat its narrative.

Propose the commit plan in the report field `commit_plan` as ordered entries `{id, summary, expected_paths, covers}`, one entry per independently reviewable commit. `covers` lists the Definition of Done item numbers (counted from one) that the entry implements, and every item is covered at least once. Every `expected_paths` entry lies inside the brief's `allowed_paths`: a path the plan needs beyond them is a risk in `risks`, not a plan entry. `report submit` refuses a plan that breaks these rules and names the reason. The coordinator's default plan is one entry per item. When the proposed plan differs from it, set `risks.status: present` and describe the difference in `risks.details`: the report then waits for a manual accept. An accept, manual or by `batch auto-decide` under `approval_policy: auto`, pins the reported plan without a plan file.

Escalate a blocker naming the missing ADR or precedent card when the Context Package lacks one the decision needs; do not reconstruct it by reading the whole repository.

Run only the checks that distinguish the architectural decision. The architect must not run the full batch verification set just to establish a baseline: that proof belongs to the developer and the independent QA gates. Escalate if a broad baseline is the only way to establish a material premise. The architect brief therefore approves no verification commands: report `checks_run` as an empty list and name each decision-specific check with its result in `output`.

When part of the brief stays undone, list each undone item in `incomplete_items` under the common contract. Its `target_role` is `architect` (a narrowed architect retry), `developer`, `code-review`, or `qa`. A narrowed architect retry decides only the carried items; it repeats the commit plan only when an item changes that plan.

</div>

## 3. Contracts

- **Input (Input/Brief):** the immutable coordinator brief: the ticket, the explicit allowed paths, the acceptance criteria, the prohibitions, the issue branch, the worktree, and the required verification commands.
- **Process (Process):** select only the evidence that distinguishes the options; prepare the decision brief and the commit plan; escalate an irreducible uncertainty or the need for a broad baseline check.
- **Output (Output/Report):** the decision brief, `commit_plan`, and the completion report that refers to the brief; `changed files: none`, `commit SHA: not applicable — read-only role`, an empty `checks_run`.

## Source

[architect.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/architect.md)
