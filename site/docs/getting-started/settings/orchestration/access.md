# Доступ и контейнер

`access_policy` в `.harness/orchestration.json` описывает режим запуска и доступ к сети,
файлам, образам и окружению. `extensions` выбирает реализации, которые проверяют и применяют
план. Это отдельный контракт от [назначений и tool_policy](roles.md): список инструментов
не доказывает права процесса, а `transport: external` сам по себе не означает контейнер.

## Когда политика не задана

В управляемом `.harness/orchestration.example.json` нет `access_policy`, а все шесть extensions
равны `none`. Пример не выбирает за проект образы, сеть и пути хоста. Без явной политики brief
сохраняет историческое поведение `inherit`; оно не доказывает sandbox-изоляцию.

Если добавить **любой** `access_policy`, даже `{}` или `mode: inherit`, `dispatch send`
потребует выбранную реализацию `extensions.runtime_access`. `none` не подтверждает доступ,
поэтому отправка блокируется до handoff; тихого отката к прежнему `inherit` нет.
Установленный JSON и успешный health ещё не доказывают готовность native-исполнителя.

## Defaults: компоненты доступа {#defaults}

`access_policy.defaults` задаёт общие компоненты `mode`, `container`, `environment`, `network`,
`filesystem`. Все компоненты необязательны, но внутри заданных объектов действуют требования
таблицы. Значения сети и окружения относятся к выбранному плану; без политики прежнее
`inherit` не превращается в запрет сети или очистку окружения.

| Поле | Контракт |
| --- | --- |
| `access_policy.defaults.mode` | `inherit`, `sandbox`, `unsandboxed`. Если компонент не задан, resolver выбирает `inherit`. Встроенный контейнерный исполнитель отклоняет `unsandboxed`; допустимость схемы не доказывает поддержку средой. |
| `access_policy.defaults.container.engine` | `docker` или `podman`; default внутри заданного `container` — `docker`. Сам контейнерный компонент не добавляется автоматически. |
| `access_policy.defaults.container.worker_image` | Обязателен внутри `container`: строка — ссылка на образ, например `harness-worker:local`. От 1 до 255 символов, начинается с буквы/цифры, без пробелов и ведущего `-`. |
| `access_policy.defaults.container.proxy_image` | Необязательная ссылка на образ в том же формате. Исполнитель требует её при непустом `network.hosts`; если тег задан, образ должен существовать локально. |
| `access_policy.defaults.environment` | Массив уникальных имён по `[A-Za-z_][A-Za-z0-9_]*`, никогда не значений. `[]` очищает список; без заданного компонента он не добавляется в план. |
| `access_policy.defaults.network.hosts` | Массив явных DNS-имён без URL, порта и wildcard; до 253 символов, метки до 63. Внутри заданного `network` поле обязательно. При отсутствии сетевого компонента resolver использует `[]`. |
| `access_policy.defaults.filesystem[].resource` | Обязателен в каждой записи: `checkout`, `git_common`, `shared_storage`, `cache`. Массив `filesystem` необязателен; выбранный план по умолчанию содержит `[]`. |
| `access_policy.defaults.filesystem[].path` | Непустая строка без NUL. Обязательна только для `cache` и запрещена для остальных ресурсов. Относительный путь считается от worktree; `~` раскрывает resolver. |
| `access_policy.defaults.filesystem[].access` | Обязателен в каждой записи: `read` или `write`. Реальные права среды проверяются отдельно, а не выводятся из текста конфига. |
| `access_policy.defaults.filesystem[].variable` | Только у `cache`: имя переменной окружения по `[A-Za-z_][A-Za-z0-9_]*`, например `CARGO_HOME`. Контейнерный исполнитель сам передаёт `--env <имя>=<путь кэша>`; путь берётся из плана, а не из окружения `serve`. Имя уникально среди кэшей компонента, не совпадает с именем из `environment` и не входит в имена, которые задаёт runtime (ADR 0032). |

Ресурсы `checkout`, `git_common` и `shared_storage` разрешаются из worktree и хранилища проекта;
их произвольный `path` указать нельзя. У read-only роли нельзя запросить `write` для этих
корней. Отдельный `cache` может иметь свой доступ. Обязательные корни и операционный scratch
resolver добавляет отдельно: `filesystem: []` не удаляет требования к работе и отчётам.

