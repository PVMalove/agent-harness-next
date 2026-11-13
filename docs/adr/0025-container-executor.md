# Встроенный контейнерный исполнитель

**Статус: ACCEPTED. Частично заменён ADR 0022.** Argv движка, запуск, наблюдение, остановку и
удаление worker-а и QA-команд выполняет `harness-runtime` (ADR 0022); Python проверяет план и
закреплённые digest. Контракт ниже уже учитывает решения ADR 0022: значения `environment` из
окружения runtime, удаление объектов при выходе исполнения, at-most-once staged launch, только эпоха
runtime store на Linux и суженные монтирования контейнерного QA.

## Контекст системы

`access_policy` (#615, #630) описывает режим доступа, сеть и файловые ресурсы worker-а, а
`extensions.runtime_access` должен применить этот план к реальному запуску. Поставляемой реализации
не было, и любой план, отличный от `inherit`, блокировал `dispatch send`. Внутренний sandbox агента
при этом давал EPERM на записи вне checkout (например, кэш `uv`), а снять его в текущей сессии
нельзя без ослабления native approval. Изоляцию даёт отдельный контейнер на каждый dispatch, при
условии что он исполняет тот же утверждённый план, а не расширяет его.

## Действующий контракт

- Ядро поставляет одну native-реализацию `runtime_access` под именем `docker`: контейнерный
  исполнитель (Docker или Podman, режим движка определяется в `observe()`). Остальные среды
  по-прежнему подключаются как project-owned `module:factory`.
- Исполнитель запускает только external dispatch: он оборачивает команду external-адаптера и не
  знает конкретного агента. Флаги агента (отключение внутреннего sandbox, allowlist из
  `brief.allowed_tools`) задаёт проектный адаптер. In-process транспорт с этим исполнителем даёт
  блокер. Роль, которую `access_policy` не называет, к исполнителю не попадает; см. раздел
  «Решения реализации #1014».
- Native approval сохраняется: исполнитель не включает auto-approve и не подтверждает действия за
  человека. Изоляция контейнера не заменяет dispatch approval.
- Монтируются только ресурсы плана, по тем же абсолютным путям: `read` → read-only, `write` →
  read-write. Это сохраняет `gitdir` linked worktree и аргументы `--repo`/`--brief`; `/workspace`
  и перезапись путей отклонены. Тёплые кэши — только `cache`-ресурсы плана; named volumes и
  постоянный контейнер отклонены, чтобы весь доступ оставался видимым в плане. Контейнерный QA
  монтирует план суженно: `run_root` (каталог clean-room под `shared_storage`) на запись,
  `git_common` только на чтение и `cache` плана; `artifacts`, issue worktree и весь
  `shared_storage` не монтируются (ADR 0022).
- `network.hosts` исполняется через egress-proxy allowlist: worker подключён к internal-сети без
  прямого выхода, а proxy — sidecar-контейнер того же dispatch из отдельного proxy-образа харнесса.
  На Podman proxy дополнительно подключается к отдельной внешней сети с DNS: у стандартной сети
  `podman` DNS отключён, а DNS internal-сети не разрешает внешние имена. Обе сети имеют labels
  dispatch и execution и удаляются после контейнеров. Worker к внешней сети не подключается (#943).
- Секреты передаются только по именам переменных из компонента `environment` плана (`-e NAME`);
  значения берутся из окружения `harness-runtime serve` и не попадают в конфиг, brief, argv, IPC
  и слои образа. Auth-файлы не монтируются.
- Владелец файлов совпадает с пользователем хоста: rootful → `--user uid:gid`, rootless Podman →
  `--userns=keep-id`, rootless Docker → worker с явным `--user 0:0` (UID 0 внутри отображается на
  пользователя хоста независимо от `USER` образа; sidecar остаётся без флага пользователя и
  работает от `USER` своего образа). При SELinux enforcing — `label=disable`, без
  перемаркировки файлов хоста. Движок и режим `observe()` получает от runtime
  (`container.observe`), а runtime делает один запрос `<engine> info`; удалённый Podman, Docker с userns-remap и ответ, не совпадающий с выбранным
  движком, блокируют запуск до старта worker-а. `HARNESS_EXECUTOR=docker` и имя расширения `docker`
  не меняются для всех движков. `safe.directory` и HOME задаются через env и tmpfs, поэтому образ
  worker-а может быть любым; поставляемый `Dockerfile.sandbox` — лишь типовая база.
- Конфиг: `extensions.runtime_access: "docker"` и компоненты `container`/`environment` в
  `access_policy` с теми же overrides ролей и операций. Отдельного CLI-флага нет: доступ
  фиксируется при approval, а не при send.
- В конфиге указывается тег образа. Resolver остаётся без проб; `dispatch propose` вызывает
  `observe()` и записывает digest worker- и proxy-образа в brief рядом с планом — в transition
  digest, но не в `plan_digest`. Handoff запускает образы по digest; отсутствующий или
  пересобранный образ — блокер и новый propose.
- Handoff detached: `launch_id` — id контейнера. Все объекты получают метки dispatch и репозитория.
  При выходе исполнения runtime сохраняет логи и exit code в `executions` и удаляет объекты;
  незавершённое удаление повторяет reconcile. `harness cleanup` убирает сирот. Живой worker без
  явной команды не останавливается.
- Неудачный staged launch выполняется не больше одного раза: runtime откатывает созданные объекты,
  а dispatch становится `blocked` без повторного запуска (ADR 0022).
- Исполнитель работает только в эпохе runtime store и только на Linux. На файловом ledger и вне
  Linux `dispatch preflight` блокирует его с remedy.
- Clean-room QA использует тот же исполнитель синхронно, если задан
  `access_policy.operations.qa.container`: каждая gate-команда — отдельный foreground-контейнер
  (`--rm --init`) из образа, закреплённого в brief QA-dispatch, с планом `operations.qa`. Exit code
  и потоки команды становятся её evidence; по сроку команды runtime останавливает контейнер с
  grace-периодом. Sidecar-proxy и сеть живут весь QA run.

## Операционные последствия

- Dockerfile-ы и proxy поставляются в payload `.harness/container/`; образ собирает пользователь
  командой из guide, харнесс образы не собирает и не скачивает.
- Хост LLM API должен быть явно перечислен в `network.hosts`; ssh-remote через proxy не работает.
- Тесты идут через публичный путь coordinator с подменённым исполнителем команд движка; smoke с
  настоящим движком выполняется в CI и исключён из `make verify`. Границу проверки движков описывает
  раздел «Решения реализации #710».

## Решения реализации #710

**Принято оператором (2026-10-29).** Ticket #710 поставляет базовый образ worker-а, руководство по
настройке и smoke с настоящим Docker; Python и Rust runtime он не меняет.

| Текст ADR | Решение #710 | Причина |
|---|---|---|
| Флаги агента, включая отключение внутреннего sandbox, задаёт проектный адаптер | Guide ссылается на поставляемый адаптер `claude_worker.py` (раздел «Решения реализации #1125») | Ни один пример не содержит auto-approve и обхода безопасности. |
| Smoke с настоящим Docker исключён из `make verify` | Маркер `docker_smoke` отбрасывает `addopts` в `pyproject.toml` для любого прогона pytest по умолчанию (`make verify`, `make test`, coverage, diff-coverage); CI job `docker-smoke` выбирает его явно через `-m docker_smoke`, а модуль smoke внесён в `EXCLUDED_FROM_GATE` diff-coverage | Один источник исключения: машина разработчика с Docker не запускает smoke случайно, а gate не считает отброшенные строки непокрытыми. |
| Образ собирает пользователь командой из guide | Guide поставляется только с `backend-orchestration` как `.harness/docs/container-executor.md` из `harness/docs/`, на английском, как соседние контракты агентов; корневой `docs/` в целевой проект не копируется | Guide читают агенты и пользователи целевого проекта. |

Как работает реализация:

- **`Dockerfile.sandbox`.** Debian stable slim с тегом по дате, `git`, `curl`, `jq`,
  `ca-certificates`, `python3` с `venv`, `uv` закреплённой версии и Node.js с `npm`. Образ не
  объявляет `ENTRYPOINT`, `CMD`, `USER`, `VOLUME` и `ENV` и не содержит секретов: точку входа,
  пользователя, HOME и окружение задаёт runtime. Заголовок даёт команды `docker build` и
  `podman build` и пример `FROM`; `Dockerfile.proxy` получил строку `podman build`. Оба файла —
  payload `.harness/container/` с контролем дрейфа.
- **Smoke.** `tests/orchestration/test_docker_smoke.py` гоняет публичные команды coordinator против
  настоящих `harness-runtime`, Git worktree, store и `docker`. Путь worker-а: `dispatch propose`,
  `create` и `send` с исполняемым shell-адаптером в монтировании artifacts; адаптер пишет evidence,
  а хост проверяет владельца файла (uid и gid хоста), HTTPS и HTTP к `github.com` через sidecar,
  `403` для `example.com` и отсутствие прямого выхода. Путь QA: `qa run` с gate-командами
  проверки пользователя и `exit 3` даёт отчёт `failed` и stage evidence с кодом 3. Оба пути
  проверяют, что объектов с меткой dispatch не осталось. Без движка или образов smoke
  пропускается, а `HARNESS_REQUIRE_DOCKER_SMOKE=1` превращает пропуск в провал.
- **CI job `docker-smoke`.** Job собирает `harness-runtime`, базовый образ из
  `Dockerfile.sandbox`, проектный образ worker-а `FROM` него и proxy-образ, затем запускает
  `pytest -m docker_smoke` с `HARNESS_REQUIRE_RUNTIME=1` и `HARNESS_REQUIRE_DOCKER_SMOKE=1` и
  отдаёт отчёт `junit-docker-smoke` в dashboard. Smoke зависит от внешней сети (`github.com`,
  `example.com`, реестры базовых образов).
- **Граница проверки.** Настоящие smoke покрывают rootful Docker на runner GitHub Actions и
  rootless Podman на Fedora с SELinux enforcing (`podman-smoke`, #811). Rootful Podman,
  rootless Docker и Docker на хосте с SELinux enforcing остаются проверенными лишь argv-матрицей
  и scripted-движком.

## Решения реализации #1014

**Принято оператором (2026-11-10).** На #936 контейнерный воркер architect, developer и
code-review написал отчёт, но `dispatch wait` закончился `startup_timeout` с
`model-self-report-missing`. В контейнере нет runtime-сокета, поэтому воркер не может выполнить
`dispatch self-report` и `dispatch heartbeat`, а без self-report отчёт этих ролей не принимается.
Кроме того, любая authored `access_policy` переводила in-process роли под исполнитель, и
контейнерный QA нельзя было включить, не переводя все роли на `external`. Оператор выбрал два
варианта из #1014: подтверждение воркера на хосте (вариант 1) и действие контейнера только там, где
его задаёт слой `access_policy` (вариант 3).

| Текст ADR или тикета | Решение #1014 | Причина |
|---|---|---|
| Вариант 1: host-side обёртка выполняет self-report и heartbeat от имени контейнера | Self-report и heartbeat записывает coordinator на хосте в `execution_reaction.observe`, который вызывают `dispatch wait`, `dispatch status --dispatch` и `report submit`. Отдельной обёртки адаптера нет | Статус dispatch пишет только Python (ADR 0022), и все проверки self-report остаются в одном месте. |
| Вариант 2: receipt исполнителя заменяет self-report | Отклонён | Receipt не доказывает модель, а гейты отчётов и классификация startup пришлось бы менять. |
| Монтирование runtime-сокета в контейнер | Отклонено | Нарушает границу «Действующего контракта»: сокет и запись в ledger worker-у не даются. |
| Структурные события контейнерного воркера | Runtime при каждом reconcile работающего контейнера заменяет снимок его stdout и stderr в `executions/<id>/` (запись во временный файл и `rename`). Долгоживущего `logs --follow` нет | Снимок не требует восстановления после рестарта runtime и использует ту же операцию движка, что и сохранение логов при выходе. Цена — полный поток при каждом опросе. |
| Сравнение модели | Модель из события `init` сравнивается с `resolved_model` точно, как в `dispatch self-report` | Адаптер передаёт `--model` из brief, а brief хранит полное имя модели. Ослаблять сравнение без нового решения нельзя. |
| Несовпадение модели или checkout | Записывается с `match: false` без перевода в `blocked`; `dispatch wait` отвечает `model_mismatch` или `worktree_mismatch`, а `blocked` dispatch получает после выхода контейнера | Store запрещает `blocked`, пока execution может работать (ADR 0021). Остановку воркера харнесс без явной команды не выполняет. |
| Вариант 3: `runtime_access: docker` действует только на роли и операции с контейнером | Роль, которую не называют ни `access_policy.defaults`, ни `access_policy.roles.<роль>`, получает прежний legacy-inherit план (`runtime_extension: none`, тот же digest) для любого расширения | Такая роль ничего не просила; без этого правила любая `access_policy` блокировала in-process роли. |
| Контракт `docker` требует `defaults.container` | Требуется `defaults.container`, если задан `defaults`; без `defaults` — `operations.qa.container`. Схема и `harness health` проверяют одно и то же | Контейнерный QA можно включить одним `operations.qa`. |
| Критерий 3: запрет схемой с сообщением при загрузке | In-process роль, которую называют `defaults` или `roles.<роль>`, даёт предупреждение при загрузке конфигурации, а не ошибку; `dispatch preflight` по-прежнему её блокирует. Без `defaults` предупреждение получает и override роли без `container` | Ошибка загрузки остановила бы и external роли, и контейнерный QA, и команды уже созданных dispatch той же конфигурации. |
| Отчёт воркера, который вышел до `report submit` | Если self-report на хосте совпал, а отчёт лежит в `report_staging_path`, выход не переводит dispatch в `blocked`: статус получает `staged_report`, а `dispatch wait` отвечает `report_staged`. Без staged-отчёта выход, как и раньше, даёт `worker-exited-without-report` | Воркер в контейнере не может сам выполнить `report submit`, поэтому его выход сразу после записи отчёта — обычный путь, а не сбой (критерий 2). Решение принято при реализации после ревью и ждёт подтверждения оператора. |

Как работает реализация:

- **Снимок потока.** `settle_container` для работающего контейнера своей execution выполняет
  `<engine> logs <id>` в `stdout.log.partial` и `stderr.log.partial` и переименовывает их поверх
  логов. Ошибка снимка не меняет состояние execution: выход сохраняет логи заново.
- **Self-report на хосте.** `container_attestation.attest` работает только для `running`
  и `exited` execution docker-плана. Он читает полные строки первых 4 МиБ снимка, берёт первое событие
  `{"type": "system", "subtype": "init"}` и вызывает `record_self_report`: ту же функцию, что и
  `dispatch self-report`. Worktree — путь ресурса `checkout` закреплённого плана. Записи
  `model_self_report` и `worktree_attestation` получают `source: container-host`, а attestation —
  доказательство запуска `container`: id контейнера, digest образов из `runtime_images`, путь
  checkout и `executor: docker`. Повторное наблюдение при записанном self-report ничего не
  записывает, кроме heartbeat.
- **Heartbeat.** Каждое наблюдение работающего контейнера обновляет `heartbeat_at` с
  `heartbeat_note: container running`. Срок запуска не меняется: контейнер без события `init`
  заканчивается `startup_timeout` с `model-self-report-missing`.
- **События.** `dispatch observe` для контейнерного dispatch читает тот же снимок;
  `read_events` принимает журнал из shared logs или из каталога `executions` runtime store.
- **Отчёт.** Отчёт из `report_staging_path` записывается на хосте командой
  `report submit --file`. Пока контейнер работает, отчёт ждёт выхода (`pending_report`). Если
  контейнер вышел раньше, `execution_reaction.react` проверяет `container_attestation.staged_report`:
  docker-план, self-report с `source: container-host` и `match: true` и файл отчёта. Тогда dispatch
  остаётся живым со `staged_report`, а `dispatch wait` отвечает `report_staged`. Иначе выход даёт
  `blocked` с `worker-exited-without-report` (ADR 0021).
- **Граница доверия.** Модель в событии `init` печатает процесс в контейнере, движок её не
  проверяет. Доказательство так же сильно, как `dispatch self-report` воркера: оно ловит ошибку
  конфигурации адаптера, но не злонамеренный воркер. Checkout, образы и контейнер берутся из плана и
  execution, а не из вывода воркера.
- **Граница проверки.** Шов с настоящим `harness-runtime` и scripted Podman
  (`tests/orchestration/test_container_runtime.py`) проверяет self-report, несовпадение модели,
  heartbeat, события, приём отчёта до выхода и после него. Smoke с настоящим движком
  (`test_podman_smoke.py`, `test_docker_smoke.py`) проходит полный цикл для architect. Developer и
  code-review идут тем же путём (`requires_attestation`, `attest_runtime_worktree`), но отдельным
  smoke не проверены. Совпадение имени модели в событии `init` настоящего агента с `resolved_model`
  проверено только адаптером smoke, который печатает имя из brief.

## Решения реализации #1125

**Ждёт подтверждения оператора.** #1125 просил ADR о контейнерном worker разработчика и review.
Большая часть контракта уже принята в разделах #710 и #1014: образ и его закрепление по digest,
учётные данные по имени через `environment`, сеть через `access_policy`, монтирования, выбор режима
слоем `access_policy` и self-report на хосте. #1125 закрывает пробелы, из-за которых работающий
контейнерный worker всё ещё попадал в `blocked`, и записывает, что остаётся открытым.

| Пробел | Решение #1125 | Причина |
|---|---|---|
| Контейнер вышел раньше первого наблюдения хоста | `attest` подтверждает и вышедший контейнер по сохранённому stdout, а `observe` вызывает его до `react`. `report submit` сначала подтверждает контейнерный worker (`attest_before_submit`) и только потом проверяет self-report | Короткий worker пишет отчёт и выходит раньше, чем coordinator вызовет `dispatch wait` или `status`. Без self-report `staged_report` не срабатывал, и выход давал `worker-exited-without-report` |
| Событие `init` после длинного вывода | Поиск идёт по полным строкам первых 4 МиБ снимка, а не по первым 64 КиБ | Вывод hooks или одна длинная строка до `init` прятали событие, и dispatch уходил в `startup_timeout` |
| Адаптер в контейнере | `send` запускает `.py`-адаптер контейнерного плана через `python3` образа. `claude_worker.py` при `HARNESS_EXECUTOR=docker` просит только записать отчёт в `report_staging_path` и не просит команд coordinator. Пример shell-адаптера из руководства заменён ссылкой на этот адаптер | Python хоста не существует в образе, а промпт процессного режима требовал `dispatch self-report` до работы, который в контейнере невыполним. Пример ставил промпт после variadic `--allowedTools` и не давал read-only роли записи отчёта |
| Учётные данные в логах | Runtime хранит в записи запуска имена `environment` плана и заменяет их значения длиной от 8 байт на `[redacted:<имя>]` в снимке и в логах при выходе | Логи лежат в `.harness`, который каждый контейнерный worker монтирует на чтение; worker может напечатать полученный ключ |
| `harness health` | `orchestration.worker_binaries` для роли в контейнере проверяет движок в PATH serve и образы в локальном хранилище движка (`image inspect`), а не `claude` или `codex` на хосте. `claude` ищется и в `~/.local/bin` | CLI агента живёт в образе; прежняя проверка давала ложный `fail` |

Открытые пункты:

- **Hooks проекта.** Управляемые hooks (`.claude/settings.local.json`, `.claude/hooks/`) не
  отслеживаются Git и не попадают в issue worktree даже на хосте, поэтому в контейнере их нет.
  Способ доставки hooks в worktree решает #1122; контейнер получит их тем же путём.
- **Срок запуска** считается от `sent_at`, поэтому создание сети, proxy и контейнера входит в
  `startup_timeout_seconds`. `dispatch wait` отвечает `startup_timeout` событием и dispatch не
  блокирует.
- **Сравнение модели** остаётся точным. Несовпадение имени в событии `init` настоящего CLI с
  `resolved_model` не проверено на живом агенте.
- **Граница проверки.** Шов с настоящим `harness-runtime` и scripted Podman проверяет выход до
  наблюдения, `report submit` первым после выхода, замену значений в логах и запуск `python3`.
  Живой прогон с Docker и настоящим `claude` в образе не выполнялся.
