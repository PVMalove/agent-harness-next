# Messaging Integration: интеграция сообщений

## 1. Название и локализация

- **English:** Messaging Integration
- **Русский (1:1):**

```text
Интеграция сообщений
```

## 2. Полное описание

Messaging Integration: write-роль для границ outbox, схемы и маршрутизации сообщений, retry и dead-letter queue. У координатора пока нет маршрута dispatch для этой роли (#1159): её не планируют, а тикет, которому нужна такая работа, эскалируется координатору.

Предполагаемая область роли: allowed paths brief для messaging или инфраструктуры, без несвязанных изменений сервиса. Результатом было бы совместимое изменение с последствиями для доставки и обработки отказов, подтверждённое проверками контракта, маршрутизации и путей отказа.

## 3. Контракты

- **Вход (Input/Brief):** immutable brief с allowed paths сообщений, контрактом, правилами маршрутизации и retry/DLQ, DoD и required checks.
- **Выход (Output/Report):** commit SHA совместимого изменения; перечень файлов и проверок; последствия delivery/failure, риски, блокеры и следующий gate.

## Источник

[messaging-integration.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/messaging-integration.md)
