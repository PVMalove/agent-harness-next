# Agent prompt blocks

The web console's Task Board builds the "Agent prompt" of a ticket in the planner's `/to-guide`
format. It takes the two fixed blocks below from this file: the body of each `##` section is copied
verbatim into the prompt. A missing file or section leaves the block out. Other text is ignored.

## Architecture invariants

- Target architecture only, no temporary Python rewrites. Rust native execution/process/OCI/durable SQLite WAL/verification runtime; Python skills/AI workflow/policy. One authoritative writer for each entity.
- Preserve prior approved plans, existing issue blockers, immutable evidence, security boundaries and branch history; no silent broad permissions or master commits.
- Linux Fedora + SELinux rootless Podman and Windows compatibility. Strict typed errors, idempotency keys and restart recovery.
- Developer tests: impact-scoped; after failure exact nodeids/--lf only; release needs independent full clean-room QA on final candidate SHA.

## Implementation discipline

Read approved ADR/spec and existing tests. Do not assume outdated implementation is present; fetch current file and branch. Describe ownership/interfaces before edits; TDD against public CLI/process seam, then production change. Run cargo fmt/clippy/test plus affected Python checks, capture executable evidence and real commit SHA. Only one complete final QA per candidate in normal path. Distinguish infra/test failures; no bypass, no force push. Independent Standards+Spec review and PR to approved integration branch. If a spec conflict exists, surface a concrete ADR choice rather than coding incompatible implementations.
