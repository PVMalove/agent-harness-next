# Секреты и токены

Harness работает с четырьмя видами учётных данных: авторизацией CLI агента, секретами интеграций,
токеном IPC runtime и токеном веб-консоли. Их используют разные процессы, и один вид не заменяет
другой.

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
| Секрет интеграции | В окружении или native-конфиге по правилам runtime. В инвентаре хранятся только имена. |
| Токен IPC runtime | В отдельном файле `<repo-id>.token`, который создаёт `harness-runtime serve`. |
| Токен веб-консоли | У сервера консоли. После открытия URL запуска ещё и в HttpOnly-cookie браузера. |

Не переносите содержимое файлов авторизации CLI в `.harness/project.json`,
`.harness/orchestration.json`, brief или промпт. Авторизуйте CLI его собственным способом:
инвентарь интеграций в сервис не входит.

## Передача секретов контейнеру

Компонент `environment` в `access_policy.defaults` или в переопределении роли содержит только
имена переменных, без значений:

```json {.ah-code-wrap}
{
  "environment": ["ANTHROPIC_API_KEY"]
}
```

Это фрагмент политики, а не полный `orchestration.json`. Используйте имя, которое ожидает ваш
адаптер агента. Движок контейнеров получает `--env NAME` и берёт значение из окружения процесса
`harness-runtime serve`. Окружение терминала, в котором вы потом вызываете coordinator, не
используется.

В Bash значение можно ввести так, чтобы оно не отображалось на экране и не попало в историю команд:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

Если runtime уже работает, остановите его обычным способом и запустите заново с новым
окружением. Если runtime работает как сервис, задайте переменную в окружении сервиса. Не
запускайте второй runtime для того же репозитория.

- Если переменной с указанным именем нет в окружении runtime, `dispatch preflight` и отправка
  блокируются.
- Список имён входит в digest плана. Переменная, добавленная после `dispatch propose`, не попадёт
  в уже предложенный dispatch.
- Нельзя перечислять имена, которые задаёт сам исполнитель: `HOME`, `GIT_CONFIG_COUNT`,
  `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`.
- Если `network.hosts` не пуст, зарезервированы ещё `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`,
  `https_proxy`, `NO_PROXY`, `no_proxy`.

Доступ к API зависит ещё и от сетевого allowlist. Поля политики и проверки описаны в
[руководстве по backend-оркестрации](../../backend-orchestration.md).

## Секреты интеграций

В `secret_refs` допустимы только имена по шаблону `[A-Z][A-Z0-9_]*`, например:

```json {.ah-code-wrap}
{
  "secret_refs": ["ANTHROPIC_API_KEY"]
}
```

Список только фиксирует, какие переменные нужны интеграции. Он не экспортирует переменные, не
передаёт их контейнеру и не проверяет авторизацию. Контейнеру переменные передаёт отдельный
`environment`. Полный контракт описан на странице [«Интеграции»](integrations.md).

## Токен IPC runtime {#ipc-runtime}

На Unix `harness-runtime serve` создаёт токен в `$XDG_RUNTIME_DIR/harness/<repo-id>.token`,
если `XDG_RUNTIME_DIR` задан абсолютным путём. Иначе токен лежит в `/tmp/harness-<uid>/<repo-id>.token`.
У runtime-каталога права `0700`, у файла токена и сокета `0600`. На Windows runtime берёт
`XDG_RUNTIME_DIR` или `%LOCALAPPDATA%\harness` и полагается на проверки доступа платформы.

Клиент читает токен сам, копировать его в проектный конфиг или команду не нужно. Если runtime
работает как сервис, он и его клиенты должны видеть один runtime-каталог. После перезапуска
сервер создаёт новый токен. Подробнее на странице [Rust runtime](../../architecture/runtime.md).

## Токен веб-консоли {#web-console}

Сервер консоли создаёт токен при запуске, а launcher печатает URL с этим токеном. Когда вы
открываете верный URL, сервер перенаправляет браузер на адрес без токена и ставит cookie с
`HttpOnly` и `SameSite=Strict`. В проектные контракты токен не попадает.

Считайте URL запуска учётными данными: не вставляйте его в issue, отчёт, скриншот или промпт.
Новый процесс сервера получает новый токен. Если снова открыть уже работающую консоль, токен
не меняется. Запуск описан в [быстром старте](../index.md).

## Если значение попало в чужие руки

1. Ключ модели или интеграции отзовите у поставщика и выпустите новый. Затем обновите
   авторизацию CLI или окружение нужного процесса.
2. Для IPC-токена перезапустите runtime. Для токена консоли остановите сервер консоли и
   запустите новый процесс. Закрытая вкладка или TUI сервер не останавливают.
3. Удалите значение из логов, отчётов и публикаций, до которых можете дотянуться. Если значение
   попало в Git, сначала отзовите его: удаление из текущего файла не стирает историю.
4. Проверьте доступ, не печатая значение. Промпт для агента должен просить проверить имена,
   наличие переменных и результат авторизации. Читать файлы авторизации и показывать секрет агент
   не должен.

## Связанные настройки

- [Зависимости и окружение](environment.md): окружение хоста, сервиса и образа.
- [Установка и обновление hooks](../../hooks/install-and-update.md): управляемые записи native-конфигов.
- [Контейнер](container.md): настройка исполнителя от начала до конца.
