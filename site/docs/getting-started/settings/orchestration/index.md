# orchestration.json

`.harness/orchestration.json` задаёт для backend-оркестрации назначения ролей, согласование,
доступ и проверки. Coordinator читает файл, чтобы подготовить brief и выбрать следующий шаг;
`harness-runtime` берёт из него настройки исполнения. Соглашения проекта (язык, ветки, трекер и
общий QA gate) задаёт [project.json](../project.md).

## Где лежит и когда появляется

Когда вы устанавливаете capability `backend-orchestration`, установщик создаёт отсутствующий файл
из управляемого примера `.harness/orchestration.example.json`. Дальше файл ведёт проект.
`harness update` обновляет пример и не трогает `orchestration.json`, если вы его меняли. Файл без
локальных правок (равный своему baseline в `.harness/harness.lock`) `update` заменяет новым
шаблоном и сохраняет прежние байты в бэкапе. Перезаписать изменённый файл можно только явно,
флагом `--force-seed-file .harness/orchestration.json`; так одну настройку не вносят.

Схема лежит в `.harness/orchestration/orchestration.schema.json`. Необязательное строковое
поле `$schema` указывает редактору путь `./orchestration/orchestration.schema.json`.

## Настроенные назначения и режим без них

Если в конфигурации есть профили или назначения, нужны четыре ключа верхнего уровня:

| Поле | Назначение |
| --- | --- |
| `provider_profiles` | Профили провайдеров: capability, резервные профили и ограничения. |
| `assignment_plans` | Назначения используемых ролей: runtime, model, effort, транспорт и потолок записи. Непустой набор должен включать `code-review`. |
| `concurrency_budget` | Целое число не меньше `1`: сколько batch могут быть активны одновременно. Подробности в [политиках](policies.md). |
| `verification_commands` | Массив строк: полный gate для независимого QA. Подробности в [верификации](verification.md). |

Необязательные политики берут встроенные значения там, где это предусматривает контракт.
Значение в управляемом примере может отличаться от значения по умолчанию.

Coordinator работает и без файла. В этом режиме явных назначений нет: runtime берётся из
вызывающей сессии, а границы задачи задаёт batch. Пустая заготовка тоже не включает явные
назначения:

```json
{
  "$schema": "./orchestration/orchestration.schema.json",
  "provider_profiles": {},
  "assignment_plans": {},
  "concurrency_budget": 1,
  "verification_commands": []
}
```

Coordinator распознаёт эту заготовку как seed; это не пример настроенного маршрута. Без
конфигурации команды QA берутся из `project.json.qa_gate_commands`, поэтому проверьте, что там
заданы реальные проверки. В явной конфигурации заполните `verification_commands` командами своего
проекта: пустой список не доказывает качество кода. Схема допускает и конфигурацию без профилей,
назначений и устаревших зон, поэтому правило четырёх ключей действует не всегда.

## Карта раздела

| Страница | Что настраивается |
| --- | --- |
| [Роли и транспорт](roles.md) | `provider_profiles`, `assignment_plans`, `communication_policy`, `tool_policy`: исполнители, языки и рабочие наборы инструментов. |
| [Политики](policies.md) | Согласование, повторы, продолжение сессии, preflight, параллелизм и lease. |
| [Доступ и контейнер](access.md) | `access_policy`, `extensions`, доступ к ресурсам, сеть и контейнерный исполнитель. |
| [Верификация](verification.md) | Команды и планы QA, профили проверки, Repo Map и Context Package. |

Как запускать batch, согласовывать шаги и восстанавливаться после сбоев, описано в
[руководстве по backend-оркестрации](../../../backend-orchestration.md).
[Мастер консоли](../../../console-configuration.md) помогает выбрать конфигурацию и показывает
диагностику.

## Проверка и нормализация {#config-validation}

В корне установленного проекта выполните:

```bash
python3 .harness/orchestration/coordinator.py --repo . config validate --json
python3 .harness/orchestration/coordinator.py --repo . config validate --canonical --json
harness health .
```

Первая команда проверяет контракт и выводит диагностику; на невалидный конфиг она отвечает
кодом `2`. Вторая ещё и отклоняет написание, которое нужно нормализовать: код
`config-noncanonical`. `harness health` проверяет конфигурацию вместе с остальными настройками
проекта. Если CLI установлен не как `harness`, возьмите точку входа пакета из
[справочника CLI](../../../reference/cli.md).

Валидатор отклоняет неизвестные поля. При загрузке coordinator нормализует в памяти только
зарегистрированные enum-поля и предупреждает об исправлении. ID, model, пути и команды он не
нормализует. Ни чтение, ни обычная проверка файл не переписывают. Битый JSON, повторяющиеся ключи
и секреты исправляйте сами. Чтобы записать нормализацию в файл, есть отдельный `--fix`. Сначала
посмотрите результат `config validate --fix --dry-run --json`, как описано в
[руководстве](../../../backend-orchestration.md).

## Настроить с агентом {#agent-setup}

Скопируйте промпт в сессию агента, открытую в нужном проекте. Агент сначала проверит состояние,
затем задаст недостающие вопросы. Записывать файл он будет только после того, как вы посмотрите
и согласуете diff.

??? quote ah-skill-text "Промпт для агента: с чего начать"

    ```text
    Help me configure backend orchestration for this repository.
    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.

    1. Read .harness/project.json and .harness/orchestration.json if present,
       the installed orchestration schema, .harness/orchestration.example.json,
       and the role manifests. Do not read credentials or authentication files.
       Run the available read-only harness health and config validate commands.
       If backend-orchestration is not installed, explain what is missing first;
       do not invent a config layout or install anything implicitly.
    2. Summarize existing settings. Do not ask for known values or replace them
       with the managed example. Missing config and an empty seed can use the
       invoking session; do not call either case broken by default.
    3. Ask one unresolved question at a time. Start with whether to keep session-based
       assignments or configure explicit role assignments. Clarify the required roles,
       runtimes/models, write boundaries and full QA commands only where needed.
       Offer 2-4 concrete choices plus «Другое». Put an evidence-based recommendation
       first, mark it «Рекомендуется», and explain each consequence in one line.
       If no recommendation is justified, ask for the missing fact instead.
       Example: «Как выбирать исполнителей?» — «Из текущей сессии»,
       «Явные назначения по ролям», «Другое». Recommend only after inspecting context.
    4. Use only schema fields and values supported by the validator, repository
       evidence or my answers. Do not guess a model, effort, path or QA command.
       With non-empty assignments, include code-review and validate profile references.
       Do not widen permissions, enable auto approval or change unrelated policies.
       Never request, read, print or store token/key values.
    5. Show the proposed configuration diff, explain defaults versus chosen values,
       and list unanswered questions. Wait for my approval before writing.
       Apply only approved changes with Edit/Write; preserve unrelated settings.
       Run config validate --canonical --json and harness health again through the
       installed entry points. Report results and anything not checked. Do not commit,
       launch workers, start a batch or open a PR as part of configuration.
    ```
