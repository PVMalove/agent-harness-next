# Database Migrations — Database migrations

## 1. Name and localization

- **English:** Database Migrations
- **Russian (1:1):**

```text
Миграции базы данных
```

## 2. Full description

Database Migrations is a write role for schema and data boundaries only. It starts on the `schema-change` or `data-migration` risk trigger, works within the allowed paths of the brief for database/infrastructure, and does not take on unrelated service changes.

The role creates the migration and records the rollout and rollback conditions. Before the handoff it checks the migration and compatibility with the project commands and runs the required risk review. Irreversibility, incomplete rollback evidence, or an overlap of zones requires a coordinator decision.

## 3. Contracts

- **Input (Input/Brief):** an immutable brief with the schema/data change, the allowed paths, the compatibility strategy, the DoD, the prohibitions and the migration checks.
- **Output (Output/Report):** the migration commit SHA; changed files; the migration/compatibility check results; the rollout/rollback conditions, risks, blockers and the next gate.

## Source

[database-migrations.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/database-migrations.md)
