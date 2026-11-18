# Developer: разработчик

## Интерактивный скилл developer

Источник: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/developer/SKILL.md).
Скилл поставляется в `engineering-suite` и реализует согласованное изменение в текущей issue-ветке
в обычной сессии, вне dispatch координатора. До правки любого файла он проверяет три предусловия:
задачу с критериями приёмки (существующий тикет, если репозиторий задаёт правило Issue First),
читаемый `.harness/project.json` с `branch_pattern` и `base_branch` и текущую ветку, которая
соответствует `branch_pattern` и не является `base_branch` или `integration/*`. Если предусловия
нет, скилл ничего не меняет и возвращает отчёт с блокером, который его называет.

Границы изменения задают разделы тикета `## Relevant Files (Discovery Context)`,
`## Contract touchpoints` и `## Out of scope`; путь вне них требует одобрения человека. Работа
завершена, когда выполнены команды `Verify` из критериев приёмки, целевые тесты и lint/typecheck из
`qa_gate_commands`. Seam согласуется с человеком до первого теста, дальше работа идёт через `/tdd`. Скилл заканчивает
человекочитаемым отчётом в чате из пяти разделов: изменения, проверки (pass, fail или not run),
непроверенное, риски и блокеры. Скилл не коммитит, не пушит, не открывает PR, не запускает code
review и не меняет метки трекера. В `/fast-implement` он выполняет шаги реализации, а review,
commit, push и передачу в `/to-pull-requests` оставляет `/fast-implement`.

## Роль оркестрации `developer`

Интерактивный скилл и роль координатора `developer` разные. Внутри dispatch действуют манифест роли
и brief, скилл их не повторяет и не расширяет. Дальше описан контракт роли.

Источник: [`harness/orchestration/roles/developer.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md) и общий контракт [`common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/common.md).

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

Используйте эту роль для обычных изменений backend-сервиса, которые остаются в явных allowed paths brief. У работы со схемой или миграцией данных, outbox, схемой сообщений, маршрутизацией, повторными попытками и DLQ пока нет маршрута dispatch (#1159): если brief её требует, эскалируйте через обычный путь блокера.

Результат: реализация, которая выполняет `definition_of_done` brief. Докажите её целевыми и обязательными проверками проекта. Если изменение задевает риск-триггер, назовите его в необязательном поле отчёта `risk_triggers` именами из манифеста роли `code-review`; неизвестное имя `report submit` отклоняет. Каждую проверку запускайте через установленный bounded summary wrapper. В отчёт пишите только команду, статус, упавший тест и короткую очищенную ошибку. Полный вывод храните в его локальном пути артефакта, но не в handoff и не в чате следующего воркера.

Место изменения ищите сначала по `starting_files` и `symbol_graph` из Context Package, а потом уже поиском по репозиторию. Упавший тест перезапускайте по его node id через bounded wrapper, а не весь набор.

</div>

Остальные правила роли лежат в `references/` рядом с манифестом и читаются по условию:

- **Red-Green-Refactor с тест-автором** (`references/developer-test-author.md`, перед первым тестом). Цикл берётся из `tdd/references/test-author.md`, роль добавляет свои правила: seam из `accepted_design.output`, путь блокера, одну команду preflight. Если preflight тест-автора отвечает ровно `{"status":"ok"}`, developer проходит каждый шаг реализации как цикл «сначала тест» с отдельным `test-author`. Любой другой ответ preflight оставляет обычный TDD. Цикл не создаёт новый dispatch, роль, состояние или запись в ledger.
- **Developer-retry** (`references/developer-retry.md`). Retry продолжает работу от `snapshot_commit` новыми коммитами (fix-forward). Amend, squash, reset, rebase и force-push коммитов до `snapshot_commit` запрещены. Brief с непустым `rebase_target_commit` сначала требует rebase на точно этот target, потом исправление.
- **Блокировка коммита.** Если hook или другой инструмент блокирует `git commit`, developer ничего не откатывает. Он останавливается с `tooling_blocker` и перечисляет незакоммиченные файлы в `uncommitted_files` внутри этого объекта.
- **План коммитов.** Developer следует плану коммитов из brief. В первичном dispatch и rebase связь коммитов и пунктов плана «многие ко многим». В developer-retry каждый новый коммит закрывает ровно один пункт плана. `commit_map` обязателен, если в brief есть `commit_plan`.
- **Перенесённые пункты** (`references/developer-carried-items.md`). Каждый пункт из `carried_items` developer-retry закрывает новыми коммитами и отмечает в `carried_item_closure` либо помечает `not_closed` с причиной.
- **Перезапуск только упавших тестов** (`references/developer-rerun-failed-tests.md`, только если в проекте есть `scripts/verify.py`). После падения developer перезапускает только упавшее: `scripts/verify.py --worktree-cache --only tests` или `--failed-only`. Такой результат только диагностика: он не заменяет `verification_commands` brief в `checks_run` и не разрешает publish.

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief координатора: явные allowed paths записи, DoD, ветка и worktree, запреты и команды проверки.
- **Процесс (Process):** реализация только в allowed paths brief, на issue-ветке и в изолированном worktree; целевые и обязательные проверки, а при риск-триггере ещё и обязательный review.
- **Выход (Output/Report):** реализация, commit SHA, точные changed files, выполненные проверки, остаточные риски и блокеры.

## Источник

[developer.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/developer.md)