## Overrides ролей {#role-overrides}

`access_policy.roles.<ключ>` принимает имена manifest'ов: `architect`, `developer`, `code-review`,
`qa`, `verification`, `conflict-resolver`, `database-migrations`, `messaging-integration`.
Каждый override заменяет **названный компонент целиком**; остальные берутся из defaults.
Формат и ограничения полей те же, что в таблице выше:

- `access_policy.roles.<ключ>.mode`.
- `access_policy.roles.<ключ>.container.engine`, `access_policy.roles.<ключ>.container.worker_image`, `access_policy.roles.<ключ>.container.proxy_image`.
- `access_policy.roles.<ключ>.environment`.
- `access_policy.roles.<ключ>.network.hosts`.
- `access_policy.roles.<ключ>.filesystem[].resource`, `access_policy.roles.<ключ>.filesystem[].path`, `access_policy.roles.<ключ>.filesystem[].access`, `access_policy.roles.<ключ>.filesystem[].variable`.

Например, `filesystem` с одним `checkout: read` не добавляется к defaults, а заменяет весь
их массив. У `container` также нет глубокого слияния: если повторить только `worker_image`,
`proxy_image` из defaults исчезнет, а пропущенный `engine` снова получит default `docker`.
Повторите необходимые поля компонента явно, включая `podman`, если выбран именно он.

## Overrides операций coordinator {#operation-overrides}

`access_policy.operations.<ключ>` принимает только `qa`, `git`, `publish`. Операцию выполняет
coordinator, поэтому resolver использует defaults и override операции, **без override роли**.
Её собственные записи имеют тот же формат:

- `access_policy.operations.<ключ>.mode`.
- `access_policy.operations.<ключ>.container.engine`, `access_policy.operations.<ключ>.container.worker_image`, `access_policy.operations.<ключ>.container.proxy_image`.
- `access_policy.operations.<ключ>.environment`.
- `access_policy.operations.<ключ>.network.hosts`.
- `access_policy.operations.<ключ>.filesystem[].resource`, `access_policy.operations.<ключ>.filesystem[].path`, `access_policy.operations.<ключ>.filesystem[].access`, `access_policy.operations.<ключ>.filesystem[].variable`.

Поэтому операция coordinator может писать clean-room checkout, Git metadata или общее хранилище,
даже если роль QA read-only. Операционные требования проверяются отдельно.
`qa run` и publish используют закреплённый план; интеграционные команды local QA/refresh/resolve
читают план операции из текущей конфигурации. Подробности — в
[backend-руководстве](../../../backend-orchestration.md).

## Реализации: extensions {#extensions}

`extensions` — необязательный словарь строк. Допустимы ровно шесть ключей:

| Ключ extensions | Назначение |
| --- | --- |
| `transport_health` | Наблюдение здоровья транспорта. |
| `verification_environment_health` | Наблюдение среды проверки. |
| `retry_reason_classifier` | Классификация причины повтора; решение остаётся за coordinator. |
| `context_telemetry_provider` | Наблюдаемая телеметрия контекста. |
| `human_notifier` | Уведомления человеку. |
| `runtime_access` | Нативное подтверждение, применение плана и handoff worker. Встроенное имя `docker` выбирает контейнерный исполнитель Docker/Podman. |

Для каждого ключа default — `none`. Другие формы — имя реализации, заранее зарегистрированной
хост-процессом, или `module:factory`: фабрика без аргументов в импортируемом проектном модуле.
Неизвестная или непригодная реализация даёт отказ. Само имя не устанавливает пакет и не
создаёт реализацию. Extensions не добавляют инструменты модели и не меняют system prompt.

В поставке есть встроенное имя `docker` для `runtime_access`; оно работает с обоими движками.
При его выборе схема и валидатор требуют `access_policy.defaults.container` с `worker_image`.
Любой другой provider проект должен сам реализовать и проверить.

## Контейнерный план {#container}

