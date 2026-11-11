# Доступ и контейнер

План доступа описывает разрешения worker. Применяет их runtime или исполнитель, который подтвердил поддержку плана. Сначала настрой среду, затем согласуй dispatch.

[Обзор оркестрации](../../backend-orchestration.md)

## Доступ ролей: `access_policy` и `runtime_access` {#access_policy-runtime_access}

Необязательный раздел `access_policy` задаёт режим sandbox и границы сети и файловой системы для
worker. Без него brief сохраняет `inherit`, а `dispatch send` ведёт себя как раньше. Раздел не
требует `assignment_plans`: coordinator читает `access_policy` и в конфиге, где есть только он.

```json
"access_policy": {
  "defaults": {"mode": "sandbox",
               "network": {"hosts": ["github.com"]},
               "filesystem": [{"resource": "checkout", "access": "write"},
                              {"resource": "git_common", "access": "write"},
                              {"resource": "cache", "access": "write", "path": "~/.cache/uv"}]},
  "roles": {"code-review": {"filesystem": [{"resource": "checkout", "access": "read"}]}},
  "operations": {"qa": {"network": {"hosts": []}}}
},
"extensions": {"runtime_access": "my_runtime:factory"}
```

- Компоненты `mode` (`inherit`, `sandbox`, `unsandboxed`), `network.hosts` и `filesystem`
  выбираются независимо от транспорта роли: `in-process` или `external`. Компонент `container`
  называет образы встроенного исполнителя `docker`, а `environment` — имена переменных окружения
  для его worker-а (см. ниже). План без этих компонентов сохраняет прежнюю форму и прежний digest.
- Override роли (`roles`) или операции (`operations`: `qa`, `git`, `publish`) заменяет только те
  компоненты, которые в нём указаны, а остальные берутся из `defaults`. Операции `qa`, `git` и
  `publish` выполняет сам coordinator, а не worker, поэтому к ним применяются только `defaults` и
  собственный override операции, а `roles` — никогда. Операцию выбирает сама команда: `publish` для
  `--purpose publish`, `qa` для роли `qa` и `integration local-qa`, `git` для `integration refresh`
  и `integration resolve`. Что именно проверяется, описывает раздел «Доступ QA, Git и publish» ниже.
- `filesystem` называет ресурс: `checkout`, `git_common`, `shared_storage` или `cache` (только `cache`
  требует `path`). Coordinator превращает их в реальные пути worktree, общего Git-каталога и
  хранилища. Корень диска и домашний каталог целиком отклоняются.
- Права на запись не расширяют `write_paths` brief, tool policy и нативные подтверждения, а
  read-only роль не получает запись в `checkout`, `git_common` и `shared_storage`.
- Coordinator записывает разрешённый план (`runtime_access`) в brief, и его sha256 входит в
  transition digest утверждения. Правка конфига после `dispatch propose` не расширяет
  утверждённый dispatch: новый доступ требует нового `propose` и нового approval. Briefs без этого
  поля остаются валидными и читаются как `inherit`.
- `dispatch preflight` показывает разрешённый план и сверку с `runtime_access`. Настройки пользователя
  и аттестация Git-checkout не считаются доказательством текущих прав сети и файловой системы.
- Расширение `runtime_access` — это нативная реализация, которая наблюдает окружение именно этого
  worker, применяет план и выполняет handoff (`observe`, `apply`, `handoff`). Значение `none` ничего
  не доказывает, поэтому без нативной реализации coordinator блокирует `dispatch send` для плана с
  `sandbox`, `unsandboxed`, хостами или путями. Блокировка наступает до передачи работы: тихой
  подмены и отката на `inherit` нет, а нативное подтверждение ничем не заменяется. Харнесс
  поставляет одну реализацию — встроенный контейнерный исполнитель `docker` (следующий раздел).
  Любую другую среду подключает модуль вашего проекта, как `my_runtime:factory` в примере выше. Пока
  проект не выбрал реализацию, любой `access_policy`, даже `mode: inherit`, блокирует
  `dispatch send`. `dispatch status` сохраняет статус и доказательство worker (`runtime_access`).

Если `dispatch send` остановлен, ошибка называет причину. Реализация, которая сама называет свой
блокер (так делает `docker`), передаёт и собственный remedy, а `dispatch preflight` показывает её
наблюдения в `runtime_access.verification.environment`. Иначе remedy общий: подготовить указанные
хосты, пути и режим в новой сессии runtime; подключить реализацию `runtime_access`, которая
проверяет реальный запуск worker; повторить `dispatch preflight`.

