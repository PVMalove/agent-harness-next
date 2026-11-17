# project.json

`.harness/project.json` задаёт соглашения проекта: язык отчётов, ветки, QA-команды, трекер,
тестовую зону, политику hooks и локальную память. Роли и исполнение задач описывает другой файл,
[`orchestration.json`](orchestration/index.md).

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

Установщик создаёт файл из шаблона при `harness init`, `adopt` или `update`, если файла ещё нет
и сборка включает настройки проекта: `engineering-suite` или расширяющая её `backend-orchestration`.
Дальше значения ведёт проект. Рядом установщик кладёт `.harness/project.schema.json`, редактор
находит её по ссылке `"$schema": "./project.schema.json"`.

Если файла нет, `harness health` не считает это ошибкой. Если файл есть, это должен быть
JSON-объект с обязательными полями `language`, `base_branch`, `branch_pattern` и
`qa_gate_commands`. Неизвестные ключи запрещены, в том числе во вложенных объектах.

## Как читать справочник

В таблицах две колонки: поле и его контракт. Контракт называет тип, ограничения, влияние поля и,
где это помогает, пример. Путь вроде `test_runner.database.ready_command` обозначает вложенное поле,
`[]` обозначает элемент массива.

Схема не объявляет значений `default`. Значения в полном примере и в шаблоне установщика выбраны
для примера и не служат общими значениями по умолчанию. Что происходит без необязательного поля,
описано отдельно у каждого поля.

## Поля верхнего уровня

| Поле | Контракт |
| --- | --- |
| `$schema` | Необязательная строка для редактора, обычно `./project.schema.json`. Код harness это поле не читает. |
| `language` | Обязательная строка: `ru` или `en`. Задаёт язык отчётов code-review и шаблона тела PR. |
| `base_branch` | Обязательная непустая строка. Ветка выпуска и база проекта: от неё `/to-spec` создаёт integration-ветку эпика. Если эпика нет, задачи строятся от этой ветки. Пример: `main`. |
| `branch_pattern` | Обязательная непустая строка с корректным регулярным выражением для имени issue-ветки. Имя ветки по нему проверяют branch hooks. Пример: `^feature/issue-[0-9]+-.+`. |
| `qa_gate_commands` | Обязательный массив строк, по схеме каждая строка непустая. QA gate выполняет команды по порядку. Пустой массив схема допускает, но qa-gate на нём останавливается и просит указать проверки. |
| `shell` | Необязательная строка: `bash` или `powershell`. Если отсутствует, qa-gate использует `bash`. |
| `tracker` | Необязательный объект, который явно выбирает трекер. Внутри обязателен `tracker.type`, для GitHub и GitLab нужны ещё host и project. |
| `ci_required_checks` | Необязательный массив уникальных непустых имён CI-проверок. `integration collect-ci` принимает CI evidence, только если прошли все эти проверки. Если список пуст или его нет, работает только локальный QA. |
| `test_paths` | Необязательный непустой массив уникальных относительных glob-шаблонов без сегментов `..`. Задаёт зону записи test-author. Чтобы test-author включился, нужны ещё runner и успешный preflight. |
| `test_runner` | Необязательный объект, который описывает изолированный запуск одного теста. Внутри обязателен `test_runner.command`, build и database подключаются отдельно. |
| `test_author` | Необязательный объект: исполнитель test-author в коротком `/fast-implement`. runtime, model и effort задаются явно. Полный маршрут берёт выбор из утверждённого brief developer. |
| `hook_policy` | Необязательный объект с обязательным profile и необязательными escalations. Если объекта нет, действует профиль `standard`. |
| `story_points` | Необязательный объект со шкалой и порогами маршрутизации. Если объект есть, нужны все четыре вложенных поля. Без объекта маршрутизация по story points не настроена. |
| `memory` | Необязательный объект с единственным обязательным полем `memory.enabled`. Без объекта память выключена. |
| `memory_policy` | Необязательный объект: какие источники брать в память, что скрывать из чувствительных данных и какой бюджет у памяти. Если объект есть, нужны все шесть полей. |

С `shell: bash` qa-gate запускает QA-команду через `bash -lc`, с `shell: powershell` через
`powershell -NoProfile -NonInteractive -Command`. На native Windows выберите оболочку явно:
`bash` в `PATH` может оказаться запускателем WSL. Команду runner тестов (ниже) harness
запускает как argv без shell при любом значении `shell`.

Если `project.json` нет, `branch_pattern` в нём не задан или пуст, branch hooks используют
встроенный шаблон `^feature/issue-[0-9]+-.+`.

## Трекер: tracker

| Поле | Контракт |
| --- | --- |
| `tracker.type` | Обязательная строка внутри объекта: `github`, `gitlab` или `local`. `local` выбирает markdown-трекер без online-проверок. |
| `tracker.host` | Строка, обязательная для `github` и `gitlab`: hostname, можно с портом. Без схемы URL, пути и userinfo. Пример: `gitlab.example.test:4443`. |
| `tracker.project` | Строка, обязательная для `github` и `gitlab`: полный путь минимум из двух сегментов, без `/` в начале и в конце. В сегментах допустимы латинские буквы, цифры, `_`, `.`, `-`. Пример: `group/sub/project`. |

