# Контейнер

Встроенный исполнитель `docker` запускает утверждённого внешнего worker в отдельном контейнере
Docker или Podman. Контейнерный QA включается отдельно, и тогда каждая команда gate получает свой
контейнер. Здесь описана настройка по шагам, полный справочник полей находится на странице
[«Доступ и контейнер»](orchestration/access.md).

## Когда нужен и что меняет {#when-to-use}

Исполнитель нужен, если вы хотите ограничить доступ worker к ресурсам проекта или дать ему
повторяемый набор инструментов в образе. Он работает только с `transport: external`, с
`in-process` coordinator ставит блокер. Разрешение dispatch и native approval агента остаются в
силе. Контейнер не подтверждает действия за человека, не включает auto-approve и не расширяет
закреплённый план.

Harness не собирает, не скачивает и не публикует образы, их готовите вы. `dispatch propose`
закрепляет локальные image ID, и запуск использует именно их. Если вы правите конфиг или
пересобираете образ, нужны новые propose и approval: иначе изменения в dispatch не попадут.

## Требования к хосту {#host}

Нужны Linux, локальный движок, runtime store и запущенный `harness-runtime serve`.
CLI `docker` или `podman` должен быть в `PATH` **процесса runtime**, а у пользователя этого
процесса должен быть доступ к движку. Репозиторий и все ресурсы плана должны быть доступны по тем
же абсолютным путям.

| Среда | Что проверено в репозитории |
| --- | --- |
| Rootful Docker на Linux | Живой smoke в CI: worker и QA. |
| Rootless Podman, Fedora, SELinux enforcing, cgroup v2 | Живой smoke на self-hosted runner. Пользователю делегированы cpu, memory и pids. |
| Rootful Podman; rootless Docker; Docker с SELinux enforcing | Только argv-матрица и scripted engine. Живой smoke для этих сочетаний не подтверждён. |
| Remote Podman; Docker `userns-remap`; CLI-обёртка с несовпадающим `info` | Не поддержаны: preflight блокирует запуск. |
| Не Linux или файловый ledger | Контейнерный исполнитель блокируется. |

Если проект ещё на файловом ledger, сначала остановите активную работу с ним и согласуйте
миграцию с человеком. Rust CLI требует заполнить `--approved-by`, `--approved-at` и `--reason`,
одного `migrate --repo .` мало. В Bash в корне целевого проекта выполните:

```bash {.ah-code-wrap}
read -r -p 'Approved by (human): ' MIGRATION_APPROVER
read -r -p 'Approval time (RFC 3339): ' MIGRATION_APPROVED_AT
read -r -p 'Approved migration reason: ' MIGRATION_REASON
harness-runtime migrate --repo . \
  --approved-by "$MIGRATION_APPROVER" \
  --approved-at "$MIGRATION_APPROVED_AT" --reason "$MIGRATION_REASON"
```

Укажите настоящее одобрение: время не в будущем, approver не начинается с `policy:`. Не
запускайте миграцию, пока работают владельцы ledger, и выполняйте remedy, который она печатает.
Если проект уже работает с runtime store, для настройки контейнера повторная миграция не нужна.

```bash {.ah-code-wrap}
harness-runtime serve --repo .
```

`serve` должен работать всё время. У него и coordinator должны совпадать пользователь,
репозиторий и IPC-каталог. На Unix абсолютный `XDG_RUNTIME_DIR` задаёт каталог
`$XDG_RUNTIME_DIR/harness`, без него runtime берёт `/tmp/harness-<uid>`. У сервиса свои `PATH` и
окружение, и переменная, изменённая в другом терминале, на них не влияет. Не запускайте второй
runtime для того же репозитория.

## Сборка образов {#images}

Команды ниже собирают образы на выбранном движке. В целевом проекте с установленной
`backend-orchestration` исходники образов лежат в `.harness/container/`. В репозитории самого
harness они лежат в `harness/container/`: замените в каждой команде оба вхождения пути.

### База и proxy

Выберите **один** движок: Docker и Podman хранят образы раздельно.

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

