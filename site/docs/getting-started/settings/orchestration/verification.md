# Верификация

В `.harness/orchestration.json` задаются команды проверок, правила выбора тестов и лимиты
контекста для ролей. Начните с полного QA, затем выделите быстрые проверки для developer и review.
Repo Map и Context Package настраивайте по размеру проекта и окну контекста модели.

«По умолчанию» на этой странице означает поведение, когда поле пропущено. Управляемый
`.harness/orchestration.example.json` содержит свои примеры значений: проверьте его команды и
лимиты на своём проекте. JSON-фрагменты ниже дополняют существующий конфиг.

## Полный gate {#full-gate}

| Поле | Контракт |
| --- | --- |
| `verification_commands` | Массив непустых строк: shell-команды полного QA. В управляемом примере `[]`; команды проекта задайте явно. Конфиг с пустым списком валиден, но `qa run` без команд откажется запускаться. |

Обычный clean-room QA выполняет весь список в отдельном checkout на `candidate_sha`. Зелёный
прогон developer или review это доказательство не заменяет. Если SHA изменился, нужен новый QA.
Правило полного gate перед publish описано в [QA gate](../../../guides/qa-gate.md). Исключение
для планов тикета в `integration/*` разобрано [ниже](#verification-plans).

## Быстрые проверки ролей {#role-checks}

| Поле | Контракт |
| --- | --- |
| `developer_verification_commands` | Массив непустых строк. Если поля нет, берётся `verification_commands`. Явный `[]` допустим, но тогда у developer нет проверок. |
| `review_verification_commands` | Такой же массив для независимой проверки кандидата в code-review. Без поля берётся `verification_commands`; явный `[]` допустим. |

В управляемом примере общие списки пустые, поэтому сам пример тесты не настраивает. Сначала
найдите рабочие команды проекта, затем выберите более узкие команды для быстрых циклов. В отчёте
роль перечисляет ровно команды из полученного brief и не подменяет их своими.

## Подготовка и диагностика QA {#qa-preparation}

| Поле | Контракт |
| --- | --- |
| `qa_preparation` | Массив shell-команд, по умолчанию `[]`. QA выполняет их в checkout кандидата до gate и останавливается на первой ошибке. При пустом списке QA сразу запускает проверки. |
| `qa_environment_probes` | Массив shell-команд, по умолчанию `[]`. Независимые пробы окружения в том же checkout; запускаются только после ошибки подготовки. Например, проверка доступности нужного реестра. |
| `qa_project_file_checks` | Массив shell-команд, по умолчанию `[]`. Независимые офлайн-проверки файлов проекта в том же checkout; запускаются только после ошибки подготовки. Например, согласованность manifest и lock-файла. |

Элементы этих массивов должны быть непустыми строками. Берите команды из реального toolchain
проекта: общей проверки сети или lock-файла здесь нет.

- Упала проверка файлов проекта: подтверждён дефект проекта.
- Упала проба окружения, а проверки файлов прошли: подтверждена инфраструктурная причина.
- Нужных проб или проверок нет, или результат ничего не доказывает: нужна диагностика. Один сбой
  установки зависимостей ещё не доказывает проблему инфраструктуры.

## Профили и планы проверки {#verification-plans}

### Профили области

`verification_profiles` задаёт необязательный массив профилей. При `batch create` coordinator
берёт **первый** профиль, чьи шаблоны покрывают все `allowed_paths` batch, и закрепляет его
команды для developer и review. Если ни один профиль не покрывает scope целиком, действуют общие
списки; пустая область профиль не выбирает. Профиль не заменяет полный список QA.

| Поле | Контракт |
| --- | --- |
| `verification_profiles[].paths` | Обязательный непустой массив путей или glob относительно корня репозитория. Без ведущего `/`, обратного слеша, пустых сегментов, `.` и `..`. |
| `verification_profiles[].developer` | Обязательный массив shell-команд developer; `[]` допустим. |
| `verification_profiles[].review` | Обязательный массив shell-команд code-review; `[]` допустим. |

Пример **для этого репозитория**: профиль взят из управляемого примера, `make verify` запускает
полный gate из Makefile. `pytest -n 8` требует pytest-xdist. Не переносите эти пути и команды в
другой проект без проверки.

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

Необязательный `verification_plan_policy` закрепляется при создании batch. При `dispatch propose`
coordinator строит по нему план для developer-retry, code-review и QA. У первого
developer-dispatch такого плана нет. Без политики действуют закреплённые списки команд.

| Поле | Контракт |
| --- | --- |
| `verification_plan_policy.max_related_tests` | Обязательное целое ≥ 1: порог числа тестов ChangeImpact. Если тестов больше, pytest расширяется до `full`. Значения по умолчанию нет; в управляемом примере `200`. |
| `verification_plan_policy.ticket_diff_selection` | Boolean, по умолчанию `false`. При `true` **и** цели `integration/*` включает выбор тестов по diff тикета, описанный ниже. |
| `verification_plan_policy.stages[].stage_id` | Обязательная непустая строка, уникальная среди стадий. |
| `verification_plan_policy.stages[].kind` | Обязателен: `lint`, `typecheck`, `pytest`, `clean-room` или `custom`. Выбор связанных тестов действует на `pytest`. |
| `verification_plan_policy.stages[].argv` | Обязательный непустой массив непустых строк: программа и аргументы, а не строка shell. Для `focused` pytest coordinator добавляет к нему выбранные nodeid. |
| `verification_plan_policy.stages[].timeout_seconds` | Обязательное целое ≥ 1: таймаут стадии в секундах. Общего значения по умолчанию нет. |

`stages` должен содержать хотя бы одну стадию, и среди них **обязательно стадию `pytest`**. Без
неё валидатор отклоняет политику: план не сможет покрыть связанные тесты в review и QA
(`impact_not_covered`). Обычный план выбирает связанные тесты для retry и review. Если влияние
неизвестно, выбор расширяется до `full`; QA получает `full`. Пустой выбор `focused` означает
`not_run`, а не успешный прогон.

**Выбор по diff тикета.** Если `ticket_diff_selection` включён и цель `integration/*`, планы
retry, review **и QA** берут тесты из `base..candidate` (`ticket-diff`) и не расширяются до
`full`. В выбор попадают добавленные и изменённые Python-тесты и соответствующие Rust test
targets. Если тестов в diff нет, остаются статические стадии, а стадия тестов получает `not_run`.
Команды этих brief coordinator выводит из плана. Это диагностика ветки тикета: для публикации
по-прежнему нужен полный gate на финальном SHA. При `false` или цели в ветку по умолчанию
действует обычный план. Подробный контракт описан в
[ADR 0023](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0023-incremental-verification.md).

Следующий фрагмент повторяет шаблон из управляемого примера с его порогом и таймаутами; это
**не значения по умолчанию**. Используйте его, только когда проверите команды и время прогона на
своём проекте.

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
| `retry_verification.test_command` | Обязательная непустая shell-строка внутри `retry_verification`. Coordinator добавляет к ней экранированные пути `related_tests` из Context Package и получает одну команду. |
| `test_path_patterns` | Массив непустых glob-строк, по которым delta-review узнаёт тестовые пути. Без поля или при `[]` действуют `tests/**`, `**/tests/**`, `**/test_*.py`, `**/*_test.py`. |

Если `retry_verification` нет или связанных тестов нет, retry сохраняет обычные команды
developer. Сам по себе этот механизм не меняет первый developer-dispatch, review и полный QA.
Настроенный план проверки дополнительно выбирает тесты по ChangeImpact или по diff тикета.

`test_path_patterns` не задаёт права записи test-author. Его зоны `test_paths` и runner задаются в
[project.json](../project.md); правила запуска описаны в [гайде test-author](../../../agents/test-author.md).

## Repo Map и Context Package {#context}

Repo Map показывает tracked-файлы закреплённого коммита: пути, а при доступном parser bundle ещё
сигнатуры и связи. Это не полный текст репозитория и не точный call graph. Context Package
собирает diff, стартовые файлы и указатели, зависимости, связанные тесты и справочный контекст в
пределах бюджета. Кэш карты не служит источником истины.

### Фильтры и лимиты Repo Map

Необязательный `repo_map_policy` дополняет встроенные исключения: секреты, зависимости,
сгенерированные и бинарные файлы. Пустой allow-list эти исключения не отменяет.

| Поле | Контракт |
| --- | --- |
| `repo_map_policy.allow_paths` | Массив glob-строк, по умолчанию `[]`: allow-list ничего не ограничивает. Непустой список пропускает только совпавшие пути. |
| `repo_map_policy.deny_paths` | Массив glob-строк, по умолчанию `[]`: дополнительные исключения путей. |
| `repo_map_policy.redact_paths` | Массив glob-строк, по умолчанию `[]`. Сейчас фильтр убирает совпавший путь из карты целиком, а не только тело файла. |
| `repo_map_policy.redact_symbols` | Массив glob-строк имён символов, по умолчанию `[]`: скрывает совпавшие функции и классы из карты. |
| `repo_map_policy.max_files` | Целое ≥ 1, по умолчанию `10000`: предел числа файлов. |
| `repo_map_policy.max_file_bytes` | Целое ≥ 1, по умолчанию `2000000`: предел размера обрабатываемого файла в байтах. |
| `repo_map_policy.max_path_length` | Целое ≥ 1, по умолчанию `4096`: предел длины пути в символах. |
| `repo_map_policy.max_symbol_length` | Целое ≥ 1, по умолчанию `256`: предел длины имени символа. |
| `repo_map_policy.max_signature_length` | Целое ≥ 1, по умолчанию `2048`: предел длины сигнатуры. |
| `repo_map_policy.timeout_seconds` | Целое ≥ 1, по умолчанию `10`: таймаут Git-вызовов в секундах. |
| `repo_map_policy.max_tokens` | Целое ≥ 1: бюджет итогового JSON карты. Если бюджет не задан ни в CLI, ни в политике, действует `4000`. Бюджет из CLI не может превышать потолок из политики. |

Элементы массивов должны быть непустыми строками; glob сравниваются с учётом регистра.
`timeout_seconds: 30` и `max_tokens: 8000` в управляемом примере выбраны для примера и не являются
значениями по умолчанию.

### Уровень карты и parser bundle

| Поле | Контракт |
| --- | --- |
| `repo_map_policy.tier` | `full` или `minimal`, по умолчанию `full`: попытка семантического разбора или только список путей. Если bundle недоступен или не проверен, карта может деградировать до `minimal` с указанием причины. |
| `repo_map_policy.min_tier` | `full` или `minimal`. Без поля проверки уровня нет. Задаёт минимальный уровень карты, при котором dispatch допускается. |
| `repo_map_policy.min_tier_by_role.architect` | `full` или `minimal`: заменяет общий минимум для architect. Без ключа действует `min_tier`, если он задан. |
| `repo_map_policy.min_tier_by_role.developer` | Такая же замена для developer. |
| `repo_map_policy.min_tier_by_role.code-review` | Такая же замена для code-review. |
| `repo_map_policy.parser_bundle_registry_paths` | Массив непустых строк, по умолчанию `[]`: дополнительные локальные каталоги, где искать bundle; относительные пути считаются от репозитория. Встроенный локальный registry проверяется первым. |
| `repo_map_policy.parser_bundle_timeout_seconds` | Целое ≥ 1, по умолчанию `30`: таймаут parser subprocess в секундах. |
| `repo_map_policy.parser_bundle_max_output_bytes` | Целое ≥ 1, по умолчанию `10000000`: предел вывода parser subprocess в байтах. |

`repo_map_policy.min_tier_by_role` принимает только три перечисленные роли. Остальные роли
используют общий минимум или работают без проверки уровня, если минимум не задан. `tier: full` сам
по себе полный разбор не гарантирует; `min_tier: full` блокирует dispatch с деградировавшей
картой. Не снижайте минимум автоматически, чтобы обойти ошибку. Bundle проверяется по lock и
хешам; во время dispatch по сети ничего не устанавливается. Подробнее в
[ADR 0008](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0008-repo-map.md).

### Бюджет Context Package

Все значения необязательного `context_package_policy` задаются целыми числами ≥ 1.

| Поле | Контракт |
| --- | --- |
| `context_package_policy.max_tokens` | По умолчанию `200000`: потолок оценки токенов всего пакета. |
| `context_package_policy.context_window_tokens` | По умолчанию `250000`: настроенное окно целевой модели. Лимит провайдера это поле не проверяет. |
| `context_package_policy.reserved_prompt_tokens` | По умолчанию `20000`: резерв под инструкции и системный промпт. |
| `context_package_policy.symbol_graph_depth` | По умолчанию `2`: глубина обхода графа символов и импортов при сборке. |
| `context_package_policy.max_related_tests` | По умолчанию `25`: предел связанных тестов. Если тестов больше, сборка пакета завершается ошибкой; молча тесты не отбрасываются. |
| `context_package_policy.min_starting_files` | По умолчанию `5`: минимум стартовых файлов при ручной регистрации. |
| `context_package_policy.max_starting_files` | По умолчанию `10`: максимум стартовых файлов. |
| `context_package_policy.section_index_min_tokens` | По умолчанию `20000`: начиная с этого размера большой Markdown- или Python-файл может войти в пакет оглавлением или индексом символов с диапазонами строк. |

Условия: `min_starting_files ≤ max_starting_files`, резерв меньше окна,
`max_tokens ≤ context_window_tokens − reserved_prompt_tokens`. Если пакет всё равно не помещается,
сборка завершается ошибкой. Индекс применяется там, где его можно построить и где он сокращает
объём; терять контекст молча он не разрешает.

Сверяйте эти соотношения с учётом значений по умолчанию: canonical validation сейчас проверяет
бюджет, только когда все три числа заданы явно. Например, один `max_tokens: 240000` эту проверку
проходит, но с окном и резервом по умолчанию превышает доступные `230000`, и подготовка Context
Package такой конфиг отклонит. Успешная проверка частичного объекта не заменяет сверку итоговых
лимитов.

Эти бюджеты разные: число тестов **плана** расширяет прогон, число тестов **пакета** ограничивает
его сборку. На dispatch действует ещё `adaptive_continuation_policy.context_limit` из
[политик](policies.md#continuation): если увеличить окно пакета, бюджет роли не вырастет.

Фрагмент со значениями по умолчанию. Перед применением сопоставьте окно с выбранной моделью.
Управляемый пример задаёт больше: `max_tokens: 260000` и `context_window_tokens: 300000`.

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

Промпты сначала изучают текущую конфигурацию и спрашивают о неизвестном. Полный gate, установку
зависимостей и сборку parser bundle агент запускает только отдельным действием, не во время
настройки.

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

После изменения выполните [canonical validation и health](index.md#config-validation). Они
проверяют контракт, но не доказывают, что команды работают в clean-room, образ готов, bundle
доступен или пакет помещается в реальное окно модели. Это проверяйте отдельно на подходящем
кандидате; сохранённый успешный прогон другого SHA не заменяет новый QA.
