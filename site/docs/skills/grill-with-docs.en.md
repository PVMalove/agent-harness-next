# Grill With Docs — Grill with documents

## 1. Name and localization

- **English name:** `grill-with-docs`
- **Russian translation:**

```text
Прожарь с документами
```

## 2. Full translation of the skill text

<div class="ah-skill-text" markdown="1">

```yaml
name: grill-with-docs
description: "Runs /grilling with /domain-modeling: updates explicitly approved CONTEXT.md terms and considers ADRs for significant decisions. Use explicitly to also maintain domain docs; use /grill-me for Discovery Context only."
disable-model-invocation: true
```

Run `/grilling` with `/domain-modeling` for context selection, vocabulary, and document formats.
Before any glossary or ADR edit, read `/grilling`'s `references/domain-doc-writes.md`
(`../grilling/references/domain-doc-writes.md` from this skill) and follow it.

</div>

## 3. Contracts

- **Input (Input/Brief):** an idea, plan or decision in the working directory.
- **Output (Output/Report):** the refined plan and the updated ADRs/glossary when needed.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/grill-with-docs/SKILL.md)
