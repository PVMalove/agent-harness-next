# Верификация

В `.harness/orchestration.json` задаются команды проверок, правила выбора тестов и лимиты
контекста для ролей. Начните с полного QA, затем выделите быстрые проверки developer и review.
Repo Map и Context Package настраивайте по размеру проекта и доступному контексту модели.

Здесь «по умолчанию» означает поведение при пропущенном поле. Управляемый
`.harness/orchestration.example.json` содержит отдельные примеры значений: его команды и лимиты
нужно проверить для своего проекта. JSON-фрагменты ниже дополняют существующий конфиг.

## Полный gate {#full-gate}

| Поле | Контракт |
| --- | --- |
| `verification_commands` | Массив непустых строк — shell-команд полного QA. В управляемом примере `[]`; команды проекта задаются явно. Пустой список допустим для конфига, но без проверок `qa run` откажется запускаться. |

Обычный clean-room QA выполняет полный список в отдельном checkout на `candidate_sha`.
Зелёный developer или review не заменяет это доказательство. После изменения SHA нужен новый
QA; правило полного gate перед publish описано в [QA gate](../../../guides/qa-gate.md).
Исключение для планов тикета в `integration/*` разобрано [ниже](#verification-plans).

## Быстрые проверки ролей {#role-checks}

| Поле | Контракт |
| --- | --- |
| `developer_verification_commands` | Массив непустых строк. Если поля нет, берётся `verification_commands`. Явный `[]` допустим, но не задаёт проверок developer. |
| `review_verification_commands` | Такой же массив для независимой проверки code-review на кандидате. Без поля — `verification_commands`; явный `[]` допустим. |

Управляемый пример содержит пустые общие списки. Их наличие само по себе не настраивает тесты.
Сначала найдите рабочие команды проекта, затем выберите более узкие команды для быстрых циклов.
В отчёте роль должна перечислить ровно команды полученного brief, а не подменить их своими.

## Подготовка и диагностика QA {#qa-preparation}

| Поле | Контракт |
| --- | --- |
| `qa_preparation` | Массив shell-команд, default `[]`. Выполняется в checkout кандидата до gate; останавливается на первой ошибке. При пустом списке QA сразу запускает проверки. |
| `qa_environment_probes` | Массив shell-команд, default `[]`. Независимые пробы окружения в том же checkout, только после ошибки подготовки. Например, проверка доступности нужного реестра. |
| `qa_project_file_checks` | Массив shell-команд, default `[]`. Независимые офлайн-проверки файлов проекта в том же checkout, только после ошибки подготовки. Например, согласованность manifest и lock-файла. |

Все элементы этих массивов — непустые строки. Выберите команды из реального toolchain проекта:
универсальной проверки сети или lock-файла здесь нет.

- Упала проверка файлов проекта → подтверждён дефект проекта.
- Упала проба окружения, а проверки файлов успешны → подтверждена инфраструктурная причина.
- Нет необходимых проб/проверок или результат не даёт доказательства → нужна диагностика;
  один сбой установки зависимостей ещё не доказывает проблему инфраструктуры.

## Профили и планы проверки {#verification-plans}

### Профили области

`verification_profiles` — необязательный массив. При `batch create` берётся **первый** профиль,
чьи шаблоны покрывают все `allowed_paths` batch. Его команды замораживаются для developer
и review. Без полного покрытия используются общие списки; пустая область профиль не выбирает.
Профиль не заменяет полный список QA.

| Поле | Контракт |
| --- | --- |
| `verification_profiles[].paths` | Обязательный непустой массив путей/glob относительно корня репозитория. Без ведущего `/`, обратного слеша, пустых сегментов, `.` и `..`. |
| `verification_profiles[].developer` | Обязательный массив shell-команд developer; `[]` допустим. |
| `verification_profiles[].review` | Обязательный массив shell-команд code-review; `[]` допустим. |

Пример **для этого репозитория**: профиль взят из управляемого примера, `make verify` — полный
gate из Makefile. `pytest -n 8` требует pytest-xdist. Эти пути и команды нельзя переносить
в другой проект без проверки.

```json {.ah-code-wrap}
{
  "verification_commands": ["make verify"],
  "developer_verification_commands": ["make lint"],
  "review_verification_commands": ["make lint"],
  "verification_profiles": [
    {
      "paths": ["harness/console/**", "tests/console/**"],
      "developer": ["make lint", "pytest -q -n 8 tests/console"],
      "review": ["make lint", "pytest -q -n 8 tests/console"]
    }
  ]
}
```

### План по влиянию изменений

Необязательный `verification_plan_policy` замораживается при создании batch. При
`dispatch propose` из него строится план для developer-retry, code-review и QA. У первого
developer-dispatch такого плана нет. Без политики остаются замороженные списки команд.

| Поле | Контракт |
| --- | --- |
| `verification_plan_policy.max_related_tests` | Обязательное целое ≥ 1. Порог числа тестов ChangeImpact: превышение расширяет pytest до `full`. Default не задан; в управляемом примере `200`. |
| `verification_plan_policy.ticket_diff_selection` | Boolean, default `false`. При `true` **и** цели `integration/*` включает выбор тестов diff тикета, описанный ниже. |
| `verification_plan_policy.stages[].stage_id` | Обязательная непустая строка, уникальная среди стадий. |
| `verification_plan_policy.stages[].kind` | Обязателен: `lint`, `typecheck`, `pytest`, `clean-room` или `custom`. Выбор связанных тестов применяется к `pytest`. |
| `verification_plan_policy.stages[].argv` | Обязательный непустой массив непустых строк — программа и аргументы, а не строка shell. Для `focused` pytest к нему добавляются выбранные nodeid. |
| `verification_plan_policy.stages[].timeout_seconds` | Обязательное целое ≥ 1 — таймаут стадии в секундах. Общего default нет. |

`stages` должен содержать хотя бы одну стадию и **обязательно стадию `pytest`**. Без неё политика
отклоняется: план не сможет покрыть связанные тесты при review/QA (`impact_not_covered`).
Обычный план выбирает связанные тесты для retry/review; неизвестное влияние расширяет выбор до
`full`, QA получает `full`. Пустой `focused`-выбор означает `not_run`, а не успешный прогон.

**Выбор по diff тикета.** При включённом `ticket_diff_selection` для `integration/*` планы
retry, review **и QA** выбирают тесты из `base..candidate` (`ticket-diff`), без расширения до
`full`. Включаются добавленные/изменённые Python-тесты и соответствующие Rust test targets.
Если тестов в diff нет, остаются статические стадии, а стадия тестов получает `not_run`.
Команды этих brief выводятся из плана. Это диагностика ветки тикета; для публикации остаётся
полный gate на финальном SHA. При `false` или цели в ветку по умолчанию действует обычный план.
Подробный контракт — [ADR 0023](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0023-incremental-verification.md).

Следующий фрагмент — шаблон из управляемого примера, с его порогом и таймаутами, **не defaults**.
Используйте его только после проверки команд и времени прогона на своём проекте.

```json {.ah-code-wrap}
{
  "verification_plan_policy": {
    "max_related_tests": 200,
    "ticket_diff_selection": false,
    "stages": [
      {"stage_id": "lint", "kind": "lint", "argv": ["make", "lint"], "timeout_seconds": 900},
      {"stage_id": "tests", "kind": "pytest", "argv": ["pytest", "-q", "-n", "8"], "timeout_seconds": 1800}
    ]
  }
}
```

## Связанные тесты {#related-tests}

| Поле | Контракт |
| --- | --- |
| `retry_verification.lint` | Обязательный массив shell-команд внутри заданного `retry_verification`; может быть `[]`. Выполняется перед выбранными тестами developer-retry. |
| `retry_verification.test_command` | Обязательная непустая shell-строка внутри `retry_verification`. К ней одной командой добавляются экранированные пути `related_tests` из Context Package. |
| `test_path_patterns` | Массив непустых glob-строк для распознавания тестовых путей при delta-review. Без поля или при `[]` используются `tests/**`, `**/tests/**`, `**/test_*.py`, `**/*_test.py`. |

Без `retry_verification` или без связанных тестов retry сохраняет обычные команды developer.
Этот механизм сам по себе не меняет первый developer-dispatch, review и полный QA. План
проверки, если он настроен, дополнительно задаёт выбор по ChangeImpact или diff тикета.

`test_path_patterns` не задаёт права записи тест-автора. Его зоны `test_paths` и runner находятся
в [project.json](../project.md); правила запуска описаны в [гайде test-author](../../../agents/test-author.md).

## Repo Map и Context Package {#context}

Repo Map — обзор tracked-файлов закреплённого commit: пути и, при доступном parser bundle,
сигнатуры и связи. Это не полный текст репозитория и не точный call graph. Context Package
собирает diff, стартовые файлы/указатели, зависимости, связанные тесты и справочный контекст
в пределах бюджета. Кэш карты не служит источником истины.

### Фильтры и лимиты Repo Map

Необязательный `repo_map_policy` дополняет встроенные исключения секретов, зависимостей,
сгенерированных и бинарных файлов. Пустой allow-list не отменяет эти исключения.

| Поле | Контракт |
| --- | --- |
| `repo_map_policy.allow_paths` | Массив glob-строк, default `[]`: без дополнительного ограничения по allow-list. Непустой список разрешает только совпавшие пути. |
| `repo_map_policy.deny_paths` | Массив glob-строк, default `[]`: дополнительные исключения путей. |
| `repo_map_policy.redact_paths` | Массив glob-строк, default `[]`. Текущий фильтр исключает совпавший путь из карты целиком, а не только тело файла. |
| `repo_map_policy.redact_symbols` | Массив glob-строк имён символов, default `[]`: скрывает совпавшие функции/классы из карты. |
| `repo_map_policy.max_files` | Целое ≥ 1, default `10000`: предел числа файлов. |
| `repo_map_policy.max_file_bytes` | Целое ≥ 1, default `2000000`: предел размера файла для обработки, в байтах. |
| `repo_map_policy.max_path_length` | Целое ≥ 1, default `4096`: предел длины пути в символах. |
| `repo_map_policy.max_symbol_length` | Целое ≥ 1, default `256`: предел длины имени символа. |
| `repo_map_policy.max_signature_length` | Целое ≥ 1, default `2048`: предел длины сигнатуры. |
| `repo_map_policy.timeout_seconds` | Целое ≥ 1, default `10`: таймаут Git-вызовов в секундах. |
| `repo_map_policy.max_tokens` | Целое ≥ 1. Бюджет итогового JSON карты: без заданного бюджета CLI/политики — `4000`. Явный CLI-бюджет не может превышать заданный потолок политики. |

Элементы массивов — непустые строки; glob сопоставляются с учётом регистра. В управляемом
примере `timeout_seconds: 30` и `max_tokens: 8000` — это выбранные значения, не defaults.

### Уровень карты и parser bundle

| Поле | Контракт |
| --- | --- |
| `repo_map_policy.tier` | `full` или `minimal`, default `full`: попытка семантического разбора либо только список путей. При недоступном/непроверенном bundle возможна деградация до `minimal` с причиной. |
| `repo_map_policy.min_tier` | `full` или `minimal`. Без поля гейт по tier не задан. Определяет минимальный уровень для допуска dispatch. |
| `repo_map_policy.min_tier_by_role.architect` | `full` или `minimal`: переопределяет общий минимум для architect. Без ключа действует `min_tier`, если он задан. |
| `repo_map_policy.min_tier_by_role.developer` | Такой же override для developer. |
| `repo_map_policy.min_tier_by_role.code-review` | Такой же override для code-review. |
| `repo_map_policy.parser_bundle_registry_paths` | Массив непустых строк, default `[]`: дополнительные локальные каталоги поиска bundle; относительные пути считаются от репозитория. Встроенный локальный registry проверяется первым. |
| `repo_map_policy.parser_bundle_timeout_seconds` | Целое ≥ 1, default `30`: таймаут parser subprocess в секундах. |
| `repo_map_policy.parser_bundle_max_output_bytes` | Целое ≥ 1, default `10000000`: предел вывода parser subprocess в байтах. |

В `repo_map_policy.min_tier_by_role` разрешены только три перечисленные роли. Остальные
используют общий минимум или работают без гейта, если он не задан. `tier: full` сам по себе
не гарантирует полный разбор; `min_tier: full` блокирует dispatch с деградировавшей картой.
Не снижайте этот минимум автоматически ради обхода ошибки. Bundle проверяется по lock и хешам;
сетевая установка во время dispatch не выполняется. Подробнее —
[ADR 0008](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0008-repo-map.md).

### Бюджет Context Package

В необязательном `context_package_policy` все значения — целые ≥ 1.

| Поле | Контракт |
| --- | --- |
| `context_package_policy.max_tokens` | Default `200000`: потолок оценки токенов всего пакета. |
| `context_package_policy.context_window_tokens` | Default `250000`: настроенное окно целевой модели; само поле не проверяет лимит провайдера. |
| `context_package_policy.reserved_prompt_tokens` | Default `20000`: резерв под инструкции и системный промпт. |
| `context_package_policy.symbol_graph_depth` | Default `2`: глубина обхода графа символов/импортов при сборке. |
| `context_package_policy.max_related_tests` | Default `25`: предел связанных тестов. Превышение останавливает сборку пакета с ошибкой, без молчаливого отсечения. |
| `context_package_policy.min_starting_files` | Default `5`: минимум стартовых файлов при ручной регистрации. |
| `context_package_policy.max_starting_files` | Default `10`: максимум стартовых файлов. |
| `context_package_policy.section_index_min_tokens` | Default `20000`: порог, начиная с которого большой Markdown/Python-файл может войти оглавлением/индексом символов с диапазонами строк. |

Условия: `min_starting_files ≤ max_starting_files`, резерв меньше окна,
`max_tokens ≤ context_window_tokens − reserved_prompt_tokens`. Если пакет всё равно не помещается,
сборка завершается ошибкой. Индекс применяется там, где его можно построить и он сокращает объём;
это не разрешение молча терять контекст.

Проверяйте эти соотношения с учётом defaults: текущая canonical validation сверяет бюджет,
только когда все три числа заданы явно. Например, один `max_tokens: 240000` проходит эту
проверку, но с defaults окна и резерва превышает доступные `230000`; подготовка Context Package
отклонит такой конфиг. Успешная валидация частичного объекта не заменяет сверку итоговых лимитов.

Это отдельные бюджеты: число тестов **плана** расширяет прогон, число тестов **пакета** ограничивает
его сборку. На dispatch действует ещё и `adaptive_continuation_policy.context_limit` из
[политик](policies.md#continuation): увеличение окна пакета не повышает бюджет роли.

Фрагмент со значениями по умолчанию; перед применением сопоставьте окно с выбранной моделью.
Управляемый пример использует более высокие `max_tokens: 260000` и `context_window_tokens: 300000`.

```json {.ah-code-wrap}
{
  "context_package_policy": {
    "max_tokens": 200000,
    "context_window_tokens": 250000,
    "reserved_prompt_tokens": 20000,
    "symbol_graph_depth": 2,
    "max_related_tests": 25,
    "min_starting_files": 5,
    "max_starting_files": 10,
    "section_index_min_tokens": 20000
  }
}
```

## Настройка с агентом {#agent-setup}

Промпты сначала исследуют текущую конфигурацию и спрашивают о неизвестном. Полный gate,
установку зависимостей и сборку parser bundle агент запускает только отдельным действием,
не в ходе настройки.

??? quote ah-skill-text "Промпт для агента: команды, профили и планы QA"

    ```text
    Help me configure verification for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema and managed
    example, build/test manifests, CI configuration and existing verification scripts.
    Inspect existing read-only health/config checks. Do not run arbitrary project commands yet.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Establish the full clean-room QA command list first. Then ask which focused developer
    and independent review commands are acceptable. Explain missing-field fallback to the
    full list and that explicit empty lists provide no role checks; never silently empty a gate.
    Ask whether QA preparation is needed. Separate environment probes from offline project-file
    checks; neither a preparation error alone nor missing probes proves an infrastructure cause.
    Ask whether path profiles are useful. Explain first whole-scope match and batch freezing.
    Use only commands and paths found in this repository or explicitly supplied by me.
    Ask whether verification_plan_policy is needed. If yes, agree on max_related_tests,
    stage argv and measured/justified timeouts. Require unique stage IDs and a pytest stage;
    explain how this requirement fits the project's actual test runner before proposing a plan.
    Explain ordinary full/focused selection, unknown impact and empty-selection not_run.
    Ask separately before enabling ticket_diff_selection: it changes retry, review AND QA
    for integration/* to tests in the ticket diff, without widening to full. It does not
    replace the final full release gate. Leave it false unless I explicitly choose it.
    Ask whether retry_verification and test_path_patterns need changes. Distinguish retry's
    Context Package tests from plan ChangeImpact and from test-author write zones in project.json.

    Preserve unrelated settings. Show the exact proposed diff, command provenance, fallbacks,
    empty lists and which settings need a new batch. Wait for approval, then apply only that
    diff with Edit/Write. Run installed config validate --canonical --json and harness health.
    Report checks and remaining gaps. Ask separately before running the actual full QA,
    preparation or network probes. Do not create batches, send workers, install dependencies,
    weaken release checks, migrate state, change Git, commit or open a PR.
    ```

??? quote ah-skill-text "Промпт для агента: Repo Map и бюджет контекста"

    ```text
    Help me configure repo_map_policy and context_package_policy for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema and managed
    example, Repo Map documentation, existing parser bundle metadata and model assignments.
    Use tracked path metadata to understand languages and scope; do not read authentication
    files, excluded secret files or token/key values. Do not install or fetch a bundle.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.

    Ask which source paths should be included/excluded and which symbols should be hidden.
    Explain built-in exclusions, case-sensitive globs and that redact_paths excludes whole
    paths in the current implementation. Preserve existing privacy restrictions.
    Ask whether path-only minimal is sufficient or parser-backed full is needed, then agree
    separately on global/per-role minimum tiers. Only architect, developer and code-review
    have role overrides. Full generation can degrade; a required full tier blocks dispatch.
    Check local bundle provenance/availability without changing it. Explain blockers instead
    of lowering minimum tiers or inventing registry paths. Agree on justified size/time limits.
    Ask for the chosen model's supported context window if local evidence is insufficient.
    Agree on reserved prompt headroom and package/role budgets; validate max_tokens fits
    context_window_tokens minus reserved_prompt_tokens and does not ignore the role budget.
    Resolve omitted values to defaults yourself: canonical validation currently misses an
    over-budget partial object when window or reserve is omitted; package preparation rejects it.
    Agree on graph depth, starting-file bounds and the section-index threshold.
    Explain that the package's related-test cap fails on overflow, while the plan's cap widens
    test selection. Never silently truncate tests or raise caps merely to hide a failure.

    Use only supported fields and evidence or my answers. Show the exact proposed diff,
    effective defaults, tier admission consequences and assumptions. Wait for approval,
    then apply only that diff with Edit/Write. Run installed config validate --canonical --json
    and harness health. Report checks and remaining gaps, including parser execution or model
    limits not verified. Do not register packages, create batches, send workers, install/build
    bundles, change privacy policy, migrate state, change Git, commit or open a PR.
    ```

## Проверка конфигурации {#config-validation}

После изменения выполните [canonical validation и health](index.md#config-validation).
Они проверяют контракт, но не доказывают, что команды работают в clean-room, образ готов,
bundle доступен или пакет помещается в реальное окно модели. Такие проверки выполняйте отдельно
на подходящем кандидате; сохранённый успешный прогон другого SHA не заменяет новый QA.
