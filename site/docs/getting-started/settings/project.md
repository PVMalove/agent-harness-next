# project.json

`.harness/project.json` задаёт соглашения проекта: язык отчётов, ветки, QA-команды, трекер,
тестовую зону, политику hooks и локальную память. Файл не заменяет
[`orchestration.json`](orchestration/index.md), который описывает роли и исполнение задач.

## Настроить project.json с агентом {#agent-setup}

??? quote ah-skill-text "Промпт для агента: базовые поля и ветки"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Configure only language, base_branch and branch_pattern from the installed schema.
    Read actual branch/CI conventions; ask for unresolved choices. Preserve the repository layout
    and existing branch policy. Do not create or switch branches as part of editing metadata.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: QA gate и shell"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Find real lint/build/test commands in manifests and CI. Ask which belong in qa_gate_commands
    and which shell is intended, including native Windows behavior. Do not invent a make target.
    Explain that configuration validation does not execute those checks; ask before actual QA.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: трекер и CI"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Derive tracker type/host/project from repository evidence, then ask about unresolved choices.
    Agree on ci_required_checks from actual workflow/check names, not guessed labels.
    Never request tokens; online checks/login/permission changes need separate authorization.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: тесты и test-author"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether test-author is wanted. Read its dedicated guide before proposing test_paths,
    test_runner command/build/database or the optional short-route test_author profile.
    Use existing literal test directories and one separate {test_id} argument. Distinguish approved
    developer inheritance from the explicit short profile. Do not promise unsupported runtimes.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: политика hooks"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read current hook_policy and installed profile rules. Ask about required warnings/escalation
    paths while preserving critical guards and user hooks. Never lower protection to hide failures.
    Explain how supported hook updates preserve managed fingerprints; do not hand-edit generated policy.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: story points и память"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask separately whether story_points routing and memory/memory_policy are needed.
    Use only supported thresholds, runtime/model choices and allowlisted source types/paths.
    Explain retrieval limits and redaction before opting in; do not index private material by default.
    Preserve unresolved decisions instead of filling every optional field.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Где лежит и когда появляется

Файл создаётся из шаблона при `harness init`, `adopt` или `update` для сборки, включающей
настройки проекта (`engineering-suite` и расширяющий её `backend-orchestration`), если его ещё
нет. Дальше значения ведёт проект. Рядом устанавливается `.harness/project.schema.json`;
ссылка для редактора — `"$schema": "./project.schema.json"`.

Если файла нет, `harness health` не сообщает об ошибке отсутствия. Если файл есть,
он должен быть JSON-объектом с обязательными полями `language`, `base_branch`, `branch_pattern`
и `qa_gate_commands`. Неизвестные ключи запрещены, в том числе во вложенных объектах.

## Как читать справочник

В таблицах две колонки: поле и его контракт — тип, ограничения, влияние и пример, где он полезен.
Путь вроде `test_runner.database.ready_command` обозначает вложенное поле; `[]` — элемент массива.

Схема не объявляет значений `default`. Значения в полном примере и шаблоне установщика —
выбранные настройки, а не универсальные defaults. Поведение при отсутствии необязательных
полей указано отдельно.

## Поля верхнего уровня

