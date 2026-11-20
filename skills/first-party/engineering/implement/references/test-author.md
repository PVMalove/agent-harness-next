# Test author in the full route

Read this before a developer dispatch when the project enables the test author. The route itself
(preflight, executor, brief permission, log root, in-process launcher and refusals) is owned by the
developer role: `.harness/orchestration/roles/references/developer-test-author.md`. The cycle is in
`../tdd/references/test-author.md`. This file covers only what the coordinator prepares.

- Install the project harness in the exact `send.worker_worktree` before dispatch, with
  `test_paths` and `test_runner` enabled there. Never copy the main checkout's runtime state or
  trust.
- Give the developer `Agent(test-author)` in `tool_policy.roles.developer`, or keep a project
  override that already allows it. Never widen the approved tools at launch.
- Point the worker prompt at the role reference above instead of restating the route. An
  unavailable author keeps ordinary TDD and never creates a blocker or changes the Rust ledger.
