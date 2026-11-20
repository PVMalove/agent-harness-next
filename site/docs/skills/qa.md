# QA: обеспечение качества

Источник: [`harness/orchestration/roles/qa.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md) и общий контракт [`common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/common.md).

## 1. Название и локализация

- **Английское название:** `QA`
- **Русский перевод:**

```text
Обеспечение качества
```

## 2. Полный перевод манифеста роли

<div class="ah-skill-text" markdown="1">

```yaml
name: qa
mode: read-only
required_capabilities:
  - independent-verification
```

### QA

Используйте эту роль, когда нужна независимая проверка. Ни одна сессия воркера её не получает: координатор запускает QA через `qa run`, а clean-room QA runner выполняет `verification_commands` brief на точном кандидате и сам пишет отчёт. Адаптер воркера отклоняет QA-brief, а `report submit` отклоняет QA-отчёт, написанный вручную.

Отчёт перечисляет каждую утверждённую команду в `checks_run`; команда, до которой прогон не дошёл, получает `not_run`. Упавшая команда ведёт к developer-retry. QA никогда не меняет production-код и не пишет тесты и fixtures, которые доказывают изменение.

</div>

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief, candidate commit/SHA, критерии приёмки и независимые команды проверки.
- **Процесс (Process):** координатор запускает `qa run`; модельного воркера нет.
- **Выход (Output/Report):** отчёт clean-room QA runner: каждая утверждённая команда в `checks_run` со статусом `pass`, `fail` или `not_run`; `changed files: none`, `commit SHA: not applicable — read-only role`.

## Источник

[qa.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md)
