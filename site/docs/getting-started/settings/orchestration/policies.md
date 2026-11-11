# Политики

Политики `.harness/orchestration.json` определяют согласование и границы автоматических
продолжений: сколько повторов допустимо, когда привлечь человека и какие сроки применять.
Назначения исполнителей описаны в [ролях](roles.md), права ресурсов — в [доступе](access.md),
а команды и планы QA — в [верификации](verification.md).

## Как читать значения

Ниже приведены тип, допустимые значения, default и действие каждого поля. Все группы политик
необязательны; пропущенные вложенные параметры берут встроенные значения. Исключение:
если указан объект `infrastructure_retry_policy`, в нём обязателен `enabled`.

Default взят из схемы и проверен по коду; когда JSON Schema не содержит ключа `default`,
использовано значение из её описания и загрузчика. Число в управляемом примере — отдельный
выбор: сейчас пример задаёт `auto`, 3 повтора developer и 6 продолжений, а defaults —
`manual_all`, `1` и `2`. Не копируйте пример целиком ради одной настройки.

## Согласование {#approval}

| Поле | Контракт |
| --- | --- |
| `approval_policy` | Строка: `manual_all`, `milestone`, `low_risk`, `auto`. По умолчанию: `manual_all`. Определяет, какие шаги подтверждает человек, а какие — политика. Поведение каждого значения — ниже. |
| `human_approval_gate` | Строка: `trusted`, `tty`. По умолчанию: `trusted`. `trusted` принимает CLI-аргументы `--approved-by` / `--approved-at`; `tty` требует интерактивного подтверждения в терминале. С `auto` допустим только `trusted`. |
| `approval_ttl_seconds` | Целое ≥ `1`. Необязателен. Без поля явное согласование не истекает. Ограничивает возраст `--approved-at`; `14400` в управляемом примере — выбранный срок, не default. |
| `low_risk_paths` | Массив непустых строк (минимум одна). Необязателен. Без разрешённых путей ничего не считается low risk. Допустимы `dir/**`, `**` или точный файл относительно репозитория, без ведущего `/`, сегментов `.`, `..` и пустых сегментов. Весь `allowed_paths` batch должен помещаться в эти границы. |
| `worker_attestation_required` | Boolean: `true` / `false`. По умолчанию: `false`. `true` требует аттестацию всех ролей. При `false` она всё равно обязательна для `architect`, `developer`, `conflict-resolver`, `database-migrations`, `messaging-integration`, `code-review`. Для `auto` нужно `true`. |

### Режимы approval_policy

| Значение | Поведение |
| --- | --- |
| `manual_all` | Каждый шаг и принятие отчёта требуют ручного согласования. Встроенный default. |
| `milestone` | Автоматически принимает чистый отчёт `completed` без рисков, блокеров, risk triggers и упавших проверок. QA, publish и batch с совпавшими risk triggers остаются ручными вехами. |
| `low_risk` | Те же условия автоматического принятия, но только если весь scope batch входит в `low_risk_paths` или разрешённые устаревшие зоны. Без подходящих путей автоматического принятия нет. |
| `auto` | Автоматический маршрут от согласования batch до принятого publish в утверждённых границах. Решения записываются как `policy:auto` с evidence. Ошибки целостности, исчерпание бюджета или отсутствие автоматического маршрута останавливают путь. Нужны `trusted` и аттестация всех ролей. |

Фрагмент с ручным согласованием:

```json
{
  "approval_policy": "manual_all",
  "human_approval_gate": "trusted"
}
```

`auto` требует согласованной комбинации полей; следующий фрагмент показывает форму,
а не рекомендацию включать её:

```json
{
  "approval_policy": "auto",
  "human_approval_gate": "trusted",
  "worker_attestation_required": true
}
```

Политика фиксируется при создании batch. Для `auto` и конфиг проекта, и план batch должны
продолжать выбирать `auto`; не должно быть `auto_stop` или ручного восстановления.
`resume-stop` и `rewind` сохраняют историю и возвращают последующие шаги к `manual_all`.
Смена файла не возобновляет остановленный автоматический путь. Автополитика не открывает PR:
для этого нужно отдельное явное подтверждение человека; auto-merge запрещён.
Порядок работы с batch и approvals — в [backend-руководстве](../../../backend-orchestration.md).

## Повторы и внимание {#retries}

