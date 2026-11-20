# Skills

The capability (a named composition in `harness/CAPABILITIES.json`) defines the set of skills. Some upstream skills are overridden for this workflow, some
are added as first-party, and the rest ship as they are. An override is a deliberate edit
on top of upstream, not local drift: in a comparison with the locked snapshot such skills show up as
changed, and this is expected.

## Project overrides

| Skill | What is changed |
| --- | --- |
| `triage` | A namespaced taxonomy of state labels, separate execution-mode and route (`pipeline::*`) axes instead of the upstream names; the outcome follows the grilling verdict. |
| `to-spec` | Converts grilling decisions and approved Discovery Context into a local technical specification. |
| `to-tickets` | Splits an approved specification into verifiable tickets with waves and a traceability matrix, links them to the epic, and does not rewrite its decisions. With `--review <epic>`, rechecks the published tickets against the epic criteria without writing. |
| `implement` | Gates with approval, separate roles, mandatory review and QA checks, an issue branch from the integration branch, an early blocker report, and a recovery route. |
| `ask-matt` | Takes the developer's choice into account: a two-axis review, or a move to commit and push. Its precondition is `harness update` and `/setup-labels`, not the upstream label setup. |
| `code-review` | Outputs the report in the language from the project configuration; the Standards axis carries the code-smell baseline, the Spec axis takes the ticket and epic bounds and reports a status for each acceptance criterion. |
| `diagnosing-bugs` | Before hypotheses, looks for past fixes through a read-only search of the project memory, if memory is enabled; reproduction stays mandatory. |
| `tdd` | Adds refactoring after a green test and verifiable test rules: one behavior at an agreed seam, an independent expectation, deterministic clocks and RNG, the same DBMS for SQL. |
| `grilling` | When memory is enabled, looks for precedents before the first design round; pointers do not replace explicit consent to an artifact. |
| `grill-me` | A thin wrapper over the project version: the `/grilling` interview and approved Discovery Context, without editing `CONTEXT.md` or ADRs. |
| `grill-with-docs` | The same wrapper plus maintenance of the glossary and architectural decisions. |
| `wayfinder` | Map tickets carry the execution mode and state; taking a ticket puts it into progress. |
| `setup-matt-pocock-skills` | Records the tracker in `.harness/project.json` and keeps the guides that `harness update` installs in `.harness/instructions/`; `/setup-labels` creates the labels. |

## Engineering

| Skill | Manual only | Description |
| --- | --- | --- |
| `ask-matt` | yes | Router: which skill or flow fits the situation. |
| `grill-with-docs` | yes | An interview that takes the existing code into account; maintains the glossary and architectural decisions in parallel. |
| `triage` | yes | An issue or PR through the triage state machine: category, check, brief. |
| `improve-codebase-architecture` | yes | Looks for opportunities to deepen modules, shows a report, then a grilling on the chosen one. |
| `setup-matt-pocock-skills` | yes | One-time setup of the tracker, the label taxonomy, and the layout of domain documents. |
| `tdd` | no | The red → green → refactor cycle. |
| `to-spec` | yes | Write a verifiable specification after approval. |
| `to-tickets` | yes | Decomposition of an approved specification into vertical slices with blocking links. |
| `wayfinder` | yes | A decision map for work that does not fit into one session. |
| `implement` | yes | A pipeline with roles and gates. |
| `prototype` | no | A throwaway prototype for a design question. |
| `research` | no | Research from primary sources; the result is a file in the repository. |
| `domain-modeling` | no | The domain model: glossary and architectural decisions. |
| `codebase-design` | no | A vocabulary of "deep" modules: interface, seam, adapter, testability. |
| `code-review` | no | A two-axis review: Standards and Spec. |
| `resolving-merge-conflicts` | no | Resolving a conflict during a merge or rebase. |
| `wizard` | no | An interactive bash wizard for steps that only a human can perform. |
| `diagnosing-bugs` | no | A diagnosis loop for hard defects and performance degradations. |

## Productivity

| Skill | Manual only | Description |
| --- | --- | --- |
| `grill-me` | yes | Stress-testing a plan and collecting Discovery Context; reads domain docs only. |
| `grilling` | no | A stress test of a plan, decision, or idea. |
| `handoff` | yes | Handing over context to another session or model. |
| `teach` | yes | Explain a new concept in the context of this project. |
| `to-questionnaire` | yes | Turn an unresolved question into a questionnaire for another person. |
| `wait-what` | yes | Restating the agent's last answer in different words. |
| `writing-for-agents` | no | Documents for agents: skills and project instructions. |

"Manual only" means that the skill is invoked as a command and the model does not pick it on its own.

## Project additions

These skills were added specially for this build — they do not exist upstream.

### Project skills (first-party)

| Skill | Description |
| --- | --- |
| `qa-gate` (skill) | A full local quality run from `qa_gate_commands` in an isolated fork before a PR. |
| `to-guide` (skill) | A guide with prompts for manually implementing a `hitl` ticket. |
| `setup-labels` (skill) | One-time creation and update of tracker labels from the project vocabulary. |
| `to-pull-requests` (skill) | The manual publication and completion path: branch check, PR/MR body, ticket closure; with `--release <epic>`, the release PR of the integration branch and the epic closure. |
| `fast-implement` (skill) | A single-pass path without gates for small tasks. |
| `delivery-stats` (skill) | A cost report for a closed epic: tokens, cache, code volume, comparison with the baseline. |
| `architect` (skill) | Manual comparison of architectural options; when memory is enabled, looks for precedents. |
| `developer` (skill) | Implements an agreed change in the issue branch and reports changes, checks, unverified items, risks and blockers. |
| `publish-epic` (skill) | Publishes an approved specification as the epic with its labels and creates the integration branch with the grill docs. |
| `pr-composer` (subagent) | Fills in the PR body from the project template and returns the path to the file. |

`pr-composer` ships as a subagent, not as a skill: a session or another skill calls it, and the model
does not pick it on its own.

## Related pages

- [“/implement”](../guides/implement.md)
- [“/fast-implement”](../guides/fast-implement.md)
- [CLI](cli.md)
