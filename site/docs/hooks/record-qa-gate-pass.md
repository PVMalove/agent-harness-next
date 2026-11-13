# record-qa-gate-pass

## 1. Название и локализация
- **Английское название:** record-qa-gate-pass
- **Русский перевод / Суть:**

```text
Запись успешного прохождения QA Gate
```
## 2. Полное описание
Скрипт `record-qa-gate-pass.sh` записывает маркер успешного QA-гейта. Навык `qa-gate` (см. его `SKILL.md`) вызывает скрипт последним шагом, сразу после того как все команды из `qa_gate_commands` прошли. Навык работает в изолированном контексте (fork), и хук `mark-qa-gate-passed.sh` (PostToolUse) для вызовов внутри fork может не сработать. Поэтому навык пишет маркер сам. Путь к скрипту навыки `qa-gate` и `to-pull-requests` берут из `CLAUDE_PROJECT_DIR`. Если переменная не задана (второй runtime), они берут его из основного worktree: первой записи `git worktree list --porcelain`, где установлен `.claude/hooks/`.

Навык `to-pull-requests` вызывает тот же скрипт из checkout ветки PR, когда `coordinator.py qa evidence` уже подтвердил текущий SHA. Так принятое QA-доказательство coordinator попадает в маркер без повторного прогона QA-гейта.

Скрипт вычисляет состояние checkout: хеш последнего коммита (`git rev-parse HEAD`) и хеш незакоммиченных изменений (`git diff HEAD | git hash-object --stdin`). Эту строку он записывает в `.claude/.qa-gate/passed`: текущее состояние кода прошло проверку качества.
## 3. Контракты
- **Вход (Input/Brief):** необязательная переменная окружения `CLAUDE_PROJECT_DIR` (по умолчанию текущий каталог) задаёт корень проекта. Текущий рабочий каталог выбирает checkout, для которого пишется маркер, поэтому скрипт запускают из checkout тестируемой ветки или ветки PR.
- **Выход (Output/Report):** создаёт или обновляет маркер `.claude/.qa-gate/passed` со строкой `<HEAD_hash>:<diff_hash>`. Если состояние вычислить не удалось, скрипт завершается кодом `2`.
## Источник

[record-qa-gate-pass.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/record-qa-gate-pass.sh)