| Поле | Контракт |
| --- | --- |
| `retry_policy.max_developer_retries` | Целое ≥ `0`. По умолчанию: `1`. Предел повторов developer после замечаний review или QA; `0` запрещает такие повторы. Это не продолжения worker session. |
| `auto_retry_min_severity` | Строка: `info`, `warning`, `error`, `blocker`. По умолчанию: `info`. Минимальная серьёзность finding для автоматического review-retry; фиксируется в плане batch. Это порог маршрутизации, а не разрешение игнорировать находки. |
| `attention_policy.retry_queue_seconds` | Целое ≥ `1`. По умолчанию: `3600`. Сколько принятый retry может ждать своего dispatch до привлечения человека. |
| `attention_policy.max_infrastructure_retries` | Целое ≥ `0`. По умолчанию: `2`. Бюджет operational retry на один candidate: инфраструктура, transport, context pressure. `0` — без таких повторов. |
| `attention_policy.stale_dispatch_seconds` | Целое ≥ `1`. По умолчанию: `3600`. После такого молчания живого dispatch он считается stale и требует внимания. Это не команда остановки процесса. |
| `attention_policy.heartbeat_interval_seconds` | Целое ≥ `1`. По умолчанию: `300`. Желаемый интервал heartbeat в секундах. В brief записывается `max(1, min(heartbeat_interval_seconds, stale_dispatch_seconds // 3))`. |
| `infrastructure_retry_policy.enabled` | Boolean: `true` / `false`. По умолчанию: `false`. Сам объект необязателен, но внутри него `enabled` обязателен. Включает ограниченное восстановление в уже согласованных границах, используя бюджет attention; не выдаёт native-права. |

Пороги attention и разрешение инфраструктурного восстановления фиксируются в immutable brief.
Правка конфигурации посреди dispatch не расширяет уже одобренные права или бюджет.
Включённое восстановление не обходит `needs_attention`: сначала требуется разрешить причину
остановки. По умолчанию инфраструктурный бюджет равен `2`, но автоматическое восстановление
через `infrastructure_retry_policy.enabled` выключено.

## Продолжение сессии {#continuation}

Повтор developer и продолжение worker session — разные механизмы с отдельными лимитами.
Достижение адаптивного порога даёт основание рассмотреть продолжение, а не разрешение
бесконечно запускать новые сессии. Допустимость checkpoint/resume определяется ролью и
состоянием dispatch; порядок действий — в [backend-руководстве](../../../backend-orchestration.md).

| Поле | Контракт |
| --- | --- |
| `continuation_policy.max_continuations` | Целое ≥ `1`. По умолчанию: `2`. Предел продолжений worker session на один dispatch. |
| `continuation_policy.max_rate_limit_resumes` | Целое ≥ `1`. По умолчанию: `1`. Предел автоматических возобновлений после rate limit. Отдельный счётчик внутри лимитов продолжения. |
| `adaptive_continuation_policy.context_limit` | Целое ≥ `1`. По умолчанию: `150000`. Порог объёма контекста для рассмотрения продолжения; также задаёт context budget brief. Не является общим лимитом оплаченных токенов задачи. |
| `adaptive_continuation_policy.tdd_cycle_count` | Целое ≥ `1`. По умолчанию: `3`. Порог числа TDD-циклов для планового продолжения. |
| `adaptive_continuation_policy.failure_log_bytes` | Целое ≥ `1`. По умолчанию: `20000`. Порог размера лога ошибок в байтах для планового продолжения. |
| `adaptive_continuation_policy.context_warn_ratio` | Число: `0 < value ≤ 1`. По умолчанию: `0.8`. Доля context limit для предупреждения. При defaults: `150000 × 0.8 = 120000`. Сигнал сам не разрешает checkpoint и не меняет состояние. |

## Таймауты и preflight {#timeouts-preflight}

### Исполнение

Все сроки и интервалы в этой таблице — секунды. Ожидание ответа coordinator не равно
сроку жизни процесса: истечение startup/wait само по себе не доказывает его остановку.

| Поле | Контракт |
| --- | --- |
| `execution_policy.worker_startup_timeout_seconds` | Целое ≥ `1`. По умолчанию: `120`. Ожидание первого self-report. Истечение не доказывает остановку worker и не разрешает дублирующий запуск. |
| `execution_policy.dispatch_wait_timeout_seconds` | Целое ≥ `1`. По умолчанию: `60`. Срок одного ожидания dispatch в секундах; не общий срок исполнения worker. |
| `execution_policy.dispatch_poll_interval_seconds` | Целое ≥ `1`. По умолчанию: `5`. Интервал опроса dispatch в секундах. |
| `execution_policy.rate_limit_retry_seconds` | Целое ≥ `1`. По умолчанию: `60`. Пауза перед повтором при rate limit, если провайдер не указал срок. |
| `execution_policy.worker_execution_timeout_seconds` | Целое ≥ `1`. По умолчанию: `14400`. Срок исполнения worker под supervisor runtime. По истечении runtime останавливает группу процессов. |
| `execution_policy.stop_grace_seconds` | Целое ≥ `1`. По умолчанию: `30`. Пауза между SIGTERM и SIGKILL группе процессов при остановке по сроку; применяется и к остановке QA-контейнера команды. |
| `execution_policy.qa_command_timeout_seconds` | Целое ≥ `1`. По умолчанию: `3600`. Срок одной контейнерной QA-команды под runtime; затем контейнер останавливается с заданной stop grace. |

