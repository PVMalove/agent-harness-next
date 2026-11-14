# Политики

Политики `.harness/orchestration.json` задают согласование и границы автоматических продолжений:
сколько повторов допустимо, когда звать человека и какие сроки действуют. Назначения исполнителей
описаны в [ролях](roles.md), права на ресурсы в [доступе](access.md), команды и планы QA в
[верификации](verification.md).

## Как читать значения

Для каждого поля таблицы указывают тип, допустимые значения, значение по умолчанию и действие.
Все группы политик необязательны; пропущенные вложенные параметры берут встроенные значения.
Исключение: если вы указали объект `infrastructure_retry_policy`, в нём обязателен `enabled`.

Значения по умолчанию взяты из схемы и сверены с кодом. Если в JSON Schema нет ключа `default`,
значение взято из описания поля и загрузчика. Числа в управляемом примере выбраны отдельно:
пример задаёт `auto`, 3 повтора developer и 6 продолжений, а по умолчанию действуют
`manual_all`, `1` и `2`. Не копируйте пример целиком ради одной настройки.

## Согласование {#approval}

| Поле | Контракт |
| --- | --- |
| `approval_policy` | Строка: `manual_all`, `milestone`, `low_risk`, `auto`. По умолчанию: `manual_all`. Определяет, какие шаги подтверждает человек, а какие политика. Поведение каждого значения описано ниже. |
| `human_approval_gate` | Строка: `trusted`, `tty`. По умолчанию: `trusted`. `trusted` принимает CLI-аргументы `--approved-by` / `--approved-at`; `tty` требует подтвердить шаг интерактивно в терминале. С `auto` допустим только `trusted`. |
| `approval_ttl_seconds` | Целое ≥ `1`. Необязателен. Без поля явное согласование не истекает. Ограничивает возраст `--approved-at`. `14400` в управляемом примере выбран для примера и не является значением по умолчанию. |
| `low_risk_paths` | Массив непустых строк (минимум одна). Необязателен. Без него ни один путь не считается low risk. Допустимы `dir/**`, `**` или точный файл относительно репозитория, без ведущего `/`, сегментов `.`, `..` и пустых сегментов. Весь `allowed_paths` batch должен помещаться в эти границы. |
| `worker_attestation_required` | Boolean: `true` / `false`. По умолчанию: `false`. `true` требует аттестацию всех ролей. При `false` аттестация всё равно обязательна для `architect`, `developer`, `conflict-resolver`, `database-migrations`, `messaging-integration`, `code-review`. Для `auto` нужно `true`. |

### Режимы approval_policy

| Значение | Поведение |
| --- | --- |
| `manual_all` | Каждый шаг и принятие отчёта человек согласует вручную. Это встроенное значение по умолчанию. |
| `milestone` | Coordinator сам принимает чистый отчёт `completed` без рисков, блокеров, risk triggers и упавших проверок. QA, publish и batch с совпавшими risk triggers остаются ручными вехами. |
| `low_risk` | Те же условия автоматического принятия, но только если весь scope batch входит в `low_risk_paths` или в разрешённые устаревшие зоны. Если подходящих путей нет, coordinator ничего не принимает сам. |
| `auto` | Coordinator сам проводит batch от согласования до принятого publish в утверждённых границах. Каждое решение он записывает как `policy:auto` с evidence. Ошибка целостности, исчерпанный бюджет или отсутствие автоматического маршрута останавливают путь. Нужны `trusted` и аттестация всех ролей. |

Фрагмент с ручным согласованием:

```json
{
  "approval_policy": "manual_all",
  "human_approval_gate": "trusted"
}
```

`auto` работает только с согласованной комбинацией полей. Следующий фрагмент показывает форму;
это не совет включать `auto`:

```json
{
  "approval_policy": "auto",
  "human_approval_gate": "trusted",
  "worker_attestation_required": true
}
```

Coordinator закрепляет политику, когда создаёт batch. Чтобы `auto` продолжал работать, и конфиг
проекта, и план batch должны по-прежнему выбирать `auto`, а в истории не должно быть `auto_stop`
или ручного восстановления. `resume-stop` и `rewind` сохраняют историю и переводят следующие шаги
на `manual_all`. Правка файла не возобновляет остановленный автоматический путь. Автополитика не
открывает PR: для этого человек отдельно подтверждает действие. Auto-merge запрещён.
Как работать с batch и approvals, описано в [backend-руководстве](../../../backend-orchestration.md).

## Повторы и внимание {#retries}

