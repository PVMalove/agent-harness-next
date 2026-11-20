# Включение и конфигурация

Включите capability, проверьте конфигурацию и оцените границы задачи до создания batch. Все поля описаны в разделе [Настройки](../../getting-started/settings/orchestration/index.md).

[Обзор оркестрации](../../backend-orchestration.md)

## Включение {#1}

Для нового git-репозитория выберите только `backend-orchestration`. CLI сам добавит зависимость
`engineering-suite`.

```bash
python3 harness/bin/harness.py init /path/to/repository \
  --project-type software \
  --stack python \
  --capability backend-orchestration \
  --base-branch main \
  --language ru \
  --qa-gate-command "python -m pytest"
```

В PowerShell замените `python3` на `python`, а `\` на обратную кавычку. Не передавайте
`engineering-suite` отдельно: capability уже включает её через `extends`.

Если харнесс в проекте уже установлен, сначала посмотрите локальный drift, затем обновите набор
capability:

```bash
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository --capability backend-orchestration
```

Без явного флага `update` не перезаписывает изменённые managed files. `--force-managed-files`
обновляет только managed snapshot и сохраняет seed-документы. `--force-seed-files` перезаписывает
только seed. `--force` делает и то и другое. После каждого включения или изменения конфигурации
выполните:

```bash
python3 harness/bin/harness.py health /path/to/repository
```

## Настройка `.harness/orchestration.json` {#2-harnessorchestrationjson}

Назначения ролей, команды проверок и политики выбирайте по [справочнику полей](../../getting-started/settings/orchestration/index.md). Если seed-конфига нет или он пуст, coordinator берёт дефолты для `in-process`. Заданные политики coordinator объединяет с дефолтами, даже если `assignment_plans` нет. Проверьте конфигурацию до dispatch.

### Нормализация и проверка конфига {#_3}

При загрузке coordinator нормализует конфиг только в памяти (`normalization.v1`). Для перечисленных
enum-полей он убирает пробелы по краям, приводит регистр и применяет документированные алиасы
(`in_process` → `in-process`, `manual-all` → `manual_all`, `low-risk` → `low_risk`). На каждое
исправление он выдаёт предупреждение (WARN) с ID поля, а файл не меняет. ID, модели, пути и команды
он не нормализует. Битый JSON, дубликат ключа, секрет и неоднозначное значение дают ошибку. При
дубликате ключа coordinator никогда не берёт последнее значение.

- `config validate --json` печатает диагностику: файл, JSON pointer, код, допустимые значения и
  безопасную копию полученного значения. Если конфиг невалиден, команда завершается с кодом 2.
- `config validate --canonical --json` вдобавок отклоняет написание, которое требует
  нормализации (код `config-noncanonical`).
- `config validate --fix --dry-run --json` показывает diff безопасной нормализации.
  `config validate --fix --json` записывает его одной транзакцией и сохраняет резервную копию.

### Бюджет контекста и preflight {#preflight}

Coordinator не создаёт batch, пока `batch preflight` не подтвердит ограниченный scope. `batch create`
вызывает preflight сам. Укажите ожидаемые changed paths, один bounded context или сервис и
размер diff с запасом. Если значения превышают политику проекта, сначала разделите задачу через
`/to-tickets`. Не отдавайте её architect как задачу на исследование:

```bash
python .harness/orchestration/coordinator.py --repo . batch preflight \
  --ticket '#123' --allowed-path 'services/payments/**' \
  --definition-of-done 'Добавить валидацию платежа' \
  --expected-file services/payments/validation.py \
  --expected-service payments --expected-changed-lines 120
