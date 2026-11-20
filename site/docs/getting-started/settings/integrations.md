# Интеграции

`.harness/integrations.json` учитывает конфигурации MCP, plugins, hooks и других интеграций
проекта. Для каждого файла инвентарь хранит runtime, SHA-256 и действие проверки. Интеграцию
подключает native-конфиг runtime, а запись в инвентаре её не включает.

## Кто обновляет файл

Установщик регистрирует hook-конфиги при `harness init`, `adopt` и `update`. При повторной
регистрации он заменяет запись этой интеграции и сохраняет остальные записи. Собственные
интеграции проект вносит в инвентарь сам. Если существующий инвентарь не читается, установщик
не заменяет его пустым и завершается ошибкой: сначала исправьте формат файла.

При обновлении hooks установщик добавляет управляемые записи к настройкам пользователя и не
заменяет native-конфиг целиком. `managed_entries` хранит отпечатки handlers, которые harness
записал раньше. По ним установщик отличает устаревшую запись harness от правки пользователя.
Подробности в разделе [установка и обновление hooks](../../hooks/install-and-update.md).

## Структура и ограничения

На верхнем уровне лежит объект с `schema: 1` и массивом `integrations`. Каждая запись в массиве тоже объект:

| Поле | Правило проверки |
| --- | --- |
| `id` | Непустая строка, уникальная в инвентаре. |
| `kind` | Одно из `mcp`, `plugin`, `hook`, `runtime-setting`, `other`. |
| `runtimes` | Непустой массив строк с именами runtime. Валидатор не задаёт закрытого списка имён. |
| `config` | Непустой относительный путь внутри проекта, без сегментов `..`. Файл должен существовать. |
| `sha256` | 64 строчных шестнадцатеричных символа. Хэш должен совпадать с байтами файла `config`. |
| `secret_refs` | Массив имён переменных по шаблону `[A-Z][A-Z0-9_]*`. Поле можно опустить, тогда список пуст. Значения секретов сюда не записывают. |
| `verify` | Строка, непустая после удаления пробелов по краям: действие, которым проверяют интеграцию. |
| `managed_entries` | Необязательный массив уникальных SHA-256, каждый отпечаток из 64 строчных шестнадцатеричных символов. Для hooks его пишет установщик. |

`files.integrations` проверяет форму `verify`, но не выполняет записанное действие. В `secret_refs`
проверка тоже смотрит только на имена: есть ли переменные и доступен ли внешний сервис, она не
проверяет.

## Какие native-конфиги нужно учитывать

Валидатор ищет в корне проекта эти файлы. Для каждого найденного файла нужна запись с этим путём
в `config`:

- `.mcp.json`
- `.claude/settings.json`
- `.claude/settings.local.json`
- `.codex/hooks.json`
- `.kimi/mcp.json`
- `opencode.json`
- `opencode.jsonc`

Если ни одного из этих файлов нет, проверка не считает ошибкой отсутствие инвентаря.
В `config` можно указывать и другие пути.

## Пример записи

Пример учитывает `.claude/settings.json`, в котором ровно `{}` и перевод строки LF.
Это только пример инвентаря: заменять свой конфиг пустым объектом не нужно.

```json {.ah-code-wrap}
{
  "schema": 1,
  "integrations": [
    {
      "id": "claude-settings",
      "kind": "runtime-setting",
      "runtimes": ["claude"],
      "config": ".claude/settings.json",
      "sha256": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
      "secret_refs": [],
      "verify": "Review the project settings in Claude Code"
    }
  ]
}
```

Для своего файла вычислите хэш его текущих байтов:

```bash {.ah-code-wrap}
python3 -c 'import hashlib, pathlib; print(hashlib.sha256(pathlib.Path(".claude/settings.json").read_bytes()).hexdigest())'
```

## Проверка и исправление ошибок

Если CLI установлен, из каталога проекта выполните:

```bash {.ah-code-wrap}
harness health .
```

Из исходников harness та же проверка запускается так: `python3 harness/bin/harness.py health <repo>`.
Результат показывает проверка `files.integrations`. Без lock-файла проекта она получает `skipped`.

| Диагностика | Что проверить |
| --- | --- |
| `project integrations are not inventoried` | Добавьте запись для каждого перечисленного native-конфига. |
| `file is missing` | Проверьте путь `config` и наличие файла. |
| `hash mismatch` | Просмотрите diff native-конфига. Если изменение верное, обновите `sha256`. Для управляемых hooks используйте `harness update`. |
| Ошибка поля записи | Сверьте запись с таблицей ограничений выше. |

Затем выполните действие `verify` самой интеграции: успешный health не означает, что внешний
сервис доступен.

## Настройка с агентом {#agent-setup}

??? quote ah-skill-text "Промпт для агента: учесть интеграции проекта"

    ```text
    Help me configure the project integration inventory.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/integrations.json if present, the installed integrations validator,
    hook installation/update guide and runtime discovery documentation. Inspect native config
    file names and existing inventory metadata without printing authentication values.
    Never read auth files or request, print, copy or store token/key values.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Ask which existing MCP/plugin/hook/runtime-setting should be recorded, for which runtimes
    and what exact verification action confirms it. Inventory registration does not activate
    an integration or perform login. Use only actual repository-relative config paths.
    Explain schema: 1, unique IDs, allowed kinds and SHA-256 of current config bytes.
    Ask for variable NAMES only in secret_refs; this neither exports variables nor verifies auth.
    Treat managed_entries as installer-owned fingerprints; do not fabricate them or reset hashes
    merely to silence health. For managed hooks, propose the supported update procedure separately.
    Preserve existing native config and unrelated inventory entries. If an existing inventory
    is malformed, report it and propose a repair rather than replacing it with an empty list.
    Show the exact proposed diff and why each entry is needed. Include hashes, never config
    contents that could contain secrets. Wait for approval, then apply only that inventory diff
    with Edit/Write. Run harness health and inspect files.integrations. A skipped check is not
    a pass; explain missing prerequisites. Ask separately before executing verify actions,
    connecting services or changing native settings. Report checks and unresolved activation.
    Do not install plugins, enable MCP servers, change credentials or permissions, run updates,
    change Git, commit or open a PR as part of inventory registration.
    ```

## Связанные настройки

- [Секреты и токены](secrets.md): где хранить значения и как передавать их контейнеру.
- [Контейнер](container.md): как настроить передачу переменных и сетевой доступ.
- [Зависимости и окружение](environment.md): инструменты хоста и worker-образа.
- [Обнаружение runtime](../../runtime-discovery.md): native roots и маршруты скиллов.
