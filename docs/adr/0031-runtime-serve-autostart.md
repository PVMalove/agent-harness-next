# Автозапуск harness-runtime serve на время /implement

**Статус: ACCEPTED (2026-11-12).** Тикет #1088. Документ дополняет ADR 0021 (разделы 2 и 8) и
ADR 0024 (матрица 2a): он фиксирует, кто запускает и останавливает `harness-runtime serve` для
маршрута `/implement` и как сервер узнаёт, что больше не нужен.

## Контекст системы

После перехода на runtime store (ADR 0020) каждая команда coordinator обращается к
`harness-runtime serve`. Без сервера команда отказывает с `[runtime_unavailable]`, и разработчик
запускает serve вручную вне песочницы агента: песочница закрывает сокет Docker, поэтому serve,
запущенный из Bash агента, не обслужит QA docker executor. Python не запускает процессы
(ADR 0021), поэтому coordinator сервер не стартует.

Нужен механизм, который запускает serve перед первой командой coordinator, переиспользует уже
работающий сервер, останавливает свой сервер после `/implement` и никогда не останавливает ручной,
чужой или занятый сервер.

## Действующий контракт

### 1. Выбор механизма

| Вариант | Суть | Решение |
|---|---|---|
| A | Обёртка запуска `/implement` | отвергнут: ручной шаг; не работает внутри открытой сессии |
| B | Hook вне песочницы и файл владельца с PID и счётчиком сессий | отвергнут: нужен межплатформенный flock, проверка простоя вне store гоночная |
| C | Остановка только по таймауту простоя | отвергнут как основной: останавливает не по завершении `/implement`; остаётся страховкой (TTL) |
| D | Hook вне песочницы и учёт владельцев внутри serve | **выбран** |

В варианте D процесс запускает hook coding-приложения, а не Bash агента, поэтому существующие
блокирующие hooks не получают исключений. Сервер, запущенный hook-ом, помечен как «свой» и сам
решает об остановке; ручной serve не помечен и сам не останавливается никогда. Защита ручного
сервера структурная, а не основана на проверке PID.

### 2. Владельцы внутри serve

- `harness-runtime serve [--repo R] [--owner-session K] [--owner-pid P] [--owner-ttl-seconds N]`
  (только Unix). С `--owner-session` сервер свой и стартует с владельцем `K`; без флага — ручной.
- Ключ владельца: `<session_id>` основного агента или `<session_id>/<agent_id>` субагента;
  1–256 символов `[A-Za-z0-9._:/-]`, иначе `malformed_request`.
- IPC-операции `runtime.attach {key, owner_pid?}` и `runtime.release {key}` есть в `features`
  `hello` любого runtime, ручного тоже. Ответ: `{owned, owners, busy, exiting}` и `attached` или
  `released`. Release только меняет множество, сервер он не останавливает.
- Живость владельца: при attach runtime наблюдает identity процесса `owner_pid` (pid и время
  старта, `state::identity::observe`). Владелец удаляется, если `judge` даёт `owner-dead` или
  `owner-pid-reused`, либо если он не обновлялся дольше `--owner-ttl-seconds` (по умолчанию
  3600 с). Каждый вызов coordinator обновляет владельца. На macOS время старта не наблюдается,
  работает только TTL.
- Решение об остановке принимает поток accept-цикла раз в 1 с, поэтому после решения serve
  соединений не принимает. Соединение, которое ядро поставило в backlog уже после решения,
  закрывается при выходе: клиент видит `NotRunning`, а `ensure` запускает новый serve и повторяет
  попытку. Условия: сервер свой, после очистки владельцев нет,
  открытых соединений нет, открытых read snapshot нет, store простаивает. Тогда сокет удаляется,
  в stderr пишется строка, процесс завершается с кодом 0.
- На Windows `Lifetime` всегда ручной: флагов владельца нет, автозапуска нет.

### 3. Простой store

`state::idle::busy` перечисляет причины занятости:

- dispatch в состоянии `dispatched` или `working`;
- QA lane с удерживаемым lease;
- непустая очередь QA;
- исполнение не в `exited` и не в `lost` (покрывает идущий QA run).

