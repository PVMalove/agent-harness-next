# Messaging Integration

## 1. Name and localization

- **English:** Messaging Integration
- **Russian (1:1):**

```text
Интеграция сообщений
```

## 2. Full description

Messaging Integration is the write role for outbox, message schema and routing, retry and dead-letter queue boundaries. The coordinator has no dispatch route to it yet (#1159): it is not planned, and a ticket that needs such work escalates to the coordinator.

Its intended scope is the brief's allowed paths for messaging or infrastructure, without unrelated service changes. Its output would be a compatible change with its delivery and failure-handling consequences, proved by the project's contract, routing and failure-path checks.

## 3. Contracts

- **Input (Input/Brief):** an immutable brief with the allowed messaging paths, the contract, the routing and retry/DLQ rules, the DoD, and the required checks.
- **Output (Output/Report):** the commit SHA of the compatible change; the list of files and checks; delivery/failure consequences, risks, blockers, and the next gate.

## Source

[messaging-integration.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/messaging-integration.md)