| Поле | Контракт |
| --- | --- |
| `retry_policy.max_developer_retries` | Целое ≥ `0`. По умолчанию: `1`. Сколько раз developer может повторить работу после замечаний review или QA; `0` запрещает такие повторы. Продолжения worker session сюда не входят. |
| `auto_retry_min_severity` | Строка: `info`, `warning`, `error`, `blocker`. По умолчанию: `info`. Минимальная серьёзность finding, при которой coordinator сам отправляет отчёт на review-retry; значение закрепляется в плане batch. Это порог маршрутизации, а не разрешение игнорировать находки. |
| `attention_policy.retry_queue_seconds` | Целое ≥ `1`. По умолчанию: `3600`. Сколько принятый retry может ждать своего dispatch, прежде чем coordinator позовёт человека. |
| `attention_policy.max_infrastructure_retries` | Целое ≥ `0`. По умолчанию: `2`. Бюджет operational retry на один candidate: инфраструктура, transport, нехватка контекста. `0` запрещает такие повторы. |
| `attention_policy.stale_dispatch_seconds` | Целое ≥ `1`. По умолчанию: `3600`. Если живой dispatch молчит дольше, он считается stale и требует внимания. Процесс это поле не останавливает. |
| `attention_policy.heartbeat_interval_seconds` | Целое ≥ `1`. По умолчанию: `300`. Желаемый интервал heartbeat в секундах. В brief записывается `max(1, min(heartbeat_interval_seconds, stale_dispatch_seconds // 3))`. |
| `infrastructure_retry_policy.enabled` | Boolean: `true` / `false`. По умолчанию: `false`. Сам объект необязателен, но внутри него `enabled` обязателен. Разрешает ограниченное восстановление в уже согласованных границах за счёт бюджета attention; native-права не выдаёт. |

Пороги attention и разрешение инфраструктурного восстановления закрепляются в неизменяемом brief.
Правка конфигурации посреди dispatch не расширяет уже одобренные права и бюджет. Включённое
восстановление не обходит `needs_attention`: сначала устраните причину остановки. По умолчанию
инфраструктурный бюджет равен `2`, но автоматическое восстановление через
`infrastructure_retry_policy.enabled` выключено.

## Продолжение сессии {#continuation}

Повтор developer и продолжение worker session работают по-разному и имеют отдельные лимиты.
Сработавший адаптивный порог позволяет рассмотреть продолжение, но не разрешает запускать новые
сессии без конца. Возможны ли checkpoint и resume, зависит от роли и состояния dispatch; порядок
действий описан в [backend-руководстве](../../../backend-orchestration.md).

| Поле | Контракт |
| --- | --- |
| `continuation_policy.max_continuations` | Целое ≥ `1`. По умолчанию: `2`. Сколько раз можно продолжить worker session в одном dispatch. |
| `continuation_policy.max_rate_limit_resumes` | Целое ≥ `1`. По умолчанию: `1`. Сколько раз coordinator сам возобновляет работу после rate limit. Это отдельный счётчик внутри лимитов продолжения. |
| `adaptive_continuation_policy.context_limit` | Целое ≥ `1`. По умолчанию: `150000`. Объём контекста, после которого coordinator рассматривает продолжение; он же задаёт context budget brief. Это не общий лимит оплаченных токенов задачи. |
| `adaptive_continuation_policy.tdd_cycle_count` | Целое ≥ `1`. По умолчанию: `3`. Число TDD-циклов, после которого планируется продолжение. |
| `adaptive_continuation_policy.failure_log_bytes` | Целое ≥ `1`. По умолчанию: `20000`. Размер лога ошибок в байтах, после которого планируется продолжение. |
| `adaptive_continuation_policy.context_warn_ratio` | Число: `0 < value ≤ 1`. По умолчанию: `0.8`. Доля context limit, после которой coordinator предупреждает. При значениях по умолчанию: `150000 × 0.8 = 120000`. Предупреждение само не разрешает checkpoint и не меняет состояние. |

## Таймауты и preflight {#timeouts-preflight}

### Исполнение

Все сроки и интервалы в этой таблице заданы в секундах. Ожидание ответа coordinator и срок жизни
процесса различаются: если истёк срок startup или wait, процесс мог не остановиться.

| Поле | Контракт |
| --- | --- |
| `execution_policy.worker_startup_timeout_seconds` | Целое ≥ `1`. По умолчанию: `120`. Сколько coordinator ждёт первый self-report. Истечение срока не доказывает, что worker остановился, и не разрешает второй запуск. |
| `execution_policy.dispatch_wait_timeout_seconds` | Целое ≥ `1`. По умолчанию: `60`. Срок одного ожидания dispatch в секундах; это не общий срок работы worker. |
| `execution_policy.dispatch_poll_interval_seconds` | Целое ≥ `1`. По умолчанию: `5`. Интервал опроса dispatch в секундах. |
| `execution_policy.rate_limit_retry_seconds` | Целое ≥ `1`. По умолчанию: `60`. Пауза перед повтором при rate limit, если провайдер не указал срок. |
| `execution_policy.worker_execution_timeout_seconds` | Целое ≥ `1`. По умолчанию: `14400`. Сколько worker может работать под supervisor runtime. По истечении runtime останавливает группу процессов. |
| `execution_policy.stop_grace_seconds` | Целое ≥ `1`. По умолчанию: `30`. Пауза между SIGTERM и SIGKILL, когда runtime останавливает группу процессов по сроку. Действует и при остановке QA-контейнера команды. |
| `execution_policy.qa_command_timeout_seconds` | Целое ≥ `1`. По умолчанию: `3600`. Сколько может идти одна контейнерная QA-команда под runtime. Затем runtime останавливает контейнер с паузой stop grace. |

