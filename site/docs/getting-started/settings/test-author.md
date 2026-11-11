# Test-author

`test-author` — необязательный помощник developer: пишет **один поведенческий тест** следующего
шага Red → Green → Refactor и запускает его через защищённый runner. Production-код, скелет,
рефакторинг и orchestration остаются у developer. Это in-session субагент, а не отдельная роль
ledger. Если защита недоступна, developer продолжает обычный TDD без незащищённого автора.

## Поля project.json {#configuration}

Настройки находятся в `.harness/project.json`. Для активации нужны `test_paths` и `test_runner`;
короткому маршруту дополнительно нужен явный `test_author`. Все три группы необязательны для
проекта в целом. Пример ниже использует pytest и существующий каталог `tests`: модель и effort
показывают выбор пользователя, **не defaults**. Подробнее о файле — [project.json](project.md).

```json {.ah-code-wrap}
{
  "test_paths": ["tests/**"],
  "test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]},
  "test_author": {"runtime": "claude", "model": "sonnet", "effort": "high"}
}
```

| Поле | Контракт |
| --- | --- |
| `test_paths` | Непустой массив уникальных относительных glob без `..`. Для автора — только существующие зоны `<каталог>/**` с литеральными сегментами; дополнительные ограничения ниже. |
| `test_runner.command` | Argv без shell, минимум два непустых строковых аргумента. Ровно один отдельный `{test_id}`, не первый: runner заменяет его одним выбранным test ID. Два placeholder отклоняет `harness health`, хотя draft-07 схема не выражает это ограничение полностью. |
| `test_runner.build.command` | Обязателен внутри заданного `build`: непустой argv, без `{test_id}` и NUL. Запускает сборку в защищённой фазе. |
| `test_runner.build.artifact_paths` | Обязательный внутри `build` непустой массив уникальных литеральных `<каталог>/**`. Заранее существующие пустые каталоги; сборка получает свежие backing directories на запись, тест — на чтение. Runner не очищает непустой каталог за пользователя. |
| `test_runner.database.engine` | Обязателен внутри `database`: ID production-движка по `[a-z][a-z0-9_-]{0,63}`. Не означает автоматическую установку СУБД. |
| `test_runner.database.test_ids` | Обязательный непустой массив уникальных непустых строк — селекторов `fnmatchcase`. Только совпавший тест запускает БД. |
| `test_runner.database.command` | Обязательный непустой argv без `{test_id}` и NUL. Запускает отдельный сервер БД в foreground внутри песочницы. |
| `test_runner.database.ready_command` | Обязательный непустой argv без `{test_id}` и NUL. Проверяет готовность сервера; shell-подстановка в argv не выполняется. |
| `test_author.runtime` | Обязателен внутри short-профиля: ID по `[A-Za-z0-9][A-Za-z0-9_-]*`. Сейчас защищённый адаптер есть только для `claude`; другие ID не превращаются в выбор другого CLI. |
| `test_author.model` | Обязательный явный ID/alias CLI по `[A-Za-z0-9][A-Za-z0-9._:-]*`, без пробелов. Нет модели по умолчанию. |
| `test_author.effort` | Обязателен: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max` или `ultra`. Допустимость по схеме не доказывает поддержку значения выбранным CLI. Default нет. |

Без `build` отдельной фазы сборки нет; без `database` нет отдельного сервера. Если они заданы,
нужны **все** перечисленные поля внутри соответствующего объекта. Исходники и `test_paths`
при сборке доступны только на чтение. БД получает приватные каталоги через
`HARNESS_TEST_DATABASE_DIR` и `HARNESS_TEST_DATABASE_SOCKET_DIR`, без TCP и доступа к сервисам
хоста. Проектный wrapper читает эти переменные сам. Для чистой доменной логики БД не нужна;
SQL проверяйте на production-движке. Детали — [контракт runner](../../hooks/run-test.md).

## Короткий маршрут /fast-implement {#short-route}

Короткий маршрут выбирает runtime/model/effort **из `test_author` проекта**, даже если модель
текущей сессии другая. До первого теста разработчик согласует требование и seam — публичную
границу, на которой проверяется поведение. В этом маршруте нет coordinator, architect и
независимой QA.

В корне установленного целевого проекта проверьте выбор и защиту:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo .
python3 -I -B .harness/health/test_author.py preflight --repo .
```

`resolve` показывает runtime/model/effort и `source: project`. `preflight` отвечает одной
JSON-строкой: только точный `{"status":"ok"}` разрешает автора. Exit code 0 сам по себе не
означает готовность: отказ тоже возвращается как `{"status":"disabled","reason":"…"}`.
Проба изоляции создаёт и удаляет временную песочницу; LLM, выбранный тест, сборку и БД не запускает.