### Объём задачи до запуска

Preflight проверяет ожидаемый объём перед созданием batch. При превышении сначала уточните
оценку или разделите тикет; не поднимайте лимит автоматически. Коэффициенты ниже служат
оценке контекста, а не гарантии стоимости или фактического расхода токенов.
Оценка для допуска — максимум явно заданного числа и суммы оценок по строкам и файлам.
Поэтому меньший `--expected-context-tokens` не снижает вычисленный минимум.

| Поле | Контракт |
| --- | --- |
| `preflight_policy.require_estimates` | Boolean: `true` / `false`. По умолчанию: `true`. Требует оценки объёма до запуска. `false` отключает это требование, а не остальные ограничения. |
| `preflight_policy.max_definition_of_done_items` | Целое ≥ `1`. По умолчанию: `5`. Максимум пунктов Definition of Done. |
| `preflight_policy.max_dependencies` | Целое ≥ `1`. По умолчанию: `3`. Максимум зависимостей от других тикетов. |
| `preflight_policy.max_expected_files` | Целое ≥ `1`. По умолчанию: `12`. Максимум ожидаемых изменённых файлов. |
| `preflight_policy.max_expected_services` | Целое ≥ `1`. По умолчанию: `1`. Максимум затрагиваемых сервисов. |
| `preflight_policy.max_expected_changed_lines` | Целое ≥ `1`. По умолчанию: `800`. Максимум ожидаемых изменённых строк. |
| `preflight_policy.max_expected_context_tokens` | Целое ≥ `1`. По умолчанию: `80000`. Максимальная оценка контекста до запуска; не счётчик фактически оплаченных токенов. |
| `preflight_policy.estimated_tokens_per_changed_line` | Целое ≥ `1`. По умолчанию: `20`. Коэффициент оценки: токены на изменённую строку. |
| `preflight_policy.estimated_tokens_per_file` | Целое ≥ `1`. По умолчанию: `2000`. Коэффициент оценки: токены на затронутый файл. |

## Параллелизм и lease {#concurrency-lease}

| Поле | Контракт |
| --- | --- |
| `concurrency_budget` | Целое ≥ `1`. По умолчанию: `1`. Предел одновременно активных batch. В режиме без явных назначений используется `1`; при настроенной конфигурации ключ обязателен. Не снимает ограничение одного writer внутри batch. |
| `lease_ttl_seconds` | Целое ≥ `1` и ≤ `86400`. По умолчанию: `300`. Lease QA lane в runtime store, в секундах. Владелец продлевает его каждую треть срока; runtime проверяет живость владельца после истечения. |
| `execution_policy.qa_lease_seconds` | Целое ≥ `1`. По умолчанию: `1800`. Lease файловой QA lane в секундах. Не заменяет `lease_ttl_seconds` текущего runtime store и не задаёт deadline QA-команды. |

`lease_ttl_seconds`, таймаут исполнения worker и срок ручного approval независимы.
Один не заменяет другой и не обнуляет остальные ограничения.

## Устаревшие поля {#legacy}

Существующие конфиги с зонами остаются валидными. `<ключ>` — имя записи словаря,
а не буквальный JSON-ключ. Для новой конфигурации используйте явные пути.

| Поле | Контракт |
| --- | --- |
| `backend_zones.<ключ>.paths` | Массив непустых строк (минимум одна). Обязателен внутри существующей зоны. Устаревшие именованные границы; новые batch используют `allowed_paths` внутри потолка `assignment_plans.<ключ>.write_paths`. Зоны больше не определяют допуск параллельных batch. |
| `low_risk_zones` | Массив непустых строк. Устаревшие имена из `backend_zones`. Их пути добавляются к разрешённым low-risk путям; для новых конфигов используйте `low_risk_paths`. Старый batch без явного scope по-прежнему определяется своей зоной. |

Например, прежний список зон:

