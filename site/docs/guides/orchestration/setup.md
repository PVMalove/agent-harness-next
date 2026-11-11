# Включение и конфигурация

Включи capability, проверь конфигурацию и оцени границы задачи до создания batch. Справочник полей — в разделе [Настройки](../../getting-started/settings/orchestration/index.md).

[Обзор оркестрации](../../backend-orchestration.md)

## Включение {#1}

Для нового git-репозитория выберите только `backend-orchestration`. CLI разрешит зависимость от
`engineering-suite` автоматически.

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --project-type software \
  --stack python \
  --capability backend-orchestration \
  --base-branch main \
  --language ru \
  --qa-gate-command "python -m pytest"
```

В PowerShell замените `python3` на `python`, а `\` на обратную кавычку. Не передавайте отдельно
`engineering-suite`: capability уже содержит её через `extends`.

Чтобы включить её в существующем проекте с харнессом, сначала посмотрите локальный drift, затем
обновите выбранный набор capability:

```bash
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository --capability backend-orchestration
```

`update` не перезаписывает изменённые managed files без явного флага. `--force-managed-files`
обновляет только managed snapshot и сохраняет seed-документы, `--force-seed-files` перезаписывает
только seed, а `--force` объединяет оба действия. После любого включения или изменения конфигурации
выполните:

```bash
python3 harness/bin/harness.py health /path/to/repository
```

## Настройка `.harness/orchestration.json` {#2-harnessorchestrationjson}

Выбирай назначения ролей, команды проверок и политики по [справочнику полей](../../getting-started/settings/orchestration/index.md). Если seed-конфига нет или он пуст, coordinator берёт дефолты для `in-process`. Заданные политики coordinator объединяет с дефолтами, даже если `assignment_plans` нет. Проверь конфигурацию перед dispatch.

### Нормализация и проверка конфига {#_3}

При загрузке coordinator нормализует конфиг только в памяти (`normalization.v1`): для перечисленных
enum-полей он убирает пробелы по краям, приводит регистр и применяет документированные алиасы
(`in_process` → `in-process`, `manual-all` → `manual_all`, `low-risk` → `low_risk`). На каждое
исправление он выдаёт предупреждение (WARN) с ID поля, а файл не меняет. ID, модели, пути и команды
он не нормализует. Битый JSON, дубликат ключа, секрет и неоднозначное значение — ошибки; при дубликате
coordinator никогда не берёт последнее значение.

- `config validate --json` печатает диагностику: файл, JSON pointer, код, допустимые значения и
  безопасное полученное значение. Для невалидного конфига команда завершается с кодом 2.
- `config validate --canonical --json` дополнительно отклоняет написание, которое требует
  нормализации (код `config-noncanonical`).
- `config validate --fix --dry-run --json` показывает diff безопасной нормализации, а
  `config validate --fix --json` записывает его транзакцией с резервной копией.

### Бюджет контекста и preflight {#preflight}

Coordinator не создаёт новый batch, пока `batch preflight` не подтвердит ограниченный scope. `batch create`
вызывает его автоматически. Укажите ожидаемые changed paths, один bounded context/service и
консервативный размер diff. Если значения выше project policy, сначала разделите задачу через `/to-tickets`;
не передавайте её architect как discovery-задачу:

```bash
python .harness/orchestration/coordinator.py --repo . batch preflight \
  --ticket '#123' --allowed-path 'services/payments/**' \
  --definition-of-done 'Добавить валидацию платежа' \
  --expected-file services/payments/validation.py \
  --expected-service payments --expected-changed-lines 120