Маршрут сохраняет согласованное требование и один сценарий в локальный prompt-файл, затем
использует launcher (эта команда уже запускает CLI агента):

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo .   --prompt-file '<local-prompt-file>'
```

Подставьте существующий файл с заданием, без секретов. Launcher повторно проверяет защиту,
передаёт выбранные model/effort и задание через stdin. Неподдержанный runtime launcher другим не заменяет.

## Полный маршрут /implement {#full-route}

Автор наследует `resolved_runtime`, `resolved_model`, `resolved_effort` из **утверждённого brief
developer**. Short-профиль и более поздние изменения orchestration этот выбор не меняют.
Шаблон `.claude/agents/test-author.md` использует `model: inherit`, без собственного effort;
developer вызывает `Agent(test-author)` без переопределения model/effort.

Для external developer харнесс и защита должны быть установлены **в worker worktree**.
Откройте этот точный путь в Claude Code и примите диалог доверия сами. Состояние orchestration
из основного checkout туда не копируется. В сессии developer, запущенной в этом worktree:

```bash {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py resolve --repo . \
  --brief '<approved-developer-brief.json>'
python3 -I -B .harness/health/test_author.py preflight --repo . \
  --brief '<approved-developer-brief.json>'
```

Источник выбора — `developer`. В approved brief требуется `Agent(test-author)` или `Agent`.
Для существующей политики инструментов проверьте `tool_policy.roles.developer`, сохранив другие
разрешения; старое approval расширять нельзя. Изменение требует нового propose/approval.
Правила инструментов — в [назначениях ролей](orchestration/roles.md).

Автор пишет только в test-зону **и** scope brief worker. Логи runner в linked worktree общие:
`<main>/.harness/.sandboxes/runs/isolated-test-<run_id>/log.txt`. Developer передаёт путь к этому
evidence, не разрешение писать production-код основного checkout.

In-process developer с защитой основного checkout и отдельным worker worktree получает
`checkout_mismatch` и продолжает обычный TDD. Отказ автора не создаёт новый dispatch, blocker
или запись ledger. Полный [контракт test-author](../../agents/test-author.md) описывает цикл
и требования к независимому ожиданию теста.

## Условия активации {#activation}

- Linux, bubblewrap 0.9.0+ и непривилегированные user namespaces. На Windows/macOS —
  `isolation_unavailable`. Checkout не в `/tmp`, `/run`, `/dev` или `/proc`.
- Установлены agent, исполняемые scoped guard и runner. Нужны Bash и Python, а также инструменты
  выбранного теста/сборки/БД. Непроверенные инструменты не становятся поддержанными от одной записи argv.
- `test_paths` указывает существующие литеральные каталоги. Нет symlink на пути, файлов с несколькими
  hard links и вложенных друг в друга зон. Первый сегмент не `.git`, `.harness`, `.claude`, `.agents`
  или `.codex`; остальные сегменты без `*?[]{}` и обратного слеша. Например, `tests/*.py` может пройти
  схему, но не активацию автора.
- `CLAUDE_PROJECT_DIR` соответствует checkout. Claude Code не запущен с `CLAUDE_CODE_SIMPLE=1`
  или `CLAUDE_CODE_SAFE_MODE=1`. Для **точного пути** есть принятое человеком решение доверия.
  Не исправляйте его ручной записью в auth/trust-файл; откройте проект и примите диалог.
- Выбран runtime с защищённым адаптером. Сейчас это Claude Code; минимальная версия CLI в харнессе
  не закреплена. Preflight проверяет agent/hook статически, живое срабатывание подтверждается отдельно.

Guard ограничивает `Write`/`Edit` тестовой зоной, а `Bash` — одним вызовом `run-test.sh <test-id>`
(в том числе через доверенный системный Bash). Shell-метасимволы, `--probe` и дополнительные
команды автора отклоняются. `--probe` вызывают preflight и developer; автору он для обхода guard недоступен.

## Причины отказа preflight {#refusals}

Preflight останавливается на первом отказе. Исправьте причину и повторите проверку; не отключайте guard
ради `ok`. Таблица объединяет выбор исполнителя и проверки защищённого адаптера.

| Код | Причина → действие |
| --- | --- |
| `test_author_missing` | Нет short-профиля → для короткого маршрута задайте runtime/model/effort; для полного передайте approved brief. |
| `test_author_config_invalid` | Некорректный профиль/brief или устаревший fixed model/effort в agent → сверяйте выбранный источник и шаблон, не подставляйте другой runtime. Локальный seed заменяйте только после просмотра diff. |
| `runtime_unsupported` | Нет защищённого адаптера runtime → обычный TDD; поддержка другого CLI автоматически не включается. |
| `checkout_mismatch` | Проверяется другой checkout или не совпала идентичность full-route сессии → запускайте защиту в worker с его brief; не подменяйте идентичность переменной. |
| `project_untrusted` | Не подтверждены Git root/идентичность/доверие к точному пути → откройте нужный checkout в Claude Code и примите диалог. |
| `claude_code_unsupported` | Режим CLI отключает нужные hooks → используйте поддержанное окружение, не обходите проверку. |
| `agent_missing` | Нет корректного `.claude/agents/test-author.md` → проверьте установку в нужном checkout. |
| `scoped_hook_unsupported` | В frontmatter нет ожидаемого scoped PreToolUse hook → сравните с текущим шаблоном, сохраните защиту. |
| `test_paths_missing` | Нет тестовых зон → настройте существующие каталоги тестов. |
| `test_runner_missing` | Нет runner config → задайте проверенный single-test argv. |
| `config_invalid` | Неверный формат полей runner/зон → исправьте конфигурацию по контракту. |
| `write_zone_rejected` | Неприемлемый glob, symlink, hard link или пересечение зон → выберите допустимые каталоги без расширения на production. |
| `guard_hook_unavailable` | Guard отсутствует/не исполняется/отвечает неверно → проверьте установленный файл и Python. Это не доказательство живого срабатывания hook. |
| `isolation_unavailable` | Нельзя подтвердить sandbox → проверьте Linux, bubblewrap, namespaces и расположение checkout; иначе обычный TDD. |
| `runner_unavailable` | Нет/не работает runner либо нужный интерпретатор → проверьте установленные файлы и PATH. |
| `selector_unavailable` | Защищённый адаптер не может вызвать модуль выбора → проверьте целостность `.harness/health/test_author.py`. |
| `orchestration_unavailable` | Плановая диагностика не может загрузить orchestration → проверьте установленный backend; это не выбор short-профиля за пользователя. |
| `preflight_failed` | Неизвестный/невалидный/слишком длинный ответ или сбой preflight → исследуйте установленную защиту, не принимайте произвольный текст за `ok`. |

`agent_tool_unavailable` — решение developer при отсутствии инструмента `Agent` в brief,
а не JSON-причина общего preflight. На этапе launcher возможны `runtime_unavailable`,
`prompt_missing`, `prompt_unavailable`, `author_unavailable`: проверьте выбранный CLI, файл задания
и завершение процесса. Они не дают права на незащищённый запуск.

## Живая проверка {#live-check}

`harness health .` показывает `hooks.test_author`, выбранный runtime/model/effort и источник.
Он диагностирует план developer с пометкой `planned`, а при отсутствии плана — short-профиль.
Это не замена approved brief. Если opt-in нет, проверка пропускается; недоступный необязательный автор
даёт предупреждение и не ломает обычный маршрут. Health не запускает LLM, тест, сборку или БД.

В **исходниках самого харнесса** доступна отдельная живая проверка, требующая входа в Claude Code
и расходующая квоту; перед её запуском согласуйте это действие:

```bash {.ah-code-wrap}
make test-author-probe
```

Она берёт runtime/model/effort из плана developer, проверяет guard, поведенческий Red, вызов
автора external developer в worker и Green неизменного теста. Обычные verify/CI её не запускают.
Файлы `test-author-probe-*.json` сохраняются в общей `.harness/.sandboxes/reports/`: этап, checkout,
exit code, время и сообщённые runtime usage/стоимость. Неизвестные метрики остаются `null`;
лимит не считается расходом, доля подписочной квоты не вычисляется из USD.

## Ограничения и обычный TDD {#limits}

В этой поставке проверены Python-тесты через unittest/pytest. Rust-тесты
`native/harness-runtime/crates/*/tests` этим решением не поддержаны: произвольный argv в схеме
не доказывает поддержку стека. Обязательные Rust QA-команды сохраняются.

Ошибка импорта/компиляции, fixture, сборки (`build_failed`, `build_timeout`) или недоступная БД
(`database_unavailable`) — не поведенческий Red. Ответ автора `needs_skeleton` требует от developer
только типов/сигнатур, `contract_gap` — уточнения требования; нельзя ослаблять ожидание ради Green.
После трёх подряд неудачных вызовов по одному тесту developer идёт по обычному blocker-пути.
Отказ активации, напротив, оставляет обычный TDD без нового blocker/ledger state.

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
    exact-path user trust and approved Agent(test-author) permission; never spoof trust or widen
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
