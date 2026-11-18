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
description: Stress-test an idea or plan with /domain-modeling. Update explicitly approved terms in CONTEXT.md and consider ADRs for significant decisions. Use /grill-me for interview and Discovery Context only.
disable-model-invocation: true
```

Run `/grilling` with `/domain-modeling` for context selection, vocabulary, and document formats.
Apply the interview's write gate before any edit.

- Use `CONTEXT-MAP.md` when present to identify the owning `CONTEXT.md`. Confirm the term, its
  definition, and its owning context with the user before writing. Create a missing glossary only
  for the first explicitly approved term, in its owning context when the parent is writable.
- Check permissions and Git status for the target immediately before editing. For a read-only file
  or a glossary with staged, unstaged, or untracked edits from outside this session, preserve the
  file and report the approved term and definition in chat. Preserve changes made since the previous
  check. Do not change permissions, stage, or overwrite existing work.
- Offer an ADR only if the accepted decision is hard to reverse, the rationale is not obvious, and
  the user chose between genuine alternatives. Wait for explicit approval to create the ADR.
  Use the owning context's ADR directory and the domain-modeling template. Keep a proposal in chat
  if the target is unavailable.
- In the final summary, name each edited glossary path and term, each proposed ADR, and each
  created ADR path. Mark any approved term that could not be written.

</div>

## 3. Contracts

- **Input (Input/Brief):** an idea, plan or decision in the working directory.
- **Output (Output/Report):** the refined plan and the updated ADRs/glossary when needed.

## Source

[SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/grill-with-docs/SKILL.md)
