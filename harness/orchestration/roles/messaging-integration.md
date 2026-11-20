---
name: messaging-integration
mode: write
required_capabilities:
  - messaging-integration
risk_triggers:
  - outbox
  - message-schema-routing
  - retry-dlq
---

# Messaging integration

Use this role when the approved batch plan selects `--writer-role messaging-integration` for
outbox, message schema or routing, retry or dead-letter queue work. The brief pins the issue
worktree, start SHA, write scope and checks. Follow the report and retry contracts in `common.md`.

Its intended scope is those messaging boundaries only: the brief's allowed paths for messaging or
infrastructure, without unrelated service implementation. The output would be a compatible messaging
change with its delivery and failure-handling consequences, proved by the project's contract,
routing and failure-path checks.