В базовом образе есть `git`, `curl`, `jq`, CA certificates, Python с `uv`, Node.js и npm.
Текущий Dockerfile закрепляет Debian `trixie-20261020-slim` и `uv:0.12.21`.
Rust, gcc и CLI агента база не устанавливает.

### Проектный Dockerfile.worker

Шаблон ниже добавляет Rust из выбранного официального Rust-образа, gcc, libc6-dev и Claude Code.
`jq` и `uv` приходят из базы. Сохраните шаблон в проекте как `Dockerfile.worker`. Все версии
выберите явно: Rust-образ с тегом или digest, совместимые версии Debian-пакетов и CLI. Для сборки
runtime этого репозитория нужен Rust 1.89 или новее, у другого проекта свои требования.

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

Rust-образ должен иметь структуру официального образа (`/usr/local/cargo`, `/usr/local/rustup`)
и совместимые с базой Linux и ABI. `CARGO_HOME` указывает на временный HOME worker, а установленный
toolchain лежит вне его. Harness не поставляет готовый worker-образ: соберите шаблон и проверьте
образ вживую в своей среде под uid хоста.

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

Для Podman замените `docker build` на `podman build` с теми же аргументами и базовым образом,
собранным в Podman. Не передавайте токены через build-args. Выбранные версии должны существовать
в реестрах. Значения здесь не подставлены намеренно: их выбирает проект.

### Контракт worker-образа

- Нужны `/bin/sh`, интерпретатор из shebang адаптера и все инструменты агента и QA. QA
  запускается как `/bin/sh -c '<команда>'`.
- Образ должен работать под произвольным uid. Rootful-движок запускает контейнер с uid:gid хоста,
  и записи в `/etc/passwd` для него может не быть. Режим пользователя runtime выбирает по движку.
- `HOME` лежит в tmpfs `/harness-home`. Файлы авторизации и инструменты из прежнего HOME образа
  worker не увидит, поэтому ставьте инструменты вне домашнего каталога.
- Runtime сам задаёт entrypoint, пользователя и рабочий каталог. Не полагайтесь на свои
  `ENTRYPOINT`, `CMD` или `USER`. Не объявляйте `VOLUME`: анонимные тома останутся после удаления
  контейнера.
- В образе не должно быть секретов. Runtime запускает контейнер с `--pull never`, `--cap-drop ALL`
  и `no-new-privileges`, сокет движка не монтирует.

## Поля конфигурации {#configuration}

Ниже фрагмент `.harness/orchestration.json` из руководства исполнителя. Подставьте выбранный
движок, нужные хосты и свой путь кэша. QA в этом примере получает доступ к Python registry, но не
получает ключ модели. Модели и provider profiles настраиваются в существующих назначениях.

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
| `extensions.runtime_access` | `docker` для обоих движков. Если выбран `docker`, обязателен `access_policy.defaults.container`. |
| `access_policy.defaults.container.engine` | `docker` (по умолчанию) или `podman`. Extension в обоих случаях называется `docker`. |
| `access_policy.defaults.container.worker_image` | Обязательная ссылка на существующий локальный worker-образ. |
| `access_policy.defaults.container.proxy_image` | Образ proxy. Исполнителю он нужен, если список хостов не пуст. Заданный образ должен существовать локально. |
| `access_policy.defaults.mode` | Для этого исполнителя `sandbox` или `inherit`. Схема допускает и `unsandboxed`, но исполнитель его отклоняет. |
| `access_policy.defaults.environment` | Уникальные имена переменных, без значений. Эти переменные должны быть в окружении runtime. |
| `access_policy.defaults.network.hosts` | Точные DNS-имена без схемы URL, порта и wildcard. `[]` отключает сеть. |
| `access_policy.defaults.filesystem` | Ресурсы `checkout`, `git_common`, `shared_storage`, `cache` с доступом `read` или `write`. Поля элементов: `resource`, `access`, `path`, `variable`. `path` обязателен для `cache` и запрещён для остальных ресурсов. Необязательный `variable` допустим только у `cache`. |
| `access_policy.operations.qa.container` | Включает контейнер для QA. Одного `defaults.container` мало: без этого override QA работает на хосте. |
| `execution_policy.worker_execution_timeout_seconds` | Целое число от 1, по умолчанию `14400`: сколько секунд может работать worker. |
| `execution_policy.qa_command_timeout_seconds` | Целое число от 1, по умолчанию `3600`: сколько секунд может идти одна команда контейнерного QA. |
| `execution_policy.stop_grace_seconds` | Целое число от 1, по умолчанию `30`: пауза в секундах перед принудительным завершением. |
| `assignment_plans.<ключ>.transport` | `external` для каждой роли, которую отправляют в контейнер. По умолчанию схема ставит `in-process`, а он здесь блокируется. Меняйте transport в существующем плане роли и сохраняйте её runtimes и model. |