### Объём задачи до запуска

Preflight проверяет ожидаемый объём задачи до создания batch. Если оценка превышает лимит,
сначала уточните её или разделите тикет; не поднимайте лимит автоматически. Коэффициенты ниже
нужны только для оценки контекста: стоимость и фактический расход токенов они не гарантируют.
Для допуска coordinator берёт максимум из явно заданного числа и суммы оценок по строкам и
файлам. Поэтому меньший `--expected-context-tokens` не снижает вычисленный минимум.

| Поле | Контракт |
| --- | --- |
| `preflight_policy.require_estimates` | Boolean: `true` / `false`. По умолчанию: `true`. Требует оценить объём до запуска. `false` снимает только это требование, остальные ограничения действуют. |
| `preflight_policy.max_definition_of_done_items` | Целое ≥ `1`. По умолчанию: `5`. Максимум пунктов Definition of Done. |
| `preflight_policy.max_dependencies` | Целое ≥ `1`. По умолчанию: `3`. Максимум зависимостей от других тикетов. |
| `preflight_policy.max_expected_files` | Целое ≥ `1`. По умолчанию: `12`. Максимум ожидаемых изменённых файлов. |
| `preflight_policy.max_expected_services` | Целое ≥ `1`. По умолчанию: `1`. Максимум затрагиваемых сервисов. |
| `preflight_policy.max_expected_changed_lines` | Целое ≥ `1`. По умолчанию: `800`. Максимум ожидаемых изменённых строк. |
| `preflight_policy.max_expected_context_tokens` | Целое ≥ `1`. По умолчанию: `80000`. Максимальная оценка контекста до запуска; это не счётчик оплаченных токенов. |
| `preflight_policy.estimated_tokens_per_changed_line` | Целое ≥ `1`. По умолчанию: `20`. Коэффициент оценки: токены на изменённую строку. |
| `preflight_policy.estimated_tokens_per_file` | Целое ≥ `1`. По умолчанию: `2000`. Коэффициент оценки: токены на затронутый файл. |

## Параллелизм и lease {#concurrency-lease}

| Поле | Контракт |
| --- | --- |
| `concurrency_budget` | Целое ≥ `1`. По умолчанию: `1`. Сколько batch могут быть активны одновременно. Без явных назначений действует `1`; в настроенной конфигурации ключ обязателен. Ограничение «один writer внутри batch» это поле не снимает. |
| `lease_ttl_seconds` | Целое ≥ `1` и ≤ `86400`. По умолчанию: `300`. Срок lease QA lane в runtime store, в секундах. Владелец продлевает lease каждую треть срока; после истечения runtime проверяет, жив ли владелец. |
| `execution_policy.qa_lease_seconds` | Целое ≥ `1`. По умолчанию: `1800`. Срок lease файловой QA lane в секундах. Не заменяет `lease_ttl_seconds` текущего runtime store и не задаёт deadline QA-команды. |

`lease_ttl_seconds`, таймаут исполнения worker и срок ручного approval независимы: ни один из них
не заменяет другой и не отменяет остальные ограничения.

## Устаревшие поля {#legacy}

Существующие конфиги с зонами остаются валидными. `<ключ>` означает имя записи словаря, а не
буквальный JSON-ключ. В новой конфигурации задавайте явные пути.

| Поле | Контракт |
| --- | --- |
| `backend_zones.<ключ>.paths` | Массив непустых строк (минимум одна). Обязателен внутри существующей зоны. Задаёт устаревшие именованные границы. Новые batch используют `allowed_paths` внутри потолка `assignment_plans.<ключ>.write_paths`. Зоны больше не решают, можно ли запускать batch параллельно. |
| `low_risk_zones` | Массив непустых строк: устаревшие имена из `backend_zones`. Пути этих зон добавляются к разрешённым low-risk путям; в новых конфигах используйте `low_risk_paths`. Старый batch без явного scope по-прежнему получает границы от своей зоны. |

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

Для low-risk классификации те же пути можно записать явно:

```json
{
  "low_risk_paths": [
    "site/docs/**"
  ]
}
```

Оба блока показывают фрагменты, а не полные конфиги. Не удаляйте `backend_zones`, пока на них
ссылаются `assignment_plans.<ключ>.zone` или старые batch. При миграции сохраните прежний scope:
новая запись путей не должна расширять автоматическое согласование.

## Настроить с агентом {#agent-policy-setup}

Выберите промпт для нужной группы. Агент сначала читает текущие значения и спрашивает только о
недостающих решениях. Инструкции написаны по-английски, вопросы и сводки агент задаёт по-русски.

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

После правки выполните команды из [индекса](index.md#config-validation). Права и контейнер
настраиваются в [доступе](access.md), команды и планы проверок в [верификации](verification.md).
Эта страница их не переопределяет.