| Поле | Контракт |
| --- | --- |
| `$schema` | Необязательная строка для редактора, обычно `./project.schema.json`. Код harness это поле не читает. |
| `language` | Обязательная строка: `ru` или `en`. Язык отчётов code-review и шаблона тела PR. |
| `base_branch` | Обязательная непустая строка. Ветка выпуска/база проекта: от неё `/to-spec` создаёт integration-ветку эпика; без эпика она служит резервной базой. Пример: `main`. |
| `branch_pattern` | Обязательная непустая строка с корректным регулярным выражением для имени issue-ветки. Проверяется branch hooks. Пример: `^feature/issue-[0-9]+-.+`. |
| `qa_gate_commands` | Обязательный массив строк; по схеме каждая строка непустая. QA gate выполняет команды по порядку. Пустой массив допустим как конфигурация, но qa-gate останавливается и просит указать проверки. |
| `shell` | Необязательная строка: `bash` или `powershell`. Если отсутствует, qa-gate использует `bash`. |
| `tracker` | Необязательный объект явного выбора трекера. Внутри обязателен `tracker.type`; для GitHub/GitLab также нужны host и project. |
| `ci_required_checks` | Необязательный массив уникальных непустых имён CI-проверок. Все должны пройти для принятия CI evidence через `integration collect-ci`. Если список пуст или отсутствует, остаётся локальный QA. |
| `test_paths` | Необязательный непустой массив уникальных относительных glob-шаблонов без сегментов `..`. Зона записи test-author; для активации также нужен runner и успешный preflight. |
| `test_runner` | Необязательный объект изолированного запуска одного теста. Внутри обязателен `test_runner.command`; build и database подключаются отдельно. |
| `test_author` | Необязательный объект исполнителя короткого `/fast-implement`: runtime, model и effort задаются явно. Полный маршрут использует выбор из утверждённого brief developer. |
| `hook_policy` | Необязательный объект с обязательным profile и необязательными escalations. Без всего объекта применяется профиль `standard`. |
| `story_points` | Необязательный объект шкалы и порогов маршрутизации. При наличии нужны все четыре вложенных поля. Без объекта маршрутизация по story points не настроена. |
| `memory` | Необязательный объект с единственным обязательным полем `memory.enabled`. Без объекта память выключена. |
| `memory_policy` | Необязательный объект отбора источников, редактирования чувствительных данных и бюджета памяти. При наличии нужны все шесть полей. |

`shell: bash` запускает QA-команду через `bash -lc`; `shell: powershell` — через
`powershell -NoProfile -NonInteractive -Command`. Для native Windows выбирайте подходящую
оболочку явно: `bash` в `PATH` может оказаться запускателем WSL. Команда runner тестов ниже
остаётся argv без shell независимо от `shell`.

Если `project.json` отсутствует целиком, branch hooks используют встроенный шаблон
`^feature/issue-[0-9]+-.+`. Пустое `branch_pattern` в существующем файле этот fallback не включает.

## Трекер: tracker

| Поле | Контракт |
| --- | --- |
| `tracker.type` | Обязательная строка внутри объекта: `github`, `gitlab` или `local`. `local` выбирает markdown-трекер без online-проверок. |
| `tracker.host` | Строка, обязательная для `github` и `gitlab`: hostname с необязательным портом. Без схемы URL, пути и userinfo. Пример: `gitlab.example.test:4443`. |
| `tracker.project` | Строка, обязательная для `github` и `gitlab`: полный путь минимум из двух сегментов, без начального/конечного `/`. Сегменты допускают латинские буквы, цифры, `_`, `.`, `-`. Пример: `group/sub/project`. |

Корректный явный `tracker` определяет выбор трекера для health. Если объекта нет, трекер
выводится из `origin`, а health предупреждает и предлагает конфигурацию. Сертификаты, прокси
и учётные данные остаются в личных настройках CLI трекера.

## Тестовая зона и runner

`test_paths` принимает, например, `tests/**`. Для активации test-author этого недостаточно:
изолированный runner разрешает только существующие зоны `<каталог>/**` с литеральными
сегментами, без symlink, вложенных друг в друга зон и запрещённых служебных каталогов.
Шаблон `tests/*.py` может пройти конфигурационный health, но получить `write_zone_rejected`
на preflight. Полные условия — в [руководстве test-author](../../agents/test-author.md).

| Поле | Контракт |
| --- | --- |
| `test_runner.command` | Массив минимум из двух непустых строк: программа и аргументы. Ровно один элемент равен `{test_id}`, и он не первый. Runner заменяет его выбранным ID как одним аргументом; shell-подстановка не выполняется. Пример: `["python3", "-m", "unittest", "{test_id}"]`. |

Без `test_paths` или `test_runner` тест-автор не активируется; отсутствие этих необязательных
полей само по себе не делает конфиг невалидным. Успешный health не заменяет preflight изоляции.

### Сборка перед тестом: test_runner.build

Внутри необязательного объекта обязательны оба поля:

| Поле | Контракт |
| --- | --- |
| `test_runner.build.command` | Непустой argv из непустых строк, без NUL и без `{test_id}` даже внутри аргумента. Сборка выполняется без shell в песочнице. |
| `test_runner.build.artifact_paths` | Непустой массив уникальных относительных `<каталог>/**`. До завершающего `/**` — литеральные сегменты без glob-метасимволов, `.`/`..`, обратных слешей и управляющих символов. |

