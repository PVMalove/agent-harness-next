# Карта hooks

Каталог hook-скриптов Harness Next: что перехватывает каждый хук, какой контракт у входа и выхода и где лежит исходник.
Каждый управляемый hook отвечает единым JSON-вердиктом ([hook-response](hook-response.md)) и подчиняется профилю
политики проекта; критические guards профилем не отключаются.

## Git и ветки

| Hook | Событие | Назначение |
| --- | --- | --- |
| [block-dangerous-git](block-dangerous-git.md) | `PreToolUse(Bash)` | Блокировка разрушительных Git-команд. |
| [block-direct-master](block-direct-master.md) | `PreToolUse(Bash)` | Запрет прямых коммитов и пушей в защищённые ветки (`master`, `main`, `base_branch`, `integration/*`). |
| [block-pr-merge](block-pr-merge.md) | `PreToolUse(Bash)` | Запрет автослияния PR/MR: merge выполняет человек. |
| [block-public-attribution](block-public-attribution.md) | `PreToolUse(Bash)` | Блокировка AI-атрибуции в публичных Git-метаданных. |
| [check-branch-name](check-branch-name.md) | `PreToolUse(Bash)` | Проверка имени новой ветки и существования связанной задачи (Issue First). |
| [check-worktree-branch-name](check-worktree-branch-name.md) | `PreToolUse(EnterWorktree)` | То же для ветки, создаваемой вместе с worktree. |

## QA и проверки

| Hook | Событие | Назначение |
| --- | --- | --- |
| [require-qa-gate](require-qa-gate.md) | `PreToolUse(Bash)` | Блокировка создания PR/MR без успешного QA. |
| [record-qa-gate-pass](record-qa-gate-pass.md) | вызывается скиллом | Фиксация успешного прохождения QA gate для текущего состояния. |
| [mark-qa-gate-passed](mark-qa-gate-passed.md) | `PostToolUse(Bash)` | Маркировка прохождения QA-гейта после последней команды `qa_gate_commands`. |
| [require-bounded-check](require-bounded-check.md) | `PreToolUse(Bash)` | Ограниченный вывод полного тестового прогона через обёртку `test_summary.py`. |
| [targeted-check-reminder](targeted-check-reminder.md) | `PreToolUse(Write/Edit)`, `Stop`, `SubagentStop` | Напоминание в конце хода роли отчитать targeted-проверки brief. |
| [run-test](run-test.md) | скрипт, не hook | Изолированный запуск одного выбранного теста в bubblewrap. |

## Политика и рискованные пути

| Hook | Событие | Назначение |
| --- | --- | --- |
| [protect-hook-policy](protect-hook-policy.md) | `PreToolUse` (Bash и инструменты файлов) | Защита политики hooks: ключ `hook_policy`, настройки и каталоги hooks. |
| [block-scratch-outside-docs-tasks](block-scratch-outside-docs-tasks.md) | `PreToolUse(Write/Edit)` | Черновики задач пишутся только в `docs/tasks/` внутри проекта. |
| [impact-first-touch](impact-first-touch.md) | `PreToolUse(Write/Edit)` | Предупреждение о первом касании рискованного пути в операции. |
| [sensitive-path-recheck](sensitive-path-recheck.md) | `PreToolUse(Write/Edit)`, профиль `strict` | Предупреждение о каждой новой правке чувствительного пути. |

## Test-author

| Hook | Событие | Назначение |
| --- | --- | --- |
| [test-author-guard](test-author-guard.md) | `PreToolUse` (подключён frontmatter агента) | Защитный hook субагента test-author: ровно три вида разрешённых вызовов. |
| [test-author-preflight](test-author-preflight.md) | скрипт, не hook | Проверка, что test-author можно включить без потери защиты. |

## Служебные

| Документ | Тип | Назначение |
| --- | --- | --- |
| [hook-response](hook-response.md) | общий модуль | Конверт ответа управляемых hooks: JSON-вердикт, код возврата и профиль политики. |
| [install-and-update](install-and-update.md) | установка | Слияние управляемых записей файла настроек и адаптер второго runtime. |
| [count-skill-usage](count-skill-usage.md) | `PreToolUse(Skill)` | Учёт вызовов скиллов, best-effort, никогда не блокирует. |

## Связанные документы

- Навыки и роли конвейера: [карта навыков](../skills/index.md)
- Агенты и руководства: [карта агентов](../agents/index.md)
- Справочник по hooks: [reference/hooks](../reference/hooks.md)
