# Контейнер

Встроенный исполнитель `docker` запускает утверждённого внешнего worker в отдельном контейнере
Docker или Podman. Контейнерный QA включается отдельно: каждая команда gate получает свой
контейнер. Эта страница проводит через настройку; полный справочник полей — в
[«Доступе и контейнере»](orchestration/access.md).

## Когда нужен и что меняет {#when-to-use}

Исполнитель нужен, если вы хотите ограничить доступ worker к ресурсам проекта или дать ему
повторяемый набор инструментов в образе. Он работает только с `transport: external`; `in-process` даёт блокер.
Разрешение dispatch и native approval агента сохраняются. Контейнер не подтверждает действия
за человека, не включает auto-approve и не расширяет закреплённый план.

Харнесс не собирает, не скачивает и не публикует образы. Вы готовите их заранее; `dispatch propose`
закрепляет локальные image ID, запуск использует эти ID. После правки конфига или пересборки образа
нужны новые propose и approval: только так изменения попадут в dispatch.

## Требования к хосту {#host}

Нужны Linux, локальный движок, runtime store и работающий `harness-runtime serve`.
CLI `docker`/`podman` должен быть в `PATH` **процесса runtime**, а его пользователь — иметь
доступ к движку. Репозиторий и все ресурсы плана должны быть доступны по тем же абсолютным путям.

| Среда | Что проверено в репозитории |
| --- | --- |
| Rootful Docker на Linux | Живой CI smoke worker + QA. |
| Rootless Podman, Fedora, SELinux enforcing, cgroup v2 | Живой smoke на self-hosted runner; пользователю делегированы cpu, memory и pids. |
| Rootful Podman; rootless Docker; Docker с SELinux enforcing | Только argv-матрица и scripted engine. Живой smoke для этих сочетаний не подтверждён. |
| Remote Podman; Docker `userns-remap`; CLI-обёртка с несовпадающим `info` | Не поддержаны: preflight блокирует запуск. |
| Не Linux или файловый ledger | Контейнерный исполнитель блокируется. |

При переходе с файлового ledger сначала остановите его активную работу и согласуйте миграцию
с человеком. Текущий Rust CLI требует заполненные `--approved-by`, `--approved-at` и `--reason`;
одного `migrate --repo .` недостаточно. В Bash в корне целевого проекта:

```bash {.ah-code-wrap}
read -r -p 'Approved by (human): ' MIGRATION_APPROVER
read -r -p 'Approval time (RFC 3339): ' MIGRATION_APPROVED_AT
read -r -p 'Approved migration reason: ' MIGRATION_REASON
harness-runtime migrate --repo . \
  --approved-by "$MIGRATION_APPROVER" \
  --approved-at "$MIGRATION_APPROVED_AT" --reason "$MIGRATION_REASON"
```

Укажите реальное одобрение: время не в будущем, approver не `policy:`. Не запускайте миграцию,
пока работают владельцы ledger; следуйте remedy, который она печатает. Если runtime store уже используется,
повторная миграция для настройки контейнера не нужна.

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

`serve` остаётся запущенным. У него и coordinator должны совпадать пользователь, репозиторий и
IPC-каталог: на Unix абсолютный `XDG_RUNTIME_DIR` задаёт `$XDG_RUNTIME_DIR/harness`, иначе —
`/tmp/harness-<uid>`. Сервис получает собственные `PATH` и окружение; изменение переменной в другом
терминале их не меняет. Не запускайте второй runtime для того же репозитория.

## Сборка образов {#images}

Команды ниже собирают образы на выбранном движке. В целевом проекте с установленным
`backend-orchestration` исходники лежат в `.harness/container/`. В репозитории самого харнесса
они находятся в `harness/container/`: замените оба вхождения пути в каждой команде.

### База и proxy

Выберите **один** движок. Образы Docker и Podman находятся в разных хранилищах.

```bash {.ah-code-wrap}
docker build -f .harness/container/Dockerfile.sandbox \
  -t harness-sandbox:local .harness/container
docker build -f .harness/container/Dockerfile.proxy \
  -t harness-proxy:local .harness/container
```

```bash {.ah-code-wrap}
podman build -f .harness/container/Dockerfile.sandbox \
  -t harness-sandbox:local .harness/container
podman build -f .harness/container/Dockerfile.proxy \
  -t harness-proxy:local .harness/container
```