Каталоги артефактов заранее существуют и пусты. Runner монтирует свежие каталоги запуска:
при сборке на запись, при тесте только на чтение. Исходники и тестовая зона во время сборки
доступны только на чтение. Непустые каталоги runner отклоняет, а не очищает.

### Тестовая БД: test_runner.database

Внутри необязательного объекта обязательны все четыре поля:

| Поле | Контракт |
| --- | --- |
| `test_runner.database.engine` | Строка по шаблону `[a-z][a-z0-9_-]{0,63}`: имя production-движка. Это идентификатор, а не закрытый enum названий БД. |
| `test_runner.database.test_ids` | Непустой массив уникальных непустых селекторов `fnmatchcase`, без NUL; строки только из пробелов недопустимы. БД получают только совпавшие тесты. |
| `test_runner.database.command` | Непустой argv из непустых строк, без NUL и `{test_id}`. Запускает сервер в foreground внутри песочницы. |
| `test_runner.database.ready_command` | Непустой argv с теми же ограничениями; проверяет готовность отдельной БД перед тестом. |

Сервер и проверка готовности получают `HARNESS_TEST_DATABASE_DIR` и
`HARNESS_TEST_DATABASE_SOCKET_DIR`. Их читает wrapper проекта; shell-подстановка в argv
не выполняется. Подробнее — [сборка и тестовая БД](../../hooks/run-test.md).

## Исполнитель короткого маршрута: test_author

Внутри объекта обязательны все три поля; неявного runtime, модели или effort нет.

