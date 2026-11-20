# Pull requests in triage

A PR (a merge request on GitLab) runs through the same roles and states as an issue. These are its deltas; steps 1 and 3 of the triage process also read and verify the diff.

- **Resolve the reference.** Resolve a bare `#42` to an issue or PR per the tracker config.
- **Read the labels against the code.** `status::ready` + `afk` means a brief is attached and an agent should take the next step on the diff; `status::ready` + `hitl` means it's ready for the maintainer to review or merge.
- **Discovery.** In "Show what needs attention", include external PRs in the buckets and tag each line `[PR]` or `[issue]`. Discovery surfaces only *external* PRs (the tracker config defines who counts as external) — a collaborator's in-flight PR is not triage work. This filter is discovery-only; an explicitly named PR is always triaged regardless of author.
