## 1. Название и локализация
- **Английское название:** Hook installation and update (settings merge, second runtime adapter, hooks.policy check)
- **Русский перевод / Суть:**

```text
Установка и обновление hooks: слияние управляемых записей файла настроек с записями пользователя, адаптер hooks второго coding runtime и проверка hooks.policy в harness health.
```
## 2. Полное описание
`harness init`, `harness adopt` и `harness update` для проектов с возможностью `engineering-suite` ставят скрипты `.claude/hooks/` и подключают их в файлах настроек runtime. Файл настроек принадлежит и harness, и пользователю, поэтому команды не перезаписывают его целиком, а сливают в него управляемые записи шаблона и сохраняют всё остальное.

### Слияние по пути команды
- **Единица слияния.** Управляемая запись — это handler, команда которого ссылается на скрипт `.claude/hooks/<имя>` из шаблона. Единицей слияния служит пара «событие и скрипт» шаблона; путь команды определяет, что считать управляемым, а не порядок и не номер записи в файле.
- **Что делает слияние.** Недостающая управляемая запись добавляется. Устаревшая запись, которую harness записывал раньше, заменяется шаблонной. Запись пользователя, у которой команда не ссылается на скрипт из шаблона, не меняется и не удаляется.
- **Отпечатки.** Что harness когда-либо записал, хранится как отпечатки (`managed_entries`) в записи интеграции `.harness/integrations.json`. По ним слияние отличает устаревшую управляемую запись от записи, которую пользователь изменил. Отпечатки не копируют текст команд.
- **Нет файла или нечитаемый файл.** Если файла нет, `harness` записывает байты шаблона. Файл, который не читается как JSON-объект или имеет неподходящую форму `hooks`, остаётся без изменений, а отчёт сообщает `cannot merge` с причиной.
- **Флаги заменяют слияние.** `--force-seed-file .claude/settings.local.json` и `--force-seed-files` сохраняют прежний смысл: файл целиком заменяется шаблоном, записи пользователя в нём теряются. Слияние их не заменяет.

### Конфликт без перезаписи
Если пользователь изменил управляемую запись в том же событии (другая команда или другой matcher при том же скрипте, лишние поля handler), слияние не знает, чьё изменение верно, и не перезаписывает её. Запись, перенесённую на другое событие, слияние считает записью пользователя и не меняет, а шаблонную запись на своём событии добавляет заново, без конфликта. Изменённая запись в том же событии остаётся как есть, `harness` печатает предупреждение `[WARNING]`, перечисляет каждую запись строкой `hooks conflict: <файл>: <событие> [<matcher>] <скрипт>` и подсказывает команду `--force-seed-file <файл>`, которая после просмотра заменит файл шаблоном. Конфликтная запись не попадает в записанные отпечатки, поэтому повторный `update` сообщает о ней снова, пока владелец не решит её судьбу.

### Идемпотентный update
Повторный `harness update` без изменений в проекте не меняет ни байта в файле настроек и в `.harness/integrations.json`, не дублирует управляемые записи и печатает отчёт по каждому файлу runtime:

```text
hooks merge: .claude/settings.local.json: added=0 replaced=0 current=<N> user=<M> conflicts=0
hooks check: .claude/settings.local.json: critical wired 9/9
```

- `hooks merge` — итог слияния. Счётчики считают единицы «событие и скрипт»: `added` добавлены, `replaced` заменены шаблонными, `current` уже совпадали с шаблоном, `user` — записи пользователя, `conflicts` — изменённые управляемые записи. При установке из шаблона строка имеет вид `installed from template`.
- `hooks conflict` — по одной строке на конфликт, после предупреждения.
- `hooks check` — сколько критических hooks подключено из общего числа и какие пропущены (`missing: <hook>`), например когда конфликтная запись сменила matcher критического hook в том же событии, и hook перестал покрывать свой инструмент.

### Файл effective policy hooks
После файлов hooks установка записывает `.harness/hook-policy.json` (ADR 0024, раздел 3). Это единственный писатель файла: `harness health` его не пишет, а решения hooks, coordinator и Rust runtime его не читают.

