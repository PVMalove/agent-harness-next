# Agent prompt blocks

The web console's Task Board builds the "Agent prompt" of a ticket in the planner's `/to-guide`
format. Two of its blocks are fixed text: ARCHITECTURE INVARIANTS and IMPLEMENTATION DISCIPLINE.
For each block the board takes the first source that has it:

1. the epic's `## Architecture invariants` or `## Implementation discipline` section, which
   `/to-tickets` writes into the epic body;
2. the same `##` section of this file, the project-wide default.

The body of a section is copied verbatim up to the next `##` heading. An empty or missing section
leaves the block out. Text outside these two sections is ignored. Fill the sections below with
rules that hold for every epic of this project, or leave a section empty to have no default.

## Architecture invariants

- Target architecture only, no temporary Python rewrites. Rust native execution/process/OCI/durable SQLite WAL/verification runtime; Python skills/AI workflow/policy. One authoritative writer for each entity.
- Preserve prior approved plans, existing issue blockers, immutable evidence, security boundaries and branch history; no silent broad permissions or master commits.
- Linux Fedora + SELinux rootless Podman and Windows compatibility. Strict typed errors, idempotency keys and restart recovery.
- Developer tests: impact-scoped; after failure exact nodeids/--lf only; release needs independent full clean-room QA on final candidate SHA.

## Implementation discipline

Read approved ADR/spec and existing tests. Do not assume outdated implementation is present; fetch current file and branch. Describe ownership/interfaces before edits; TDD against public CLI/process seam, then production change. Run cargo fmt/clippy/test plus affected Python checks, capture executable evidence and real commit SHA. Only one complete final QA per candidate in normal path. Distinguish infra/test failures; no bypass, no force push. Independent Standards+Spec review and PR to approved integration branch. If a spec conflict exists, surface a concrete ADR choice rather than coding incompatible implementations.