Store, который не является authority, не занят. Store, который нельзя прочитать, занят:
без доказательства простоя сервер не останавливается. Зависший живой dispatch держит сервер до
решения оператора — это требование, а не дефект.

### 4. Клиентские команды

`harness-runtime ensure --repo R --session S [--agent A] [--owner-pid P] [--owner-ttl-seconds N]
[--attach-only]` и `harness-runtime release --repo R --session S [--agent A]` (только Unix; на
Windows — usage и код 2). Ответ — одна строка JSON в stdout.

| Команда | Исход | `status` | Код |
|---|---|---|---|
| ensure | сервер ответил на attach | `reused` (`owned` true или false) | 0 |
| ensure | сервер без `runtime.attach` в features (старый ручной serve) | `reused`, `attached: false` | 0 |
| ensure | сервера нет, свой serve запущен и ответил | `started` (`pid`, `log`) | 0 |
| ensure | serve отказал при старте (не `lease_held`) | `refused` (`exit_code`, `error`, `remedy`, `log`) | 2 |
| ensure | serve не ответил за 40 с | `timeout` (`log`) | 2 |
| ensure | `--attach-only` без сервера | `not_running` | 3 |
| ensure, release | сбой самой команды | — | 1 |
| release | сервера нет / ключ не был владельцем / ключ удалён | `not_running` / `not_attached` / `released` | 0 |

- ensure запускает `current_exe serve --owner-session …` отсоединённо: stdin закрыт, stdout и
  stderr — в `<каталог runtime>/<repo-id>.serve.log` (права 0600, файл открывается после той же
  проверки каталога, что у serve), `process_group(0)`. Журнал только дописывается, после строки
  `--- harness-runtime ensure <pid>: starting serve`, и никогда не обнуляется: ensure, проигравший
  гонку старта, не стирает строки работающего сервера. Причину отказа ensure ищет только в строках
  после своего маркера. Ребёнок, завершившийся с `lease_held`
  (гонка двух ensure), означает, что другой ensure уже запустил сервер: ensure повторяет attach.
  Attach с `exiting: true` — ensure ждёт исчезновения сокета и запускает новый сервер.
- release никогда не посылает сигналов.

### 5. Hook `runtime-autostart` (только Claude Code)

- Подключение: `PreToolUse` (matcher `Bash`), `Stop`, `SubagentStop` в `settings.local.json.tmpl`.
  `.codex/hooks.json` hook не получает (раздел 6).
- `PreToolUse`: команда без `.harness/orchestration/coordinator.py` — тишина. Корень: путь
  coordinator из команды (относительный — от `cwd` payload), его третий родитель, затем
  `git rev-parse --path-format=absolute --git-common-dir` и его родитель (основной checkout).
- Проект сессии: тот же `git rev-parse --git-common-dir` от `CLAUDE_PROJECT_DIR` даёт основной
  checkout проекта сессии. `cwd` payload для этого не используется: агент меняет его через `cd`.
  Пустая или незаданная `CLAUDE_PROJECT_DIR` означает, что проект сессии неизвестен, и любой
  репозиторий считается чужим. Если основной checkout проекта сессии не совпадает с основным
  checkout из команды (coordinator чужого репозитория или путь, лишь упомянутый в `echo`/`grep`),
  hook никакой бинарник не запускает: `PreToolUse` предупреждает
  `[runtime-autostart-failed]` «coordinator репозитория … не относится к основному checkout
  проекта сессии», `Stop` и `SubagentStop` молчат. Так текст команды не выбирает бинарник вне
  проекта сессии.
- Допущение о доверии: сборка `<main>/native/harness-runtime/target/release/harness-runtime`
  основного checkout проекта сессии считается доверенной. Hook исполняет её вне песочницы агента
  и вне проверок прав, поэтому агент, которому песочница разрешает запись в `target/release`
  основного checkout, может подменить исполняемый файл. Проверка свежести по dep-info защищает от
  устаревшей сборки, но не от подмены; это остаточный риск автозапуска.