Встроенный исполнитель требует Linux, runtime store и доступный локальный движок.
Отправляемые через него роли должны использовать `transport: external`. Харнесс не собирает
и не скачивает образы: пользователь готовит их отдельно, `dispatch propose` закрепляет digest,
а если образ изменился после approval, нужен новый согласованный план.

- Для непустого `network.hosts` нужен локальный `proxy_image`. Выход идёт через отдельный
  egress proxy только по HTTP(S), порты 80/443, к точным разрешённым хостам. Поддомены, wildcard,
  IP-литералы и SSH этим списком не разрешаются. При `[]` контейнер получает `--network none`.
- `environment` содержит только имена. Значения берутся из окружения `harness-runtime serve`;
  после их смены runtime нужно перезапустить. Имена входят в digest, значения не попадают
  в конфиг, brief, argv, evidence и логи. Auth-файлы агента не монтируются. Отсутствующее имя
  в окружении runtime — блокер, а не повод попросить ключ в чате.
- Исполнитель резервирует `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`,
  `HARNESS_EXECUTOR`; при сетевом доступе также `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`,
  `https_proxy`, `NO_PROXY`, `no_proxy`. Эти имена нельзя включать в список передачи.
- Контейнер для QA включается только через явный `access_policy.operations.qa.container`.
  Одного `defaults.container` недостаточно: без override команды QA остаются на хосте.

Следующий JSON — фрагмент для объединения с текущей конфигурацией, а не готовая установка.
Теги образов, API-хост и имя переменной — примеры; замените их подтверждёнными значениями
проекта. Профили и external transport здесь не настраиваются.

```json
{
  "access_policy": {
    "defaults": {
      "mode": "sandbox",
      "container": {
        "engine": "docker",
        "worker_image": "harness-worker:local",
        "proxy_image": "harness-proxy:local"
      },
      "environment": [
        "LLM_API_KEY"
      ],
      "network": {
        "hosts": [
          "llm-api.example.com"
        ]
      },
      "filesystem": [
        {
          "resource": "checkout",
          "access": "write"
        },
        {
          "resource": "git_common",
          "access": "write"
        },
        {
          "resource": "shared_storage",
          "access": "write"
        },
        {
          "resource": "cache",
          "path": "~/.cache/uv",
          "access": "write"
        }
      ]
    },
    "roles": {
      "code-review": {
        "filesystem": [
          {
            "resource": "checkout",
            "access": "read"
          }
        ]
      }
    },
    "operations": {
      "qa": {
        "container": {
          "worker_image": "harness-worker:local"
        },
        "environment": [],
        "network": {
          "hosts": []
        }
      }
    }
  },
  "extensions": {
    "runtime_access": "docker"
  }
}
```

В примере `code-review` заменяет только filesystem, наследуя остальные компоненты.
QA заменяет container, environment и network: его контейнер использует `docker`, не получает
`LLM_API_KEY`, не наследует proxy и работает без сети. Это не настройка доступа git/publish.

Как подготовить образы, среду и сеть и устранить блокеры, описано на странице
[«Контейнер»](../container.md) и в установленном `.harness/docs/container-executor.md`.
Имена и значения секретов разобраны в [«Секреты и токены»](../secrets.md).

## Настроить с агентом {#agent-access-setup}

Сначала согласуйте общий доступ, затем при необходимости контейнерные компоненты.
Агент должен спрашивать только недостающие решения и показывать весь итоговый план до записи.