Если `tracker` задан корректно, health берёт трекер из него. Если объекта нет, health определяет
трекер по `origin`, предупреждает и предлагает конфигурацию. Сертификаты, прокси и учётные данные
остаются в личных настройках CLI трекера.

## Тестовая зона и runner

`test_paths` принимает, например, `tests/**`. Но чтобы включить test-author, этого мало.
Изолированный runner принимает только существующие зоны вида `<каталог>/**` с литеральными
сегментами. Зона не может быть symlink, лежать внутри другой зоны или быть запрещённым служебным
каталогом. Шаблон `tests/*.py` может пройти проверку конфигурации в health, но preflight откажет
с `write_zone_rejected`. Полные условия описаны в [руководстве test-author](../../agents/test-author.md).

| Поле | Контракт |
| --- | --- |
| `test_runner.command` | Массив минимум из двух непустых строк: программа и аргументы. Ровно один элемент равен `{test_id}`, и он не первый. Runner подставляет на его место выбранный ID одним аргументом, без shell-подстановки. Пример: `["python3", "-m", "unittest", "{test_id}"]`. |

Без `test_paths` или `test_runner` test-author не включается, но конфиг без этих необязательных
полей остаётся валидным. Успешный health не заменяет preflight изоляции.

### Сборка перед тестом: test_runner.build

Внутри необязательного объекта обязательны оба поля:

| Поле | Контракт |
| --- | --- |
| `test_runner.build.command` | Непустой argv из непустых строк, без NUL и без `{test_id}` даже внутри аргумента. Runner запускает сборку в песочнице без shell. |
| `test_runner.build.artifact_paths` | Непустой массив уникальных относительных `<каталог>/**`. До завершающего `/**` идут литеральные сегменты без glob-метасимволов, `.`/`..`, обратных слешей и управляющих символов. |

Каталоги артефактов должны существовать заранее и быть пустыми. Runner монтирует на их место
свежие каталоги запуска: при сборке на запись, при тесте только на чтение. Исходники и тестовая
зона во время сборки доступны только на чтение. Непустой каталог runner не очищает, а отклоняет.

### Тестовая БД: test_runner.database

Внутри необязательного объекта обязательны все четыре поля:

| Поле | Контракт |
| --- | --- |
| `test_runner.database.engine` | Строка по шаблону `[a-z][a-z0-9_-]{0,63}`: имя production-движка. Это свободный идентификатор, список допустимых названий БД не задан. |
| `test_runner.database.test_ids` | Непустой массив уникальных непустых селекторов `fnmatchcase`, без NUL и не из одних пробелов. БД получают только тесты, которые совпали с селектором. |
| `test_runner.database.command` | Непустой argv из непустых строк, без NUL и `{test_id}`. Запускает сервер БД в foreground внутри песочницы. |
| `test_runner.database.ready_command` | Непустой argv с теми же ограничениями. Перед тестом проверяет, что отдельная БД готова. |

Сервер и проверка готовности получают переменные `HARNESS_TEST_DATABASE_DIR` и
`HARNESS_TEST_DATABASE_SOCKET_DIR`. Их читает wrapper проекта: runner не подставляет переменные
в argv через shell. Подробнее в разделе [сборка и тестовая БД](../../hooks/run-test.md).

## Исполнитель короткого маршрута: test_author

Внутри объекта обязательны все три поля. Runtime, модель и effort по умолчанию не подставляются.