База содержит `git`, `curl`, `jq`, CA certificates, Python с `uv`, Node.js и npm.
В текущем Dockerfile закреплены Debian `trixie-20261020-slim` и `uv:0.12.21`.
Rust, gcc и CLI агента база не устанавливает.

### Проектный Dockerfile.worker

Следующий шаблон добавляет Rust из выбранного официального Rust-образа, gcc/libc6-dev и
Claude Code. `jq` и `uv` наследуются из базы. Сохраните его как `Dockerfile.worker` в проекте.
Все версии выберите явно: Rust-образ с тегом/digest, совместимые версии Debian-пакетов и CLI.
Для сборки runtime этого репозитория нужен Rust ≥ 1.89; другой проект задаёт свои требования.

```dockerfile {.ah-code-wrap}
ARG RUST_IMAGE
FROM ${RUST_IMAGE} AS rust_toolchain

FROM harness-sandbox:local
ARG GCC_PACKAGE_VERSION
ARG LIBC6_DEV_PACKAGE_VERSION
ARG CLAUDE_CODE_VERSION
RUN test -n "$GCC_PACKAGE_VERSION" \
    && test -n "$LIBC6_DEV_PACKAGE_VERSION" \
    && test -n "$CLAUDE_CODE_VERSION" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       "gcc=$GCC_PACKAGE_VERSION" "libc6-dev=$LIBC6_DEV_PACKAGE_VERSION" \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@anthropic-ai/claude-code@$CLAUDE_CODE_VERSION"
COPY --from=rust_toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust_toolchain /usr/local/rustup /usr/local/rustup
ENV PATH="/usr/local/cargo/bin:${PATH}" \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/harness-home/.cargo
```

Для образа Rust нужна структура официального образа (`/usr/local/cargo`, `/usr/local/rustup`)
и совместимая с базой Linux/ABI. `CARGO_HOME` указывает на временный HOME worker, а установленный
toolchain остаётся вне него. Проверьте образ под uid хоста: этот шаблон нужно собрать и проверить
вживую в вашей среде; это не готовый поставляемый образ.

```bash {.ah-code-wrap}
read -r -p 'Official Rust image, pinned tag/digest: ' WORKER_RUST_IMAGE
read -r -p 'Debian gcc package version: ' WORKER_GCC_VERSION
read -r -p 'Debian libc6-dev package version: ' WORKER_LIBC_VERSION
read -r -p 'Claude Code version: ' WORKER_CLAUDE_VERSION
docker build -f Dockerfile.worker -t harness-worker:local \
  --build-arg RUST_IMAGE="$WORKER_RUST_IMAGE" \
  --build-arg GCC_PACKAGE_VERSION="$WORKER_GCC_VERSION" \
  --build-arg LIBC6_DEV_PACKAGE_VERSION="$WORKER_LIBC_VERSION" \
  --build-arg CLAUDE_CODE_VERSION="$WORKER_CLAUDE_VERSION" .
```

Для Podman замените `docker build` на `podman build`, используя те же аргументы и его базовый
образ. Не передавайте токены через build-args. Выбранные версии должны существовать в реестрах;
значения здесь намеренно не подставлены за проект.

### Контракт worker-образа

- Нужны `/bin/sh`, интерпретатор shebang адаптера и все инструменты агента/QA. QA запускается
  как `/bin/sh -c '<команда>'`.
- Образ должен работать под произвольным uid: rootful использует uid:gid хоста; запись в
  `/etc/passwd` может отсутствовать. Режим пользователя выбирает runtime по движку.
- `HOME` — tmpfs `/harness-home`; файлы авторизации и инструменты в прежнем HOME образа
  worker не увидит. Устанавливайте инструменты вне домашнего каталога.
- Runtime задаёт entrypoint, пользователя и рабочий каталог. Не полагайтесь на свои
  `ENTRYPOINT`, `CMD` или `USER`; не объявляйте `VOLUME`: анонимные тома останутся после удаления.
- В образе не должно быть секретов. Runtime использует `--pull never`, `--cap-drop ALL` и
  `no-new-privileges`; сокет движка не монтируется.

## Поля конфигурации {#configuration}

Это фрагмент `.harness/orchestration.json` из руководства исполнителя. Подставьте выбранный
движок, нужные хосты и свой cache path. QA здесь получает доступ к Python registry и не получает
ключ модели. Настройки моделей и provider profiles остаются в существующих назначениях.