```

Без `preflight_policy` coordinator ограничивает DoD (5), dependencies (3), файлы (12), сервисы (1),
diff (800 строк) и ожидаемый context (80k tokens). Пример `orchestration.example.json` задаёт
8/5/25/2/2000/150k. Проект настраивает эти значения через `preflight_policy`.
`context_package_policy` использует консервативную token estimate и резервирует место для системных
инструкций. Байтовый предел остаётся только для диагностической совместимости. `symbol_graph_depth`
(по умолчанию 2) в этой политике управляет глубиной import-графа для *каждого* автоматического
Context Package. Это касается и пакетов, которые coordinator строит сам при `dispatch create` для
architect/developer/code-review, а не только ручного `context-package register`.
`--max-package-tokens` на `context-package register` — только более строгий потолок для одного
пакета. Значение выше сконфигурированного `context_package_policy.max_tokens` coordinator отклоняет
с ошибкой, а не применяет молча. Поднять лимит можно только правкой `context_package_policy.max_tokens`
в конфиге проекта, после которой `harness health` должен пройти. `max_related_tests` (по умолчанию 25)
— отдельный fail-loud предохранитель. Если import-граф стартовых файлов задевает больше
related_tests, чем этот предел, сборка пакета завершается `ContextPackageError`. Она не добавляет
молча в оценку токенов половину test suite. `--max-related-tests` переопределяет предел для
одного ручного `context-package register`. Все role sessions на том же base/candidate
переиспользуют один immutable shared Context Package. Новый пакет coordinator строит только для нового
candidate. `continuation_policy` (2 continuations, из них максимум один automatic 429 resume) и
`retry_policy` (один developer retry) делают циклы конечными. `harness health` проверяет все поля.
Effort допускает только документированные уровни (`none`…`ultra`).

### Tool policy и context budget в brief {#tool-policy-context-budget-brief}

Кроме model/effort и `verification_commands`, каждый immutable brief явно записывает два значения,
выбранных из `.harness/orchestration.json`, а не из чата:

- `allowed_tools` — рабочий набор инструментов именно этой роли. Без `tool_policy` действует дефолт
  режима из manifest: `read-only` (architect, code-review, qa) — `Read`, `Grep`, `Glob`, `Bash`, без
  `Edit`/`Write`; `write` — те же плюс `Edit` и `Write`. Read-only роль работает по Context Package,
  не сканирует весь репозиторий и не подгружает нерелевантные инструменты. Список — рабочий набор
  роли, а не deny-list: brief не отключает глобальные инструменты runtime.
- `context_budget` — токены из `adaptive_continuation_policy.context_limit` (по умолчанию 150000):
  тот же порог, от которого считается `context_advisory`. `dispatch create` (и `--propose`)
  отклоняет автоматический Context Package, если его `estimated_tokens` больше этого бюджета. Так
  происходит, даже если оценка укладывается в `context_package_policy.max_tokens`. Потолок пакета может
  быть выше бюджета роли, но роль должна получить пакет, который помещается в её контекст.

Проект переопределяет набор необязательным `tool_policy`. Запись роли важнее записи режима, а запись
режима важнее встроенного дефолта:

```json
"tool_policy": {
  "modes": {"read-only": ["Read", "Grep", "Glob"]},
  "roles": {"qa": ["Read", "Grep", "Glob", "Bash"]}
}
```

`harness health` принимает только ключи `modes` (`read-only`/`write`) и `roles` (имена из role
manifests), а значением — непустой список уникальных строк. Brief без этих двух полей (созданный до
их появления) остаётся валидным. Brief с одним из двух полей или с некорректной формой значений
отклоняется. Brief — неизменяемая запись выбора на момент approval. Поэтому поздняя правка
`tool_policy` или `context_limit` не делает уже созданный dispatch невалидным. Новые значения
попадут только в следующие brief.

### Политика операционных циклов: attention, approval TTL и extensions {#attention-approval-ttl-extensions}

Три необязательных раздела `.harness/orchestration.json` управляют тем, как coordinator останавливает
зацикленные retry и как проверяет approval. Пропущенное поле берёт дефолт, а resolved-значения
coordinator записывает в каждый brief как `orchestration_policy`, поэтому правка файла посреди
dispatch не меняет условия, под которыми dispatch был утверждён:

```json
"attention_policy": {"retry_queue_seconds": 3600, "max_infrastructure_retries": 2, "stale_dispatch_seconds": 3600},
"approval_ttl_seconds": 3600,
"extensions": {"transport_health": "none", "verification_environment_health": "none",
               "retry_reason_classifier": "none", "context_telemetry_provider": "none", "human_notifier": "none",
               "runtime_access": "none"}
```

- `attention_policy` — пороги флага `needs_attention` (см. [Attention state](decisions.md#attention-state)): сколько принятый retry может ждать
  своего dispatch, сколько operational retry (`verification-infrastructure`, `transport`,
  `context-pressure`) допустимо на один candidate (`0` — ни одного) и после какого молчания живой
  dispatch считается stale.
- `approval_ttl_seconds` — срок жизни явного `--approved-at`. Coordinator отклоняет более старое
  (или датированное в будущем) approval и не использует его повторно. Без поля approval не истекает.
  Пример `orchestration.example.json` задаёт `14400`; из него `harness init` создаёт конфиг.
- `extensions` — подключаемые интерфейсы вне ядра coordinator: `transport_health`,
  `verification_environment_health`, `retry_reason_classifier`, `context_telemetry_provider`,
  `human_notifier`, `runtime_access`. Значение — `none` (инертный дефолт), имя, зарегистрированное
  хост-процессом, или `module:factory` (вызываемая без аргументов фабрика в импортируемом модуле).
  Неизвестное имя — fail-closed. Ни один extension не добавляет model tool и не меняет system prompt.

`harness health` проверяет форму всех трёх разделов. Coordinator читает заданные политики, даже если `assignment_plans` нет, и объединяет их с дефолтами.