- **Содержимое.** `schema` (1); `policy` — нормализованные профиль и эскалации ключа `hook_policy` из `.harness/project.json` (проект без ключа получает `standard` без эскалаций); `hook_policy_sha256` — digest раздела `policy`; `critical_guards` — hook_id критических строк матрицы; `hook_versions` — SHA-256 байтов каждого шаблона `.claude/hooks/*.sh|*.py`. Файл — JSON с отступом 2 и отсортированными ключами, UTF-8 без BOM, строки заканчиваются LF.
- **Связь с brief.** `hook_policy_sha256` файла считается той же функцией и из того же ключа `hook_policy`, что и `hook_policy_sha256`, который закрепляет brief при `dispatch create`. Для одной конфигурации значения совпадают.
- **Отчёт и идемпотентность.** Команда печатает строку `hooks policy: .harness/hook-policy.json: written|unchanged hook_policy_sha256=<hex>`. Повторный `harness update` без изменения конфигурации не перезаписывает файл.
- **Ошибка.** Некорректный `hook_policy` или нечитаемый `.harness/project.json` завершают команду с кодом 2, сообщением и подсказкой исправления; существующий файл остаётся прежним.
- **Lock и удаление.** Файл не входит в `harness.lock` и не принимается `--force-seed-file`. `harness uninstall` удаляет его вместе с `.harness/` без резервной копии, потому что следующая установка создаёт его заново.

### Адаптер второго coding runtime
Второй runtime получает файл `.codex/hooks.json` из шаблона `harness/project/codex-hooks.json.tmpl`. Он вызывает те же скрипты `.claude/hooks/*.sh`, поэтому решения и коды ответа hooks совпадают; команда запуска сначала переходит в корень репозитория (`cd "$(git rev-parse --show-toplevel)"`). Файл сливается по тем же правилам, что и `.claude/settings.local.json`: по пути команды, с конфликтами без перезаписи и с тем же отчётом. Запись интеграции называется `engineering-suite-codex-hooks`; `harness uninstall` убирает файл и запись.

- **Подключённый набор.** Адаптер подключает критические guards на `PreToolUse` для `Bash` (`protect-hook-policy`, `block-public-attribution`, `block-direct-master`, `block-pr-merge`, `check-branch-name`, `require-qa-gate`, `block-dangerous-git`) и поведенческий `require-bounded-check`, как у блокирующего набора профиля `standard` первого runtime. Правки файлов этот runtime присылает как `tool_name: "apply_patch"` с телом патча в `tool_input.command` и без `file_path`; группа `PreToolUse` с matcher `apply_patch|Write|Edit` (runtime сопоставляет и каноническое имя, и алиасы `Write`/`Edit`) подключает `protect-hook-policy` и `block-scratch-outside-docs-tasks`. Оба берут пути из заголовков патча через адаптер `apply_patch_payload.py` и решают так же, как для `Write`/`Edit` первого runtime; неразбираемый патч блокируется с `reason_code` `apply-patch-unparseable`. Advisory `targeted-check-reminder` подключён на `Stop` и `SubagentStop`: этот runtime доставляет оба события, payload несёт `session_id`, `stop_hook_active` и у `SubagentStop` — `agent_id`, а при коде `0` stdout принимает только JSON или пустую строку.
- **Что не подключено.** Остальные hooks на `Write` и `Edit`, `EnterWorktree` и `Skill` не подключаются: события `EnterWorktree` и `Skill` в этом runtime нет, а поведенческие и учётные hooks к `apply_patch` не подключаются. Поэтому не подключены строки `Write`/`Edit` hooks ChangeImpact: `impact-first-touch`, `sensitive-path-recheck` и журнал касаний `targeted-check-reminder`. Без журнала напоминание второго runtime молчит; `harness health` перечисляет эти три строки вместе с проверкой вне hook. Учётный `mark-qa-gate-passed` на `PostToolUse` для `Bash` тоже не подключается: этот runtime вызывает `PostToolUse` и после команды `Bash` с ненулевым кодом выхода, а в его payload нет поля с кодом выхода. Подключённый hook записал бы маркер `.claude/.qa-gate/passed` для упавшего QA-прогона, и `require-qa-gate` разрешил бы создание PR. Маркер у рабочей копии один на оба runtime, поэтому во втором runtime его записывает навык `qa-gate` через `record-qa-gate-pass.sh` после успешного прогона всех команд. Этот runtime не задаёт `CLAUDE_PROJECT_DIR`, поэтому навыки `qa-gate` и `to-pull-requests` берут скрипт из основного worktree — первой записи `git worktree list --porcelain`, где установлен `.claude/hooks/`. `harness health` показывает такие hooks как отсутствующие (см. `hooks.policy`).
- **Доверие проекту.** Проектные hooks этого runtime запускаются только после того, как пользователь доверил слою `.codex/` проекта и подтвердил каждый hook по хэшу. До этого hooks не работают, и защиту дают проверки Rust runtime и coordinator, а не hooks. После `harness init` и после каждого `harness update`, который меняет `.codex/hooks.json`, hook нужно подтвердить заново, потому что хэш изменился.

