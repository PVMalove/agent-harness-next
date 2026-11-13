# Conflict Resolver: разрешение конфликтов

Источник: [`harness/orchestration/roles/conflict-resolver.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/conflict-resolver.md) и общий контракт [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

## 1. Название и локализация

- **Английское название:** `Conflict resolver`
- **Русский перевод:**

```text
Разрешение конфликтов
```

## 2. Полное описание

Conflict Resolver разрешает текстовый конфликт между веткой тикета (candidate) и сдвинувшимся integration SHA (target). Это write-роль. Она же чинит проваленную проверку CI или local-QA уже обновлённой пары: тогда `resolver.trigger: verification-failure`, в brief есть `failed_evidence_ids`, конфликтных файлов нет, а правка остаётся в scope brief. Назначить роль вручную нельзя. Её вызывает только `integration resolve`: команда создаёт отдельный resolver batch рядом с завершённым batch тикета.

Роль работает в issue-ветке и worktree своего batch и открывает скилл `resolving-merge-conflicts`. Она сохраняет требования обеих сторон из секции `resolver` brief и не добавляет функциональность сверх них. Роль никогда не делает `--abort` и force-push.

Если требования сторон несовместимы, роль не угадывает. Она пишет checkpoint: конкретная несовместимость и варианты с последствиями. Ответ человека записывается отдельным событием `human-decision`, и тот же dispatch продолжается. Новый developer не стартует, соседние batch продолжают работу. Если резолюции нужна правка собственного кода тикета, это дефект тикета: роль сообщает `cause: task-defect`, и работа уходит обычному developer.

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief с секцией `resolver`: тикет, требования обеих сторон, SHA candidate и target, scope, запреты, план коммитов, проверки, остаток бюджета (два автоматических target SHA) и `report_staging_path`.
- **Процесс (Process):** rebase на точный SHA target, разрешение каждого конфликта с сохранением обеих сторон, проверки проекта, коммит резолюции. При несовместимости роль пишет checkpoint.
- **Выход (Output/Report):** commit SHA резолюции, точные changed files, проверки и блок `resolver`: сохранённые требования, решения человека, причина, коммиты по плану. Принятая резолюция идёт узким маршрутом: повторного review нет, но QA и CI либо local-QA новой пары обязательны.

## Источник

[conflict-resolver.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/conflict-resolver.md)
