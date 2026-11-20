---
name: database-migrations
mode: write
required_capabilities:
  - database-migrations
risk_triggers:
  - schema-change
  - data-migration
---

# Database migrations

Use this role when the approved batch plan selects `--writer-role database-migrations` for
schema or data migration work. The brief pins the issue worktree, start SHA, write scope and
verification commands. Follow the report and retry contracts in `common.md`.

Its intended scope is schema and data boundaries only: the brief's allowed paths for the database or
infrastructure, without unrelated service implementation. The output would be a migration change
with its rollout and rollback considerations, proved by the project's migration and compatibility
checks.
