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

The coordinator has no dispatch route to this role yet (#1159): do not plan it. A ticket that needs
schema or data migration work escalates to the coordinator.

Its intended scope is schema and data boundaries only: the brief's allowed paths for the database or
infrastructure, without unrelated service implementation. The output would be a migration change
with its rollout and rollback considerations, proved by the project's migration and compatibility
checks.