??? quote ah-skill-text "Промпт для агента: доступ и реализации"

    ```text
    Help me configure access_policy and extensions for this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema,
    managed example and role manifests. Read .harness/docs/container-executor.md
    when container execution is involved. Run available read-only health/config checks.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.
    Never read authentication files or request, print or store token/key values.

    First distinguish keeping unauthored legacy inherit from declaring an access policy.
    Explain that even an authored inherit policy blocks dispatch send until a working
    runtime_access provider verifies it; none is not an access proof.
    Ask which executor is intended: the built-in docker provider, an existing trusted
    project provider, or keeping the current unauthored behavior. Do not choose
    unsandboxed as a workaround for blockers. Do not invent a module:factory provider.
    Ask for the minimal network hosts, named filesystem resources/cache paths and access
    levels. Then ask which role and qa/git/publish operation overrides are needed.
    Explain whole-component replacement: container/network/filesystem/environment
    entries do not deep-merge. Operations use defaults plus their own override, never
    a role override. Keep read-only roles read-only and retain operational requirements.
    For docker, verify defaults.container.worker_image is present. Explain that
    container QA requires an explicit operations.qa.container; defaults alone do not
    containerize QA. Do not enable other extensions just because fields are available.

    Use only supported fields and repository evidence or my answers; do not guess
    paths, image tags, module names or hosts. Preserve unrelated configuration.
    Show the exact proposed diff and a concise summary of inherited/replaced components.
    Wait for my approval, then apply only the approved diff with Edit/Write.
    Run installed config validate --canonical --json and harness health again.
    For an existing dispatch I identify, inspect installed dispatch preflight --help
    and run the read-only preflight with the required arguments. Without a suitable
    dispatch, report native verification as not performed; do not create one to test.
    Report checks and remaining blockers. Do not send workers, create batches, install
    extensions, build/pull images, migrate state, change Git, commit or open a PR.
    ```

??? quote ah-skill-text "Промпт для агента: контейнер, сеть и окружение"

    ```text
    Help me configure the container access components of this repository.

    Follow repository instructions. Keep questions, choices and user-facing summaries in Russian.
    Read .harness/project.json, .harness/orchestration.json, the installed schema,
    managed example and role manifests. Read .harness/docs/container-executor.md
    when container execution is involved. Run available read-only health/config checks.
    Ask only for unresolved facts, one question at a time. Offer 2-4 concrete choices
    plus «Другое», with one consequence each. Put an evidence-based recommendation
    first and mark it «Рекомендуется»; otherwise ask for the missing fact.
    Never read authentication files or request, print or store token/key values.

    Check the documented Linux/runtime-store prerequisites and existing role transport.
    Ask which local engine (docker/podman) and existing worker/proxy image references
    should be used. Explain that roles sent through the container executor need external
    transport. If assignment transport must change, show that as a separate explicit
    change; do not silently switch roles while configuring resource access.
    Ask for the complete required HTTP(S) host allowlist, including the model API host.
    No URL, port, wildcard or IP literal; do not infer that subdomains or SSH are allowed.
    A non-empty host list needs a proxy image. Show the full allowlist for review.
    Ask only for environment variable NAMES and explain which list replaces defaults.
    Validate names and reject executor-reserved names. Do not read their values.
    Ask which interactive shell I use. For Bash and a user-approved name, offer
    a manual silent command such as
    read -rs -p 'LLM_API_KEY: ' LLM_API_KEY; export LLM_API_KEY
    using the validated chosen name. The user enters the value privately; never run
    this command yourself or request the resulting value. Explain that the user must
    restart harness-runtime serve to supply changed values; do not restart it yourself.
    Check whether QA should have its own container, hosts and environment list.
    Do not copy an image tag or API hostname from an example without confirmation.

    Use only supported fields and repository evidence or my answers; do not guess
    paths, image tags, module names or hosts. Preserve unrelated configuration.
    Show the exact proposed diff and a concise summary of inherited/replaced components.
    Wait for my approval, then apply only the approved diff with Edit/Write.
    Run installed config validate --canonical --json and harness health again.
    For an existing dispatch I identify, inspect installed dispatch preflight --help
    and run the read-only preflight with the required arguments. Without a suitable
    dispatch, report native verification as not performed; do not create one to test.
    Report checks and remaining blockers. Do not send workers, create batches, install
    extensions, build/pull images, migrate state, change Git, commit or open a PR.
    ```

## Проверка и дальше

Начните с [проверки конфигурации](index.md#config-validation). Затем `dispatch preflight`
проверяет среду конкретного запуска без создания контейнера. Используйте параметры из help
установленного coordinator, а не выдуманный ID dispatch. Наличие engine, образов, переменных
и доказательств доступа проверяется отдельно от JSON. Устраните отказ до send;
не снимайте ограничения ради обхода блокера. Команды QA — в [верификации](verification.md).
