# Verification: recheck the candidate

Source: [role manifest](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/verification.md) and [shared contract](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## Role manifest

```yaml
name: verification
mode: read-only
required_capabilities:
  - backend-development
risk_triggers:
  - verification-infrastructure
```

Use this role only after a developer report was blocked for an operational reason
(`verification-infrastructure`, `transport`, or `context-pressure`) while its candidate commit is
already present and unchanged. Re-run the approved verification commands against the immutable
pinned candidate. Do not edit source, tests, fixtures, or Git state.

Its successful report makes the registered candidate eligible for the ordinary risk assessment;
it never accepts the candidate, bypasses review or QA, or changes any prior evidence.

When part of the brief stays undone, list each undone item in `incomplete_items` under the common
contract. Its `target_role` is `verification` (a narrowed verification retry on the same pinned
candidate), `code-review` or `qa`. A narrowed verification retry still re-runs every approved
verification command.

## When to use

An operational failure prevented checks of an existing candidate. If new code is needed, the coordinator routes work back to developer.
