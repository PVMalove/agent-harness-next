# block-scratch-outside-docs-tasks

## 1. Название и локализация
- **Английское название:** Block Scratch Outside Docs Tasks
- **Русский перевод / Суть:**

```text
Блокировка сохранения черновиков вне каталога задач
```
## 2. Полное описание
Хук срабатывает перед записью или правкой файла (`PreToolUse(Write/Edit)`) и следит, чтобы агент хранил артефакты по правилам `docs/agents/artifacts.md` и `docs/agents/git-workflow.md`: черновики задач в `docs/tasks/`, тела PR и комментариев в `.harness/.sandboxes/pr_body/`.

Как хук решает:
1. Хук читает JSON из stdin и JSON-парсером берёт `tool_input.file_path`. Windows-разделители он приводит к `/` до проверки. Путь вне проекта (`CLAUDE_PROJECT_DIR`) хук блокирует с сообщением, что путь вышел за пределы проекта. Исключение: каталог памяти Claude Code `<CLAUDE_CONFIG_DIR или ~/.claude>/projects/<slug>/memory/`, туда писать можно. Если путь не удаётся разрешить или в payload нет `tool_input.file_path`, хук тоже блокирует.
2. Если имя файла содержит `pr-body`, `pr-comment` или `issue-comment`, это тело PR или комментария:
   - хук разрешает запись только прямо в каталог публикационных файлов `.harness/.sandboxes/pr_body/` (например, `.harness/.sandboxes/pr_body/pr-body-<issue>-<slug>.md`) и блокирует любой другой путь, включая `docs/tasks/`. После успешной отправки через `gh`/`glab` агент удаляет файл; если отправка не удалась, файл остаётся для повторной попытки.
   - Любой другой файл в `.harness/.sandboxes/pr_body/` хук блокирует.
3. Для остальных файлов (рабочие файлы, черновики, спецификации):
   - Привязанный scratchpad сессии разрешён: `.harness/.sandboxes/scratch/sessions/<session_id>/scratchpad/`. Запись туда проходит, только если `<session_id>` в пути совпадает с `session_id` из входного JSON и подходит под `[A-Za-z0-9][A-Za-z0-9_-]{0,127}`. Путь другой сессии хук блокирует. Системный каталог scratchpad runtime вне проекта блокируется как путь вне проекта.
   - Служебные каталоги `.harness/.sandboxes/` `cache`, `logs`, `runs`, `reports` и `worktrees` разрешены.
   - Если путь ведёт во временный системный каталог (`AppData\Local\Temp`, `AppData\Roaming\Temp`, содержит `/tmp/` или `/scratchpad/`), хук блокирует запись и напоминает, что спецификации и черновики задач хранятся в `docs/tasks/`. Каталоги `.scratch`, `.claude`, `.agents` с подкаталогом `tmp`, `scratch` или `temp` под это правило не попадают.
4. Второй runtime присылает правку как `apply_patch` (`tool_name: "apply_patch"`, патч в `tool_input.command`). Хук передаёт такой payload адаптеру `apply_patch_payload.py fanout`. Адаптер разбирает патч так же, как runtime, и для каждого пути из заголовков `*** Add File:`, `*** Update File:`, `*** Delete File:`, `*** Move to:` (абсолютного от `cwd` payload) снова запускает этот хук с payload `Write{file_path}`. Первый отказ адаптер возвращает как есть, поэтому патч на несколько файлов блокируется, если заблокирован хотя бы один путь. Хук блокирует с префиксом `[apply-patch-unparseable]` и подсказкой о формате патча в трёх случаях: патч нельзя разобрать (runtime сам бы его отверг), `tool_input.command` не строка, адаптера нет. Второй runtime не задаёт `CLAUDE_PROJECT_DIR`, поэтому адаптер передаёт корень checkout, в который переходит команда hook из шаблона. Shell-вызов `apply_patch <<'EOF'` в Bash этот хук не проверяет: в первом runtime он тоже не подключён к Bash.
5. Если ни одно условие блокировки не сработало, хук разрешает операцию.
## 3. Контракты
- **Вход (Input/Brief):** JSON вызова инструмента через stdin, в том числе `tool_input.file_path` и `session_id`.
- **Выход (Output/Report):** код `0` разрешает вызов инструмента. Код `2` блокирует его, а в stderr хук пишет нарушенное правило из документации. В конверте `hook_response.py` блок получает `reason_code` `scratch-location`, а неразбираемый патч `apply_patch` получает `apply-patch-unparseable`.
## Источник

[block-scratch-outside-docs-tasks.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/block-scratch-outside-docs-tasks.sh), [apply_patch_payload.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/apply_patch_payload.py)
