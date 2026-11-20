# Доступ и контейнер

План доступа описывает разрешения worker. Применяет их runtime или исполнитель, который подтвердил поддержку плана. Сначала настройте среду, затем согласуйте dispatch.

[Обзор оркестрации](../../backend-orchestration.md)

## Доступ ролей: `access_policy` и `runtime_access` {#access_policy-runtime_access}

Необязательный раздел `access_policy` задаёт для worker режим sandbox и границы сети и файловой
системы. Без него brief сохраняет `inherit`, а `dispatch send` ведёт себя как раньше. Раздел не
требует `assignment_plans`: coordinator читает `access_policy`, даже если в конфиге больше ничего
нет.

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

- Компоненты `mode` (`inherit`, `sandbox`, `unsandboxed`), `network.hosts` и `filesystem` не
  зависят от транспорта роли (`in-process` или `external`). Компонент `container` называет образы
  встроенного исполнителя `docker`, а `environment` перечисляет имена переменных окружения для его
  worker (см. ниже). План без этих двух компонентов сохраняет прежнюю форму и прежний digest.
- Override роли (`roles`) или операции (`operations`: `qa`, `git`, `publish`) заменяет только
  указанные в нём компоненты, остальные берутся из `defaults`. Операции `qa`, `git` и `publish`
  выполняет сам coordinator, а не worker. Поэтому к ним применяются только `defaults` и override
  самой операции, а `roles` никогда. Операцию выбирает команда: `publish` для `--purpose publish`,
  `qa` для роли `qa` и `integration local-qa`, `git` для `integration refresh` и
  `integration resolve`. Что именно coordinator проверяет, описывает раздел «Доступ QA, Git и
  publish» ниже.
- `filesystem` называет ресурс: `checkout`, `git_common`, `shared_storage` или `cache`. `path`
  нужен только для `cache`. Элемент `cache` может задать `variable`: имя переменной, через которую
  контейнерный исполнитель сам передаёт разрешённый путь кэша (`--env NAME=<путь>`), например
  `CARGO_HOME` (ADR 0032). Имя должно быть уникальным среди кэшей и не совпадать с `environment` и
  с именами, которые задаёт runtime. Кэш без `variable` сохраняет прежний digest плана.
  Coordinator превращает ресурсы в реальные пути worktree, общего Git-каталога и хранилища. Корень
  диска и весь домашний каталог он отклоняет.
- Права на запись не расширяют `write_paths` brief, tool policy и нативные подтверждения.
  Read-only роль не получает запись в `checkout`, `git_common` и `shared_storage`.
- Coordinator записывает разрешённый план (`runtime_access`) в brief, и sha256 плана входит в
  transition digest утверждения. Правка конфига после `dispatch propose` не расширяет утверждённый
  dispatch: для нового доступа нужны новый `propose` и новый approval. Brief без этого поля
  остаётся валидным и читается как `inherit`.
- `dispatch preflight` показывает разрешённый план и сверку с `runtime_access`. Настройки
  пользователя и аттестация Git-checkout не доказывают текущие права сети и файловой системы.
- Расширение `runtime_access` даёт нативную реализацию. Она наблюдает окружение именно этого
  worker, применяет план и выполняет handoff (`observe`, `apply`, `handoff`). Значение `none`
  ничего не доказывает. Поэтому без нативной реализации coordinator блокирует `dispatch send` для
  плана с `sandbox`, `unsandboxed`, хостами или путями. Блокировка наступает до передачи работы:
  coordinator не подменяет план молча, не откатывается на `inherit` и ничем не заменяет нативное
  подтверждение. Харнесс поставляет одну реализацию, встроенный контейнерный исполнитель `docker`
  (следующий раздел). Любую другую среду подключает модуль вашего проекта, как `my_runtime:factory`
  в примере выше. Пока проект не выбрал реализацию, любой `access_policy`, даже `mode: inherit`,
  блокирует `dispatch send`. `dispatch status` сохраняет статус и доказательство worker
  (`runtime_access`).

Если `dispatch send` остановлен, ошибка называет причину. Реализация, которая сама называет свой
блокер (так делает `docker`), передаёт и свой remedy, а `dispatch preflight` показывает её
наблюдения в `runtime_access.verification.environment`. Иначе remedy общий:

1. Подготовьте указанные хосты, пути и режим в новой сессии runtime.
2. Подключите реализацию `runtime_access`, которая проверяет реальный запуск worker.
3. Повторите `dispatch preflight`.

## Встроенный контейнерный исполнитель `docker` {#docker}