Override роли или операции заменяет **весь названный компонент**, например `container`,
`environment` или `network`. Операция QA берёт defaults и свой override, а настройки роли QA не
берёт. Если меняете Docker на Podman, измените engine и в defaults, и во всех явных container
overrides. Не расширяйте права read-only ролей. Полный справочник на странице
[«Доступ и контейнер»](orchestration/access.md).

Кэш между запусками сохраняется только в ресурсах `cache` плана, которые монтируются по тому же
абсолютному пути. Относительный путь считается от worktree dispatch, `~` раскрывается на хосте.
Сообщите инструменту этот путь через его настройки или переменную. Можно задать имя переменной в
поле `variable` элемента `cache`: тогда исполнитель сам передаст контейнеру
`--env <variable>=<путь кэша>`, и окружение `harness-runtime serve` настраивать не нужно. Это имя
не должно совпадать с именами из `environment` и с именами, которые задаёт runtime (`HOME`,
`TMPDIR`, `CARGO_TARGET_DIR`, имена прокси и другие). Для кэша cargo в QA укажите в
`operations.qa.filesystem` абсолютный путь `.harness/.sandboxes/cache/cargo` основного checkout с
`"variable": "CARGO_HOME"` и заранее создайте каталог (`mkdir -p`). Каждый QA-прогон сам задаёт
`CARGO_TARGET_DIR` внутри своего run root. Поэтому cargo-этапы одного прогона используют уже
собранные зависимости, а каталог удаляется вместе с прогоном. Пример и способ замера описаны в
разделе «Caches» файла `harness/docs/container-executor.md`.
Контейнер не сохраняет свой HOME между запусками.
Хостовый `~/.gitconfig` не монтируется. Git identity задаётся в конфиге репозитория или через
разрешённые имена переменных. Worker получает artifacts на запись и shared storage на чтение,
к runtime socket у него доступа нет.

### Адаптер агента {#agent-adapter}

Используйте поставляемый адаптер Claude Code `.harness/adapters/claude_worker.py`. Coordinator
запускает `.py`-адаптер контейнерного плана через `python3` из образа. Адаптер лежит в `.harness/`,
а этот каталог контейнер видит по тому же пути. При `HARNESS_EXECUTOR=docker` адаптер:

- запускает `claude -p <промпт>` на переднем плане с `--output-format stream-json --verbose`,
  чтобы хост читал событие `init` и шаги worker;
- передаёт `allowed_tools` из brief с `--permission-mode dontAsk`, а каталог входящих отчётов
  через `--add-dir`. Read-only роль получает `Edit(//<report_staging_path>)` и может записать
  только свой отчёт;
- просит worker записать отчёт в `report_staging_path` и остановиться. `dispatch self-report`,
  `dispatch heartbeat` и `report submit` в контейнере не выполняются, их делает хост.

В образе worker нужны `python3`, `git` и `claude` в `PATH`. В неинтерактивном режиме человек не
сможет подтвердить действие вне allowlist, и оно не выполнится.

```bash {.ah-code-wrap}
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch '<approved-dispatch-id>' --adapter "$PWD/.harness/adapters/claude_worker.py"
```

Эта команда запускает worker. Чтобы только проверить конфигурацию, используйте preflight (ниже),
а не send. Собственный адаптер другого агента должен соблюдать те же правила: печатать stream-json
с событием `init`, ставить промпт перед variadic-флагами, писать отчёт в `report_staging_path`, не
вызывать команды coordinator и выходить с кодом агента.

