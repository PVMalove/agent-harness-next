# Developer: разработчик

Источник: [`harness/orchestration/roles/developer.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md) и общий контракт [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## 1. Название и локализация

- **Английское название:** `Developer`
- **Русский перевод:**

```text
Разработчик
```

## 2. Перевод манифеста роли

Перевод охватывает заголовок манифеста и его вводную часть. Остальные разделы кратко описаны ниже, полный текст есть в источнике на английском.

<div class="ah-skill-text" markdown="1">

```yaml
name: developer
mode: write
required_capabilities:
  - backend-development
risk_triggers:
  - api-public-contract
  - transactions
  - authorization-security
  - concurrency-retry
```

### Разработчик

Используйте эту роль для обычных изменений backend-сервиса, которые остаются в явных allowed paths brief. Не делайте работу со схемой или миграцией данных и работу с outbox, схемой сообщений, маршрутизацией, повторными попытками или DLQ: эти специальные триггеры принадлежат своим ролям.

Результат: реализация, которая выполняет критерии приёмки handoff. Докажите её целевыми и обязательными проверками проекта, а если применяется триггер из списка, ещё и review риска. Каждую проверку запускайте через установленный bounded summary wrapper. В отчёт пишите только команду, статус, упавший тест и короткую очищенную ошибку. Полный вывод храните в его локальном пути артефакта, но не в handoff и не в чате следующего воркера.

Место изменения ищите сначала по `starting_files` и `symbol_graph` из Context Package, а потом уже поиском по репозиторию. Упавший тест перезапускайте по его node id через bounded wrapper, а не весь набор.

</div>

Остальные разделы манифеста:

- **Red-Green-Refactor с тест-автором.** Если preflight тест-автора отвечает ровно `{"status":"ok"}`, developer проходит каждый шаг реализации как цикл «сначала тест» с отдельным `test-author`. Любой другой ответ preflight оставляет обычный TDD. Цикл не создаёт новый dispatch, роль, состояние или запись в ledger.
- **Developer-retry.** Retry продолжает работу от `snapshot_commit` новыми коммитами (fix-forward). Amend, squash, reset, rebase и force-push коммитов до `snapshot_commit` запрещены. Brief с непустым `rebase_target_commit` сначала требует rebase на точно этот target, потом исправление.
- **Блокировка коммита.** Если hook или другой инструмент блокирует `git commit`, developer ничего не откатывает. Он останавливается с `tooling_blocker` и перечисляет незакоммиченные файлы в `uncommitted_files`.
- **План коммитов.** Developer следует плану коммитов из brief. В первичном dispatch и rebase связь коммитов и пунктов плана «многие ко многим». В developer-retry каждый новый коммит закрывает ровно один пункт плана. `commit_map` обязателен, если в brief есть `commit_plan`.
- **Перенесённые пункты.** Каждый пункт из `carried_items` developer-retry закрывает новыми коммитами и отмечает в `carried_item_closure` либо помечает `not_closed` с причиной.
- **Перезапуск только упавших тестов.** После падения developer перезапускает только упавшее: `scripts/verify.py --worktree-cache --only tests` или `--failed-only`. Такой результат только диагностика: он не заменяет `verification_commands` brief в `checks_run` и не разрешает publish.

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief координатора: явные allowed paths записи, DoD, ветка и worktree, запреты и команды проверки.
- **Процесс (Process):** реализация только в allowed paths brief, на issue-ветке и в изолированном worktree; целевые и обязательные проверки, а при риск-триггере ещё и обязательный review.
- **Выход (Output/Report):** реализация, commit SHA, точные changed files, выполненные проверки, остаточные риски и блокеры.

## Источник

[developer.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md)