```

Без `preflight_policy` coordinator ограничивает пункты DoD (5), dependencies (3), файлы (12),
сервисы (1), diff (800 строк) и ожидаемый контекст (80k tokens). Пример `orchestration.example.json`
задаёт 8/5/25/2/2000/150k. Проект меняет эти значения в `preflight_policy`.

`context_package_policy` оценивает токены с запасом и резервирует место для системных инструкций.
Байтовый предел остался только для диагностики и совместимости. `symbol_graph_depth` (по умолчанию 2)
задаёт глубину import-графа для *каждого* автоматического Context Package. Это касается и пакетов,
которые coordinator строит сам при `dispatch create` для architect, developer и code-review, а не
только ручного `context-package register`.

`--max-package-tokens` в `context-package register` только ужесточает потолок для одного пакета.
Значение выше `context_package_policy.max_tokens` из конфига coordinator отклоняет с ошибкой и не
применяет молча. Поднять лимит можно только в `context_package_policy.max_tokens` конфига проекта.
После правки `harness health` должен пройти.

`max_related_tests` (по умолчанию 25) работает как отдельный предохранитель с явной ошибкой. Если
import-граф стартовых файлов задевает больше связанных тестов, сборка пакета завершается
`ContextPackageError`. Она не добавляет молча половину тестов в оценку токенов.
`--max-related-tests` меняет этот предел для одного ручного `context-package register`.

Все role sessions на одних base/candidate используют один неизменяемый общий Context Package.
Новый пакет coordinator строит только для нового candidate. `continuation_policy` (2 continuations,
из них не больше одного автоматического resume после 429) и `retry_policy` (один developer retry)
ограничивают число циклов. `harness health` проверяет все поля. Для effort допустимы только
документированные уровни (`none`…`ultra`).

### Tool policy и context budget в brief {#tool-policy-context-budget-brief}

Кроме model, effort и `verification_commands`, каждый неизменяемый brief записывает ещё два значения.
Coordinator берёт их из `.harness/orchestration.json`, а не из чата:

- `allowed_tools`: рабочий набор инструментов этой роли. Без `tool_policy` действует дефолт
  режима из manifest. Режим `read-only` (architect, code-review, qa) получает `Read`, `Grep`, `Glob`,
  `Bash` без `Edit` и `Write`. Режим `write` получает те же инструменты плюс `Edit` и `Write`.
  Read-only роль работает по Context Package, не сканирует весь репозиторий и не загружает лишние
  инструменты. Это рабочий набор роли, а не deny-list: brief не отключает глобальные инструменты
  runtime.
- `context_budget`: число токенов из `adaptive_continuation_policy.context_limit` (по умолчанию
  150000). От этого же порога считается `context_advisory`. `dispatch create` (и с `--propose`)
  отклоняет автоматический Context Package, если его `estimated_tokens` больше бюджета, даже когда
  оценка укладывается в `context_package_policy.max_tokens`. Потолок пакета может быть выше бюджета
  роли, но роль должна получить пакет, который помещается в её контекст.

Проект переопределяет набор необязательным полем `tool_policy`. Запись роли важнее записи режима,
а запись режима важнее встроенного дефолта:

```json
"tool_policy": {
  "modes": {"read-only": ["Read", "Grep", "Glob"]},
  "roles": {"qa": ["Read", "Grep", "Glob", "Bash"]}
}
```

`harness health` принимает только ключи `modes` (`read-only` или `write`) и `roles` (имена из role
manifests). Значение должно быть непустым списком уникальных строк. Brief без этих двух полей
(созданный до их появления) остаётся валидным. Brief только с одним из полей или с неверной формой
значений coordinator отклоняет. Brief фиксирует выбор на момент approval и потом не меняется.
Поэтому поздняя правка `tool_policy` или `context_limit` не делает созданный dispatch невалидным.
Новые значения попадут только в следующие brief.

### Политика операционных циклов: attention, approval TTL и extensions {#attention-approval-ttl-extensions}

Три необязательных раздела `.harness/orchestration.json` задают, как coordinator останавливает
зациклившиеся retry и проверяет approval. Пропущенное поле получает дефолт. Итоговые значения
coordinator записывает в каждый brief как `orchestration_policy`. Поэтому правка файла во время
dispatch не меняет условия, под которыми его утвердили:

```json
"attention_policy": {"retry_queue_seconds": 3600, "max_infrastructure_retries": 2, "stale_dispatch_seconds": 3600},
"approval_ttl_seconds": 3600,
"extensions": {"transport_health": "none", "verification_environment_health": "none",
               "retry_reason_classifier": "none", "context_telemetry_provider": "none", "human_notifier": "none",
               "runtime_access": "none"}
```

- `attention_policy`: пороги флага `needs_attention` (см. [Attention state](decisions.md#attention-state)).
  Поля задают, сколько принятый retry может ждать своего dispatch, сколько operational retry
  (`verification-infrastructure`, `transport`, `context-pressure`) допустимо на один candidate
  (`0` запрещает их совсем) и после какого молчания живой dispatch считается stale.
  `heartbeat_interval_seconds` (по умолчанию 300) задаёт, как часто worker шлёт heartbeat. Brief
  записывает интервал не больше трети `stale_dispatch_seconds`.
- `approval_ttl_seconds`: срок жизни явного `--approved-at`. Более старое approval или approval с
  датой в будущем coordinator отклоняет и повторно не использует. Если поля нет, approval не
  истекает. Пример `orchestration.example.json` задаёт `14400`, и `harness init` создаёт конфиг
  из этого примера.
- `extensions`: подключаемые интерфейсы вне ядра coordinator: `transport_health`,
  `verification_environment_health`, `retry_reason_classifier`, `context_telemetry_provider`,
  `human_notifier`, `runtime_access`. Значение может быть `none` (дефолт, ничего не делает), именем,
  которое зарегистрировал хост-процесс, или `module:factory` (фабрика без аргументов в импортируемом
  модуле). Неизвестное имя даёт отказ (fail-closed). Ни один extension не добавляет model tool и не
  меняет system prompt.

`harness health` проверяет форму всех трёх разделов.