| Поле | Контракт |
| --- | --- |
| `test_author.runtime` | Строка по шаблону `[A-Za-z0-9][A-Za-z0-9_-]*`. ID выбранного runtime; отсутствие защищённого адаптера даёт отказ, а не переключение на другой CLI. |
| `test_author.model` | Строка по шаблону `[A-Za-z0-9][A-Za-z0-9._:-]*`. Явный CLI ID модели или alias без пробелов. |
| `test_author.effort` | Строка: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` или `ultra`. Допустимое значение контракта ещё не доказывает поддержку выбранным CLI. |

Короткий `/fast-implement` читает этот профиль. Полный `/implement` наследует
`resolved_runtime`, `resolved_model`, `resolved_effort` из утверждённого brief developer;
при ошибке brief он не откатывается к профилю проекта. Значения примера ниже — явный выбор,
не рекомендация модели и не defaults. В профиль не записывают секреты.

## Политика hooks: hook_policy

| Поле | Контракт |
| --- | --- |
| `hook_policy.profile` | Обязательная строка внутри объекта: `minimal`, `standard` или `strict`. Базовый профиль hooks. |
| `hook_policy.escalations[].paths` | Непустой массив уникальных относительных glob-шаблонов без `..`. Совпадение затронутого пути включает эскалацию; `*` и `?` в семантике fnmatch могут пересекать `/`. |
| `hook_policy.escalations[].roles` | Непустой массив уникальных ролей: `developer`, `review`, `qa`, `coordinator`. Ограничивает применение эскалации ролями. |
| `hook_policy.escalations[].profile` | Обязательная строка каждой эскалации: `minimal`, `standard` или `strict`. Не может быть слабее базового профиля; это дополнительно проверяет health. |

Каждая эскалация задаёт `paths` или `roles` либо оба поля. Coordinator требует совпадения всех
заданных условий и выбирает самый строгий применимый профиль. При формировании advisory-ответов
hooks используют самый строгий профиль из базового и всех эскалаций. Критические guards
действуют при любом профиле, включая `minimal`.
Переменная `HOOK_PROFILE` и параметры инструментов не переопределяют этот объект; hook
`protect-hook-policy` запрещает агентским инструментам его менять. Правку политики выполняет
владелец проекта. См. [установку и обновление hooks](../../hooks/install-and-update.md).

## Оценка задач: story_points

При наличии объекта все поля обязательны. Он доступен без capability `backend-orchestration`.

| Поле | Контракт |
| --- | --- |
| `story_points.scale` | Непустой массив целых чисел от 1. Шкала для to-tickets; шаблон использует `[1, 2, 3, 5, 8, 13, 21]`. Валидатор не требует строго последовательность Фибоначчи. |
| `story_points.fast_threshold` | Целое число. Оценка не выше порога предлагает `pipeline::fast`; в шаблоне `3`. |
| `story_points.full_threshold` | Целое число. Оценка не ниже порога предлагает `pipeline::full`; в шаблоне `5`. |
| `story_points.gray_zone` | Целое число для второго консультативного прохода оценки между порогами; в шаблоне `4`. |

Согласуйте шкалу и порядок порогов сами: текущая схема и валидатор проверяют типы этих чисел,
но не доказывают согласованность маршрутизации.

## Локальная память: memory и memory_policy

| Поле | Контракт |
| --- | --- |
| `memory.enabled` | Boolean: `true` или `false`. Включение памяти; без объекта `memory` используется `false`. Одного `true` недостаточно без разрешённых источников и путей. |
| `memory_policy.source_types` | Массив строк: `adr`, `glossary`, `task_archive`, `qa_finding`, `completion_report`, `ledger`. Пустой список не разрешает никакие источники. |
| `memory_policy.allow_paths` | Массив непустых относительных POSIX-шаблонов. Нельзя абсолютные пути, `:`, обратный слеш, пустые сегменты, `.`/`..` и завершающий `/`. Пустой список не разрешает никакие пути. |
| `memory_policy.redact_rules` | Массив корректных регулярных выражений длиной 1–512 символов каждое. Может быть пустым. |
| `memory_policy.min_similarity` | Конечное число от 0 до 1. Поле зарезервировано для cosine-vector поиска; сейчас не фильтрует ранги FTS5. |
| `memory_policy.top_k` | Целое число от 1: предел количества возвращаемых указателей памяти. |
| `memory_policy.max_tokens` | Целое число от 1: бюджет памяти в токенах. |

Если `memory_policy` отсутствует целиком, парсер использует пустые `source_types`, `allow_paths`
и `redact_rules`, `min_similarity: 0`, `top_k: 5`, `max_tokens: 1000`. Это поведение парсера,
не `default` схемы. Если объект указан, нужны все шесть полей. Память активна только при
`memory.enabled: true` и непустых списках `source_types` и `allow_paths`.

## Полный пример

Цельный пример ниже использует русский язык отчётов, локальный трекер и runner unittest.
Он не включает необязательные build/database и не гарантирует готовность test-author:
каталог `tests` должен существовать, а preflight — подтвердить адаптер и изоляцию.
Замените ветку, команды и профиль исполнителя настройками своего проекта.

```json {.ah-code-wrap}
{
  "$schema": "./project.schema.json",
  "language": "ru",
  "base_branch": "main",
  "branch_pattern": "^feature/issue-[0-9]+-.+",
  "qa_gate_commands": ["python3 -m unittest discover"],
  "shell": "bash",
  "tracker": {"type": "local"},
  "ci_required_checks": [],
  "test_paths": ["tests/**"],
  "test_runner": {
    "command": ["python3", "-m", "unittest", "{test_id}"]
  },
  "test_author": {
    "runtime": "claude",
    "model": "sonnet",
    "effort": "high"
  },
  "hook_policy": {"profile": "standard"},
  "story_points": {
    "scale": [1, 2, 3, 5, 8, 13, 21],
    "fast_threshold": 3,
    "full_threshold": 5,
    "gray_zone": 4
  },
  "memory": {"enabled": false},
  "memory_policy": {
    "source_types": [],
    "allow_paths": [],
    "redact_rules": [],
    "min_similarity": 0,
    "top_k": 5,
    "max_tokens": 1000
  }
}
```

## Проверка

После правки выполните из каталога проекта, если CLI установлен:

```bash {.ah-code-wrap}
harness health .
harness health . --json
```

Из исходников harness эквивалент — `python3 harness/bin/harness.py health <repo>`.
Команда без `--fix` ничего не исправляет. Проверка `files.project_json` сообщает ошибки формы
и бизнес-правил; JSON-режим печатает машиночитаемый отчёт. Если в отчёте есть `fail`, команда
завершается кодом 1. Исправляйте указанное поле и повторяйте проверку; не подменяйте её успех
пустым списком QA-команд. Для test-author отдельно нужен preflight из руководства роли.

Схема помогает редактору и мастеру консоли; health дополняет её бизнес-правилами, например
ровно одним `{test_id}` и запретом понижения hook-профиля.

## Дальше

- [Все настройки проекта](index.md)
- [Настройки test-author](test-author.md)
- [Руководство test-author](../../agents/test-author.md)
- [Backend-оркестрация](../../backend-orchestration.md)
