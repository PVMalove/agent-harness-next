# protect-hook-policy

## 1. Название и локализация
- **Английское название:** protect-hook-policy (PreToolUse Hook)
- **Русский перевод / Суть:**

```text
Защита политики hooks: запрет агенту менять ключ hook_policy, настройки и каталоги hooks; запись в .harness/project.json через shell идёт только по ручному подтверждению человека.
```
## 2. Полное описание
Критичный hook `PreToolUse` для Bash и инструментов файлов (`Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `apply_patch` второго runtime). Он защищает политику hooks во всех профилях (`minimal`, `standard`, `strict`): блокирует правку, а запись в `.harness/project.json` через shell отдаёт на ручное подтверждение человека (см. раздел про Bash). Решение не зависит от роли и окружения: `HOOK_PROFILE` и подобные переменные hook не читает. Политику hooks меняет человек (ADR 0024, раздел 1).

Решение принимает `protect_hook_policy.py` по принципу fail closed. Действие проходит, только если модуль вернул код `0` и слово `allow`. Если Python нет, модуль вернул другой код или скопирован не полностью, hook возвращает код `2`. Через конверт `hook_response.py` hook отвечает вердиктом с `hook_id` `protect-hook-policy` и одним из `reason_code`, который сценарий называет префиксом `[reason_code]` в первой строке stderr.

**Инструменты файлов.** Путь из `file_path`/`notebook_path` hook разрешает через `realpath` относительно `cwd` payload и сравнивает по хвосту. Поэтому symlink на защищаемый файл, каталог-symlink, другой checkout или worktree решение не меняют. Регистр имён hook не различает.
- `.claude/settings*.json`, `.codex/hooks.json` и всё внутри каталогов `.claude/hooks` и `.codex/hooks`: блок с кодом `agent-config-edit`.
- `.harness/project.json`: правка разрешена, только если разобранный ключ `hook_policy` до и после неё совпадает. Hook сравнивает разобранные значения, а не байты; отсутствие ключа тоже считается значением. Если ключ добавлен, изменён или удалён, hook блокирует с кодом `hook-policy-changed`. Код `hook-policy-unparseable` hook даёт, если JSON до или после правки не разбирается, не является объектом или содержит повторяющийся ключ, либо результат правки нельзя вычислить заранее (`old_string` не найден или неоднозначен, `NotebookEdit`). Правка других ключей разрешена.

**Bash.** Любая запись в `.harness/project.json` требует ручного подтверждения человека (`project-json-shell-write`). В Claude Code (задан `CLAUDE_PROJECT_DIR`) hook отвечает вердиктом `ask`: runtime показывает запрос с причиной, а человек подтверждает или отклоняет. Агент пишет в `description` команды, что и зачем меняется. Вне Claude Code и без конверта `hook_response.py` тот же отказ остаётся блоком (код `2`). Записью hook считает:
- перенаправление в этот файл (`>`, `>>`, `>|`, `&>`, `<>`, с номером дескриптора и heredoc). Цели перенаправлений находит строгий лексер `pr_commands.StrictLexer` (`strict_redirections`);
- упоминание файла аргументом любой программы, кроме читающих. Читающие: `cat`, `grep`, `rg`, `head`, `tail`, `wc`, `ls`, `jq`, `diff`, `sed` без `-i`/`--in-place`, `echo`, `printf`, `cd` и безопасные подкоманды git (`status`, `diff`, `log`, `show`, `add`, `commit`, `blame`, `ls-files` и т. п.). Пишущие, например: `tee`, `cp`, `mv`, `install`, `dd of=`, `truncate`, `ln`, `sed -i`, `git checkout|restore`, код интерпретатора (`python -c`, `perl -pi`), `bash -c`;
- программу за обёрткой `command`, `env`, `sudo` или `timeout` hook оценивает так же, как без обёртки: `command ls .harness` и `timeout 5 sed -n 1,5p .harness/project.json` разрешены, а `sudo cp a .harness/project.json` блокируется. Опции обёртки hook разбирает по таблице `WRAPPERS`. Обёртку с опцией не из таблицы (`env -C`, `env -S`, `sudo -D`, `sudo -e`) hook сам считает пишущей программой. Присваивание `env F=.harness/project.json` перед пишущей программой тоже считается упоминанием;
- слово, которое указывает на каталог `.harness`, у любой пишущей программы (не из читающих; для git не из безопасных подкоманд). Команды `git checkout <ref> -- .harness`, `git restore --source=<ref> .harness`, `cp -r <каталог>/. .harness/`, `tar -C .harness -xf <архив>`, `unzip … -d .harness`, `rsync`, `mv .harness …`, `rm -rf .harness` заменяют или удаляют файл вместе с ключом `hook_policy`. Чтение каталога (`ls`, `git -C .harness status`) и запись в другие файлы под ним (`cp a .harness/notes.txt`) разрешены;
- слово, которое называет файл по имени `project.json`, по пути после `realpath` относительно `cwd`, корня проекта и целей `cd` команды (в том числе через symlink) или по glob (`.harness/proj*.json`).

**apply_patch второго runtime.** Второй runtime присылает правку файлов как `tool_name: "apply_patch"` с телом патча в `tool_input.command`. Адаптер `apply_patch_payload.py` разбирает патч так же, как runtime (heredoc-обёртка `<<EOF`, пробелы вокруг маркеров, `*** Environment ID:`, `*** End of File`, `*** Move to:`). Пути заголовков `*** Add File:`, `*** Update File:`, `*** Delete File:`, `*** Move to:` он превращает в абсолютные от `cwd` payload. Каждый путь получает то же решение, что `Write`/`Edit`, и патч на несколько файлов блокируется, если заблокирован хотя бы один путь. Для `.harness/project.json` ключ `hook_policy` до и после правки адаптер вычисляет по семантике runtime:

- Add: содержимое патча;
- Delete и Move с файла: файла больше нет;
- Update: применённые чанки (поиск строк с допуском по пробелам и типографским символам, как у runtime). Если строки Update в файле не найдены, hook даёт `hook-policy-unparseable`.

Патч, который runtime сам бы отверг (нет `*** Begin Patch`/`*** End Patch`, пустой путь, пустой Update, мусор после `*** End Patch`), и `tool_input.command` не строкой hook блокирует с кодом `apply-patch-unparseable` и подсказкой о формате патча. Delete или Move файла без ключа `hook_policy` разрешены: ключ не меняется.

**apply_patch в Bash.** Эта проверка дополняет правила Bash выше и никогда не снимает их отказ. Если в команде есть слово `apply_patch` и строка `*** Begin Patch`, shell-форму `[cd <каталог> &&] apply_patch <<'EOF'` разбирает адаптер, и каждую операцию hook проверяет как патч выше. Неразбираемое тело такой формы даёт `apply-patch-unparseable`. Команду другой формы hook разбирает по заголовкам патча в тексте: путь к настройкам или каталогам hooks (от `cwd`, корня проекта и целей `cd`) даёт `agent-config-edit`, путь к `.harness/project.json` даёт `hook-policy-unparseable`.

Команду вне строгого подмножества bash (`$`, обратные кавычки, скобки) hook разбирает общим разбором `pr_commands.parse`. Цель перенаправления в ней hook ищет по тексту и блокирует присваивание значения с `project.json` переменной и код интерпретатора с этим именем. Чтение файла и запись в другие файлы разрешены.

Hook блокирует по упоминанию, а не по доказанной записи (fail closed). Пишущая программа, в аргументах которой есть текст `project.json`, получает отказ, даже если файл не пишет (`gh issue comment 1 --body "edit project.json"`, `python3 -m json.tool .harness/project.json`). Текст для трекера передавайте через `--body-file`, а файл читайте инструментом `Read`. Поведение закреплено тестом `test_naming_the_file_without_a_write_fails_closed`.

Остаточные ограничения: запись через скрипт в файле, косвенность через переменные и программы, в аргументах которых файл не назван, и shell-запись в настройки и каталоги hooks (их защищает только проверка инструментов файлов).

## 3. Контракты
- **Вход (Input/Brief):** JSON-payload PreToolUse через stdin: `tool_name`, `tool_input` (`command` либо `file_path`/`notebook_path` с содержимым правки; у `apply_patch` в `command` лежит патч) и `cwd`.
- **Выход (Output/Report):**
  - **Разрешение:** код `0`; последняя строка stderr содержит вердикт `allow`.
  - **Ручное подтверждение:** только `project-json-shell-write` в Claude Code. Тело завершается кодом `3`, конверт отвечает кодом `0`, вердиктом `ask` и JSON `hookSpecificOutput.permissionDecision: "ask"` в stdout. Остальные отказы никогда не спрашивают.
  - **Блокировка:** код `2`, сообщение с префиксом `[reason_code]` в stderr и вердикт `block`. Коды: `hook-policy-changed`, `hook-policy-unparseable`, `project-json-shell-write`, `agent-config-edit`, `apply-patch-unparseable` (патч `apply_patch` не разбирается), `hook-policy-protected` (payload не разобран, в нём нет пути и команды или модуль не дал решения). Все коды зарегистрированы в `harness/orchestration/system_fields.v1.json` (`hook.reason_code`).
## Источник

[protect-hook-policy.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/protect-hook-policy.sh), [protect_hook_policy.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/protect_hook_policy.py), [pr_commands.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/pr_commands.py), [apply_patch_payload.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/apply_patch_payload.py), [hook_response.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/hook_response.py)