```json {.ah-code-wrap}
{
  "extensions": {
    "runtime_access": "docker"
  },
  "access_policy": {
    "defaults": {
      "mode": "sandbox",
      "container": {
        "engine": "docker",
        "worker_image": "harness-worker:local",
        "proxy_image": "harness-proxy:local"
      },
      "environment": [
        "ANTHROPIC_API_KEY"
      ],
      "network": {
        "hosts": [
          "api.anthropic.com",
          "github.com"
        ]
      }
    },
    "roles": {
      "code-review": {
        "network": {
          "hosts": [
            "api.anthropic.com"
          ]
        }
      }
    },
    "operations": {
      "qa": {
        "container": {
          "engine": "docker",
          "worker_image": "harness-worker:local",
          "proxy_image": "harness-proxy:local"
        },
        "environment": [],
        "network": {
          "hosts": [
            "pypi.org",
            "files.pythonhosted.org"
          ]
        },
        "filesystem": [
          {
            "resource": "cache",
            "path": "~/.cache/uv",
            "access": "write"
          }
        ]
      }
    }
  },
  "execution_policy": {
    "worker_execution_timeout_seconds": 14400,
    "qa_command_timeout_seconds": 3600,
    "stop_grace_seconds": 30
  }
}
```

| Поле | Что настроить |
| --- | --- |
| `extensions.runtime_access` | `docker` для обоих движков. При его выборе обязателен `access_policy.defaults.container`. |
| `access_policy.defaults.container.engine` | `docker` (default) или `podman`; имя extension остаётся `docker`. |
| `access_policy.defaults.container.worker_image` | Обязательная ссылка на существующий локальный worker-образ. |
| `access_policy.defaults.container.proxy_image` | Образ proxy обязателен исполнителю при непустом списке хостов; если задан, должен существовать локально. |
| `access_policy.defaults.mode` | Для этого исполнителя `sandbox` или `inherit`; допустимый схемой `unsandboxed` исполнитель отклоняет. |
| `access_policy.defaults.environment` | Уникальные имена переменных, никогда значения. Runtime должен иметь их в своём окружении. |
| `access_policy.defaults.network.hosts` | Точные DNS-имена без схемы URL, порта и wildcard; `[]` отключает сеть. |
| `access_policy.defaults.filesystem` | Ресурсы `checkout`, `git_common`, `shared_storage`, `cache`, с `read`/`write`. Поля элементов: `resource`, `access`, `path`, `variable`; `path` обязателен только для `cache` и запрещён для остальных ресурсов; необязательный `variable` допустим только у `cache`. |
| `access_policy.operations.qa.container` | Явно включите контейнер QA. Одного `defaults.container` недостаточно: без override QA остаётся на хосте. |
| `execution_policy.worker_execution_timeout_seconds` | Целое ≥ 1, default `14400`: срок worker. |
| `execution_policy.qa_command_timeout_seconds` | Целое ≥ 1, default `3600`: срок одной команды контейнерного QA. |
| `execution_policy.stop_grace_seconds` | Целое ≥ 1, default `30`: пауза перед принудительным завершением. |
| `assignment_plans.<ключ>.transport` | `external` для каждой отправляемой роли; default схемы — `in-process`, который здесь блокируется. Меняйте transport внутри существующего плана роли, сохраняя её runtimes/model. |

Override роли или операции заменяет **весь названный компонент**, например `container`,
`environment` или `network`. Операция QA берёт defaults и свой override, не настройки роли QA.
При смене Docker на Podman измените engine и в defaults, и во всех явных container overrides.
Не расширяйте права read-only ролей; полный справочник — [здесь](orchestration/access.md).

Кэши сохраняются только как ресурсы `cache` плана, монтируемые по тому же абсолютному пути.
Относительный путь считается от worktree dispatch, `~` раскрывается на хосте. Укажите инструменту
этот путь через его настройки/переменную по имени или через поле `variable` элемента `cache`:
исполнитель сам передаёт контейнеру `--env <variable>=<путь кэша>`, и окружение
`harness-runtime serve` настраивать не нужно. Имя не совпадает с именами из `environment` и с
именами, которые задаёт runtime (`HOME`, `TMPDIR`, `CARGO_TARGET_DIR`, имена прокси и другие).
Для кэша cargo в QA укажите в `operations.qa.filesystem` абсолютный путь
`.harness/.sandboxes/cache/cargo` основного checkout с `"variable": "CARGO_HOME"` и заранее
создайте каталог (`mkdir -p`). Каждый QA-прогон сам задаёт `CARGO_TARGET_DIR` внутри своего run
root: cargo-этапы одного прогона переиспользуют собранные зависимости, а каталог удаляется вместе с
прогоном. Пример и процедура измерения — в разделе «Caches» `harness/docs/container-executor.md`.
Контейнер не сохраняет свой HOME между запусками.
Хостовый `~/.gitconfig` не монтируется; Git identity задаётся в конфиге репозитория или через
разрешённые имена переменных. Worker получает artifacts на запись и shared storage на чтение;
runtime socket ему недоступен.

