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

The coordinator has no dispatch route to this role yet (#1159): do not plan it. A ticket that needs
outbox, message schema or routing, retry or dead-letter queue work escalates to the coordinator.

Its intended scope is those messaging boundaries only: the brief's allowed paths for messaging or
infrastructure, without unrelated service implementation. The output would be a compatible messaging
change with its delivery and failure-handling consequences, proved by the project's contract,
routing and failure-path checks.
