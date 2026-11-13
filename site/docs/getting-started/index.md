# Быстрый старт

Agent Harness Next устанавливает в проект скиллы, hooks и контекстные документы одним snapshot,
который можно проверить. После установки проект не зависит от репозитория harness: скиллы и hooks
работают через встроенные механизмы Claude Code и Codex, а оркестрация хранит состояние в
локальном runtime store, который ведёт Rust runtime.

!!! note "Ранний доступ"

    Сайт описывает текущую версию, но поведение и флаги ещё меняются. Перед установкой в рабочий
    проект сделайте резервную копию и проверьте требования.

## Начать с агентом {#agent-setup}

[Новый проект](../skills/start-project.md) · [Существующий проект](../skills/integrate-project.md) · [Уточнение идеи](../skills/grilling.md) · [Термины и ADR](../skills/vendor/domain-modeling.md).

??? quote ah-skill-text "Промпт для агента: начать новый проект"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read and invoke the installed start-project skill; do not duplicate or bypass its phases.
    If it cannot be located, report the missing skill instead of simulating it.
    Start with the idea: goal, users, recurring work, project type and stack constraints.
    Follow Shape to decide whether to stay in conversation, write a brief, seed a repository or
    assemble a harness. Ask before creating a repository; do not assume software or choose a stack.
    For an approved seed, agree on structure, CONTEXT.md terminology and first ADRs for stack,
    branching and QA. Record only confirmed decisions with sources; leave open choices explicit.
    For approved harness assembly, choose capability, language, branch pattern, actual QA commands
    and project.json from evidence and answers. Keep phases independently reviewable.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: подключить существующий проект"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read and invoke the installed integrate-project skill; do not duplicate its workflow.
    If unavailable, report the missing skill instead of pretending to invoke it.
    Audit read-only first: manifests, actual build/test commands, CI, branches, domain, existing
    AI instructions/configuration, ADR conventions and installed harness state. Preserve live work.
    Present findings, conflicts and the proposed installation manifest; wait for confirmation.
    Offer optional decision-history reconstruction separately when useful. Read that skill's
    RECONSTRUCT-HISTORY.md only for the approved investigation; do not invent reasons from code.
    Each proposed ADR needs evidence/source links; label uncertainty and obtain consent before
    writing inferred decisions. Create or extend the existing ADR convention and CONTEXT.md.
    Only after the approved audit/manifest, install the selected capability without replacing
    unrelated native settings. Configure project.json with discovered QA commands, not guesses.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

## Путь установки

Выберите сборку, и схема покажет, какой snapshot попадёт в проект. На узлы можно нажимать.

<div class="ah-flow" id="ah-install-flow">
  <div class="ah-core-scroll"><div class="ah-core is-fit" id="ah-install-map"></div></div>
  <div class="ah-flow-note" id="ah-install-note" aria-live="polite">
    <b>Выберите сборку</b>
    <span>Нажмите на capability или на любой узел схемы.</span>
  </div>
</div>

## Требования

| Компонент | Требование |
| --- | --- |
| Python | 3.12 или новее |
| Git | Каталог проекта уже Git-репозиторий |
| Runtime | Claude Code или Codex: скиллы и hooks подключаются их встроенными механизмами |
| ОС | Linux. На Windows нужен поддерживаемый runtime, связь с ним идёт через named pipe |
| `uv` | Нужен консоли и локальным проверкам harness. Без него health показывает `environment.uv: fail` |
| `harness-runtime` | Нужен backend-оркестрации. Для сборки из исходников нужен Rust 1.89 или новее |
| Опционально | Docker или rootless Podman для контейнерного worker и QA |

Зависимости вашего проекта harness не устанавливает. Подготовьте их сами по
[руководству по окружению](settings/environment.md).

## 1. Установите глобальный слой

Глобальный слой ставится один раз на машину. Это минимальный профиль инструкций и скиллы
`start-project` и `integrate-project`. Параметр `--runtime` можно повторять.

```bash {.ah-code-wrap}
python3 bin/install-global.py --target-home "$HOME" \
  --runtime claude --runtime codex
```

`--check` показывает статус и ничего не записывает. `--replace-conflicts` заменяет конфликтующие
файлы и сохраняет их резервные копии. MCP, модели, плагины, credentials и permissions установщик
не трогает.

