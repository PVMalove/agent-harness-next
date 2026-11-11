# Зависимости и окружение

Окружение состоит из инструментов хоста, процесса `harness-runtime serve` и, при контейнерном
исполнении, worker-образа. Наличие команды в вашем терминале не означает, что её видит сервис
runtime или контейнер.

## Проверить окружение с агентом {#agent-setup}

??? quote ah-skill-text "Промпт для агента: инструменты хоста"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read installed host requirements and inspect executable paths/versions without dumping env.
    Check Python/Git/uv and the tracker-specific glab minimum only when GitLab applies.
    Ask which OS/shell/user owns the process; propose missing-tool installation for review instead
    of executing it automatically. Project toolchain dependencies are separate from harness tools.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: окружение runtime"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Locate the actual harness-runtime binary and process user/PATH/IPC directory. Rust is required
    to build from source, not to use a prebuilt executable. Ask about service versus interactive
    launch. Migration needs its own human approval; restart only after user authorization and do
    not create a second runtime. Keep authentication values out of diagnostics.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: контейнер и worker-образ"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether containers are required at all. Read supported engine modes and check runtime-user
    access to a local engine. Distinguish distrobox/agent tools from host runtime/engine visibility.
    Verify worker /bin/sh, adapter interpreter, CLI and project tools from image/build metadata;
    image builds and live containers require separate approval. Do not mount the engine socket to workers.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: окружение консоли"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask whether the console is needed and inspect its documented uv launch path. Explain first-run
    network downloads and the bootstrap URL's credential status. Propose launch/environment changes
    for review; never print the token-bearing URL in reports or start a server without consent.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: зависимости проекта и QA"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Derive project install/QA commands from manifests and CI; do not assume harness installs them.
    .harness/.venv is the development environment of this toolkit, not every target application's env.
    Agree on separate host, worker-image and clean-room QA dependencies/preparation. Ask before
    running installation, network probes or full QA; report commands not actually exercised.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Инструменты хоста

| Компонент | Требование и проверка |
| --- | --- |
| Python | 3.12 или новее; запускайте harness подходящим интерпретатором. `environment.python`: `fail`, если версия ниже минимума. |
| `uv` | Доступен в `PATH` и запускается; нужен для окружения консоли и локальных проверок harness. `environment.uv`: `fail`, если команда недоступна. |
| Git | Установлен; проект — Git-репозиторий. Для коммитов настроены имя и email. Проверки: `environment.git`, `environment.git_identity`. |
| CLI агента | Runtime, выбранный в профиле роли, установлен и авторизован. Общий health не заменяет проверку входа в выбранный CLI. |
| `glab` | 1.117.0 или новее для GitLab-трекера. `environment.glab`: `warn` при отсутствии или старой версии, `skipped` для другого трекера. Проверка локальная, без запроса к GitLab. |

Для установленного CLI запустите проверку из каталога проекта:

```bash {.ah-code-wrap}
harness health .
```

Из исходников harness используйте `python3 harness/bin/harness.py health <repo>`.
Health проверяет отдельные свойства окружения; зелёный отчёт не означает, что все команды QA
проекта уже выполнились.

## Rust runtime и окружение сервиса

Для backend-оркестрации нужен исполняемый файл `harness-runtime`. Сборка из исходников требует
Rust 1.89 или новее — это `rust-version` workspace runtime. Компилятор нужен для сборки; при
использовании готового бинарного файла он не становится отдельной зависимостью запуска.

При переходе ledger на runtime store один раз выполните миграцию по
[руководству по backend-оркестрации](../../backend-orchestration.md). Во время работы процесс
`serve` должен оставаться запущенным:

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

У runtime и клиентов должны совпадать репозиторий, пользователь и runtime-каталог. На Unix
абсолютный `XDG_RUNTIME_DIR` задаёт каталог `$XDG_RUNTIME_DIR/harness`; без него используется
`/tmp/harness-<uid>`. На Windows используются `XDG_RUNTIME_DIR` или `%LOCALAPPDATA%\harness`.
Для сервиса проверяйте его собственные `PATH` и переменные окружения, а не только настройки
интерактивного shell. Пути IPC и токены описаны в [«Секретах и токенах»](secrets.md).

## Контейнерное исполнение

Docker или Podman нужны только при выбранном контейнерном исполнителе. Для него требуются
Linux-хост с локальным движком, CLI `docker` или `podman` в `PATH` процесса
`harness-runtime serve` и право этого пользователя обращаться к движку.

Образы должны уже находиться в локальном движке под тегами из политики: runtime запускает
контейнеры с `--pull never`. Worker-образ нужен всегда; proxy-образ — при непустом `network.hosts`.
Сборку и подготовку образов выполняет проект.

| В worker-образе | Зачем |
| --- | --- |
| `/bin/sh` | QA-команды выполняются через `/bin/sh -c`. |
| Интерпретатор из shebang адаптера | Запуск проектного адаптера агента. |
| CLI агента, Git и инструменты проекта | Выполнение роли и её команд в контейнере. |
| Поддержка произвольного uid | Rootful-движок запускает контейнер с uid:gid пользователя хоста. |

Образ не должен содержать секреты, зависеть от собственного home-каталога или объявлять `VOLUME`.
Runtime задаёт entrypoint, пользователя и рабочий каталог; `HOME` размещается в tmpfs.
Полный контракт образа и поля политики — в [руководстве по backend-оркестрации](../../backend-orchestration.md).

## Консоль

Launcher использует `uv` для запуска консоли с закреплёнными Python-зависимостями. При первом
запуске они скачиваются, поэтому нужен доступ к сети. Наличие `uv` проверяется отдельно от
доступности реестра пакетов. Команды запуска — в [быстром старте](../index.md).

## Зависимости проекта и подготовка QA

Установка harness не устанавливает библиотеки и инструменты самого проекта. Подготовьте их по
его инструкции; команды QA должны работать в том checkout и окружении, где их запускают.

Для оркестрации можно задать `qa_preparation`, например подготовку зависимостей, перед
`verification_commands`. Необязательные `qa_environment_probes` и `qa_project_file_checks`
запускаются только после неудачной подготовки, чтобы собрать независимую диагностику. Точный
порядок описан в [руководстве по backend-оркестрации](../../backend-orchestration.md).

Каталог `.harness/.venv`, который создаёт `make bootstrap` в исходниках **этого репозитория**,
содержит dev-зависимости harness. Он не заменяет окружение целевого проекта. Для отдельного
test-author дополнительно нужны рабочий runner и изоляция: см.
[руководство test-author](../../agents/test-author.md).

## Если инструмент не найден

1. Проверьте версию и `PATH` в том процессе, который выполняет действие: shell, сервис runtime
   или worker-контейнер.
2. Установите недостающую зависимость там же; изменение хоста не добавляет её в уже собранный образ.
3. После изменения окружения сервиса перезапустите runtime, затем повторите health и нужный
   preflight. Значения секретов в диагностике не печатайте.

Миграция требует человеческого одобрения: [команда и параметры](container.md#host).
