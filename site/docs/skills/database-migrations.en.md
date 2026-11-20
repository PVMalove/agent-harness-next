# Database Migrations — Database migrations

## 1. Name and localization

- **English:** Database Migrations
- **Russian (1:1):**

```text
Миграции базы данных
```

## 2. Full description

Database Migrations is the write role for schema and data boundaries. The coordinator has no dispatch route to it yet (#1159): it is not planned, and a ticket that needs schema or data migration work escalates to the coordinator.

Its intended scope is the brief's allowed paths for the database or infrastructure, without unrelated service changes. Its output would be a migration with its rollout and rollback considerations, proved by the project's migration and compatibility checks.

## 3. Contracts

- **Input (Input/Brief):** an immutable brief with the schema/data change, the allowed paths, the compatibility strategy, the DoD, the prohibitions and the migration checks.
- **Output (Output/Report):** the migration commit SHA; changed files; the migration/compatibility check results; the rollout/rollback conditions, risks, blockers and the next gate.

## Source

[database-migrations.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/database-migrations.md)