### Адаптер агента {#agent-adapter}

Используйте поставляемый адаптер Claude Code `.harness/adapters/claude_worker.py`. Coordinator
запускает `.py`-адаптер контейнерного плана через `python3` образа, а адаптер лежит в `.harness/`,
который контейнер видит по тому же пути. Под `HARNESS_EXECUTOR=docker` адаптер:

- запускает `claude -p <промпт>` на переднем плане с `--output-format stream-json --verbose`,
  поэтому хост читает событие `init` и шаги worker;
- передаёт `allowed_tools` brief с `--permission-mode dontAsk` и каталог входящих отчётов через
  `--add-dir`; read-only роль получает `Edit(//<report_staging_path>)` и может записать только
  свой отчёт;
- просит записать отчёт в `report_staging_path` и остановиться; `dispatch self-report`,
  `dispatch heartbeat` и `report submit` в контейнере не выполняются, их делает хост.

В образе worker нужны `python3`, `git` и `claude` в `PATH`. В неинтерактивном режиме действие вне
allowlist не получит подтверждения человека.

```bash {.ah-code-wrap}
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch '<approved-dispatch-id>' --adapter "$PWD/.harness/adapters/claude_worker.py"
```

Эта команда запускает worker; для проверки конфигурации ниже используйте preflight, а не send.
Собственный адаптер другого агента выполняет те же правила: печатает stream-json с событием
`init`, ставит промпт перед variadic-флагами, пишет отчёт в `report_staging_path`, не вызывает
команды coordinator и выходит с кодом агента.

Runtime заменяет значения переменных из `environment` (от 8 байт) на `[redacted:<имя>]` в логах
worker, потому что эти логи лежат в `.harness` и доступны на чтение другим контейнерным worker.
Управляемые hooks (`.claude/settings.local.json`, `.claude/hooks/`) не отслеживаются Git и не
попадают в issue worktree, поэтому в контейнере работают только hooks из отслеживаемых файлов.

## Сеть {#network}

При `network.hosts: []` worker получает `--network none`. Иначе runtime создаёт internal-сеть
и proxy sidecar; proxy — единственный выход наружу. Переменные `HTTP_PROXY`/`HTTPS_PROXY`
и их строчные варианты задаёт исполнитель, `NO_PROXY` содержит localhost, 127.0.0.1 и ::1.

- Разрешены HTTP и CONNECT, порты 80/443. SSH remote и другие протоколы через proxy не работают.
- Хост должен совпасть точно: регистр и конечная точка нормализуются, wildcard и автоматического
  допуска поддоменов нет. IP literal отклоняется даже при наличии в allowlist.
- DNS-ответы проверяются: loopback, link-local, unspecified и multicast запрещены. Это точный
  набор текущего фильтра; общего запрета всех private/RFC1918 адресов в нём нет.
- Инструмент, который игнорирует proxy-переменные, прямого egress не получает.

Для worker перечислите API выбранной модели и git-хостинг, только если он нужен заданию.
Для QA составьте отдельный список по registry проекта: Python часто требует `pypi.org` и
`files.pythonhosted.org`; Rust — хосты используемого crates.io/mirror и скачивания crate.
Точный список берите из manifest/настроек registry и отказов конкретного инструмента; два хоста
из примера не обещают доступ ко всем зависимостям.

| Симптом | Проверка и действие |
| --- | --- |
| `--network none` | Проверьте эффективный список хостов роли/операции; после одобренной смены плана нужен новый propose. |
| Proxy возвращает `403` | Сверьте точный hostname, порт и DNS-адреса; не добавляйте wildcard или весь интернет ради обхода. |
| Хост разрешён, но соединения нет | Проверьте proxy-переменные самого инструмента и доступность DNS/хоста. Проверки выполняйте в выбранном образе и плане. |

## Токен {#token}

