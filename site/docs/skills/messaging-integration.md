# Messaging Integration: интеграция сообщений

## 1. Название и локализация

- **English:** Messaging Integration
- **Русский (1:1):**

```text
Интеграция сообщений
```

## 2. Полное описание

Messaging Integration: write-роль для границ outbox, схемы и маршрутизации сообщений (message schema/routing), retry и dead-letter queue. Роль запускается, только если brief объявляет один из её риск-триггеров: `outbox`, `message-schema-routing` или `retry-dlq`. Несвязанные изменения сервиса роль не берёт.

Роль вносит совместимое изменение в allowed paths brief для messaging или инфраструктуры и прямо пишет, как оно влияет на доставку и обработку отказов. До handoff она запускает проверки контракта, маршрутизации и путей отказа, которых требует проект, и проходит обязательный risk review. Если scope неясен или не хватает доказательства, роль эскалирует вопрос и не расширяет scope.

## 3. Контракты

- **Вход (Input/Brief):** immutable brief с allowed paths сообщений, контрактом, правилами маршрутизации и retry/DLQ, DoD и required checks.
- **Выход (Output/Report):** commit SHA совместимого изменения; перечень файлов и проверок; последствия delivery/failure, риски, блокеры и следующий gate.

## Источник

[messaging-integration.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/messaging-integration.md)