В логах worker runtime заменяет значения переменных из `environment` длиной от 8 байт на
`[redacted:<имя>]`. Причина в том, что логи лежат в `.harness` и их могут читать другие
контейнерные worker. Управляемые hooks (`.claude/settings.local.json`, `.claude/hooks/`) Git не
отслеживает, и в issue worktree они не попадают. Поэтому в контейнере работают только hooks из
отслеживаемых файлов.

## Сеть {#network}

При `network.hosts: []` worker получает `--network none`. Иначе runtime создаёт internal-сеть и
proxy sidecar, и наружу можно выйти только через proxy. Переменные `HTTP_PROXY`, `HTTPS_PROXY` и
их варианты в нижнем регистре задаёт исполнитель, `NO_PROXY` содержит localhost, 127.0.0.1 и ::1.

- Разрешены HTTP и CONNECT на портах 80 и 443. SSH remote и другие протоколы через proxy не
  работают.
- Хост должен совпасть точно. Регистр и точка в конце имени нормализуются, wildcard нет, поддомены
  автоматически не разрешаются. IP literal proxy отклоняет, даже если он есть в allowlist.
- Proxy проверяет DNS-ответы и запрещает адреса loopback, link-local, unspecified и multicast.
  Это полный список текущего фильтра: все private-адреса (RFC 1918) он не запрещает.
- Инструмент, который не читает proxy-переменные, напрямую в сеть не выйдет.

Для worker перечислите API выбранной модели, а git-хостинг только если он нужен заданию.
Для QA составьте отдельный список по registry проекта. Python часто требует `pypi.org` и
`files.pythonhosted.org`, Rust требует хосты crates.io или зеркала и хост скачивания crate.
Точный список берите из manifest, настроек registry и отказов конкретного инструмента. Двух хостов
из примера может не хватить для всех зависимостей.

| Симптом | Проверка и действие |
| --- | --- |
| `--network none` | Проверьте итоговый список хостов роли или операции. Если смену плана одобрили, нужен новый propose. |
| Proxy возвращает `403` | Сверьте точный hostname, порт и DNS-адреса. Не добавляйте wildcard и не открывайте весь интернет, чтобы обойти отказ. |
| Хост разрешён, но соединения нет | Проверьте proxy-переменные самого инструмента и доступность DNS и хоста. Проверяйте в выбранном образе и плане. |

## Токен {#token}

Claude Code принимает `ANTHROPIC_API_KEY` или токен подписки из `claude setup-token`, который
передают как `CLAUDE_CODE_OAUTH_TOKEN`. Это разные способы
[авторизации Claude Code](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token):
выберите один, подходящий вашему аккаунту и версии CLI. `setup-token` выполняйте сами в личном
терминале, потому что он печатает значение. В конфиг записывается только имя выбранной переменной.

Пример для API-ключа в Bash, значение не попадает в историю команд:

```bash {.ah-code-wrap}
read -rs -p 'ANTHROPIC_API_KEY: ' ANTHROPIC_API_KEY
printf '\n'
export ANTHROPIC_API_KEY
harness-runtime serve --repo .
```

Для OAuth используйте имя `CLAUDE_CODE_OAUTH_TOKEN` вместо `ANTHROPIC_API_KEY` и при вводе, и в
`environment`. Не передавайте оба варианта на всякий случай. Если runtime уже работает,
остановите его обычным способом и запустите с новым окружением. Если runtime работает как
сервис, меняйте окружение сервиса. Движок берёт значения у runtime, а не у coordinator, который
вы запускаете позже.

Не добавляйте в `environment` зарезервированные `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`,
`GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`, а если сеть включена, ещё и proxy-переменные.
Не монтируйте auth-файлы агента. Если значение попало в лог, отчёт или Git, отзовите его,
выпустите новое и удалите копии, до которых можете дотянуться. Удаление строки из текущего файла
историю не очищает. Подробнее на странице [«Секреты и токены»](secrets.md).

## Проверки и типичные ошибки {#checks}

