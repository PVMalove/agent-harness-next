# check-branch-name

## 1. Название и локализация
- **Английское название:** check-branch-name (PreToolUse Hook)
- **Русский перевод / Суть:**

```text
Проверка имени новой ветки и существования связанной задачи (принцип "Issue First") перед созданием ветки.
```
## 2. Полное описание
Хук `PreToolUse(Bash)` не даёт агенту создать ветку без задачи в трекере. Хук разбирает команду через `shlex` и ищет `git checkout` или `git switch` с флагом создания ветки (`-b`, `-B`, `-c`, `-C`, `--create`, `--force-create`). Если такая команда есть, хук делает следующее:
1. Берёт из команды имя новой ветки.
2. Сверяет имя с регулярным выражением `branch_pattern` из `.harness/project.json` (по умолчанию `^feature/issue-[0-9]+-.+`). Если имя не подходит, хук блокирует команду.
3. Если имя подходит, хук берёт из него первое число: это ID задачи.
4. Хук передаёт ID в `tracker-issue.py`, так он проверяет принцип "Issue First". `tracker-issue.py` определяет трекер и проект резолвером трекера проекта (`.harness/health/project_tracker.py`): берёт поле `tracker` из `.harness/project.json`, а без него URL `origin` с портом и подгруппами. Issue он запрашивает с явным адресом: `gh issue view <ID> -R <хост>/<проект>` или `glab issue view <ID> -R https://<хост>/<проект>`. Проверку он пропускает, если трекер локальный, путь проекта неизвестен, пакета `.harness/health` нет или `gh`/`glab` не установлен.
5. Если проверка не прошла, хук прерывает команду и называет причину: issue не найдена (её нужно завести через `gh issue create`/`glab issue create`, `/to-spec` или `/to-tickets`), в проекте отключены issues, CLI не авторизован на хосте трекера или проект недоступен.
## 3. Контракты
- **Вход (Input/Brief):** JSON вызова инструмента `Bash` через stdin; хук читает поле `tool_input.command`.
- **Выход (Output/Report):** код `0`, если проверка прошла. Код `2` и причина в `stderr`, если имя ветки нарушает соглашение или задачу не удалось подтвердить: issue не найдена, issues отключены, нет авторизации, проект недоступен, CLI не ответил за 10 с или завершился с нераспознанной ошибкой. Если Python 3.9+ не найден, хук тоже возвращает код `2`.
## Источник

[check-branch-name.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/check-branch-name.sh), [tracker-issue.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/tracker-issue.py)
