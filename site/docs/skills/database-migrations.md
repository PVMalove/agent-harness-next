# Database Migrations: миграции базы данных

## 1. Название и локализация

- **English:** Database Migrations
- **Русский (1:1):**

```text
Миграции базы данных
```

## 2. Полное описание

Database Migrations меняет только границы схемы и данных. Это write-роль. Координатор назначает её по риск-триггеру `schema-change` или `data-migration`. Роль пишет только в allowed paths brief для базы данных или инфраструктуры и не берёт на себя несвязанные изменения сервиса.

Роль создаёт миграцию и описывает условия rollout и rollback. Перед handoff она проверяет миграцию и совместимость командами проекта и проходит обязательный risk review. Необратимость, неполное доказательство rollback или пересечение зон требуют решения координатора.

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief с изменением схемы или данных, разрешёнными путями, стратегией совместимости, DoD, запретами и проверками миграции.
- **Выход (Output/Report):** commit SHA миграции; changed files; результаты проверок миграции и совместимости; условия rollout и rollback, риски, блокеры и следующий gate.

## Источник

[database-migrations.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/database-migrations.md)
