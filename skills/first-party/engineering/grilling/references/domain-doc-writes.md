# Glossary and ADR writes

These rules apply whenever `/grilling` runs with `/domain-modeling`. They take precedence over the
`/domain-modeling` rule to create or update files as soon as a term is resolved. The interview's
write gate still applies: nothing is written while a significant fork is unresolved.

- Use `CONTEXT-MAP.md` when present to identify the owning `CONTEXT.md`. Confirm the term, its
  definition, and its owning context with the user before writing. Create a missing glossary only
  for the first explicitly approved term, in its owning context when the parent is writable.
- Check permissions and Git status for the target immediately before editing. For a read-only file
  or a glossary with staged, unstaged, or untracked edits from outside this session, preserve the
  file and report the approved term and definition in chat. Preserve changes made since the previous
  check. Do not change permissions, stage, or overwrite existing work.
- Offer an ADR only if the accepted decision is hard to reverse, the rationale is not obvious, and
  the user chose between genuine alternatives. Wait for explicit approval to create the ADR.
  Put it in the owning context's `docs/adr/`, or in the root `docs/adr/` when the decision spans
  several contexts. Use the `/domain-modeling` ADR format. Keep a proposal in chat if the target is
  unavailable.
- In the final summary, name each edited glossary path and term, each proposed ADR, and each
  created ADR path. Mark any approved term that could not be written.