| Поле | Контракт |
| --- | --- |
| `test_author.runtime` | Строка по шаблону `[A-Za-z0-9][A-Za-z0-9_-]*`: ID выбранного runtime. Если защищённого адаптера для него нет, test-author отказывает и не переключается на другой CLI. |
| `test_author.model` | Строка по шаблону `[A-Za-z0-9][A-Za-z0-9._:-]*`: ID модели в CLI или alias без пробелов. |
| `test_author.effort` | Строка: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` или `ultra`. Значение из контракта выбранный CLI может и не поддерживать. |

Короткий `/fast-implement` читает этот профиль. Полный `/implement` берёт `resolved_runtime`,
`resolved_model` и `resolved_effort` из утверждённого brief developer. Если brief с ошибкой,
`/implement` не переходит на профиль проекта. Значения в примере ниже выбраны для примера: это не
рекомендация модели и не значения по умолчанию. Секреты в профиль не записывают.

## Политика hooks: hook_policy

| Поле | Контракт |
| --- | --- |
| `hook_policy.profile` | Обязательная строка внутри объекта: `minimal`, `standard` или `strict`. Задаёт базовый профиль hooks. |
| `hook_policy.escalations[].paths` | Непустой массив уникальных относительных glob-шаблонов без `..`. Если затронутый путь совпал с шаблоном, эскалация включается. `*` и `?` работают как в fnmatch и могут захватывать `/`. |
| `hook_policy.escalations[].roles` | Непустой массив уникальных ролей: `developer`, `review`, `qa`, `coordinator`. Эскалация действует только для этих ролей. |
| `hook_policy.escalations[].profile` | Обязательная строка в каждой эскалации: `minimal`, `standard` или `strict`. Профиль не может быть слабее базового, это дополнительно проверяет health. |

Каждая эскалация задаёт `paths`, `roles` или оба поля. Coordinator применяет эскалацию, только
если совпали все её условия, и выбирает самый строгий из применимых профилей. Для advisory-ответов
hooks берут самый строгий профиль из базового и всех эскалаций. Критические guards действуют при
любом профиле, включая `minimal`. Переменная `HOOK_PROFILE` и параметры инструментов этот объект
не переопределяют, а hook `protect-hook-policy` не даёт инструментам агента его менять. Политику
правит владелец проекта. Подробнее в разделе [установка и обновление hooks](../../hooks/install-and-update.md).

## Оценка задач: story_points

Если объект есть, все его поля обязательны. Объект работает и без capability `backend-orchestration`.

| Поле | Контракт |
| --- | --- |
| `story_points.scale` | Непустой массив целых чисел от 1: шкала для to-tickets. В шаблоне `[1, 2, 3, 5, 8, 13, 21]`. Валидатор не требует, чтобы это была именно последовательность Фибоначчи. |
| `story_points.fast_threshold` | Целое число. Для оценки не выше порога to-tickets предлагает `pipeline::fast`. В шаблоне `3`. |
| `story_points.full_threshold` | Целое число. Для оценки не ниже порога to-tickets предлагает `pipeline::full`. В шаблоне `5`. |
| `story_points.gray_zone` | Целое число: оценка строго между порогами, на которой to-tickets делает второй, консультативный проход оценки. В шаблоне `4`. |

Согласуйте шкалу и порядок порогов сами: схема и валидатор проверяют только типы этих чисел,
а не то, что пороги согласованы между собой.

## Локальная память: memory и memory_policy

| Поле | Контракт |
| --- | --- |
| `memory.enabled` | Boolean: `true` или `false`. Включает память. Без объекта `memory` действует `false`. Одного `true` мало: нужны ещё разрешённые источники и пути. |
| `memory_policy.source_types` | Массив строк: `adr`, `glossary`, `task_archive`, `qa_finding`, `completion_report`, `ledger`. Пустой список не разрешает ни одного источника. |
| `memory_policy.allow_paths` | Массив непустых относительных POSIX-шаблонов. Запрещены абсолютные пути, `:`, обратный слеш, пустые сегменты, `.`/`..` и `/` в конце. Пустой список не разрешает ни одного пути. |
| `memory_policy.redact_rules` | Массив корректных регулярных выражений длиной 1–512 символов каждое. Может быть пустым. |
| `memory_policy.min_similarity` | Конечное число от 0 до 1. Поле зарезервировано для векторного поиска по косинусной близости. Сейчас оно не фильтрует ранги FTS5. |
| `memory_policy.top_k` | Целое число от 1: сколько указателей памяти вернуть самое большее. |
| `memory_policy.max_tokens` | Целое число от 1: бюджет памяти в токенах. |

Если `memory_policy` нет целиком, парсер берёт пустые `source_types`, `allow_paths`
и `redact_rules`, `min_similarity: 0`, `top_k: 5`, `max_tokens: 1000`. Эти значения задаёт парсер,
а не `default` схемы. Если объект указан, нужны все шесть полей. Память работает, только если
`memory.enabled: true`, а списки `source_types` и `allow_paths` не пусты.

## Полный пример

В примере русский язык отчётов, локальный трекер и runner unittest. Необязательных build и
database в нём нет. Пример сам не делает test-author готовым: каталог `tests` должен существовать,
а preflight должен подтвердить адаптер и изоляцию. Замените ветку, команды и профиль исполнителя
настройками своего проекта.

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

Из исходников harness та же проверка запускается так: `python3 harness/bin/harness.py health <repo>`.
Без `--fix` команда ничего не исправляет. Проверка `files.project_json` сообщает ошибки формы
и бизнес-правил, JSON-режим печатает машиночитаемый отчёт. Если в отчёте есть `fail`, команда
завершается кодом 1. Исправьте указанное поле и повторите проверку. Не добивайтесь успеха
пустым списком QA-команд. Для test-author нужен ещё preflight из руководства роли.

Схема помогает редактору и мастеру консоли. Health добавляет к ней бизнес-правила, например
ровно один `{test_id}` и запрет понижать hook-профиль.

## Дальше

- [Все настройки проекта](index.md)
- [Настройки test-author](test-author.md)
- [Руководство test-author](../../agents/test-author.md)
- [Backend-оркестрация](../../backend-orchestration.md)
