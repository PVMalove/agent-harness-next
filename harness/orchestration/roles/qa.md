---
name: qa
mode: read-only
required_capabilities:
  - independent-verification
---

# QA

Use this role when an independent verification is required. No worker session receives it: the
coordinator runs QA through `qa run`, and the clean-room QA runner executes the brief's
`verification_commands` on the exact candidate and writes the report itself. The worker adapter
refuses a QA brief, and `report submit` refuses a QA report written by hand.

The report lists every approved command in `checks_run`; a command the run never reached is
`not_run`. A failed command routes a developer retry. QA never changes production code or authors
the tests and fixtures that prove the change.
