# Инвентаризация и адаптеры агентов

`harness inventory <repo> --json` показывает ожидаемый источник каждой поставляемой версии
скилла, выбравшие его capability, путь в проекте и дрейф файлов по категориям `harness diff`.
В `hooks` и `templates` перечислены файлы хуков, нативные настройки runtime и файлы, поставляемые
как проектные шаблоны. Каждый элемент показывает путь, источник и состояние относительно
шаблона. Для файлов проекта без поставляемого источника `package_source` равен `null`.
Версия контракта указана в `schema_version`.

## Локальный MCP

Настройте MCP-клиент на команду `harness mcp /absolute/path/to/repo` с транспортом stdio.
Сервер предоставляет инструменты для чтения:

- `skill_inventory` возвращает инвентарь скиллов. Аргумент `name` фильтрует по имени.
- `artifact_inventory` возвращает полный инвентарь CLI. Аргумент `kind` выбирает
  `skills`, `hooks` или `templates`.
- `repo_map` принимает полный `commit` и необязательный путь `seed`. Использует совпадающий
  кэш полной карты, а при его отсутствии строит карту путей без создания кэша или установки
  парсера.
- `context_package` читает уже зарегистрированный пакет по `batch_id` и `package_id`. Аргумент
  `section` выбирает `summary` (по умолчанию), `diff`, `symbol_graph`, `file_hashes` или `full`.
- `accepted_qa` принимает `ticket`, `branch` и полный `candidate_commit`. Возвращает SHA,
  ID батча и результат принятого QA. Если хранилищем управляет `harness-runtime`, чтение
  требует работающего локального сервиса.

MCP не запускает проверки. Размер каждого сообщения ограничен 1 МиБ.

## Runtime Events

`harness runtime-events . --list-adapters` показывает нативные пути, правила загрузки скиллов
и возможность совместной установки. Для регистрации команд создайте
`.harness/runtime-events.json` в целевом проекте:

```json
{
  "runtimes": ["claude", "codex", "cursor"],
  "events": {
    "session_start": ["python scripts/log_session_start.py"]
  }
}
```

Выполните `harness runtime-events .`. Поддерживаются `session_start`, `session_end` и
`stop`. Адаптеры пишут в `.claude/settings.json`, `.codex/hooks.json` и
`.cursor/hooks.json`. Команда получает нативный JSON своего runtime через stdin. Если
Cursor уже импортирует события Claude Code, выберите одну регистрацию событий для Cursor.

Чтобы отключить запись, уберите команду или runtime из манифеста и повторите синхронизацию.
Чтобы отключить все записи, удалите манифест и повторите синхронизацию. Harness удаляет
только неизменённые записи из своего файла владения `.harness/runtime-events.lock.json`.
При хранении нативных конфигов в Git храните этот файл вместе с ними.

## Явный вызов скилла

```bash
harness update . --no-model-invocation qa-gate
harness update . --clear-no-model-invocation qa-gate
```

Повторите флаг для каждого скилла. `init` и `adopt` принимают те же параметры.
Harness записывает выбор в `harness.lock` и устанавливает нативную настройку Claude Code
и Cursor в `SKILL.md`, а настройку Codex в `agents/openai.yaml`. Скиллы с исходным
запретом, включая `to-pull-requests`, сохраняют его после очистки переопределения.
Подтверждение перед открытием PR по-прежнему требуется.