### Проверка hooks.policy в harness health
`harness health` содержит проверку `hooks.policy` для проектов с `engineering-suite` или `backend-orchestration`. Она показывает:

- **Профиль и источник.** `профиль standard (.harness/project.json)` или `профиль standard (по умолчанию)`, когда ключа `hook_policy` нет, плюс перечень эскалаций. Некорректный `hook_policy` — `fail`, потому что hooks применяют `strict`.
- **Наличие и исполняемость.** Каждый скрипт каталога hooks должен существовать и иметь бит исполнения; для критического hook нарушение — `fail`, для остальных — `warn`. Скрипт нескольких событий (`targeted-check-reminder.sh` на `PreToolUse`, `Stop` и `SubagentStop`) называется один раз.
- **Проводка по runtime.** `claude: критических hooks подключено 9/9`, `codex: критических hooks подключено 8/8`. Не подключённый критический hook — `fail`; отсутствующий `.codex/hooks.json` — `warn`.
- **События, которых нет у runtime.** Строка `нет события или payload: <hook>` для каждого hook, чьё событие или payload runtime не доставляет. Если у критического hook нет проверки вне hook, это `warn` с пометкой `нет проверки вне hook`, а не молчаливый пропуск; hook, у которого такая проверка есть, помечается её названием (`вне hook: …`). У второго runtime так перечислены строки `Write`/`Edit` hooks ChangeImpact: `impact-first-touch (вне hook: ChangeImpact-gate по ADR 0023)`, `sensitive-path-recheck (вне hook: граница strict (dispatch propose, qa run, publish))` и `targeted-check-reminder (вне hook: сверка checks_run)`. Hooks некритические, у каждого есть проверка вне hook, поэтому `fail` и advisory-предупреждения они не дают. Событие без инструмента (`Stop`, `SubagentStop`) каталог обозначает инструментом `*`; его покрывает группа без matcher.
- **Дрейф от шаблона.** Конфликты управляемых записей, записи для добавления или замены и скрипты, байты которых отличаются от шаблона. Если шаблонов проекта нет (автономный запуск пакета health), проверка сообщает `дрейф не проверен`.
- **Файл effective policy.** Нет `.harness/hook-policy.json` — `warn` `.harness/hook-policy.json отсутствует: effective policy hooks не записана`. Содержимое, которое не разбирается как JSON или отличается от effective policy текущей конфигурации, — `warn` `дрейф: .harness/hook-policy.json не совпадает с effective policy текущей конфигурации`. Сравнивается разобранный JSON, поэтому окончания строк CRLF дрейфом не считаются. Без шаблонов проекта сверяется только наличие файла; при некорректном `hook_policy` сверка пропускается, потому что проверка уже даёт `fail`. Оба предупреждения исправляет `harness update`.

Проект, установленный сейчас, получает `ok`: оба runtime подключают каждый критический hook, который могут доставить, а у hooks без события второго runtime есть проверка вне hook. `protect-hook-policy` второго runtime перечислен как `protect-hook-policy (MultiEdit, NotebookEdit; вне hook: hook_policy_sha256 в brief)`: этих инструментов у runtime нет. `harness update` исправляет недостающие файлы и записи; изменённый файл после просмотра заменяет `--force-seed-file <путь>`.

## 3. Контракты
- **Вход (Input/Brief):** `harness init|adopt|update <repo> --capability engineering-suite`, шаблоны `harness/project/settings.local.json.tmpl` и `harness/project/codex-hooks.json.tmpl`, записи интеграций `.harness/integrations.json`.
- **Выход (Output/Report):**
  - **Файлы:** `.claude/settings.local.json` и `.codex/hooks.json` с управляемыми записями шаблона и неизменёнными записями пользователя; записи интеграций `engineering-suite-hooks` и `engineering-suite-codex-hooks` с отпечатками `managed_entries`; сгенерированный `.harness/hook-policy.json`.
  - **Отчёт:** строки `hooks merge`, `hooks conflict` и `hooks check` для каждого файла и строка `hooks policy`; код возврата `0`, конфликт не делает команду неуспешной; некорректный `hook_policy` — код `2`.
  - **Проверка:** запись `hooks.policy` в `harness health --json` со статусом `ok`, `warn` или `fail`.
## Источник

[harness.py](../../harness/bin/harness.py), [hook_settings.py](../../harness/health/hook_settings.py), [hooks.py](../../harness/health/checks/hooks.py), [hook_policy.py](../../harness/orchestration/hook_policy.py), [codex-hooks.json.tmpl](../../harness/project/codex-hooks.json.tmpl)
