# Grilling — Hard interview

## 1. Name and localization

- **English name:** `grilling`
- **Russian translation:**

```text
Жёсткое интервью
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: grilling
description: Relentlessly interview the user about a plan, decision, or idea to stress-test their thinking. Triggered when the user wants to validate a concept or uses "grill" trigger phrases.
```

**Objective:** interview the user relentlessly to dismantle assumptions, stress-test their logic, and build a robust shared understanding. Map the entire process as a **design tree**, where every decision branches into subsequent dependencies.

**Project memory (interactive sessions):** before the first design-tree round about code or
architecture, with memory enabled, run `harness memory search . "<goal, decision, and module>"`.
Without an external CLI, use the installed entry point from the shared contract.
Repeat the search only when the subject changes after a settled decision. The shared contract
`.harness/docs/project-memory.md` describes the main-checkout config, the search and source statuses,
the hash check, and how to continue the ordinary interview without available memory. The pointers are
candidate precedents: historical and unconfirmed sources are checked, superseded ones are excluded, and
a source is opened only when necessary. The opt-in Live Artifact stays. In an orchestration dispatch,
use the Context Package and escalate missing evidence instead of calling the search.

**Core mechanics:**
1. **Rounds and the frontier:** work through the tree in discrete rounds. The **frontier** consists of every decision whose prerequisites are currently settled.
   - Ask the current frontier in a single round, showing at most 4 questions; if the frontier is larger, carry the remaining questions into the next round.
   - Never ask downstream questions until their prerequisites are answered.
   - Always wait for the user's response before computing the next round.
2. **State tracking (the trunk):** at the start of each round, briefly summarize the decisions that have just been settled. This confirms alignment before pushing the frontier forward.
3. **Tone and persona:** act as a sharp, analytical, and relentless interrogator. Be respectful but ruthless in identifying blind spots, unstated assumptions, and logical leaps.

**Discovery Context (Live Artifact):** while you explore, keep a visible list of candidate paths
that relate to the current decisions. A path must not be added to the `Live Artifact` without the user's
explicit consent. At the start of each round, show the new candidates in one group and offer: "Add to
the Live Artifact? — Yes, all / Choose individually / No". If the runtime can publish artifacts, create
it at the first approved path and update that same artifact; otherwise warn once about the plain-text
fallback and keep the list in the Trunk summary. This bookkeeping does not spend the frontier's
four-question limit.

**Repo Map first:** when the session's topic touches code, run the map on demand, once,
immediately before the first search for candidate paths — not at session start:
`python .harness/repo_map/repo_map.py --repo . --commit "$(git rev-parse HEAD)"`. Then find paths with
targeted `rg` and reads. If the CLI is absent, skip the step. The map's output stays in this session: do
not send its signatures to an external or cheap advisory model.

**Question formats:**
- **Tool-based categorical questions:** if `AskUserQuestion` is available in this runtime, ask each round through it instead of plain text.
  - *Format:* one question per entry, so each gets its own tab with a short `header`, 2–4 mutually exclusive `options` (a `label` and a `description` of what the choice means). The user can still enter a free-form answer through the always-available "Other".
  - *Recommendation:* put the recommended option first and suffix its label with "(Recommended)".
  - *Constraints:* one call is limited to 4 questions; if the frontier is larger, show the first 4 now and carry the rest into the next round. Do not discard them silently and do not make additional calls for the same round.
- **Plain text and the open-ended alternative:** not every frontier question reduces to a handful of discrete options, and not every runtime has `AskUserQuestion`. At the start of the session, if the tool is unavailable, warn the user once and use plain text from then on. For a genuinely open-ended question (for example, "what should we call this concept?") where narrowing to 2–4 candidates would misrepresent the question, use plain text instead:

  ```
  🤔 **<Question title>**: <Question body: explain *why* this decision is critical now and briefly outline the trade-offs at play; this may be several paragraphs>

  🤖 **Recommendation:** <Your recommended answer or direction>
  ```

**Information gathering (facts and decisions):**
- Finding *facts* is your job; making *decisions* is the user's job.
- If a frontier question needs data from the environment (the file system, an API, and so on), dispatch a subagent or use tools to find it. Do not ask the user to do the lookup.
- *Non-blocking:* a running tool or exploration is just an unsettled prerequisite. Do not block the round on it: ask the rest of the current frontier immediately. Only the downstream questions wait for the tool's report.

**Termination:**
The session is done when the frontier is empty: every branch of the design tree is visited, and no silent assumptions remain. Conclude by synthesizing the final plan, then ask the user to confirm the plan:

- **Yes, go to `/to-spec`:** tell the user that the next step is to invoke `/to-spec` manually, then end the grilling session. This is the recommended option.
- **No, changes are needed:** ask the user to name the decision numbers that need changes, reopen only those branches, and continue grilling.

If `AskUserQuestion` is available, ask the final choice through it. Otherwise present the same two choices as plain text and wait. Do not invoke `/to-spec` yourself, and do not treat confirmation as authorization to create tickets, branches, or code.

</div>

## 3. Contracts

- **Input (Input/Brief):** an idea, a plan, or a decision; the available facts and the questions on the frontier.
- **Output (Output/Report):** the tree of settled decisions, the synthesis of the plan, and an explicit request for the next step.

## 4. Architecture diagram

![Discovery Pipeline: from a decision to a Context Package](../diagrams/previews/discovery-pipeline.workflow.png)

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/grilling/SKILL.md)