??? quote ah-skill-text "Промпт для агента: глобальный слой"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Locate bin/install-global.py in the actual harness source and inspect --help.
    Inspect --check before proposing installation. Ask which runtime(s) and target home are needed;
    --runtime is repeatable. Show the exact command and global-file effects, then obtain approval.
    After approval run that installation and check status again. Do not replace conflicts without
    separate approval; explain the documented backup behavior. Do not configure credentials/MCP.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 2. Подключите harness к проекту

Новый проект удобнее начинать скиллом `start-project`, существующий подключайте скиллом
`integrate-project`: он сначала изучает соглашения репозитория, а потом встраивает harness.

Чтобы установить harness в Git-репозиторий напрямую, выполните:

```bash {.ah-code-wrap}
python3 harness/bin/harness.py init /path/to/repository \
  --capability engineering-suite \
  --project-type software --stack python --base-branch main --language ru \
  --qa-gate-command "make test"
```

Если в проекте уже есть свои скиллы, используйте `adopt`. Он сохраняет всё, что не входит в
выбранную capability. Если имя скилла из capability уже занято, `adopt` завершается ошибкой и
печатает список конфликтов. `--replace-conflicts` заменяет конфликтующие каталоги без резервной
копии, поэтому сначала проверьте список.

```bash {.ah-code-wrap}
python3 harness/bin/harness.py adopt /path/to/repository \
  --capability engineering-suite --replace-conflicts
```

Capability задаёт состав snapshot. Выберите одну сборку.

| Capability | Что добавляет |
| --- | --- |
| `project-foundation` | Доменно-нейтральная база по умолчанию: дизайн, research, handoff, язык проекта. |
| `mattpocock-suite` | Полный upstream-набор, закреплённый на проверенном коммите. |
| `engineering-suite` | Поверх `mattpocock-suite`: инженерный workflow, эпики и тикеты, триаж, review по двум осям, `qa-gate`, подготовка PR. |
| `backend-orchestration` | Поверх `engineering-suite`: coordinator, роли, briefs, worktrees, ledger и QA lane. |

??? quote ah-skill-text "Промпт для агента: подключить harness"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Determine whether the repository is new, established or already harnessed. Recommend the
    installed start-project, integrate-project or an explicit CLI installation based on that state.
    Inspect harness --help; ask unresolved capability, project type, stack, base branch, language
    and QA commands. Show install/adopt effects and conflicts. Execute only the approved command;
    do not silently use --replace-conflicts or overwrite project configuration.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 3. Проверьте установку: health

`health` проверяет установку и окружение. Без флагов он ничего не меняет. Запускайте его после
`init`, `adopt` или `update`, после клонирования проекта и когда агент не находит скиллы.

```bash {.ah-code-wrap}
python3 harness/bin/harness.py health /path/to/repository
python3 harness/bin/harness.py health /path/to/repository --fix
python3 harness/bin/harness.py health /path/to/repository --online
python3 harness/bin/harness.py health /path/to/repository --json
```

| Флаг | Что делает |
| --- | --- |
| без флагов | Проверяет локально файлы, каталоги, окружение и Repo Map. |
| `--fix` | Создаёт отсутствующие каталоги `.harness/` и перегенерирует устаревший registry скиллов. Системные настройки и worktree не трогает. |
| `--online` | Добавляет проверки трекера: авторизацию `gh`/`glab`, доступность origin, права и метки. Без флага выполняется только локальная `tracker.project`, остальные проверки `tracker.*` пропускаются. |
| `--json` | Печатает машиночитаемый отчёт `schema_version: 1`. |

Каждая строка помечена `✅` ok, `⚠️` warn, `❌` fail или `-` skipped. При `fail` команда печатает
причину и команду исправления. Группа «Оркестрация» появляется только с `backend-orchestration`.
В ней видны runtime, ledger, незавершённые batch, dispatch без активности и неучтённые worktree.

??? quote ah-skill-text "Промпт для агента: проверить health"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Run the installed local harness health for the exact repository; this does not require online
    checks. Explain ok/warn/fail/skipped and their concrete consequences, without copying secrets.
    Propose fixes one group at a time. Ask before --fix, inspect its effects, then run only approved
    repairs and recheck. Do not use --online without consent; tracker login and permission changes
    remain the user's actions. A skipped check is not a passed check.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 4. Первые команды

```bash {.ah-code-wrap}
python3 harness/bin/harness.py list /path/to/repository
python3 harness/bin/harness.py diff /path/to/repository
python3 harness/bin/harness.py update /path/to/repository
```

