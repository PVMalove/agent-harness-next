# QA: обеспечение качества

Источник: [`harness/orchestration/roles/qa.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md) и общий контракт [`_common.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/_common.md).

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
risk_triggers:
  - independent-verification-required
```

### QA

Используйте эту роль, когда нужна независимая проверка. Роль работает только на чтение: она не меняет production-код и не пишет тесты или fixtures, которые служат единственным доказательством изменения.

Роль возвращает QA finding. В нём названы выполненные проверки, воспроизводимое доказательство, наблюдаемый результат, дефекты и оставшиеся риски. Доказательством служит независимый запуск через интерфейс, которым пользуется проект.

Роль работает от `related_tests` из Context Package. Выйти за этот набор можно, только если он не проверяет критерии приёмки.

Если часть brief осталась невыполненной, роль перечисляет каждый пункт в `incomplete_items` по общему контракту. `target_role` у такого пункта всегда `qa`, поэтому закончить его может только суженный повтор QA. Суженный повтор QA всё равно запускает все утверждённые команды проверки. Невыполненный пункт никогда не заменяет упавшую проверку или проверку со статусом `not_run` в `checks_run`.

</div>

## 3. Контракты

- **Вход (Input/Brief):** неизменяемый brief, candidate commit/SHA, критерии приёмки и независимые команды проверки.
- **Процесс (Process):** роль независимо запускает проверки через интерфейс проекта и не меняет код, тесты или fixtures.
- **Выход (Output/Report):** QA finding с командами, воспроизводимыми доказательствами, результатом, дефектами и остаточными рисками; `changed files: none`, `commit SHA: not applicable — read-only role`.

## Источник

[qa.md](https://github.com/PVMalove/agent-harness-next/blob/master/harness/orchestration/roles/qa.md)