Для Claude Code можно использовать `ANTHROPIC_API_KEY` или токен подписки, полученный через
`claude setup-token` и передаваемый как `CLAUDE_CODE_OAUTH_TOKEN`. Это разные варианты
[авторизации Claude Code](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token):
выберите один подходящий вашему аккаунту и версии CLI. `setup-token` выполняйте сами в личном
терминале: он выводит значение. В конфиге остаётся только имя выбранной переменной.

Пример для API-ключа в Bash, без значения в истории команды:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

Для OAuth используйте имя `CLAUDE_CODE_OAUTH_TOKEN` вместо `ANTHROPIC_API_KEY` и в ручном вводе,
и в `environment`. Не передавайте оба варианта вслепую. Если runtime уже работает, штатно
остановите его и перезапустите с новым окружением; у сервиса меняется окружение именно сервиса.
Значения движок берёт у runtime, а не у позднее запущенного coordinator.

Не включайте зарезервированные `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`,
`GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR` и, при сети, proxy-переменные в `environment`.
Не монтируйте auth-файлы агента. Если значение попало в лог/отчёт/Git, отзовите его, выпустите
новое и удалите доступные копии; удаление строки из текущего файла не очищает историю.
Подробнее — [«Секреты и токены»](secrets.md).

## Проверки и типичные ошибки {#checks}