Сначала выполните [canonical validation и health](orchestration/index.md#config-validation).
Затем для существующего batch проверьте доступ, не запуская контейнер. Подставьте реальный ID:

```bash {.ah-code-wrap}
python .harness/orchestration/coordinator.py --repo . dispatch preflight \
  --batch '<batch-id>' --role developer
```

Preflight перечисляет блокеры с remedy и читает info движка и image ID. Если вы работаете не из
корня или с отдельным checkout, посмотрите параметры `--worktree` и `--candidate-commit` в `--help`.
Успешный preflight не заменяет живой smoke и не отправляет worker.

| Ошибка или блокер | Причина → действие |
| --- | --- |
| `runtime_unavailable` | Runtime не отвечает → проверьте, что serve запущен, и сверьте репозиторий, пользователя и IPC-каталог. Не запускайте второй процесс наугад. |
| `lease_held` | QA lane или ledger ещё удерживает владелец → проверьте `ledger lock-status` и владельца, дождитесь освобождения. Не снимайте живой lease через force ради настройки. |
| Переменная отсутствует | Имя есть в плане, значения нет у runtime → задайте его приватно и перезапустите runtime. Не печатайте значение для проверки. |
| `approval_mismatch` | Изменился закреплённый образ или approval → верните прежний image ID или отмените dispatch и повторите propose с новым approval. |
| Образ или движок недоступен | Проверьте у пользователя runtime реальный CLI, его PATH и права, а также локальные образы. |
| Нет `external`, задан `unsandboxed` или сеть не пуста, а proxy нет | Исправьте выбранный план по remedy. Успешная проверка JSON не значит, что исполнитель готов. |
| Корень ресурса открывает socket или каталог runtime либо пересекается с `/harness-home` | Выберите отдельный разрешённый ресурс. Сокет движка и каталоги runtime worker не получает. |

`dispatch status` и `dispatch wait` показывают то, что видит runtime. Когда worker завершается,
runtime сохраняет потоки вывода и exit code, удаляет worker, proxy и сеть. Если очистка не
закончилась, reconcile повторяет её. Оставшиеся объекты и план очистки показывает команда:

```bash {.ah-code-wrap}
harness cleanup .
```

Выполняйте `harness cleanup . --apply` только после того, как просмотрели список на удаление.
Cleanup пропускает живые исполнения, не останавливает работающий worker и не удаляет volumes.
Конкретный worker останавливает `docker stop harness-<dispatch_id>` или та же команда Podman.

Живые smoke относятся к **репозиторию harness**, а не к целевому проекту. Они лежат в
`tests/orchestration/test_docker_smoke.py` и `test_podman_smoke.py`. CI собирает runtime и
smoke-образы и запускает выбранный маркер с `HARNESS_REQUIRE_RUNTIME=1` и нужным
`HARNESS_REQUIRE_DOCKER_SMOKE=1` или `HARNESS_REQUIRE_PODMAN_SMOKE=1`, чтобы пропущенный тест не
сошёл за успешный. Smoke запускают реальные контейнеры и ходят в сеть, обычный `make verify` их не
включает. Повторяйте процедуру из CI только на подготовленном хосте и только как отдельный шаг,
а не незаметно в ходе настройки.

Выполните `make bootstrap`, соберите runtime и smoke-образы с тегами `harness-worker:smoke` и
`harness-proxy:smoke` по [Docker CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/verify.yml)
или [Podman CI](https://github.com/PVMalove/agent-harness-next/blob/master/.github/workflows/podman-smoke.yml).
Затем запустите нужный прогон из корня исходников harness. Образы `:local` из настройки проекта
теги `:smoke` автоматически не заменяют.

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

Если агент работает в distrobox или devcontainer, а движок на хосте, сначала выясните, где
запущен **runtime**. Именно он вызывает CLI движка, читает переменные по именам и передаёт
абсолютные пути mount. Если `docker` есть в среде агента, runtime всё равно может не видеть движок.

Проверьте пользователя и `PATH` runtime, его IPC-каталог, доступ к локальному движку, совпадение
путей worktree и кэша и то, что движок видит эти пути. Не отдавайте worker сокет движка, чтобы
исправить пути. Если соответствие сред не подтверждено, остановитесь на blocker. То, что preflight
читает JSON, не делает такую комбинацию проверенной средой из таблицы выше.

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