## Встроенный контейнерный исполнитель `docker` {#docker}

Значение `extensions.runtime_access: "docker"` выбирает исполнитель из поставки харнесса:
`harness-runtime` запускает каждый утверждённый external dispatch в отдельном контейнере Docker или
Podman, а при заданном `access_policy.operations.qa.container` — и каждую команду QA. Контракт
исполнителя описывают ADR 0025 и ADR 0022 (разделы «Решения реализации»); этот раздел
описывает поставленное поведение. Пошаговую настройку целевого проекта — предпосылки, сборку
образов, кэши, allowlist, блокеры, очистку и пример проектного адаптера — даёт англоязычное
руководство [`harness/docs/container-executor.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/docs/container-executor.md), которое
`backend-orchestration` ставит как `.harness/docs/container-executor.md`. Проектные реализации
`module:factory` работают, как раньше, а хост-процесс не может зарегистрировать другую реализацию
под именем `docker`.

```json
"access_policy": {
  "defaults": {
    "mode": "sandbox",
    "container": {"worker_image": "harness-worker:local", "proxy_image": "harness-proxy:local"},
    "environment": ["LLM_API_KEY"],
    "network": {"hosts": ["llm-api.example.com"]}
  },
  "roles": {"developer": {"container": {"worker_image": "harness-worker:dev",
                                        "proxy_image": "harness-proxy:local"}}},
  "operations": {"qa": {"container": {"worker_image": "harness-worker:local"},
                        "network": {"hosts": []}}}
},
"extensions": {"runtime_access": "docker"}
```

- Компонент `container` содержит `worker_image` (обязателен), необязательный `proxy_image` и
  необязательный `engine` (`docker` по умолчанию или `podman`). Тег — одна ссылка на образ без
  пробелов и без ведущего `-`. Override роли или операции заменяет компонент целиком. Resolver
  берёт теги только из конфига и не опрашивает движок, сеть и образы. `harness health` и схема
  требуют `access_policy.defaults.container`, если выбран `docker`: без него роль осталась бы без
  образа.
- Компонент `environment` — список уникальных имён переменных окружения (`[A-Za-z_][A-Za-z0-9_]*`),
  никогда не значений. Override роли или операции заменяет список целиком. План хранит имена в
  отсортированном виде, поэтому они входят в `plan_digest` и закрепляются в brief при approval:
  имя, добавленное в конфиг после `dispatch propose`, этот dispatch не получает. Значения движок
  берёт из окружения `harness-runtime serve`, поэтому после их смены runtime нужно перезапустить.
  Значения не попадают в конфиг, brief, digest, argv, evidence, логи, тексты ошибок и слои образа.
  Auth-файлы агента не монтируются.
- Каждая роль, которую отправляет `dispatch send`, должна иметь `transport: external` в
  `assignment_plans`. Исполнитель оборачивает команду external-адаптера и не знает конкретного
  агента.
- Исполнитель работает только в эпохе runtime store и только на Linux: на файловом ledger и вне
  Linux `dispatch preflight` блокирует его с remedy (`harness-runtime migrate`, затем
  `harness-runtime serve`).
- `dispatch preflight` спрашивает runtime (`container.observe`), а runtime опрашивает движок только
  на чтение: `<engine> info` определяет режим (`rootful`, `rootless`, `unknown` или `unavailable`),
  SELinux и ID демона, а `<engine> image inspect` находит локальный id каждого образа. При успехе
  evidence содержит движок, режим и id образов. Явный блокер с собственным remedy дают: недоступный
  движок, движок, чей режим нельзя определить по `info` (например, docker-совместимая обёртка
  другого движка), удалённый Podman, Docker с userns-remap, отсутствующий образ, транспорт
  `in-process`, режим `unsandboxed`, непустой `network.hosts` без `proxy_image`, корень плана,
  который открывает сокет движка или каталог runtime, содержит запятую, кавычку или перевод строки
  либо пересекается с `/harness-home`, отсутствующая в окружении `harness-runtime serve` переменная
  из `environment` и имя, которое исполнитель задаёт сам (`HOME`, `GIT_CONFIG_COUNT`,
  `GIT_CONFIG_KEY_0`, `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`, а при непустом `network.hosts` ещё
  `HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY` и их варианты в нижнем регистре). Блокер называет только
  имена переменных. Preflight перечисляет все блокеры сразу, и ни один из них не создаёт контейнер.
  Runtime проверяет переменные ещё раз перед запуском: пропавшая после approval переменная отклоняет
  send, а dispatch остаётся `approved`.
- Харнесс образы не собирает, не скачивает и не публикует. Payload `.harness/container/` содержит
  необязательный базовый образ worker-а `Dockerfile.sandbox` (Debian slim с `git`, `curl`, `jq`,
  Python с `uv` и Node.js), `Dockerfile.proxy` и код egress-proxy. Команды `docker build` и
  `podman build` для обоих образов даёт руководство; отсутствующий образ соберите или скачайте
  сами, затем повторите `dispatch preflight` и `dispatch propose`.
- `dispatch propose` опрашивает движок и закрепляет id образов в поле brief `runtime_images`
  (`{"worker": "sha256:…", "proxy": "sha256:…" | null}`) рядом с планом. Его sha256 входит в
  transition digest (`runtime_images_sha256`), но не в `plan_digest`: план остаётся функцией
  конфига, а образ под тем же тегом может измениться. `dispatch create` опрашивает движок ещё раз,
  поэтому образ, пересобранный после `propose`, меняет digest, и explicit approval со старым digest
  отклоняется. Поле есть у brief, который отправляет `dispatch send`, и у brief контейнерного QA;
  publish и хост-QA его не получают. Brief без поля остаётся валидным.
- `dispatch send` запускает только закреплённые id. Если образ пропал или изменился после
  `propose`, runtime отклоняет запуск с `approval_mismatch`, а dispatch остаётся `approved`.
  Remedy — вернуть образ с закреплённым id либо пересобрать или скачать образ, отменить dispatch
  (`dispatch cancel`) и повторить `dispatch propose`: approval для другого образа не
  переиспользуется.
- `dispatch send` передаёт supervised docker-dispatch в `execution.launch` runtime; Python argv
  движка не строит. Runtime создаёт сеть `--internal` и sidecar-proxy (если `network.hosts` не
  пуст), затем worker `harness-<dispatch_id>` командой `<engine> create --pull never` и запускает
  его `<engine> start` без ожидания (detached). Worker получает `--network none` или внутреннюю сеть
  dispatch, пользователя хоста (rootful — `--user <uid>:<gid>`, rootless Podman —
  `--userns=keep-id`, rootless Docker — `--user 0:0`; при SELinux ещё `label=disable`),
  `--cap-drop ALL`, `no-new-privileges`, HOME на tmpfs `/harness-home`, `safe.directory=*` через
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` и маркер `HARNESS_EXECUTOR=docker`.
  Каждое имя из `environment` закреплённого плана передаётся как `--env NAME` без значения. Каждый
  корень плана монтируется по тому же абсолютному пути: `read` — read-only, `write` — read-write;
  других монтирований нет. Метки `harness.dispatch`, `harness.repository`, `harness.plan_digest`,
  `harness.operation` и `harness.execution` связывают объекты с dispatch и исполнением. Квитанция
  `dispatch send` (поле `execution`) называет движок и id контейнера.
- При непустом `network.hosts` worker выходит наружу только через sidecar из закреплённого
  proxy-образа: переменные `HTTP_PROXY` и `HTTPS_PROXY` (и в нижнем регистре) указывают на него, а
  `NO_PROXY` оставляет только loopback. Прокси пропускает HTTP и `CONNECT` к точно совпадающему
  хосту плана на портах 80 и 443, отказывает IP-литералам и именам с loopback, link-local,
  unspecified или multicast адресом и отвечает `403` на всё остальное. Хост API модели нужно
  перечислить явно; ssh-remote Git через прокси не работает.
- Неудачный staged launch — at-most-once: runtime откатывает созданные объекты от новых к старым,
  исполнение становится `lost`, операция — `failed`, dispatch — `blocked`, и повторного запуска нет.
- Адаптер должен лежать внутри монтирований плана и запускаться в образе: `--entrypoint` получает
  путь адаптера. Для `.py`-адаптера coordinator передаёт интерпретатор хоста, которого в образе
  обычно нет, поэтому нужен исполняемый адаптер. Флаги агента для запуска в контейнере проектный
  адаптер выставляет по маркеру `HARNESS_EXECUTOR`.

Ограничения: worker-роль видит `shared_storage` только для чтения, а в хранилище пишет только в
`.sandboxes/scratch`, и сокет runtime в контейнер не монтируется. Поэтому команды coordinator,
которые меняют ledger (`dispatch self-report`, `dispatch heartbeat`, `report submit`), из
контейнера не выполняются: worker кладёт отчёт в `report_staging_path`, а после его выхода отчёт
записывают на хосте командой `report submit --file <путь>`. Отдельный `--checkout` роли
`code-review` в контейнер не монтируется: монтируются только корни плана. Настоящий smoke в CI (job
`docker-smoke`) проверяет только rootful Docker; Podman (rootful и rootless), rootless Docker и
хосты с SELinux подтверждены лишь argv-матрицей и scripted-движком и на живом движке не проверены.

Контейнерный QA включается только заданным `access_policy.operations.qa.container`: тогда каждая
команда QA — отдельный foreground-контейнер `--rm --init` из образа, закреплённого в brief
QA-dispatch, а sidecar и сеть живут весь QA run. Монтирование сужено: каталог clean-room на запись,
`git_common` только на чтение и `cache` плана. Exit code команды попадает в её stage evidence, а
окончание классифицирует ADR 0022 (раздел «Решения реализации»). Без
`operations.qa.container` QA остаётся на хосте, а операции `git` и `publish` всегда выполняет
coordinator в своём окружении (раздел «Доступ QA, Git и publish» ниже).

## Статус и очистка контейнерного worker {#worker}

Исполнение контейнерного worker-а наблюдает `harness-runtime`, а не coordinator. Reconcile runtime
при старте, перед каждой операцией над исполнением и раз в `dispatch_poll_interval_seconds`
сверяет контейнер с его метками: живой объект — `running`, выход с кодом — `exited`, доказанное
отсутствие — `lost`, отсутствие ответа — `unknown`. `dispatch status` и `dispatch wait`
показывают это исполнение из runtime и движок сами не спрашивают.

Когда worker завершается, runtime сохраняет его потоки (`executions/<id>/stdout.log` и
`stderr.log`), записывает код выхода в исполнение и удаляет worker, sidecar и сеть в таком
порядке; незавершённое удаление повторяет reconcile. По сроку `worker_execution_timeout_seconds`
runtime останавливает контейнер (`stop --time <stop_grace_seconds>`, затем `kill`) и записывает
`stopped_by: "deadline"`. Работающий worker без явной команды не останавливается: остановить его
можно командой движка (`docker stop harness-<dispatch_id>`). Контейнер не пишет в ledger, поэтому
обычно завершается раньше, чем отчёт записан: подготовленный отчёт лежит в `report_staging_path`,
и его записывают командой `report submit --file <путь>`.

`harness cleanup <repo>` перечисляет оставшиеся контейнеры и сети этого репозитория через runtime
(`container.objects`: runtime фильтрует их по собственной метке `harness.repository` и знает
состояние исполнения каждого объекта) и удаляет их через `container.remove` движками из
`access_policy`. Команда работает по общим правилам: предпросмотр без `--apply`, `--apply`
применяет свежий план и отказывает, если план изменился. Раздел выполняется только когда
`.harness/orchestration.json` выбирает `extensions.runtime_access: "docker"`, и одинаков для `soft`
и `hard`. Cleanup пропускает не остановленный worker (с подсказкой `<engine> stop <имя>`), объекты
живого исполнения и ответ runtime, который нельзя получить или прочитать. Volumes runtime не
перечисляет и не удаляет: анонимные volumes из `VOLUME` образа остаются за `rm`.

## Доступ QA, Git и publish {#qa-git-publish}

`qa run`, `integration local-qa`, `integration refresh`, `integration resolve` и `dispatch publish`
выполняет сам coordinator в своём процессе. Если в проекте нет `access_policy`, они работают как
раньше (`legacy-inherit`). Отказ среды всё равно останавливает их, но с обычной классификацией
ошибки Git или checkout. Если `access_policy` есть, перед действием coordinator проверяет план:

- Какой план. Для `qa run` и `dispatch publish` — план, закреплённый в approved brief. Правка
  конфига после `dispatch propose` его не расширяет. Brief без плана остаётся `legacy-inherit`. Для
  `integration local-qa`, `integration refresh` и `integration resolve` — `defaults` и override
  операции (`qa`, `git`) из живого конфига. Override роли не применяется ни к одной из них.
- Что требуется. Запись в общий Git-каталог и общее хранилище `.harness`; запись в каталог
  clean-room checkout (`qa`) или в worktree batch (`git`); пути `cache` из `filesystem`. Для `git`
  и `publish` нужна ещё и доступность remote. Coordinator проверяет хост remote по `network.hosts`,
  когда режим `sandbox` или список хостов непуст. План должен разрешать эти требования. Brief,
  закреплённый до этой версии без записи в Git и хранилище, потребует нового `dispatch propose`.
  Требование QA-роли «только чтение» не распространяется на coordinator-операцию.
- Как проверяется. Coordinator реально пробует запись (создаёт и сразу удаляет файл с уникальным
  именем) и читает remote через `git ls-remote`. Режим `inherit` ничего не утверждает о самой среде.
  Он лишь означает, что coordinator работает в своём окружении. Coordinator принимает `sandbox` и
  `unsandboxed`, только если подключённая реализация `runtime_access` подтверждает их для процесса
  coordinator (`observe` с транспортом `in-process`). Без неё режим считается неподдерживаемым.
  Харнесс не поставляет такую реализацию и не заявляет нативной поддержки: встроенный `docker`
  подтверждает только external worker и команды контейнерного QA (`operations.qa.container`, раздел
  выше), а для процесса coordinator даёт блокер. Ваш проект определяет, что именно подтверждает
  ваша реализация.
- Результат. Подтверждённый отказ (`denied`), неподдерживаемый режим (`unsupported`) и непроверенное
  требование (`unverified`, например путь не существует или remote недоступен) останавливают
  действие до первого изменения. Ошибка называет ресурс, путь и причину. Её remedy — конкретное
  действие среды. Структурное evidence (`operation`, `status`, `plan_digest`, `checks`) доступно
  в записи попытки: `qa-lane/attempts/*.json` для `qa run` (стадия `access`) и запись попытки
  `integration local-qa` (стадия `access`, поля `access` и `remedy`). `dispatch publish` возвращает
  evidence успешной проверки в поле `access`.

Что остаётся нетронутым при отказе. Отказ `qa run` происходит до постановки в очередь. Lease и
запись очереди не создаются, dispatch остаётся `approved`, предыдущие evidence и попытки
сохраняются. Следующий запуск после исправления среды проходит без ручной очистки. Любой сбой
`qa run` уже после взятия lease (создание checkout, смена состояния, запись evidence, неожиданное
исключение) снимает lease, запись очереди и состояние dispatch. Если ledger в этот момент занят,
откат ждёт lock до 30 секунд (см. «Занятый ledger, `report complete` и `ledger release-lock`»). Отказ перед `refresh`, `resolve` и
`publish` происходит до fetch, rebase, создания batch и push. Откат отказавшего rebase возвращает
worktree на issue-ветку. Отказ записи метаданных или remote при rebase и push coordinator
классифицирует как ошибку доступа (`metadata-write-denied`, `remote-access-denied`,
`remote-unreachable`), а не как конфликт или обычный сбой Git. Для классификации coordinator
запускает Git с `LC_ALL=C`.

Диагностика по сообщению:

| Сообщение | Что сделать |
| --- | --- |
| `qa access is denied: shared Git metadata (write …)` | Выдать процессу coordinator запись в указанный общий Git-каталог в sandbox или правах файловой системы. |
| `… clean-room checkout (write …)` или `could not prepare clean QA checkout storage` | Выдать запись в `.harness/.sandboxes/runs/qa` (или каталог хранилища, названный в ошибке). |
| `… is unsupported` / `mode … is not provable for the coordinator` | Подключить `runtime_access`, подтверждающую режим для coordinator, либо задать `mode: inherit` для операции в `access_policy.operations`. |
| `host … is not in the approved network hosts` | Добавить хост в `network.hosts` операции и, для операции с brief, заново выполнить `dispatch propose`. |
| `remote … ` недоступен (`unverified`) | Восстановить связь с remote из среды coordinator и повторить команду. |
| `remote-access-denied` при push | Выдать учётным данным процесса право записи в issue-ветку remote; затем повторить команду. |

Обход блокировки инструментом или хуком не предусмотрен. При блокировке остановитесь и сообщите о
ней.