Сначала выполните [canonical validation и health](orchestration/index.md#config-validation).
Для существующего batch проверьте доступ без запуска контейнера; подставьте реальный ID:

```bash {.ah-code-wrap}
python .harness/orchestration/coordinator.py --repo . dispatch preflight \
  --batch '<batch-id>' --role developer
```

Preflight перечисляет блокеры с remedy и читает engine info/image IDs. При работе не из корня
или с отдельным checkout проверьте параметры `--worktree` и `--candidate-commit` в `--help`.
Успех preflight не заменяет живой smoke и не отправляет worker.

| Ошибка или блокер | Причина → действие |
| --- | --- |
| `runtime_unavailable` | Runtime не отвечает → проверьте запущенный serve, репозиторий, пользователя и IPC-каталог. Не создавайте второй процесс вслепую. |
| `lease_held` | QA-lane/ledger ещё удерживает владелец → проверьте `ledger lock-status` и владельца; дождитесь освобождения. Не снимайте живой lease через force ради настройки. |
| Переменная отсутствует | Имя есть в плане, значения нет у runtime → задайте его приватно и перезапустите runtime. Не печатайте значение для проверки. |
| `approval_mismatch` | Изменился закреплённый образ/approval → восстановите image ID либо отмените dispatch и повторите propose с новым approval. |
| Образ/движок недоступен | Проверьте реальный CLI, его PATH/права и локальные образы у пользователя runtime. |
| Нет `external`, задан `unsandboxed` или нет proxy при непустой сети | Исправьте выбранный план по remedy; успешная JSON validation не доказывает готовность исполнителя. |
| Корень открывает socket/runtime или пересекается с `/harness-home` | Выберите отдельный разрешённый ресурс; engine socket и runtime-каталоги worker не получает. |

`dispatch status`/`dispatch wait` показывают то, что видит runtime. После выхода worker runtime
сохраняет потоки и exit code, удаляет worker, proxy и сеть; reconcile повторяет неполную очистку.
Посмотреть оставшиеся объекты и план очистки:

```bash {.ah-code-wrap}
harness cleanup .
```

Только после того, как просмотрите список на удаление, выполните `harness cleanup . --apply`.
Cleanup пропускает живые исполнения, не останавливает работающий worker и не удаляет volumes.
Конкретный worker останавливает `docker stop harness-<dispatch_id>` или эквивалент Podman.

Живые smoke **репозитория харнесса**, не произвольного целевого проекта, расположены в
`tests/orchestration/test_docker_smoke.py` и `test_podman_smoke.py`. CI собирает runtime и smoke-образы
и запускает выбранный маркер с `HARNESS_REQUIRE_RUNTIME=1` и соответствующим
`HARNESS_REQUIRE_DOCKER_SMOKE=1`/`HARNESS_REQUIRE_PODMAN_SMOKE=1`, чтобы skip не выдавался за успех.
Они запускают реальные контейнеры и используют сеть; обычный `make verify` их не включает.
Повторяйте процедуру из CI только на подготовленном хосте, а не как скрытую часть настройки.

После `make bootstrap`, сборки runtime и smoke-образов с тегами `harness-worker:smoke` и
`harness-proxy:smoke` из [Docker CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/verify.yml)
или [Podman CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/podman-smoke.yml)
выберите соответствующий прогон из корня исходников харнесса. Образы `:local` из настройки проекта
не заменяют теги `:smoke` автоматически.

```bash {.ah-code-wrap}
HARNESS_RUNTIME_BIN="$PWD/native/harness-runtime/target/debug/harness-runtime" \
HARNESS_REQUIRE_RUNTIME=1 HARNESS_REQUIRE_DOCKER_SMOKE=1 \
  .harness/.venv/bin/python -m pytest -m docker_smoke -v \
  tests/orchestration/test_docker_smoke.py
```

```bash {.ah-code-wrap}
HARNESS_RUNTIME_BIN="$PWD/native/harness-runtime/target/debug/harness-runtime" \
HARNESS_REQUIRE_RUNTIME=1 HARNESS_REQUIRE_PODMAN_SMOKE=1 \
  .harness/.venv/bin/python -m pytest -m podman_smoke -v \
  tests/orchestration/test_podman_smoke.py
```

## Особенности среды {#host-boundaries}

Если агент работает в distrobox/devcontainer, а движок — на хосте, сначала выясните, где запущен
**runtime**. Именно он вызывает CLI движка, читает имена переменных и передаёт абсолютные пути
mount. Если `docker` есть в среде агента, это ещё не значит, что runtime видит движок.

Проверьте пользователя и `PATH` runtime, его IPC-каталог, доступ к локальному движку, одинаковые
пути worktree/cache и видимость этих путей движку. Не передавайте engine socket worker ради
исправления путей. Если сопоставление среды не подтверждено, остановитесь на blocker; такая
комбинация не становится проверенной средой из таблицы только потому, что preflight читает JSON.

## Настройка с агентом {#agent-setup}

??? quote ah-skill-text "Промпт для агента: хост, образы и адаптер"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read the container guide. Establish Linux, local engine, runtime store, exact host paths and
    runtime user/PATH. Explain verified/unverified engine combinations. Ask which roles use external
    transport and whether QA needs its explicit container override. Inspect an existing adapter;
    choose image tools and pinned versions from evidence, never invented versions. Show Dockerfile,
    config and build commands for review; do not build/pull images or migrate state automatically.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: сеть контейнера"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Read effective access_policy defaults/role/operation components. Ask which model API, git and
    registry hosts are actually needed. Build and show the complete exact-host list with the user;
    no wildcard, IP literals or SSH. Explain HTTP(S) 80/443, proxy-only egress, empty-host network none
    and whole-component overrides. Do not broaden an approved plan; changes need new propose/approval.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: токен контейнера"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask only the credential variable NAME needed by the chosen adapter and which shell the user uses.
    Explain environment names versus values held by harness-runtime serve and reserved names.
    For Bash give private manual read -rs entry instructions with export; never execute the entry
    or collect its output. Ask the user to restart the existing runtime/service with that environment,
    not start a duplicate. Inspect preflight without reading or echoing credential values.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```

??? quote ah-skill-text "Промпт для агента: preflight и ошибки контейнера"

    ```text
    Follow repository instructions. Read current files before asking: project instructions,
    .harness/project.json, .harness/orchestration.json and installed schema/examples if present.
    Inspect git status and available read-only harness health diagnostics; distinguish missing,
    skipped and failed checks. Do not assume a new directory already has a harness installed.
    Keep questions, choices and user-facing summaries in Russian. Ask only unresolved questions,
    one at a time. Offer 2-4 concrete choices plus «Другое», one consequence per choice.
    Put an evidence-based recommendation first and mark it «Рекомендуется»; do not invent facts.
    Never request, read, print or store credential values or authentication-file contents.

    Ask for an existing suitable batch/worktree; inspect dispatch preflight --help before using it.
    Read-only preflight can inspect engine/image readiness without starting containers. Without a
    suitable batch report it unperformed. Explain runtime_unavailable, lease_held, missing variables
    and approval_mismatch with remedies. Never force-clear a live lease or reuse approval for new
    image IDs. Preview cleanup; deletion/live smokes/worker send require separate authorization.

    Before any durable change, show the exact proposed diff or command and its effects, then wait
    for approval of that phase. Edit configuration with Edit/Write and preserve unrelated settings.
    After approved changes, run harness health and, if orchestration is installed, config validate
    --canonical --json. Summarize results and unverified behavior. Do not create commits/PRs, change
    credentials/trust, migrate state or send workers without separate explicit authorization.
    ```