| Команда | Назначение |
| --- | --- |
| `list <repo>` | Печатает список установленных скиллов. |
| `diff <repo>` | Показывает расхождения с зафиксированным в lock-файле snapshot. `--json` печатает машиночитаемый отчёт. |
| `update <repo>` | Обновляет управляемые файлы до текущей версии harness. Если вы правили стандартные скиллы, прерывается и не трогает файлы; `--force-managed-files` заменяет ваши правки. |
| `console <repo>` | Открывает TUI-пульт или веб-консоль: задачи, оркестрация, отчёты и восстановление. |
| `cleanup <repo>` | Печатает план очистки `.harness/.sandboxes`. `--apply` удаляет, `--mode hard` требует `--apply --confirm HARD`. |
| `uninstall <repo>` | Печатает план удаления harness. `--apply --confirm UNINSTALL` удаляет harness целиком, изменённые файлы сохраняет в `.harness-uninstall-backup/`. |

`console` находится в beta. Ему нужен `uv`, а при первом запуске он скачивает зависимости, поэтому
нужен доступ к сети. `console --web` запускает Сервер консоли, печатает URL с токеном и открывает
браузер.

Если установлена `backend-orchestration`, проверьте ещё состояние оркестрации:

```bash {.ah-code-wrap}
python3 .harness/orchestration/coordinator.py --repo . dispatch preflight \
  --batch '<batch-id>' --role developer
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

??? quote ah-skill-text "Промпт для агента: первые команды"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Explain list and diff from the installed CLI and use them to show current state.
    Ask which next operation is wanted: update, cleanup preview or console. Preview update changes
    and cleanup's deletion set; update and cleanup --apply need explicit confirmation.
    Explain console first-run uv downloads and that its bootstrap URL contains a credential;
    do not print that URL in reports. Do not start services or perform cleanup just to demonstrate.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```


## 5. Runtime {#runtime}

Раздел нужен, если установлена `backend-orchestration`. После однократной миграции состояние
оркестрации хранит runtime store, и записывает в него только процесс `harness-runtime serve`.
Миграцию `harness-runtime migrate` выполняют один раз, и её одобряет человек. Порядок описан в
[руководстве по backend-оркестрации](../backend-orchestration.md).

После миграции `serve` должен работать всё время, пока вы пользуетесь оркестрацией. Запускайте его
вне песочницы агента:

```bash {.ah-code-wrap}
harness-runtime serve --repo /path/to/repository
python3 .harness/orchestration/coordinator.py --repo . runtime status
```

`runtime status` печатает pid, версию и протокол запущенного runtime. Если runtime не запущен, отказывают:

- `coordinator.py` команды `batch`, `dispatch`, `qa` и `recovery`: код 2 и `[runtime_unavailable]`;
- `harness cleanup`: worktree остаются с причиной «runtime does not answer»;
- `harness worktree-remove`: та же причина отказа.

Состояние runtime показывают `harness health` (проверка `orchestration.runtime` со строкой «Как
исправить») и веб-консоль: индикатор «Runtime» в заголовке и команда запуска на страницах
оркестрации. В Claude Code runtime запускает hook
[автозапуска](../guides/orchestration/operations.md#runtime-autostart). В Codex и на Windows
запускайте процесс сами: в отдельном терминале или как пользовательский сервис. Пример для
`systemd --user`:

```ini {.ah-code-wrap}
# ~/.config/systemd/user/harness-runtime.service
[Unit]
Description=harness-runtime serve

[Service]
ExecStart=/abs/path/to/harness-runtime serve --repo /path/to/repository
Environment=PATH=/usr/local/bin:/usr/bin:/bin
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash {.ah-code-wrap}
systemctl --user daemon-reload
systemctl --user enable --now harness-runtime.service
```

Сервис получает своё окружение, а не окружение вашего shell:

- **`PATH`.** В `ExecStart` укажите абсолютный путь к `harness-runtime`. Для контейнерного
  исполнителя добавьте в `Environment=PATH=` каталог `docker` или `podman`.
- **`XDG_RUNTIME_DIR`.** systemd задаёт сервису `/run/user/<uid>`. Клиенты ищут сокет в том же
  каталоге, поэтому в shell, где работают агент и coordinator, задайте то же значение. Если
  в shell переменной нет, клиент ищет сокет в `/tmp/harness-<uid>` и не находит runtime.

## Дальше

- [Рабочий поток](../guides/workflow.md)
- [CLI и конфигурация](../reference/cli.md)
- [Обзор архитектуры](../architecture/overview.md)
- [Rust runtime](../architecture/runtime.md)
- [Справочник](../reference/index.md)
- [Демо](../demo/index.md)
