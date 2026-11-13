# Test-author: тест-автор

## 1. Назначение

`test-author` пишет для developer следующий поведенческий тест цикла Red → Green → Refactor. Это
необязательный in-session субагент developer. Он пишет ровно один тест и запускает его через
`.claude/hooks/run-test.sh`; production-код, скелет и orchestration остаются у developer.

Исполнитель автора выбирается из конфигурации до проверки защищённого адаптера. Общая команда
`python3 -I -B .harness/health/test_author.py preflight --repo .` возвращает одну строку
`{"status":"ok"}`, если `test_paths`, `test_runner`, process isolation и scoped guard подтверждены.
При любом отказе она возвращает `{"status":"disabled","reason":"<санитизированная причина>"}`, и
developer продолжает обычный маршрут.

## 2. Конфигурация

В `.harness/project.json` задаются необязательные настройки тестовой зоны и runner:

```json {.ah-code-wrap}
"test_paths": ["tests/**"],
"test_runner": {"command": ["python3", "-m", "pytest", "{test_id}"]}
```

`test_paths`: непустой список уникальных относительных glob-шаблонов без сегментов `..`.
Схема и `harness health` принимают любой такой glob, но тест-автор включается только с зонами
записи вида `<каталог>/**`. Требования к такой зоне: остальные сегменты литеральные (без `*?[]{}` и
`\`), первый сегмент не `.git`, `.harness`, `.claude`, `.agents` или `.codex`, каталог существует,
на пути к нему нет symlink, внутри нет файлов с несколькими жёсткими ссылками, а зоны не вложены
друг в друга. Иначе preflight отвечает `write_zone_rejected`, например для `tests/*.py`.
`test_runner.command`: argv без shell, с ровно одним аргументом `{test_id}`, который стоит не
первым. Схема, validator и `harness health` используют один контракт. Если полей нет, это не
ошибка, но тест-автор выключен.

Исполнитель полного `/implement` наследует `resolved_runtime`, `resolved_model` и
`resolved_effort` из утверждённого brief developer. Передавайте `--brief <путь>` общему
preflight; текущая orchestration-конфигурация и профиль проекта уже утверждённый выбор не меняют.
Для поддержанного нативного вызова `Agent(test-author)` шаблон использует `model: inherit` и
наследует effort, поэтому developer вызывает автора без переопределения model/effort. Старый
локальный шаблон с фиксированным model или effort получает `test_author_config_invalid`. После
просмотра замените `.claude/agents/test-author.md` командой
`harness update . --force-seed-file .claude/agents/test-author.md`, чтобы вернуть наследование.

Короткий `/fast-implement` читает отдельный явный профиль в `.harness/project.json`:

```json {.ah-code-wrap}
"test_author": {"runtime": "claude", "model": "sonnet", "effort": "high"}
```

Это пример выбора пользователя, а не значения по умолчанию. Внутри профиля обязательны все три
поля. Без профиля короткий маршрут получает `test_author_missing`. Если в brief нет корректных
полей, полный маршрут получает `test_author_config_invalid` и к профилю проекта не откатывается.
`resolve --repo . [--brief <путь>]` показывает выбранные поля и их источник.

Короткий маршрут сохраняет требование и один сценарий в локальный prompt-файл и вызывает:

```sh {.ah-code-wrap}
python3 -I -B .harness/health/test_author.py run --repo . --prompt-file <prompt-файл>
```

Launcher повторно проверяет защищённый адаптер, передаёт выбранному CLI точные model/effort
и отдаёт текст задания через stdin. Launcher нужен и тогда, когда модель текущей сессии
отличается от профиля проекта. Если для настроенного runtime нет защищённого адаптера, launcher
отвечает `runtime_unsupported` и другой CLI вместо него не запускает. Сейчас защищённый адаптер
есть только для Claude Code; упоминания `.claude` ниже относятся к его guard и runner, а не к
выбору исполнителя. Чтобы переключить автора на Claude Code, добавьте `claude` с `model` и
`effort` в `assignment_plans.developer.runtimes` файла `.harness/orchestration.json`. Если runtime
в плане несколько, выберите `claude` в `assignment_plans.developer.default_runtime`. Без плана
developer runtime задаёт `test_author.runtime` файла `.harness/project.json`.

## 3. Защита

Frontmatter установленного `.claude/agents/test-author.md` подключает
`.claude/hooks/test-author-guard.py` только к этому субагенту для `Write`, `Edit` и `Bash`.

- `Write` и `Edit` проходят только после нормализации пути и только внутри `test_paths`. Symlink,
  ведущий за пределы тестовой зоны, guard отклоняет.
- `Bash` разрешает только один вызов `.claude/hooks/run-test.sh <test-id>` (допускается
  эквивалентный вызов через доверенный системный `bash`). Shell-метасимволы, `--probe`,
  дополнительные аргументы и другие команды guard отклоняет.
- Отказ мягкий: hook печатает JSON с причиной, не меняет dispatch/ledger и завершается кодом 0.
  Другие субагенты эту защиту не получают, и их маршрут не меняется.

Preflight проверяет условия и на первом нарушении отвечает `disabled` с одной
фиксированной причиной:

| Проверка | Причина отказа |
| --- | --- |
| Необязательный `--worktree <путь>` называет тот же checkout, где лежит preflight | `checkout_mismatch` |
| Выбраны runtime/model/effort из brief developer или short-профиля проекта | `test_author_missing`, `test_author_config_invalid` |
| Для выбранного runtime есть защищённый адаптер | `runtime_unsupported` |
| Checkout, где лежит preflight, совпадает с корнем своего рабочего дерева Git (`git rev-parse --show-toplevel`) | `project_untrusted` |
| `CLAUDE_PROJECT_DIR`, если передан, совпадает с этим корнем Git | `project_dir_mismatch` |
| Claude Code не запущен с `CLAUDE_CODE_SIMPLE=1` или `CLAUDE_CODE_SAFE_MODE=1` | `claude_code_unsupported` |
| Пользователь принял диалог доверия для этого checkout или для основного checkout его репозитория | `project_untrusted` |
| Установлен agent `test-author.md` | `agent_missing` |
| В agent включён scoped `PreToolUse` hook | `scoped_hook_unsupported` |
| Заданы `test_paths` и `test_runner`, зоны записи допустимы | `test_paths_missing`, `test_runner_missing`, `config_invalid`, `write_zone_rejected` |
| Файл `test-author-guard.py` исполняемый и отвечает JSON | `guard_hook_unavailable` |
| `run-test.sh --probe` подтверждает изоляцию | `isolation_unavailable`, `runner_unavailable` |

Корень проекта preflight берёт из Git, поэтому ни `export CLAUDE_PROJECT_DIR`, ни запись корня в
настройках не нужны. `CLAUDE_PROJECT_DIR`, который передал Claude Code, preflight только сверяет с
корнем Git.

Доверие preflight проверяет по записи в `~/.claude.json` (или `$CLAUDE_CONFIG_DIR/.claude.json`):
`hasTrustDialogAccepted: true` должно стоять для точного пути checkout или для основного checkout
репозитория, если checkout является его linked worktree из `git worktree list`. Нативный режим
`claude --print` диалог доверия пропускает, поэтому preflight проверяет решение сам. Новому
worktree доверенного репозитория отдельный диалог не нужен. Доверие только к родительскому
каталогу не считается: preflight отвечает `project_untrusted`, это безопасный отказ. Откройте
основной checkout в Claude Code и примите диалог (ADR 0033).

Проверки agent, hook и guard статические: preflight не запускает Claude Code и не доказывает,
что hook сработает в живой сессии. Поэтому `guard_hook_unavailable` означает только, что guard не
исполняемый или отвечает неправильно. Реальное срабатывание scoped hook подтверждает проверка
самого харнесса на настоящем Claude Code; в установленный проект она не входит. Test-author не
запускается без защиты, если agent или hook отсутствует, Claude Code работает в режиме без hooks,
проект не помечен доверенным или изоляция недоступна.

## 4. Контракт вызова

Пока preflight возвращает `{"status":"ok"}`, developer вызывает test-author перед каждым шагом
реализации. Developer передаёт требование и seam из brief architect, публичные сигнатуры,
существующие fixtures и один сценарий. Предложенный алгоритм или фрагмент реализации основанием
ожидания не становится. Seam, который не согласован в brief, developer не выдумывает, а
эскалирует обычным путём blocker. Test-author читает минимум относящихся к делу файлов, пишет один
тест только в `test_paths`, запускает выбранный тест через runner и коротко по-английски
возвращает:

1. `status`: `red`, `needs_skeleton` или `contract_gap`;
2. требование и сценарий;
3. входные данные и независимый источник ожидания;
4. идентификатор теста;
5. для `red` доказательство Red: санитизированный JSON runner и в нескольких строках проваленное
   утверждение, ожидание и фактический результат. В JSON только фиксированные ключи, поэтому эти
   три факта автор берёт из `log.txt` запуска (каталог из `run_id`).

Если runner отказал или тест оказался Green, субагент сообщает факт и останавливается. Он не
создаёт manifest, dispatch, brief/report, approval или ledger record.

## 5. Цикл Red → Green → Refactor

Цикл описан для developer прозой: это не новая роль, состояние или запись ledger.

1. Developer сверяет ожидание с требованием и источником до реализации. Принятое ожидание он не
   ослабляет ради Green. Исправить ожидание можно только при обоснованном изменении контракта,
   новым вызовом автора и новой проверкой.
2. `red` означает переход к реализации. При `needs_skeleton` developer пишет только типы и
   сигнатуры без логики и вызывает автора повторно. При `contract_gap` developer уточняет
   требование по brief или эскалирует его; угадывать контракт нельзя.
3. Ошибка компиляции или импорта, ошибка fixture и ошибка окружения не считаются поведенческим
   Red, какой бы `status` ни указал автор. Сразу зелёный тест developer явно возвращает автору, и
   успешным циклом он не считается.
4. После подтверждённого Red developer пишет минимальную реализацию до Green, рефакторит на
   Green и только затем запрашивает следующий тест.
5. После трёх подряд неудачных вызовов автора по одному тесту developer идёт обычным путём
   blocker. Отказ guard считается одним неудачным вызовом; отклонённый вызов developer не
   переформулирует. Локальный повтор автора и отдельный отказ guard не создают dispatch и
   состояние ledger и не обходят правила восстановления `/implement`.
   Независимая QA, её роль и ledger не меняются.

Сборку и отдельную тестовую БД задают необязательные `test_runner.build` и
`test_runner.database` (см. раздел 6). Тест-автор не меняет артефакты: его
`Write`/`Edit` по-прежнему ограничены `test_paths`, а недоступная защита отключает автора.

Runner запускает БД только для совпавших `test_runner.database.test_ids`; чистой доменной логике
сервер не нужен. SQL, rollback и ограничения проверяйте на production-движке.
Отказы `build_failed`, `build_timeout` и `database_unavailable` поведенческим Red не считаются.

`--probe` проверяет настройки и монтирования обеих фаз, но не запускает сборку, сервер БД
или выбранный тест. Если настройки или монтирования не прошли, preflight отвечает `disabled` с
санитизированной причиной, и developer продолжает обычный маршрут без тест-автора. Готовность
конкретной БД runner проверяет только для выбранного SQL-теста; её отказ Red не считается.

## 6. Короткий маршрут `/fast-implement`

`/fast-implement` использует того же тест-автора и тот же цикл из раздела 5, но без шагов
coordinator, architect и независимой QA: developer-сессия сама ведёт цикл от тикета до push.
Отличается только происхождение seam: он не берётся из brief architect, а согласуется с
разработчиком до первого теста. Скилл называет требование, seam, публичные сигнатуры и существующие
fixtures, останавливается до ответа разработчика и не пишет тест на несогласованном seam.
Передача автору, проверка ожидания, скелет, запрет ослаблять принятое ожидание и лимит из трёх
подряд неудачных вызовов такие же, как в полном маршруте. Локальные повторы не создают dispatch и
состояние ledger.

**Включение (opt-in).** Тест-автор выключен, пока в `.harness/project.json` нет `test_paths` и
`test_runner`. Новый проект получает их флагами `harness init --test-path` и
`--test-runner-command`. Старый проект без этих полей не меняется, и `/fast-implement` идёт обычным
`/tdd`. Чтобы включить автора в старом проекте, добавьте оба поля вручную и запустите
`harness health`.

**Защищённое окружение.** Тесты автора идут только через `.claude/hooks/run-test.sh`. Необязательные
поля `test_runner.build` (`command` и `artifact_paths`) и `test_runner.database` (`engine`,
`test_ids`, `command`, `ready_command`) готовят свежие артефакты и отдельную тестовую БД внутри
песочницы. Их задают флаги `--test-build-command`, `--test-artifact-path`, `--test-database-engine`,
`--test-database-test-id`, `--test-database-command` и `--test-database-ready-command` вместе с
`--test-runner-command`. Сборка пишет только в заранее созданные пустые каталоги артефактов, тест
читает их без права записи, а БД запускается только для совпавших `test_ids`. Чистой доменной
логике БД не нужна.

**Поддерживаемые версии и окружения.**

- Защищённый адаптер сейчас есть только для Claude Code. Выбор Codex или другого runtime
  сохраняется в диагностике и даёт `runtime_unsupported`. Харнесс не закрепляет минимальную версию
  Claude Code: preflight статически проверяет agent, scoped hook и guard, а срабатывание hook в
  живой сессии подтверждает проверка самого харнесса (`make test-author-probe`, нужны `claude` и
  вход).
- Только Linux с bubblewrap 0.9.0+ и непривилегированными user-namespaces. На Windows и macOS
  runner отвечает `isolation_unavailable`, а preflight выключает автора.
- Checkout не должен лежать в `/tmp`, `/run`, `/dev` или `/proc`. Для сборки нужен компилятор или
  инструмент, заданный в `test_runner.build.command`. Для SQL-тестов нужны инструменты выбранной СУБД
  (в проверках харнесса это `postgres`, `initdb`, `psql`, `pg_isready` в `PATH`). Без них отказывает
  только соответствующий запуск, а не весь проект.
- Для hook нужен `python3` (или `python`) в `PATH`, а проект должен быть принят в диалоге доверия
  Claude Code.

**Откат на обычный маршрут.** Если preflight ответил не `{"status":"ok"}`, hook отсутствует или
упал либо изоляция недоступна, `/fast-implement` продолжает обычным `/tdd` в той же сессии.
Одной строкой он называет разработчику санитизированную причину и незащищённого автора не
запускает. Этот исход не добавляет шагов coordinator, architect или QA и не меняет ledger.

## 7. Полный маршрут `/implement`

Автор работает рядом с external developer в worker worktree, с runtime/model/effort из его brief.
Поддержанный адаптер запускает developer прямо в checkout из brief, поэтому runtime, scoped hook
и runner относятся к тому же коду. Установите харнесс в worker checkout и включите там
`test_paths` и `test_runner`; состояние оркестрации из основного checkout не копируется.
Для worktree доверенного репозитория отдельный диалог доверия не нужен. Если основной checkout
не доверен, откройте его в Claude Code и примите диалог. Ни installer, ни developer, ни
headless-запуск не принимают решение о доверии за пользователя.

External developer запускает общий preflight с `--repo <worker_worktree> --brief <путь brief>`.
Для защищённого Claude-адаптера это `.claude/hooks/test-author-preflight.sh --worktree <worker_worktree> --brief <путь brief>`.
Следующий шаг разрешает только точный ответ `{"status":"ok"}`. В утверждённом brief также должно
быть разрешение `Agent(test-author)` или `Agent`; без него причина `agent_tool_unavailable`.
Новый шаблон orchestration задаёт именованное разрешение только роли developer. Существующие
проекты с `tool_policy` включают его явно в `tool_policy.roles.developer` и сохраняют остальные
инструменты роли. Явное ограничение проекта автоматически не расширяется, а список инструментов
фиксируется digest до approval по ADR 0024.

Автор пишет тест в `test_paths` worker checkout и запускает его runner. Developer передаёт один
конкретный тестовый путь в пределах scope brief и корень логов runner из prompt адаптера:
`<main>/.harness/.sandboxes/runs/`. В linked worktree эти логи общие; `run_id` указывает на
`isolated-test-<run_id>/log.txt` внутри этого корня. Адаптер открывает доступ к каталогу evidence,
а scoped guard сохраняет прежние ограничения записи и Bash. Код, тесты и Git-статус основного
checkout не меняются; общие runtime-логи остаются в его игнорируемой песочнице.

Preflight основного checkout с `--worktree` отдельного worker отвечает `checkout_mismatch`: его
guard и runner обслуживают только основной checkout. Поэтому in-process developer вызывает автора
через launcher своего worktree:
`python3 -I -B <worker_worktree>/.harness/health/test_author.py run --repo <worker_worktree> --brief <путь brief> --prompt-file <файл>`.
Launcher проверяет preflight worker и запускает автора с guard и runner этого worktree; правило
разрешения в brief то же. Если preflight отказал или инструмент вызова автора недоступен, worker
продолжает обычный TDD с указанной причиной, без blocker и новых записей ledger. Runtime берётся
из developer. Если для него нет защищённого адаптера, остаётся обычный TDD без подмены
исполнителя.

В этой поставке проверены Python-тесты через unittest и pytest. Rust-тесты
`native/harness-runtime/crates/*/tests` это решение не поддерживает: для них нет зон записи и
отдельного runner. Настраиваемый argv runner сам по себе не ограничен Python,
но это не доказывает поддержку другого стека. Обычные Rust QA-команды проекта остаются
обязательными для изменений Rust.

## 8. Диагностика и живая проверка

`harness health` выводит отдельную проверку `hooks.test_author`: результат preflight для
целевого checkout или санитизированную причину отказа, выбранные runtime/model/effort и
источник. Health берёт план developer из orchestration (пометка `planned`), а если плана нет,
short-профиль проекта. Плановая готовность не заменяет выбор из утверждённого brief. Без opt-in
проверка пропускается с причиной. Если необязательный автор недоступен, health предупреждает и
оставляет обычный маршрут рабочим. Результат preflight относится к checkout, для которого запущен
health; worker worktree проверяет свой preflight при вызове автора.

Каждое условие автора health показывает отдельной строкой. При отказе строка печатает шаг
исправления: команду или фрагмент конфигурации.

| Строка | Что проверяет | Шаг при отказе |
| --- | --- | --- |
| `hooks.test_author_config` | блок `test_author` в `.harness/project.json` | фрагмент блока из плана developer и `harness health --fix` |
| `hooks.test_author_root` | корень проекта по Git и совпадение с ним `CLAUDE_PROJECT_DIR`, если переменная задана | оба пути при `project_dir_mismatch` и `unset CLAUDE_PROJECT_DIR` |
| `hooks.test_author_trust` | доверие Claude Code к этому checkout или к основному checkout, который перечисляет его в `git worktree list` | путь, который нужно доверить, и `cd <основной checkout> && claude` |
| `hooks.test_author_guard` | agent, исполняемый guard и его проверка конфигурации | `harness update` или исправление `test_paths` и `test_runner` |
| `hooks.test_author_runner` | исполняемый `.claude/hooks/run-test.sh` | `harness update` |
| `hooks.test_author_probe` | probe изоляции runner | шаг по причине: bubblewrap, user namespaces, расположение checkout |

Guard и probe запускают скрипты проекта, поэтому до доверия их строки пропускаются.
`harness health --fix` добавляет отсутствующий блок `test_author` из плана developer. Порядок
включения описан в [настройке test-author](../getting-started/settings/test-author.md#enable).

Health не запускает Claude, выбранный тест, сборку или БД и не меняет доверие. Probe изоляции
создаёт и удаляет временную песочницу в общем `runs/`. Статический `preflight: ok` не доказывает,
что scoped hook сработает в живой сессии. Это проверяет `make test-author-probe`: нужны вход
в Claude Code и квота. Проба берёт runtime/model/effort из плана developer исходного проекта, без
отдельной дешёвой модели. Если адаптер выбранного runtime недоступен, проба завершается явным
отказом. Для поддержанного адаптера команда подтверждает guard, поведенческий Red и вызов автора
внешним developer в worker worktree; затем fixture developer проверяет Green неизменного теста.

Каждый вызов CLI оставляет санитизированный `test-author-probe-*.json` в общем
`.harness/.sandboxes/reports/`: checkout, этап, код выхода, время, фактические usage и стоимость,
которые вернул runtime, и отдельно лимит. Отсутствующая метрика остаётся `null`; лимит расходом не
считается. Эти файлы сохраняются после удаления clean-room проектов; полные транскрипты и
credentials в них не попадают. Точную долю подписочной квоты runtime может не сообщать, и из USD
она не вычисляется.
