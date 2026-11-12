# Troubleshooting

Страница перечисляет сообщения, которые печатают установщик, CLI и hooks, их причину и действие.
Если сообщения нет в таблице, следующий шаг — `harness health <repo>`: он показывает, что именно не
настроено, и часто сам печатает команду исправления.

## Установка и обновление

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `harness requires Python 3.12+` | Версия Python ниже поддерживаемой | Обновить Python: CLI и установщик не запускаются на старых версиях |
| `python: The term 'python' is not recognized` в PowerShell | В `PATH` нет `python` или `py` | Проверить переменную `Path`, открыть новое окно терминала или вызвать интерпретатор полным путём |
| `not a Git repository: <path>` | `init`, `adopt` или `update` запущены на каталоге без Git | Выполнить `git init` в целевом каталоге и повторить |
| `project harness already exists; use 'harness update <repo>'` | `init` там, где снимок уже установлен | Запустить `harness update` |
| `project harness is missing; use 'harness init <repo>'` | `update` там, где снимка нет | Запустить `harness init` |
| `selected skill names already exist; inspect them or use --replace-conflicts` | В проекте уже есть скиллы с теми же именами | Посмотреть список конфликтов; если замена ожидаема — повторить с `--replace-conflicts` |
| `local skill changes would be overwritten; review them or use --force` | У managed-файлов есть локальные правки | Изучить расхождения: для снимка — `--force-managed-files`, для снимка и seed-файлов — `--force` |
| `discovery path already exists and is not managed: <path>` | На месте каталога скиллов лежит что-то постороннее | Для `init` — убрать вручную или использовать `adopt`; для `adopt` — `--replace-conflicts`; для `update` — `--force` |
| `install-global.py`: `[CONFLICT] ... (re-run with --replace-conflicts ...)` | Место профиля или симлинка занято | Повторить с `--replace-conflicts`: конфликтующие файлы сначала копируются в backup |
| `install-global.py`: `Failed to create symlink` | Нет прав на создание симлинка каталога | Включить режим разработчика в системе или запустить терминал с повышенными правами |

## Конфигурация проекта

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `.harness/project.json has unknown field(s): <name>` | Поле вне строгого контракта схемы | Удалить поле либо реализовать его сразу в схеме, шаблоне и валидаторе — по отдельности это расхождение |
| `.harness/project.json tracker has unknown field(s): <name>` | Поле внутри `tracker` вне контракта | В `tracker` допустимы только `type`, `host` и `project` |

Допустимые поля верхнего уровня: `$schema`, `language`, `base_branch`, `branch_pattern`,
`qa_gate_commands`, `shell`, `tracker`, `ci_required_checks`, `test_paths`, `test_runner`,
`hook_policy`, `story_points`, `memory`, `memory_policy`.

Сертификаты, прокси и учётные данные в конфигурацию не пишутся: они остаются в личной конфигурации
CLI трекера.

## Hooks и оркестрация

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `Zero Direct Commits: push с целевым рефом '<ref>' запрещён` | Команда обновляет защищённую ветку | Работать в issue-ветке и пушить её; защищённые ветки обновляет человек через merge |
| `Zero Direct Commits: команду с git commit/push не удалось разобрать` | Команда собрана так, что hook не может понять её эффект | Разбить на простые команды без подстановок, скобок и цепочек |
| `правка меняет ключ hook_policy в .harness/project.json` | Агент пытается изменить политику hooks | Политику меняет человек; агенту разрешены правки файла без изменения ключа |
| `настройки hooks (.claude/settings*.json, .codex/hooks.json) и каталоги hooks` | Попытка записи в настройки или каталоги hooks | Эти файлы меняет человек: их содержимое определяет, что вообще блокируется |
| `this repository is in the file-ledger epoch` | Проект ещё не переведён на runtime-store, а команда требует новый epoch | Выполнить `harness-runtime migrate` один раз по [руководству миграции](upgrade-2-0.md) и повторить команду |
| `ledger validate` находит расхождение аудиторской цепочки | Состояние правили в обход CLI или цепочка повреждена | Не редактировать `.harness/orchestration/state/` вручную; прочитать отчёт и решать по маршруту восстановления |

Команды восстановления — `ledger lock-status`, `qa clear-stale-lease`, `batch rewind`,
`dispatch cancel` — не блокируются ни одним профилем hooks: иначе из отказа не выбраться.

## health как первый шаг

`harness health <repo>` без флагов ничего не меняет и показывает проверки файлов, каталогов,
окружения и графа проекта.

- `--fix` создаёт отсутствующие каталоги `.harness/` и пересобирает устаревший реестр скиллов;
  worktree он не трогает.
- `--online` добавляет проверки трекера: авторизацию CLI, доступность remote, права и метки.
- `--json` печатает машиночитаемый отчёт для скриптов.

Каждая строка помечена как `ok`, `warn`, `fail` или `skipped`; на `fail` команда печатает причину и
команду исправления. Группа «Оркестрация» появляется только при установленной
`backend-orchestration`.

## Дальше

- [CLI и конфигурация](../reference/cli.md)
- [QA gate и Release Gate](qa-gate.md)
- [Рабочий поток](workflow.md)
