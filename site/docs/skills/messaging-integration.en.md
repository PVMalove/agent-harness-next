# Messaging Integration

## 1. Name and localization

- **English:** Messaging Integration
- **Russian (1:1):**

```text
Интеграция сообщений
```

## 2. Full description

Messaging Integration is a write role for outbox boundaries, message schema/routing, retry, and dead-letter queue. It starts only when the brief declares one of its risk triggers: `outbox`, `message-schema-routing`, or `retry-dlq`; it does not absorb unrelated service changes.

The role implements a compatible change inside the brief's allowed paths for messaging/infrastructure and describes the delivery and failure consequences explicitly. Before the handoff, it runs the project-required contract, routing, and failure-path checks, and the required risk review. Unclear scope or missing evidence means escalation, not a wider scope.

## 3. Contracts

- **Input (Input/Brief):** an immutable brief with the allowed messaging paths, the contract, the routing and retry/DLQ rules, the DoD, and the required checks.
- **Output (Output/Report):** the commit SHA of the compatible change; the list of files and checks; delivery/failure consequences, risks, blockers, and the next gate.

## Source

[messaging-integration.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/messaging-integration.md)
