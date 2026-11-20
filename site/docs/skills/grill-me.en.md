# Grill Me — Grill me

## 1. Name and localization

- **English name:** `grill-me`
- **Russian translation:**

```text
Прожарь меня
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: grill-me
description: Runs the /grilling interview to stress-test an idea or plan and collects approved Discovery Context without editing CONTEXT.md or ADRs. Use explicitly before /to-spec; use /grill-with-docs to also update domain docs.
disable-model-invocation: true
```

Run the `/grilling` interview and collect its approved Discovery Context when working in a repository.
Use existing domain docs as read-only evidence. Keep proposed terms and decisions in the chat summary.

</div>

## 3. Contracts

- **Input (Input/Brief):** a plan, decision or design that the interview must test.
- **Output (Output/Report):** accepted decisions, approved paths, open questions, and the next step.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/grill-me/SKILL.md)
