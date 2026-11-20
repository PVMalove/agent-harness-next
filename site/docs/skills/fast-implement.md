# /fast-implement — короткий маршрут реализации

Запускайте `/fast-implement` вручную (в Codex используйте `$fast-implement`) для `afk`-тикета с меткой
`pipeline::fast`. Навык реализует тикет в текущей сессии через тесты, без шага architect,
отдельной роли QA и гейтов координатора. Он не открывает PR, не запускает `qa-gate` и не закрывает тикет.

## Вход

- Названный тикет, эпик или ничего. По эпику навык сам берёт первый открытый, разблокированный и
  не взятый `afk`-тикет с `pipeline::fast` из самой ранней волны и назначает его на себя.
- Тикет `hitl` уходит в `/to-guide`, тикет `pipeline::full` — в `/implement`. Без тикета при правиле
  Issue First навык просит подготовить его через `/to-spec`, `/publish-epic` и `/to-tickets`.

## Предполётная проверка

1. Открытые блокеры останавливают работу.
2. Метка тикета меняется на `status::in-progress`.
3. Integration-ветка берётся из `## Integration Branch` или строки `**Integration branch:**`
   локального тикета, иначе из эпика.
4. Если текущая ветка не подходит под `branch_pattern`, навык создаёт issue-ветку от integration-ветки
   и пушит её; подходящая текущая ветка остаётся рабочей.
5. Разделы тикета `## Relevant Files (Discovery Context)`, `## Contract touchpoints` и
   `## Out of scope` задают границы изменения, а критерии `Action -> Verify` — проверки. Правка вне
   границ требует вашего одобрения.

## Реализация и завершение

Шаги реализации выполняются по навыку `developer`: согласование шва до первого теста, `/tdd`,
необязательный тест-автор по протоколу `tdd/references/test-author.md` и проверки `Verify`. Полный
набор тестов запускает `/qa-gate` перед PR; он выполняет только `qa_gate_commands`, а
`pre_qa_commands` и оверлеи QA действуют только в `/implement`. Затем навык спрашивает «Провести code review?», ждёт
разрешения на commit и push и пушит issue-ветку. В конце он предлагает вручную запустить
`/to-pull-requests <ticket>`. Метка `status::in-progress` остаётся на тикете: после слияния
`/to-pull-requests` закрывает тикет и переводит разблокированные зависимые тикеты в `status::ready`.

[Исходный SKILL.md](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/fast-implement/SKILL.md)
