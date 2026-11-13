# Test-author

`test-author` пишет за developer **один поведенческий тест** для следующего шага
Red → Green → Refactor и запускает его через защищённый runner. Это необязательный помощник.
Production-код, скелет, рефакторинг и orchestration остаются за developer. test-author работает
как субагент внутри сессии developer, отдельной роли в ledger у него нет. Если защита недоступна,
developer продолжает обычный TDD, а незащищённого автора не запускает.

## Как включить тест-автора {#enable}

1. Задайте [`test_paths` и `test_runner`](#configuration) и добавьте в `.harness/project.json` блок
   `test_author` с runtime, model и effort. Если в `.harness/orchestration.json` есть план
   developer, этот блок из плана добавит `harness health --fix`. Существующий блок он не меняет.
2. Один раз откройте Claude Code в основном checkout репозитория и примите диалог доверия.
   Worktree этого репозитория отдельного доверия не требуют.
3. Запустите `harness health`. Под каждой строкой `hooks.test_author_*` со статусом warn есть шаг
   исправления: выполните его. Строки проверяют блок `test_author`, корень проекта по Git, доверие,
   guard, runner и probe изоляции. Повторяйте health, пока все строки не станут ok. Guard и probe
   запускают скрипты проекта, поэтому до принятия доверия health их пропускает.

```bash {.ah-code-wrap}
harness health --fix
```

## Поля project.json {#configuration}

Настройки лежат в `.harness/project.json`. Чтобы включить test-author, нужны `test_paths` и
`test_runner`. Короткому маршруту нужен ещё явный `test_author`. Для остального проекта все три
группы необязательны. В примере pytest и существующий каталог `tests`. Модель и effort в нём
выбрал пользователь, это **не значения по умолчанию**. Подробнее о файле на странице
[project.json](project.md).

```json {.ah-code-wrap}
{
  "test_paths": ["tests/**"],
  "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
  "test_author": {"runtime": "claude", "model": "sonnet", "effort": "high"}
}
```

| Поле | Контракт |
| --- | --- |
| `test_paths` | Непустой массив уникальных относительных glob без `..`. Автор принимает только существующие зоны `<каталог>/**` с литеральными сегментами. Остальные ограничения описаны ниже. |
| `test_runner.command` | Argv без shell, минимум два непустых строковых аргумента. Ровно один отдельный `{test_id}`, и он не первый: runner подставляет на его место один выбранный test ID. Два placeholder отклоняет `harness health`, хотя схема draft-07 не может полностью выразить это ограничение. |
| `test_runner.build.command` | Обязателен, если задан `build`: непустой argv, без `{test_id}` и NUL. Запускает сборку в защищённой фазе. |
| `test_runner.build.artifact_paths` | Обязателен внутри `build`: непустой массив уникальных литеральных `<каталог>/**`. Каталоги должны существовать заранее и быть пустыми. Runner подключает на их место свежие каталоги: сборке на запись, тесту на чтение. Непустой каталог runner за вас не очищает. |
| `test_runner.database.engine` | Обязателен внутри `database`: ID production-движка по `[a-z][a-z0-9_-]{0,63}`. СУБД по этому полю не устанавливается. |
| `test_runner.database.test_ids` | Обязательный непустой массив уникальных непустых строк, это селекторы `fnmatchcase`. БД запускается только для теста, который совпал с селектором. |
| `test_runner.database.command` | Обязательный непустой argv без `{test_id}` и NUL. Запускает отдельный сервер БД в foreground внутри песочницы. |
| `test_runner.database.ready_command` | Обязательный непустой argv без `{test_id}` и NUL. Проверяет, что сервер готов. Shell-подстановки в argv нет. |
| `test_author.runtime` | Обязателен в short-профиле: ID по `[A-Za-z0-9][A-Za-z0-9_-]*`. Сейчас защищённый адаптер есть только для `claude`. С другим ID автор не запускается и другой CLI вместо него не выбирается. |
| `test_author.model` | Обязателен: ID модели или alias в CLI по `[A-Za-z0-9][A-Za-z0-9._:-]*`, без пробелов. Модели по умолчанию нет. |
| `test_author.effort` | Обязателен: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` или `ultra`. Значение, которое принимает схема, выбранный CLI может не поддерживать. Значения по умолчанию нет. |

Без `build` отдельной фазы сборки нет, без `database` нет отдельного сервера БД. Если объект
задан, в нём нужны **все** перечисленные поля. Во время сборки исходники и `test_paths` доступны
только на чтение. БД получает приватные каталоги через `HARNESS_TEST_DATABASE_DIR` и
`HARNESS_TEST_DATABASE_SOCKET_DIR`, без TCP и без доступа к сервисам хоста. Проектный wrapper
читает эти переменные сам. Для чистой доменной логики БД не нужна, а SQL проверяйте на
production-движке. Подробности в [контракте runner](../../hooks/run-test.md).

## Короткий маршрут /fast-implement {#short-route}

Короткий маршрут берёт runtime, model и effort **из `test_author` проекта**, даже если у текущей
сессии другая модель. До первого теста developer согласует требование и seam, то есть публичную
границу, на которой проверяется поведение. В этом маршруте нет coordinator, architect и
независимой QA.

В корне установленного целевого проекта проверьте выбор и защиту:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo .
python3 -I -B .harness/health/test_author.py preflight --repo .
```

`resolve` показывает runtime, model, effort и `source: project`. `preflight` отвечает одной
JSON-строкой, и автора разрешает только точный ответ `{"status":"ok"}`. Exit code 0 ещё не
означает готовность: отказ тоже приходит с кодом 0 в виде `{"status":"disabled","reason":"…"}`.
Проба изоляции создаёт и удаляет временную песочницу. LLM, выбранный тест, сборку и БД она не
запускает.

Маршрут сохраняет согласованное требование и один сценарий в локальный prompt-файл и вызывает
launcher. Эта команда сама запускает CLI агента:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo .   --prompt-file '<local-prompt-file>'
```

Подставьте существующий файл с заданием, без секретов. Launcher ещё раз проверяет защиту и
передаёт выбранные model и effort, а задание отправляет через stdin. Если runtime не поддержан,
launcher не заменяет его другим.

## Полный маршрут /implement {#full-route}

Автор берёт `resolved_runtime`, `resolved_model` и `resolved_effort` из **утверждённого brief
developer**. Short-профиль и последующие правки orchestration этот выбор не меняют.
Шаблон `.claude/agents/test-author.md` задаёт `model: inherit` и не задаёт своего effort.
Developer вызывает `Agent(test-author)`, не переопределяя model и effort.

Для external developer harness и защита должны быть установлены **в worker worktree**.
Worktree доверенного репозитория отдельного диалога доверия не требует. Если основной checkout
не доверен, откройте его в Claude Code и примите диалог сами. Состояние orchestration из
основного checkout в worktree не копируется. В сессии developer, запущенной в этом worktree,
выполните:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo . \
  --brief '<approved-developer-brief.json>'
python3 -I -B .harness/health/test_author.py preflight --repo . \
  --brief '<approved-developer-brief.json>'
```

Источник выбора здесь `developer`. В approved brief нужен инструмент `Agent(test-author)` или
`Agent`. Если политика инструментов уже есть, проверьте `tool_policy.roles.developer` и сохраните
остальные разрешения. Старое approval расширять нельзя: изменение требует нового propose и
approval. Правила инструментов описаны в [назначениях ролей](orchestration/roles.md).

Автор пишет только туда, где test-зона пересекается со scope brief worker. Логи runner в linked
worktree общие: `<main>/.harness/.sandboxes/runs/isolated-test-<run_id>/log.txt`. Developer
передаёт путь к этому evidence, но не получает права писать production-код основного checkout.

Если рядом есть отдельный worker worktree, защита основного checkout отвечает `checkout_mismatch`.
Поэтому in-process developer вызывает автора через launcher своего worktree:
`python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <brief> --prompt-file <файл>`.
При отказе developer продолжает обычный TDD и записывает причину. Отказ автора не создаёт
новый dispatch, blocker или запись ledger. Цикл и требование независимо выводить ожидание теста
описаны в полном [контракте test-author](../../agents/test-author.md).

## Условия активации {#activation}

- Linux, bubblewrap 0.9.0 или новее и непривилегированные user namespaces. На Windows и macOS
  preflight отвечает `isolation_unavailable`. Checkout не лежит в `/tmp`, `/run`, `/dev` или `/proc`.
- Установлены agent, исполняемые scoped guard и runner. Нужны Bash и Python, а также инструменты
  выбранного теста, сборки и БД. Если инструмент не проверен, запись его argv в конфиг не делает
  его поддержанным.
- `test_paths` указывает существующие литеральные каталоги. На пути нет symlink, файлов с
  несколькими hard links и вложенных друг в друга зон. Первый сегмент не `.git`, `.harness`,
  `.claude`, `.agents` или `.codex`, в остальных сегментах нет `*?[]{}` и обратного слеша.
  Например, `tests/*.py` может пройти схему, но автора не включит.
- Checkout лежит в корне своего рабочего дерева Git. `CLAUDE_PROJECT_DIR` задавать не обязательно,
  но если он задан, он должен совпадать с этим корнем. Claude Code не запущен с
  `CLAUDE_CODE_SIMPLE=1` или `CLAUDE_CODE_SAFE_MODE=1`. Человек принял доверие для **этого checkout
  или основного checkout его репозитория**. Не записывайте доверие вручную в auth- или
  trust-файл: откройте проект и примите диалог.
- Выбран runtime с защищённым адаптером. Сейчас это только Claude Code, минимальная версия CLI в
  harness не закреплена. Preflight проверяет agent и hook статически, живое срабатывание
  подтверждается отдельно.

Guard разрешает автору `Write` и `Edit` только в тестовой зоне, а `Bash` только для одного вызова
`run-test.sh <test-id>` (в том числе через доверенный системный Bash). Shell-метасимволы, `--probe`
и другие команды автора guard отклоняет. `--probe` вызывают preflight и developer, автору он
недоступен, чтобы тот не обошёл guard.

## Причины отказа preflight {#refusals}

Preflight останавливается на первом отказе. Исправьте причину и повторите проверку. Не отключайте
guard ради `ok`. В таблице собраны отказы выбора исполнителя и проверок защищённого адаптера.

| Код | Причина → действие |
| --- | --- |
| `test_author_missing` | Нет short-профиля → для короткого маршрута задайте runtime, model и effort, для полного передайте approved brief. |
| `test_author_config_invalid` | Профиль или brief некорректны, либо в agent остались устаревшие фиксированные model и effort → сверьте выбранный источник с шаблоном, не подставляйте другой runtime. Локальный seed заменяйте только после просмотра diff. |
| `runtime_unsupported` | Для runtime нет защищённого адаптера → обычный TDD. Другой CLI автоматически не подключается. |
| `checkout_mismatch` | Проверка идёт в другом checkout → запускайте защиту в worker с его brief. |
| `project_dir_mismatch` | Переданный `CLAUDE_PROJECT_DIR` указывает не на корень Git checkout → запускайте автора из сессии этого worktree или через его launcher. Не подменяйте значение переменной, чтобы выдать один checkout за другой. |
| `project_untrusted` | Checkout не корень Git, или доверие не принято ни для него, ни для основного checkout репозитория → откройте основной checkout в Claude Code и примите диалог. |
| `claude_code_unsupported` | Режим CLI отключает нужные hooks → используйте поддержанное окружение и не обходите проверку. |
| `agent_missing` | Нет корректного `.claude/agents/test-author.md` → проверьте установку в нужном checkout. |
| `scoped_hook_unsupported` | В frontmatter нет ожидаемого scoped PreToolUse hook → сравните файл с текущим шаблоном и сохраните защиту. |
| `test_paths_missing` | Нет тестовых зон → настройте существующие каталоги тестов. |
| `test_runner_missing` | Нет настройки runner → задайте проверенный argv для запуска одного теста. |
| `config_invalid` | Неверный формат полей runner/зон → исправьте конфигурацию по контракту. |
| `write_zone_rejected` | Недопустимый glob, symlink, hard link или пересечение зон → выберите допустимые каталоги, не захватывая production-код. |
| `guard_hook_unavailable` | Guard отсутствует, не исполняется или отвечает неверно → проверьте установленный файл и Python. Успешная проверка guard не доказывает живое срабатывание hook. |
| `isolation_unavailable` | Песочницу подтвердить не удалось → проверьте Linux, bubblewrap, namespaces и расположение checkout. Если не помогло, обычный TDD. |
| `runner_unavailable` | Runner или нужный интерпретатор отсутствует или не работает → проверьте установленные файлы и PATH. |
| `selector_unavailable` | Защищённый адаптер не может вызвать модуль выбора → проверьте целостность `.harness/health/test_author.py`. |
| `orchestration_unavailable` | Диагностика плана не может загрузить orchestration → проверьте установленный backend. Short-профиль за пользователя при этом не выбирается. |
| `preflight_failed` | Ответ неизвестный, невалидный или слишком длинный, либо preflight упал → исследуйте установленную защиту и не принимайте произвольный текст за `ok`. |

`agent_tool_unavailable` не входит в JSON-причины общего preflight: так developer помечает своё
решение, если в brief нет инструмента `Agent`. Launcher может отказать с `runtime_unavailable`,
`prompt_missing`, `prompt_unavailable` или `author_unavailable`. Проверьте выбранный CLI, файл
задания и завершение процесса. Ни один из этих отказов не разрешает незащищённый запуск.

## Живая проверка {#live-check}

`harness health .` показывает `hooks.test_author`, выбранные runtime, model, effort и их источник.
Health проверяет план developer с пометкой `planned`, а если плана нет, проверяет short-профиль.
Approved brief эта проверка не заменяет. Если проект не включил test-author, проверка
пропускается. Если необязательный автор недоступен, health предупреждает, а обычный маршрут
работает дальше. Health не запускает LLM, тест, сборку или БД.

В **исходниках самого harness** есть отдельная живая проверка. Ей нужен вход в Claude Code, и
она расходует квоту, поэтому согласуйте запуск заранее:

```bash {.ah-code-wrap}
make test-author-probe
```

Проверка берёт runtime, model и effort из плана developer. Она проверяет guard, поведенческий
Red, вызов автора из external developer в worker и Green на неизменённом тесте. Обычные verify и
CI её не запускают. Результаты лежат в файлах `test-author-probe-*.json` в общем каталоге
`.harness/.sandboxes/reports/`: этап, checkout, exit code, время, а также usage и стоимость, если
их сообщил runtime. Неизвестные метрики остаются `null`. Лимит не считается расходом, а долю
подписочной квоты проверка из USD не вычисляет.

## Ограничения и обычный TDD {#limits}

В этой поставке проверены Python-тесты через unittest и pytest. Rust-тесты
`native/harness-runtime/crates/*/tests` test-author не поддерживает: то, что схема принимает
любой argv, не значит, что стек поддержан. Обязательные Rust QA-команды остаются в силе.

Ошибка импорта, компиляции, fixture, сборки (`build_failed`, `build_timeout`) или недоступная БД
(`database_unavailable`) не считаются поведенческим Red. Если автор ответил `needs_skeleton`,
developer добавляет только типы и сигнатуры. Если `contract_gap`, developer уточняет требование.
Ослаблять ожидание ради Green нельзя. После трёх неудачных вызовов подряд по одному тесту
developer идёт по обычному пути blocker. Если же автор не включился, developer продолжает обычный
TDD, и новый blocker или состояние в ledger не появляются.

## Настройка с агентом {#agent-setup}

??? quote ah-skill-text "Промпт для агента: короткий маршрут test-author"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the test-author guide and current test_paths/test_runner/test_author. Ask which explicit
    runtime/model/effort the short route should use; no defaults or runtime substitution.
    Check supported protected adapter, literal test zones and single-test argv. Use resolve and
    preflight for diagnostics only after explaining the temporary isolation probe. Do not run an
    author/test to configure it; ordinary TDD remains available when protection is unavailable.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: полный маршрут test-author"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the approved developer brief in its worker checkout. Inherit resolved_runtime/model/effort,
    never the short profile or later live orchestration settings. Confirm worker-local installation,
    user trust of the worker or its repository's main checkout and approved Agent(test-author)
    permission; never spoof trust or widen
    approved tools. Keep model: inherit without effort override. Use preflight with the brief in
    the correct checkout; refusal leaves ordinary TDD, not an unprotected or substituted author.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: живая проверка test-author"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Explain static hooks.test_author health/preflight versus actual scoped-hook execution.
    In the harness source, make test-author-probe needs login and spends quota. Ask explicitly
    before running it; do not select a cheaper model instead of the developer plan.
    Inspect sanitized test-author-probe reports only, never transcripts or credentials. Missing usage
    is null; a limit is not spent quota. If live execution is not authorized, report it unverified.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```
