# targeted-check-reminder.sh: напоминание о targeted-проверках

## 1. Название и локализация

- **Исходный хук:** [`harness/project/hooks/targeted-check-reminder.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/targeted-check-reminder.sh)
  и общее тело [`change_impact_hooks.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
- **Русский перевод:** напоминание в конце хода роли отчитать targeted-проверки brief.

## 2. Полное описание

Advisory-hook из матрицы ADR 0024, раздел 2a. Он работает на двух событиях:

- **`PreToolUse(Write|Edit)`.** Hook ведёт журнал касаний операции и отвечает `allow` без вывода.
  Запись `t-<sha256(realpath)[:32]>.json` содержит путь, корень checkout и вид: `report` для записи в
  `.harness/.sandboxes/scratch/inbox/*.json` (`report_staging_path`), `touch` для остального. Hook
  создаёт запись через `O_EXCL` один раз и больше её не меняет.
- **`Stop` и `SubagentStop`.** Это конец хода роли. Главный агент (coordinator, внешний worker)
  заканчивает ход событием `Stop`, роль-субагент in-process заканчивает его событием `SubagentStop`.
  Изменениями hook считает существующие файлы журнала, кроме путей под `.harness/` и `docs/tasks/` и
  самих отчётов. Если изменений нет или последний отчёт операции новее всех изменений по `mtime`, hook
  молчит. Иначе он выдаёт `warn` с кодом `targeted-checks-unreported` и stdout
  `{"systemMessage": "<текст>"}`. В тексте стоят число файлов, worktree и требование отчитать
  targeted-проверки brief в `checks_run`.

Hook никогда не продолжает ход. У `Stop` и `SubagentStop` он не отвечает `decision: block`, кодом `2`
или `additionalContext`, а при `stop_hook_active: true` отвечает `allow` без вывода. Поэтому цикла
нет. Hook не запускает тесты, `make` и `git`: он только делает `stat` файлов журнала.

- **Профили.** В `minimal` hook не работает: тело не запускается, журнал не пишется. В `standard` и
  `strict` hook ведёт журнал и напоминает.
- **Дедупликация.** Предмет напоминания состоит из отсортированного состояния
  `(путь, mtime_ns, размер)` изменённых файлов и `mtime_ns` последнего отчёта. Повторный `Stop` без
  новых изменений молчит. Новая правка или новый отчёт меняют digest и дают новое напоминание.

### Хранилище операции

Состояние трёх hooks ChangeImpact лежит в `<проект>/.harness/.sandboxes/hook-events/<operation_id>/`.
Корень проекта hook берёт по расположению модуля (`.claude/hooks/` проекта). Каталог gitignored и
одноразовый. В каталоге операции лежат маркеры уведомлений `n-<key>.json` и журнал касаний
`t-<key>.json`. Блокировок и read-modify-write нет: каждый файл hook создаёт через `O_EXCL`, поэтому
поведение одинаково на Linux и Windows. Размер хранилища ограничен:

- не больше 64 каталогов операций; при создании нового hook удаляет самые старые по `mtime`;
- не больше 2048 файлов в операции; дальше hook записи не создаёт и отвечает `allow` с диагностикой в
  stderr.

Имена файлов состоят только из hex. Временные каталоги `/tmp` и `fcntl` hook не использует.

### Второй runtime

Шаблон `.codex/hooks.json` подключает этот hook только на `Stop` и `SubagentStop`. Второй runtime
доставляет оба события с `session_id`, `stop_hook_active` и, у `SubagentStop`, `agent_id`. Правки
файлов там приходят как `apply_patch` без `file_path`, поэтому журнал касаний на `Write` и `Edit` ждёт
адаптера payload. Пока адаптера нет, журнал второго runtime пуст и напоминание молчит. `harness health`
перечисляет строку `PreToolUse` в `нет события или payload` с проверкой вне hook: coordinator сверяет
`checks_run`.

## 3. Контракт

- **Вход:** JSON события в stdin: `session_id`, `agent_id` (у субагента), `hook_event_name`.
  У `PreToolUse` ещё `tool_input.file_path` и `cwd`, у `Stop` и `SubagentStop` ещё `stop_hook_active`.
- **Выход:** всегда код `0`. Напоминание состоит из `systemMessage` в stdout, первой строки stderr
  `[targeted-checks-unreported] <текст>`, строки `evidence_ref=<путь>` и вердикта `warn`. Остальные
  вызовы получают `allow` без stdout. Внутренняя ошибка даёт `warn` `internal-error` с пустым stdout,
  чтобы частичный вывод не сломал протокол `Stop` второго runtime.

## Источник

[targeted-check-reminder.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/targeted-check-reminder.sh),
[change_impact_hooks.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/change_impact_hooks.py)
