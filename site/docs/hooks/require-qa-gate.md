# require-qa-gate

## 1. Название и локализация
- **Английское название:** require-qa-gate.sh
- **Русский перевод / Суть:**

```text
Блокировка создания PR/MR без успешного прохождения QA
```
## 2. Полное описание
Хук `PreToolUse(Bash)` блокирует `gh pr create` (создание pull request) и `glab mr create` (создание merge request), если checkout публикуемой ветки ещё не прошёл навык `qa-gate`.

Хук читает команду Bash из stdin. Если в тексте команды есть `gh pr create` или `glab mr create` либо их алиас `gh pr new`/`glab mr new`, хук находит checkout публикуемой ветки и вычисляет хэш его состояния: хэш HEAD и хэш изменений `git diff HEAD`. Затем он сверяет его с маркером `.claude/.qa-gate/passed` в этом checkout. Маркер записывает навык `qa-gate`, когда все проверки прошли. Если маркера нет или он не совпадает с текущим состоянием, хук прерывает команду и просит запустить `qa-gate`. Если команда не создаёт PR/MR или проверка прошла, хук завершается кодом `0`.

Вместо маркера хук принимает accepted QA-evidence coordinator оркестрации. Он запрашивает `qa evidence` у `.harness/orchestration/coordinator.py` основного worktree для тикета из `issue-<N>` в имени ветки и для `HEAD` checkout. Хук ничего не пишет в ledger. Но сам CLI на время чтения берёт блокировку ledger, поэтому хук ждёт его не дольше 60 секунд. Если coordinator занят или недоступен, остаётся прежний блок. Хук принимает evidence при всех условиях:

- CLI подтвердил решение `accept`, неизменность отчёта и совпадение `candidate_commit` с `HEAD`;
- в отчёте `outcome: completed`, а каждая команда `qa_gate_commands` имеет `result: pass`;
- `git diff HEAD` пуст.

Команды отчёта хук сверяет со строками `qa_gate_commands` буквально. QA lane выполняет `verification_commands` dispatch, и если они отличаются от `qa_gate_commands`, evidence не подходит и остаётся путь с маркером. Отчёты failed, unaccepted и `blocked`, другой SHA, грязное дерево и отсутствие coordinator тоже оставляют путь с маркером. Поэтому `/fast-implement` и работа вне оркестрации работают как прежде.

Ветку хук берёт из argv самой create-команды (разбор `pr_commands.py`). Флаги других команд той же строки, например `git commit -s`, веткой не считаются:
- `gh pr create`: `--head <ветка>`, `--head=<ветка>` или короткий `-H <ветка>`, `-H<ветка>`, `-H=<ветка>` (в том числе в группе флагов, `-dH <ветка>`); префикс `owner:` хук отбрасывает;
- `glab mr create`: `-s <ветка>`, `-s<ветка>`, `-s=<ветка>`, `--source-branch <ветка>`, `--source-branch=<ветка>`, в том числе в группе коротких флагов (`-fs <ветка>`). Флаг glab `-H`/`--head` задаёт репозиторий (`OWNER/REPO`), а не ветку, и хук его не учитывает;
- без флага ветки хук проверяет самый глубокий checkout проекта, который содержит `cwd` из payload, то есть текущую ветку.

Выбор ветки не уже, чем в прежней версии. Если в тексте есть `gh pr create`, хук считает веткой PR и первый `--head <ветка>`/`--head=<ветка>` во всём тексте команды (глобальный разбор `shlex.split`, как в прежнем хуке), даже если разбор create-команды по токенам его не видит. `--head` без значения или текст с `--head`, который `shlex` не разобрал, блокируют вызов.

Найденной ветке должен соответствовать ровно один checkout проекта, иначе хук блокирует вызов.

Создание PR/MR хук распознаёт по тексту команды. Упоминание `gh pr create`/`gh pr new` или `glab mr create`/`glab mr new` в кавычках или в аргументе другой команды тоже запускает проверку checkout из `cwd`. Запрет merge в `block-pr-merge.sh` на это распознавание не влияет. Хук блокирует и неоднозначные случаи:

- больше одной разной ветки (из create-команд и глобального разбора `--head`);
- флаг ветки без значения;
- create-текст с флагом ветки, который не удаётся разобрать по токенам.

Любая ошибка хука даёт код `2`, в том числе отсутствующий, неполный или синтаксически повреждённый `pr_commands.py` рядом с хуком.
## 3. Контракты
- **Вход (Input/Brief):** JSON вызова Bash через stdin: команда и `cwd`. Текущее состояние Git (HEAD и незакоммиченные изменения) в checkout публикуемой ветки.
- **Выход (Output/Report):** код `0` разрешает команду. Код `2` и сообщение в `stderr` блокируют её.
## Источник

[require-qa-gate.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/require-qa-gate.sh), [qa-gate-state.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/qa-gate-state.py), [pr_commands.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/pr_commands.py)
