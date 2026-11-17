# Зависимости и окружение

Окружение harness складывается из инструментов хоста, процесса `harness-runtime serve` и, если
роли работают в контейнере, worker-образа. Если команда есть в вашем терминале, сервис runtime
или контейнер могут её не видеть.

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
| Python | 3.12 или новее, запускайте harness этим интерпретатором. `environment.python`: `fail`, если версия ниже минимума. |
| `uv` | Есть в `PATH` и запускается. Нужен консоли и локальным проверкам harness. `environment.uv`: `fail`, если команда недоступна. |
| Git | Установлен, проект лежит в Git-репозитории. Для коммитов настроены имя и email. Проверки: `environment.git`, `environment.git_identity`. |
| CLI агента | Runtime из профиля роли установлен и авторизован. Общий health не проверяет вход в выбранный CLI. |
| `glab` | 1.117.0 или новее для GitLab-трекера. `environment.glab`: `warn`, если `glab` нет или его версию не удалось разобрать, `fail` для версии ниже минимума, `skipped` для другого трекера. Проверка локальная, к GitLab она не обращается. |

Для установленного CLI запустите проверку из каталога проекта:

```bash {.ah-code-wrap}
harness health .
```

Из исходников harness используйте `python3 harness/bin/harness.py health <repo>`.
Health проверяет отдельные свойства окружения. Зелёный отчёт не значит, что команды QA проекта
выполнятся успешно: health их не запускает.

## Rust runtime и окружение сервиса

Backend-оркестрации нужен исполняемый файл `harness-runtime`. Чтобы собрать его из исходников,
нужен Rust 1.89 или новее: так задан `rust-version` в workspace runtime. Компилятор нужен только
для сборки, готовый бинарный файл запускается без Rust.

Когда ledger переходит на runtime store, один раз выполните миграцию по
[руководству по backend-оркестрации](../../backend-orchestration.md). Пока вы работаете с
оркестрацией, процесс `serve` должен быть запущен:

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

У runtime и клиентов должны совпадать репозиторий, пользователь и runtime-каталог. На Unix
абсолютный `XDG_RUNTIME_DIR` задаёт каталог `$XDG_RUNTIME_DIR/harness`, без него runtime берёт
`/tmp/harness-<uid>`. На Windows runtime берёт `XDG_RUNTIME_DIR` или `%LOCALAPPDATA%\harness`.
Если runtime работает как сервис, проверяйте `PATH` и переменные окружения самого сервиса, а не
только интерактивного shell. Пути IPC и токены описаны на странице [«Секреты и токены»](secrets.md).

## Контейнерное исполнение

Docker или Podman нужны, только если выбран контейнерный исполнитель. Ему нужны Linux-хост с
локальным движком, CLI `docker` или `podman` в `PATH` процесса `harness-runtime serve` и право
пользователя этого процесса обращаться к движку.

Образы должны заранее лежать в локальном движке под тегами из политики: runtime запускает
контейнеры с `--pull never`. Worker-образ нужен всегда, proxy-образ нужен, если `network.hosts`
не пуст. Образы собирает и готовит проект.

| В worker-образе | Зачем |
| --- | --- |
| `/bin/sh` | QA-команды выполняются через `/bin/sh -c`. |
| Интерпретатор из shebang адаптера | Запускает проектный адаптер агента. |
| CLI агента, Git и инструменты проекта | Нужны, чтобы роль выполняла свои команды в контейнере. |
| Поддержка произвольного uid | Rootful-движок запускает контейнер с uid:gid пользователя хоста. |

В образе не должно быть секретов. Образ не должен зависеть от своего home-каталога и объявлять
`VOLUME`. Runtime сам задаёт entrypoint, пользователя и рабочий каталог, а `HOME` размещает в tmpfs.
Полный контракт образа и поля политики описаны в [руководстве по backend-оркестрации](../../backend-orchestration.md).

## Консоль

Launcher запускает консоль через `uv` с закреплёнными Python-зависимостями. При первом запуске
`uv` их скачивает, поэтому нужен доступ к сети. Проверка `environment.uv` подтверждает только, что
`uv` запускается, доступ к реестру пакетов она не проверяет. Команды запуска описаны в
[быстром старте](../index.md).

## Зависимости проекта и подготовка QA

Harness не устанавливает библиотеки и инструменты вашего проекта. Подготовьте их по инструкции
проекта. Команды QA должны работать в том checkout и окружении, где их запускают.

В оркестрации можно задать `qa_preparation`: команды подготовки, например установку зависимостей,
которые QA выполняет перед `verification_commands`. Необязательные `qa_environment_probes` и
`qa_project_file_checks` QA запускает только после упавшей подготовки, чтобы отдельно понять
причину. Точный порядок описан в [руководстве по backend-оркестрации](../../backend-orchestration.md).

`harness health` ещё до запуска QA предупреждает (`warn`), если среда не сможет выполнить
обязательные QA-команды. Эти проверки только читают окружение и ничего не запускают:

| Проверка | Предупреждает, если |
| --- | --- |
| `environment.qa_executables` | Исполняемого файла команды из `qa_gate_commands` (первое слово после присваиваний `VAR=...`) нет в `PATH`. Путь с `/` проверка ищет от корня репозитория. Команды, которые начинаются со встроенной команды shell (`cd`, `export`), не проверяются. |
| `environment.c_linker` | Проект собирает Rust (`cargo` в `qa_gate_commands` или `native/**/Cargo.toml`), а C-компоновщика `cc` нет в `PATH`. |
| `environment.runtime_socket_path` | Путь сокета runtime длиннее 100 байт при текущем `XDG_RUNTIME_DIR` (без него берётся `/tmp/harness-<uid>`, `TMPDIR` runtime не использует). Проверка работает при backend-оркестрации, на Windows пропускается. |

Запускайте health в той же среде, где агент выполняет QA, например внутри distrobox. Подробнее
на странице [«Контейнер»](container.md) и в установленном `.harness/instructions/container-executor.md`.

Каталог `.harness/.venv`, который создаёт `make bootstrap` в исходниках **этого репозитория**,
содержит dev-зависимости harness. Он не заменяет окружение целевого проекта. Отдельному
test-author нужны ещё рабочий runner и изоляция, подробнее в
[руководстве test-author](../../agents/test-author.md).

## Если инструмент не найден

1. Проверьте версию и `PATH` в том процессе, который выполняет действие: shell, сервис runtime
   или worker-контейнер.
2. Установите недостающую зависимость там же. Если поставить её на хост, в уже собранный образ
   она не попадёт.
3. Если вы изменили окружение сервиса, перезапустите runtime, затем повторите health и нужный
   preflight. Значения секретов в диагностике не печатайте.

Миграцию запускают только с одобрения человека. Команда и параметры описаны в разделе
[«Требования к хосту»](container.md#host).