- Бинарник: при `<main>/native/harness-runtime/Cargo.toml` — ровно
  `<main>/native/harness-runtime/target/release/harness-runtime`. Свежесть — по dep-info
  `harness-runtime.d`, `Cargo.lock` и всем `Cargo.toml` рабочего пространства: любой файл новее
  бинарника, нет или нечитаем `.d` — сборка устарела. Устаревшая сборка не запускается: hook
  вызывает `ensure --attach-only`, при `not_running` предупреждает «сборка устарела: cargo build
  --release …». Без исходников runtime — `harness-runtime` из `PATH`, иначе предупреждение
  «бинарник не найден».
- Окружение: перед `ensure` hook снимает переменные, которые приложение добавляет только hook-у
  (`CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION`,
  `CLAUDE_CODE_SESSION_ATTENDED`, `CLAUDE_PID`, `AI_AGENT`, `CLAUDE_EFFORT`, `TRACEPARENT`,
  `CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA`, `CLAUDE_ENV_FILE`, `COLUMNS`,
  `LINES`, `HARNESS_HOOK_ENVELOPE`): serve и его исполнения получают окружение приложения.
  `CLAUDE_PID` передаётся аргументом `--owner-pid`.
- Вывод: `started` — `{"systemMessage": …}` с pid и журналом; `reused` — тишина; отказ, таймаут,
  устаревшая сборка, нет бинарника, песочница — первая строка stderr
  `[runtime-autostart-failed] <причина>` и `{"systemMessage": …, "hookSpecificOutput":
  {"hookEventName": "PreToolUse", "additionalContext": …}}`. Hook никогда не блокирует.
- `SANDBOX_RUNTIME=1` (так Claude Code помечает песочницу) — serve не запускается,
  предупреждение «hook исполняется в песочнице агента, запустите serve вручную».
- `Stop` — `release --session S`, `SubagentStop` — `release --session S --agent A`. Оба молчат,
  никогда не блокируют и не продлевают ход.
- Конверт `hook_response.py`: `runtime-autostart` активен во всех профилях, внутренняя ошибка
  разрешает, тайм-аут тела — `INNER_TIMEOUT_SECONDS` (50 с), что больше 40 с ожидания ensure и
  меньше 60 с тайм-аута hook-а.

Основания для Claude Code проверены по исполняемому бинарнику приложения 2.1.322 (тот же код в
CLI 2.1.309): локальный hook запускается прямым spawn без обёртки песочницы; окружение hook-а —
окружение процесса плюс `CLAUDE_PID`, `CLAUDECODE`, `CLAUDE_CODE_SESSION_ID` и
`CLAUDE_PROJECT_DIR`; схема вывода hook-а содержит `systemMessage`; payload `SubagentStop` и
`PreToolUse` субагента несут `agent_id` и `session_id` родителя.

### 6. Codex и Windows — ручной путь

Для Codex в репозитории нет первичного источника о том, где исполняются hooks и какой
`session_id` получают субагенты, поэтому автозапуск для Codex не поставляется:
`codex-hooks.json.tmpl` не меняется, а `HookSpec.runtimes` ограничивает строку каталога hooks
Claude Code. На Windows автозапуска нет. В обоих случаях remedy ошибки `[runtime_unavailable]`
говорит запустить `harness-runtime serve --repo <repo>` вне песочницы агента.

## Операционные последствия

- Hook в проект ставит `harness update`. Его выполняет человек, потому что `protect-hook-policy`
  запрещает агенту править `.claude/`. Release-бинарник тоже собирает человек.
- Журнал своего сервера — `<каталог runtime>/<repo-id>.serve.log`; при отказе hook называет его.
- Сессия без `Stop` не держит сервер вечно: владелец удаляется по смерти процесса `CLAUDE_PID`
  или по TTL.
- Ручной serve останавливает только человек. Свой serve, освобождённый при занятом store,
  останавливается после простоя.
- Python по-прежнему не запускает процессы (ADR 0021): запускает только Rust-бинарник по вызову
  bash-hook-а. Hook не правит файлы проекта и не является session-start hook-ом.
- Скилл `implement` запрещает запуск serve из Bash агента: при предупреждении
  `runtime-autostart` или `[runtime_unavailable]` маршрут останавливается и разработчику
  передаются причина и журнал.