Значение `extensions.runtime_access: "docker"` выбирает исполнитель из поставки харнесса.
`harness-runtime` запускает каждый утверждённый external dispatch в отдельном контейнере Docker или
Podman. Если задан `access_policy.operations.qa.container`, в контейнере идёт и каждая команда QA.
Контракт исполнителя описывают ADR 0025 и ADR 0022 (разделы «Решения реализации»), а этот раздел
описывает поставленное поведение.

Пошаговую настройку целевого проекта (предпосылки, сборка образов, кэши, allowlist, блокеры,
очистка, пример проектного адаптера) даёт англоязычное руководство
[`harness/project/instructions/container-executor.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/instructions/container-executor.md).
`backend-orchestration` ставит его как `.harness/instructions/container-executor.md`. Проектные реализации
`module:factory` работают как раньше. Хост-процесс не может зарегистрировать другую реализацию под
именем `docker`.

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

### Конфигурация {#docker-config}

- Компонент `container` содержит обязательный `worker_image`, необязательный `proxy_image` и
  необязательный `engine` (`docker` по умолчанию или `podman`). Тег должен быть одной ссылкой на
  образ без пробелов и без ведущего `-`. Override роли или операции заменяет компонент целиком.
  Resolver берёт теги только из конфига и не опрашивает движок, сеть и образы. Если выбран
  `docker`, `harness health` и схема требуют `access_policy.defaults.container`, а без `defaults`
  требуют `access_policy.operations.qa.container`. Иначе исполнителю нечего запускать.
- Компонент `environment` перечисляет уникальные имена переменных окружения
  (`[A-Za-z_][A-Za-z0-9_]*`), но никогда не значения. Override роли или операции заменяет список
  целиком. План хранит имена отсортированными, поэтому они входят в `plan_digest` и закрепляются в
  brief при approval. Имя, добавленное в конфиг после `dispatch propose`, этот dispatch не получит.
  Значения движок берёт из окружения `harness-runtime serve`, поэтому после их смены перезапустите
  runtime. Значения не попадают в конфиг, brief, digest, argv, evidence, логи, тексты ошибок и
  слои образа. Auth-файлы агента не монтируются.
- Роль, которую называет `access_policy.defaults` или её собственный
  `access_policy.roles.<роль>`, должна иметь `transport: external` в `assignment_plans`.
  Исполнитель оборачивает команду external-адаптера и не знает, какой агент внутри. Для такой роли
  с транспортом in-process загрузка конфигурации выдаёт предупреждение, а `dispatch preflight`
  блокирует запуск. Роль, которую `access_policy` не называет, получает прежний legacy-inherit план
  и запускается in-process как раньше. Поэтому контейнерный QA можно включить одним
  `operations.qa`. Если `defaults` нет, override роли должен сам содержать `container`, иначе
  загрузка выдаст предупреждение и для него.
- Воркер в контейнере не может выполнить `dispatch self-report` и `dispatch heartbeat`. Их
  записывает coordinator на хосте по снимку stdout контейнера и утверждённому плану (ADR 0025,
  «Решения реализации»).
- Исполнитель работает только в эпохе runtime store и только на Linux. На файловом ledger и вне
  Linux `dispatch preflight` блокирует его с remedy: `harness-runtime migrate`, затем
  `harness-runtime serve`.

### Preflight и образы {#docker-preflight}

`dispatch preflight` спрашивает runtime (`container.observe`), а runtime опрашивает движок только
на чтение. `<engine> info` определяет режим (`rootful`, `rootless`, `unknown` или `unavailable`),
SELinux и ID демона. `<engine> image inspect` находит локальный id каждого образа. При успехе
evidence содержит движок, режим и id образов.

Явный блокер с собственным remedy дают:

- недоступный движок;
- движок, чей режим нельзя определить по `info` (например, docker-совместимая обёртка другого
  движка);
- удалённый Podman;
- Docker с userns-remap;
- отсутствующий образ;
- транспорт `in-process`;
- режим `unsandboxed`;
- непустой `network.hosts` без `proxy_image`;
- корень плана, который открывает сокет движка или каталог runtime, содержит запятую, кавычку или
  перевод строки либо пересекается с `/harness-home`;
- переменная из `environment`, которой нет в окружении `harness-runtime serve`;
- имя переменной, которое исполнитель задаёт сам: `HOME`, `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0`,
  `GIT_CONFIG_VALUE_0`, `HARNESS_EXECUTOR`, а при непустом `network.hosts` ещё `HTTP_PROXY`,
  `HTTPS_PROXY`, `NO_PROXY` и их варианты в нижнем регистре.

Блокер называет только имена переменных. Preflight перечисляет все блокеры сразу, и ни один из них
не создаёт контейнер. Runtime проверяет переменные ещё раз перед запуском: если переменная пропала
после approval, send отклоняется, а dispatch остаётся `approved`.

Харнесс образы не собирает, не скачивает и не публикует. Payload `.harness/container/` содержит:

- необязательный базовый образ worker `Dockerfile.sandbox` (Debian slim с `git`, `curl`, `jq`,
  Python с `uv` и Node.js);
- необязательный QA-образ `Dockerfile.qa` поверх `harness-sandbox:local` с `make`, компилятором C
  и Rust toolchain;
- `Dockerfile.proxy` и код egress-proxy.

Команды `docker build` и `podman build` для образов даёт руководство. Отсутствующий образ соберите
или скачайте сами, затем повторите `dispatch preflight` и `dispatch propose`.

`dispatch propose` опрашивает движок и закрепляет id образов рядом с планом в поле brief
`runtime_images` (`{"worker": "sha256:…", "proxy": "sha256:…" | null}`). Sha256 этого поля входит в
transition digest (`runtime_images_sha256`), но не в `plan_digest`: план зависит только от конфига,
а образ под тем же тегом может измениться. `dispatch create` опрашивает движок ещё раз. Если образ
пересобрали после `propose`, digest меняется, и explicit approval со старым digest coordinator
отклоняет. Поле есть у brief, который отправляет `dispatch send`, и у brief контейнерного QA.
Publish и QA на хосте его не получают. Brief без поля остаётся валидным.

`dispatch send` запускает только закреплённые id. Если образ пропал или изменился после `propose`,
runtime отклоняет запуск с `approval_mismatch`, а dispatch остаётся `approved`. Remedy: вернуть
образ с закреплённым id или пересобрать либо скачать образ, отменить dispatch (`dispatch cancel`)
и повторить `dispatch propose`. Approval для другого образа повторно не используется.

### Запуск worker {#docker-launch}

`dispatch send` передаёт supervised docker-dispatch в `execution.launch` runtime. Python argv движка
не строит. Если `network.hosts` не пуст, runtime создаёт сеть `--internal` и sidecar-proxy. Затем он
создаёт worker `harness-<dispatch_id>` командой `<engine> create --pull never` и запускает его
`<engine> start` без ожидания (detached). Worker получает:

- `--network none` или внутреннюю сеть dispatch;
- пользователя хоста: rootful получает `--user <uid>:<gid>`, rootless Podman получает
  `--userns=keep-id`, rootless Docker получает `--user 0:0`; при SELinux добавляется
  `label=disable`;
- `--cap-drop ALL` и `no-new-privileges`;
- HOME на tmpfs `/harness-home`;
- `safe.directory=*` через `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0`;
- маркер `HARNESS_EXECUTOR=docker`;
- каждое имя из `environment` закреплённого плана как `--env NAME` без значения.

Каждый корень плана монтируется по тому же абсолютному пути: `read` только для чтения, `write` на
чтение и запись. Других монтирований нет. Метки `harness.dispatch`, `harness.repository`,
`harness.plan_digest`, `harness.operation` и `harness.execution` связывают объекты с dispatch и
исполнением. Квитанция `dispatch send` (поле `execution`) называет движок и id контейнера.

Если `network.hosts` не пуст, worker выходит наружу только через sidecar из закреплённого
proxy-образа. Переменные `HTTP_PROXY` и `HTTPS_PROXY` (и их варианты в нижнем регистре) указывают
на него, а `NO_PROXY` оставляет только loopback. Прокси пропускает HTTP и `CONNECT` к точно
совпадающему хосту плана на портах 80 и 443. Он отказывает IP-литералам и именам с loopback,
link-local, unspecified или multicast адресом и отвечает `403` на всё остальное. Хост API модели
перечислите явно. Git по ssh через прокси не работает.

Неудачный поэтапный запуск выполняется не больше одного раза (at-most-once). Runtime откатывает
созданные объекты от новых к старым. Исполнение становится `lost`, операция `failed`, dispatch
`blocked`, повторного запуска нет.

Адаптер должен лежать внутри монтирований плана и запускаться в образе: `--entrypoint` получает
путь адаптера. Для `.py`-адаптера coordinator передаёт интерпретатор хоста, которого в образе
обычно нет, поэтому нужен исполняемый адаптер. Флаги агента для запуска в контейнере проектный
адаптер выставляет по маркеру `HARNESS_EXECUTOR`.

### Ограничения {#docker-limits}

Worker-роль видит `shared_storage` только для чтения и пишет в хранилище только в
`.sandboxes/scratch`. Сокет runtime в контейнер не монтируется. Поэтому команды coordinator, которые
меняют ledger (`dispatch self-report`, `dispatch heartbeat`, `report submit`), из контейнера не
работают. Worker кладёт отчёт в `report_staging_path`, а после выхода worker отчёт записывают на
хосте командой `report submit --file <путь>`. Отдельный `--checkout` роли `code-review` в контейнер
не монтируется: монтируются только корни плана.

Настоящий smoke в CI (job `docker-smoke`) проверяет только rootful Docker. Podman (rootful и
rootless), rootless Docker и хосты с SELinux подтверждены только argv-матрицей и scripted-движком,
на живом движке их не проверяли.

### Контейнерный QA {#docker-qa}

Контейнерный QA включается только заданным `access_policy.operations.qa.container`. Тогда каждая
команда QA идёт в отдельном foreground-контейнере `--rm --init` из образа, закреплённого в brief
QA-dispatch, а sidecar и сеть живут весь QA run. Монтирований меньше: каталог clean-room на запись,
`git_common` только на чтение и `cache` плана. Exit code команды попадает в её stage evidence, а
окончание классифицирует ADR 0022 (раздел «Решения реализации»). Без `operations.qa.container` QA
остаётся на хосте. Операции `git` и `publish` coordinator всегда выполняет в своём окружении
(раздел «Доступ QA, Git и publish» ниже).

## Статус и очистка контейнерного worker {#worker}

Исполнение контейнерного worker наблюдает `harness-runtime`, а не coordinator. Runtime сверяет
контейнер с его метками (reconcile) при старте, перед каждой операцией над исполнением и раз в
`dispatch_poll_interval_seconds`:

- живой объект: `running`;
- выход с кодом: `exited`;
- доказанное отсутствие: `lost`;
- нет ответа: `unknown`.

`dispatch status` и `dispatch wait` берут это исполнение из runtime и движок сами не спрашивают.

Когда worker завершается, runtime сохраняет его потоки (`executions/<id>/stdout.log` и
`stderr.log`) и записывает код выхода в исполнение. Затем он удаляет worker, sidecar и сеть в этом
порядке. Незавершённое удаление повторит следующий reconcile. По сроку
`worker_execution_timeout_seconds` runtime останавливает контейнер (`stop --time <stop_grace_seconds>`,
затем `kill`) и записывает `stopped_by: "deadline"`. Без явной команды работающий worker не
останавливается. Остановить его можно командой движка (`docker stop harness-<dispatch_id>`).
Контейнер не пишет в ledger, поэтому обычно завершается раньше, чем отчёт записан. Подготовленный
отчёт лежит в `report_staging_path`, и его записывают командой `report submit --file <путь>`.

`harness cleanup <repo>` перечисляет оставшиеся контейнеры и сети этого репозитория через runtime
(`container.objects`). Runtime фильтрует их по своей метке `harness.repository` и знает состояние
исполнения каждого объекта. Удаляет их `container.remove` движками из `access_policy`. Команда
работает по общим правилам: без `--apply` показывает предпросмотр, с `--apply` применяет свежий
план и отказывает, если план изменился. Этот раздел cleanup выполняется, только если
`.harness/orchestration.json` выбирает `extensions.runtime_access: "docker"`, и одинаков для `soft`
и `hard`. Cleanup пропускает:

- не остановленный worker (с подсказкой `<engine> stop <имя>`);
- объекты живого исполнения;
- ответ runtime, который нельзя получить или прочитать.

Volumes runtime не перечисляет и не удаляет. `rm` вызывается без `-v`, поэтому анонимные volumes из `VOLUME` образа остаются после удаления контейнера. Не объявляйте `VOLUME` в образе.

## Доступ QA, Git и publish {#qa-git-publish}

`qa run`, `integration local-qa`, `integration refresh`, `integration resolve` и `dispatch publish`
coordinator выполняет сам в своём процессе. Если в проекте нет `access_policy`, они работают как
раньше (`legacy-inherit`). Отказ среды всё равно их останавливает, но с обычной классификацией
ошибки Git или checkout. Если `access_policy` есть, перед действием coordinator проверяет план:

- **Какой план.** Для `qa run` и `dispatch publish` coordinator берёт план, закреплённый в approved
  brief. Правка конфига после `dispatch propose` его не расширяет. Brief без плана остаётся
  `legacy-inherit`. Для `integration local-qa`, `integration refresh` и `integration resolve` план
  собирается из `defaults` и override операции (`qa`, `git`) живого конфига. Override роли не
  применяется ни к одной из этих операций.
- **Что требуется.** Запись в общий Git-каталог и общее хранилище `.harness`, запись в каталог
  clean-room checkout (`qa`) или в worktree batch (`git`), пути `cache` из `filesystem`. Для `git`
  и `publish` нужна ещё и доступность remote. Хост remote coordinator проверяет по
  `network.hosts`, если режим `sandbox` или список хостов не пуст. План должен разрешать все эти
  требования. Brief, закреплённый до этой версии без записи в Git и хранилище, потребует нового
  `dispatch propose`. Требование «только чтение» для QA-роли не касается операции coordinator.
- **Как проверяется.** Coordinator на деле пробует запись (создаёт и сразу удаляет файл с
  уникальным именем) и читает remote через `git ls-remote`. Режим `inherit` ничего не утверждает
  о самой среде: он означает только, что coordinator работает в своём окружении. `sandbox` и
  `unsandboxed` coordinator принимает, только если подключённая реализация `runtime_access`
  подтверждает их для процесса coordinator (`observe` с транспортом `in-process`). Без неё режим
  считается неподдерживаемым. Харнесс не поставляет такую реализацию и не заявляет нативной
  поддержки. Встроенный `docker` подтверждает только external worker и команды контейнерного QA
  (`operations.qa.container`, раздел выше), а для процесса coordinator даёт блокер. Что
  подтверждает ваша реализация, определяет ваш проект.
- **Результат.** Подтверждённый отказ (`denied`), неподдерживаемый режим (`unsupported`) и
  непроверенное требование (`unverified`, например путь не существует или remote недоступен)
  останавливают действие до первого изменения. Ошибка называет ресурс, путь и причину, а remedy
  называет конкретное действие со средой. Структурное evidence (`operation`, `status`,
  `plan_digest`, `checks`) лежит в записи попытки: `qa-lane/attempts/*.json` для `qa run` (стадия
  `access`) и запись попытки `integration local-qa` (стадия `access`, поля `access` и `remedy`).
  `dispatch publish` возвращает evidence успешной проверки в поле `access`.

Что не меняется при отказе. `qa run` отказывает до постановки в очередь: lease и запись очереди не
создаются, dispatch остаётся `approved`, прежние evidence и попытки сохраняются. После исправления
среды следующий запуск проходит без ручной очистки. Если `qa run` сбоит уже после взятия lease
(создание checkout, смена состояния, запись evidence, неожиданное исключение), coordinator снимает
lease, запись очереди и состояние dispatch. Если ledger в этот момент занят, откат ждёт lock до
30 секунд (см. [«Занятый ledger, `report complete` и `ledger release-lock`»](operations.md#ledger-report-complete-ledger-release-lock)).

Перед `refresh`, `resolve` и `publish` отказ наступает до fetch, rebase, создания batch и push.
Откат отказавшего rebase возвращает worktree на issue-ветку. Отказ записи метаданных или remote при
rebase и push coordinator классифицирует как ошибку доступа (`metadata-write-denied`,
`remote-access-denied`, `remote-unreachable`), а не как конфликт или обычный сбой Git. Для этой
классификации coordinator запускает Git с `LC_ALL=C`.

Что делать по тексту ошибки:

| Сообщение | Что сделать |
| --- | --- |
| `qa access is denied: shared Git metadata (write …)` | Выдать процессу coordinator запись в указанный общий Git-каталог в sandbox или в правах файловой системы. |
| `… clean-room checkout (write …)` или `could not prepare clean QA checkout storage` | Выдать запись в `.harness/.sandboxes/runs/qa` (или в каталог хранилища из ошибки). |
| `… is unsupported` / `mode … is not provable for the coordinator` | Подключить `runtime_access`, которая подтверждает режим для coordinator, или задать `mode: inherit` для операции в `access_policy.operations`. |
| `host … is not in the approved network hosts` | Добавить хост в `network.hosts` операции, а для операции с brief заново выполнить `dispatch propose`. |
| `remote … ` недоступен (`unverified`) | Восстановить связь с remote из среды coordinator и повторить команду. |
| `remote-access-denied` при push | Выдать учётным данным процесса право записи в issue-ветку remote, затем повторить команду. |

Обойти блокировку инструментом или хуком нельзя. Если действие заблокировано, остановитесь и
сообщите о блокировке.
