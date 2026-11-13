# Troubleshooting

Здесь собраны сообщения установщика, CLI и hooks: причина каждого и что делать.
Если сообщения нет в таблице, запустите `harness health <repo>`. Он показывает, что именно не
настроено, и часто сам печатает команду исправления.

## Установка и обновление

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `harness requires Python 3.12+` | Версия Python ниже поддерживаемой | Обновите Python: CLI и установщик не запускаются на старых версиях |
| `python: The term 'python' is not recognized` в PowerShell | В `PATH` нет `python` или `py` | Проверьте переменную `Path`, откройте новое окно терминала или вызовите интерпретатор полным путём |
| `not a Git repository: <path>` | `init`, `adopt` или `update` запущены на каталоге без Git | Выполните `git init` в целевом каталоге и повторите |
| `project harness already exists; use 'harness update <repo>'` | `init` запущен там, где снимок уже установлен | Запустите `harness update` |
| `project harness is missing; use 'harness init <repo>'` | `update` запущен там, где снимка нет | Запустите `harness init` |
| `selected skill names already exist; inspect them or use --replace-conflicts` | В проекте уже есть скиллы с теми же именами | Посмотрите список конфликтов. Если замена ожидаема, повторите с `--replace-conflicts` |
| `update aborted due to local skill changes (drift).` | У managed-файлов есть локальные правки | Изучите расхождения. Чтобы заменить снимок, используйте `--force-managed-files`, снимок и seed-файлы: `--force` |
| `discovery path already exists and is not managed: <path>` | На месте каталога скиллов лежит что-то постороннее | Для `init` уберите его вручную или используйте `adopt`. Для `adopt` повторите с `--replace-conflicts`, для `update` с `--force` или `--force-managed-files` |
| `install-global.py`: `[CONFLICT] ... (re-run with --replace-conflicts ...)` | Место профиля или симлинка занято | Повторите с `--replace-conflicts`: установщик сначала скопирует конфликтующие файлы в backup |
| `install-global.py`: `Failed to create symlink` | Нет прав на создание симлинка каталога | Включите режим разработчика в системе или запустите терминал с повышенными правами |

## Конфигурация проекта

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `.harness/project.json has unknown field(s): <name>` | Поле вне строгого контракта схемы | Удалите поле или добавьте его сразу в схему, шаблон и валидатор. Если добавить только в одно место, контракт разойдётся |
| `.harness/project.json tracker has unknown field(s): <name>` | Поле внутри `tracker` вне контракта | В `tracker` допустимы только `type`, `host` и `project` |

Допустимые поля верхнего уровня: `$schema`, `language`, `base_branch`, `branch_pattern`,
`qa_gate_commands`, `shell`, `tracker`, `ci_required_checks`, `test_paths`, `test_runner`,
`hook_policy`, `story_points`, `memory`, `memory_policy`, `test_author`.

Не записывайте в конфигурацию сертификаты, прокси и учётные данные. Они остаются в личной конфигурации
CLI трекера.

## Hooks и оркестрация

| Сообщение (фрагмент) | Причина | Что делать |
| --- | --- | --- |
| `Zero Direct Commits: push с целевым рефом '<ref>' запрещён` | Команда обновляет защищённую ветку | Работайте в issue-ветке и пушьте её. Защищённые ветки обновляет человек через мерж |
| `Zero Direct Commits: команду с git commit/push не удалось разобрать` | Команда собрана так, что hook не может понять её эффект | Разбейте её на простые команды без подстановок, скобок и цепочек |
| `правка меняет ключ hook_policy в .harness/project.json` | Агент пытается изменить политику hooks | Политику меняет человек. Агент может править файл, если не меняет этот ключ |
| `настройки hooks (.claude/settings*.json, .codex/hooks.json) и каталоги hooks` | Попытка записи в настройки или каталоги hooks | Эти файлы меняет человек: от их содержимого зависит, что вообще блокируется |
| `this repository is in the file-ledger epoch` | Проект ещё не переведён на runtime store, а команде нужен новый epoch | Один раз выполните `harness-runtime migrate` по [руководству миграции](upgrade-2-0.md) и повторите команду |
| `hook_response.py: ожидается 'run <hook_id> <команда...>' с зарегистрированным hook_id` на любом вызове Bash | Новый hook, например `runtime-autostart`, подключён при старом `.claude/hooks/hook_response.py` | Выполните `harness update <repo> --force-seed-file .claude/hooks/hook_response.py`. Команда заменит конверт шаблоном, сохранит прежние байты в `.harness/.sandboxes/seed-backups/` и в том же запуске подключит hook. Обычный `harness update` не подключает hook, который старый конверт не знает. `runtime-autostart` при старом конверте только предупреждает |
| `ledger validate` находит расхождение аудиторской цепочки | Состояние правили в обход CLI или цепочка повреждена | Не редактируйте `.harness/orchestration/state/` вручную. Прочитайте отчёт и выберите маршрут восстановления |

Ни один профиль hooks не блокирует команды восстановления: `ledger lock-status`, `qa clear-stale-lease`,
`batch rewind`, `dispatch cancel` и `ledger release-lock --force`. Иначе из отказа не выбраться.
`ledger release-lock --force` при этом по-прежнему требует approval человека.

## health как первый шаг

`harness health <repo>` без флагов ничего не меняет и показывает проверки файлов, каталогов,
окружения и графа проекта.

- `--fix` создаёт отсутствующие каталоги `.harness/` и пересобирает устаревший реестр скиллов.
  Системные настройки и worktree он не меняет.
- `--online` добавляет проверки трекера: авторизацию CLI, доступность remote, права и метки.
- `--json` печатает машиночитаемый отчёт для скриптов.

Каждая строка помечена как `ok`, `warn`, `fail` или `skipped`. Для `fail` команда печатает причину и
команду исправления. Группа «Оркестрация» появляется, только если установлена
`backend-orchestration`.

## Дальше

- [CLI и конфигурация](../reference/cli.md)
- [QA gate и Release Gate](qa-gate.md)
- [Рабочий поток](workflow.md)