```json
{
  "backend_zones": {
    "docs": {
      "paths": [
        "site/docs/**"
      ]
    }
  },
  "low_risk_zones": [
    "docs"
  ]
}
```

Для low-risk классификации его пути можно записать явно:

```json
{
  "low_risk_paths": [
    "site/docs/**"
  ]
}
```

Оба блока — фрагменты, не полные конфиги. Не удаляйте `backend_zones`, пока на них ссылаются
`assignment_plans.<ключ>.zone` или старые batch. При миграции сохраните прежний scope;
изменение способа записи путей не должно расширять автоматическое согласование.

## Настроить с агентом {#agent-policy-setup}

Выберите промпт для нужной группы. Агент сначала читает существующие значения и спрашивает
только о недостающих решениях. Инструкции — на английском, вопросы и сводки — на русском.

??? quote ah-skill-text "Промпт для агента: согласование"

    ```text
    Help me configure approval policy for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask who should approve workflow steps: manual_all, milestone, low_risk or auto.
    For a new setup, explain the manual_all default; do not overwrite an existing
    choice automatically. For low_risk, ask for exact allowed paths and show the whole
    allowlist; never choose ** for convenience. Ask about trusted versus tty, whether
    explicit approvals should expire, and attestation for the remaining roles.
    Keep the six always-attested roles protected even when the flag is false.
    Do not enable auto without my explicit choice. Explain its trusted-gate and
    worker_attestation_required=true prerequisites, stop conditions and separate
    human confirmation for opening a PR. Changing config does not resume auto_stop.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

??? quote ah-skill-text "Промпт для агента: повторы и внимание"

    ```text
    Help me configure bounded retries and attention thresholds for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask separately about developer retry count, review severity threshold,
    infrastructure/transport/context retry budget, stale-worker time and heartbeat,
    and how long accepted retries may queue. Use observed project facts, not guessed
    performance. Example: «Сколько повторов developer разрешить?» — a justified
    current/default value, another supported count, zero where supported, «Другое».
    Explain which fields allow zero and that zero is not a general disable value.
    Calculate the effective heartbeat cadence from the chosen stale interval.
    Ask whether infrastructure_retry_policy.enabled should be set: enabling it only
    permits recovery inside already-approved boundaries and the attention budget;
    it does not grant network, filesystem or native permissions. Do not widen them.
    Do not treat retries as a way to suppress findings or restart a live worker.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

??? quote ah-skill-text "Промпт для агента: продолжение и лимиты"

    ```text
    Help me configure continuation, execution and preflight limits for this repository.
    Follow repository instructions; keep questions, choices and summaries in Russian.

    Read the current .harness/project.json, .harness/orchestration.json, installed
    schema and managed example before asking anything. Inspect existing policy values
    and run the available read-only health/config validation commands. Do not read
    credentials, authentication files, token/key values or unrelated private logs.
    Ask only for missing decisions, one question at a time, in Russian. Offer 2-4
    concrete Russian choices plus «Другое», each with a one-line consequence.
    Put a justified recommendation first and mark it «Рекомендуется»; otherwise ask
    for the missing fact. Preserve established values unless I explicitly change them.

    Ask about total continuations and rate-limit resumes, then context/TDD/log
    thresholds. Explain that context warnings alone authorize no state transition.
    Ask about startup wait, one dispatch wait, execution deadline and stop grace
    separately; do not confuse them with each other or with QA-command timeouts.
    Ask for typical DoD size, dependencies, expected files/services/lines and context
    estimates. Derive proposed preflight limits from those answers; do not inflate
    limits just to pass a check or describe estimates as a billed-token spending cap.
    Ask whether concurrency and the runtime QA lease need to change. Distinguish
    lease_ttl_seconds from the legacy file-lane execution_policy.qa_lease_seconds.
    Do not migrate or delete backend_zones/low_risk_zones until all assignment and
    batch references have been inspected and I have reviewed the migration diff.

    Use only fields and values supported by the schema and validator. Distinguish
    built-in defaults from the managed example; do not reset unrelated settings.
    Show the exact proposed diff, consequences and unanswered questions. Wait for my
    approval before applying only that diff with Edit/Write. Then run installed
    config validate --canonical --json and harness health, and report failures and
    anything not checked. Do not run workers, change existing batches/briefs, commit
    or open a PR. Never request or store secrets.
    ```

## Проверка и дальше

После правки выполните команды из [индекса](index.md#config-validation).
Настройки прав и контейнера находятся в [доступе](access.md), команды и планы проверок —
в [верификации](verification.md). На этой странице они не переопределяются.
