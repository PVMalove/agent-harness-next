# Секреты и токены

Для работы используются разные учётные данные: авторизация CLI агента, секреты интеграций,
токен IPC runtime и токен веб-консоли. Они принадлежат разным процессам и не заменяют друг друга.

## Настроить секреты без передачи значений агенту {#agent-setup}

??? quote ah-skill-text "Промпт для агента: доступ CLI к модели"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask which agent CLI/account type and shell are used. Read supported authentication instructions,
    never auth stores. Give the user private login/entry steps; do not accept credentials or perform
    login for them. Harness configuration must contain supported variable names, not secret values.
    Do not claim successful authentication without a separately authorized sanitized check.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: секреты контейнера"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask only required variable names, runtime process location and shell. Explain access_policy
    environment versus service environment, reserved names, proxy hosts and new approval for plan
    changes. For Bash provide manual read -rs and export instructions for the user to execute privately.
    The user restarts the existing runtime with updated environment; do not create a duplicate process.
    Use preflight metadata without printing values; see the container guide for the complete procedure.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: secret_refs интеграций"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read inventory metadata only; ask which variable names an existing integration needs.
    secret_refs documents names and neither exports them nor verifies auth. Do not read secret-bearing
    native config or fabricate managed_entries. Preserve native settings; actual credentials are
    entered by the user in the runtime's supported mechanism, separately from inventory editing.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: токены runtime и консоли"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    First distinguish IPC and console tokens. Check repository/user/IPC-directory metadata and
    service ownership without reading token files or requesting bootstrap URLs/cookies.
    IPC clients read their token themselves; the console exchanges its startup URL for a cookie.
    Explain rotation through the owning server's restart, performed by the user. If exposure is
    suspected, do not copy the value or purge history/logs automatically; agree on recovery actions.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Где находятся учётные данные

| Учётные данные | Где хранится значение |
| --- | --- |
| Доступ агента к модели | В механизме авторизации CLI или его окружении. |
| Секрет интеграции | В окружении или native-конфиге по правилам runtime; в инвентаре — только имена. |
| Токен IPC runtime | В отдельном файле `<repo-id>.token`, который создаёт `harness-runtime serve`. |
| Токен веб-консоли | У сервера; после открытия URL запуска — также в HttpOnly-cookie браузера. |

Не переносите содержимое файлов авторизации CLI в `.harness/project.json`,
`.harness/orchestration.json`, brief или промпт. Авторизуйте CLI его собственным способом;
инвентарь интеграций не выполняет вход в сервис.

## Передача секретов контейнеру

Компонент `environment` в `access_policy.defaults` или переопределении роли содержит имена,
никогда значения:

```json {.ah-code-wrap}
{
  "environment": ["ANTHROPIC_API_KEY"]
}
```

Это фрагмент политики, а не полный `orchestration.json`. Используйте имя, которое ожидает ваш
адаптер агента. Движок получает `--env NAME` и берёт значение из окружения процесса
`harness-runtime serve`, а не из терминала, в котором позднее вызвали coordinator.

В Bash можно ввести значение без отображения и без записи самого значения в историю команд:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

Если runtime уже работает, остановите его штатным способом и запустите заново с обновлённым
окружением. Для сервиса задайте переменную в окружении именно сервиса. Не запускайте второй
runtime для того же репозитория.

- Отсутствующее имя блокирует `dispatch preflight` и отправку.
- Список имён закрепляется в digest плана: добавленная после `dispatch propose` переменная не
  попадёт в уже предложенный dispatch.
- Нельзя перечислять имена, которые задаёт исполнитель: `HOME`, `GIT_CONFIG_COUNT`,
  `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`.
- При непустом `network.hosts` зарезервированы также `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`,
  `https_proxy`, `NO_PROXY`, `no_proxy`.

Доступ к API также зависит от сетевого allowlist. Поля политики и проверки описаны в
[руководстве по backend-оркестрации](../../backend-orchestration.md).

## Секреты интеграций

В `secret_refs` допустимы только имена по шаблону `[A-Z][A-Z0-9_]*`, например:

```json {.ah-code-wrap}
{
  "secret_refs": ["ANTHROPIC_API_KEY"]
}
```

Этот список документирует зависимость интеграции. Он не экспортирует переменные, не передаёт их
контейнеру и не проверяет авторизацию. Для контейнера отдельно нужен `environment`.
Полный контракт — на странице [«Интеграции»](integrations.md).

## Токен IPC runtime {#ipc-runtime}

На Unix `harness-runtime serve` создаёт токен в `$XDG_RUNTIME_DIR/harness/<repo-id>.token`,
если `XDG_RUNTIME_DIR` — абсолютный путь. Иначе используется `/tmp/harness-<uid>/<repo-id>.token`.
Runtime-каталог имеет права `0700`, файл токена и сокет — `0600`. На Windows используются
`XDG_RUNTIME_DIR` или `%LOCALAPPDATA%\harness` и проверки доступа платформы.

Клиент читает токен сам; копировать его в проектный конфиг или команду не нужно. При запуске
сервиса runtime и его клиенты должны использовать один runtime-каталог. Перезапуск сервера
создаёт новый токен. Подробнее — [Rust runtime](../../architecture/runtime.md).

## Токен веб-консоли {#web-console}

Сервер создаёт токен при запуске, а launcher печатает URL с ним. При открытии корректного URL
сервер отвечает перенаправлением на адрес без токена и устанавливает cookie с `HttpOnly` и
`SameSite=Strict`. Токен не записывается в проектные контракты.

Считайте исходный URL учётными данными: не вставляйте его в issue, отчёт, скриншот или промпт.
Новый процесс сервера получает новый токен; повторное открытие уже работающей консоли само по
себе его не меняет. Запуск описан в [быстром старте](../index.md).

## Если значение попало в чужие руки

1. Для ключа модели или интеграции отзовите значение у поставщика и выпустите новое; обновите
   авторизацию CLI или окружение нужного процесса.
2. Для IPC-токена перезапустите runtime; для токена консоли остановите именно сервер консоли и
   запустите новый процесс. Закрытие вкладки или TUI не означает остановку веб-сервера.
3. Удалите значение из доступных логов, отчётов и публикаций. Если оно попало в Git, сначала
   отзовите его: удаление из текущего файла не удаляет историю.
4. Проверьте доступ без печати значения. Промпт для агента должен просить проверить имена,
   наличие и результат авторизации, а не читать файлы авторизации или показывать секрет.

## Связанные настройки

- [Зависимости и окружение](environment.md) — окружение хоста, сервиса и образа.
- [Установка и обновление hooks](../../hooks/install-and-update.md) — управляемые записи native-конфигов.

- [Контейнер](container.md) — полный путь настройки исполнителя.
