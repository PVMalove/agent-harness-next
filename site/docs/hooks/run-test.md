# run-test.sh: изолированный запуск одного теста

## 1. Название и локализация

- **Исходный скрипт:** [`harness/project/hooks/run-test.sh`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/run-test.sh),
  ядро: [`harness/health/isolated_runner.py`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/isolated_runner.py)
- **Русский перевод:** изолированный runner одного выбранного теста.

## 2. Полное описание

`run-test.sh` запускает один тест, выбранный по идентификатору, внутри bubblewrap. Поэтому тест и
все его дочерние процессы не могут изменить production-код, `.git` и конфигурацию runner. Это не
hook события: установка `engineering-suite` копирует скрипт в `.claude/hooks/run-test.sh`, но не
подключает его в `settings.local.json`. Сам скрипт только находит Python и корень репозитория (на
два уровня выше `.claude/hooks/`) и загружает ядро из `.harness/health/` через `python3 -I -B`.
Так отключены переменные `PYTHON*`, пользовательский site, текущий каталог и запись байткода, а из
зон записи runner ничего не импортирует и не исполняет. Режима запуска без изоляции нет: любой
провал до запуска теста даёт отказ.

**Настройки.** Runner читает только `.harness/project.json` checkout и принимает из CLI лишь
идентификатор теста. Поэтому вызывающий не может расширить зону записи или подменить команду.
Оба поля необязательны. Runner проверяет их теми же функциями, что и `harness health`
(`test_paths_problems`, `test_runner_problems` в `harness/health/project_files.py`):

- `test_paths`: непустой список уникальных относительных glob без сегментов `..`; это тестовые
  пути и единственная зона записи тест-автора;
- `test_runner`: объект `{"command": [...]}`, то есть argv без шелла из непустых строк, в котором
  ровно один элемент равен `{test_id}`, и этот элемент не первый.

```json
"test_paths": ["tests/**"],
"test_runner": {"command": ["python3", "-m", "unittest", "{test_id}"]}
```

Новый проект получает эти поля флагами `harness init`. Шаблон `project.json.tmpl` пишет их только
по флагам, а некорректное значение `init` отклоняет до записи файлов:

```bash
harness init . --capability engineering-suite \
  --test-path 'tests/**' \
  --test-runner-command 'python3 -m unittest {test_id}'
```

Без флагов полей нет, и runner отказывает с `test_paths_missing` или `test_runner_missing`.
Значения по умолчанию нет: оно включило бы тест-автора в каждом новом проекте и предполагало бы
раскладку и стек проекта. Как включить тест-автора, описано в [руководстве test-author](../agents/test-author.md).

**Зоны записи.** Схема допускает любой относительный glob, но runner монтирует на запись только
записи вида `<каталог>/**`, а для остальных отказывает с `write_zone_rejected`. Каждая запись
должна пройти все проверки:

- остальные сегменты литеральные: без `*?[]{}` и `\`, непустые, не `.` и не `..`;
- первый сегмент не `.git`, `.harness`, `.claude`, `.agents` или `.codex` (без учёта регистра), и
  зона не совпадает с корнем;
- каталог существует, ни один компонент пути от корня checkout не является symlink, а `realpath`
  совпадает с самим путём;
- зоны не вложены друг в друга. Иначе тест одного запуска мог бы подменить каталог внутренней
  зоны symlink на production до монтирования в параллельном запуске;
- в зоне нет обычного файла с несколькими жёсткими ссылками: заранее созданный hardlink на
  production-файл дал бы к нему обходной доступ.

Symlink внутри зоны безопасен: запись через него попадает в монтирование только для чтения и
получает `EROFS`. Кроме зон тест пишет в `/tmp` и в свежие для каждого запуска `cache/` и
`reports/`. `/tmp` устроен как hermetic `/tmp` в Bazel: это не каталог хоста, а свой пустой каталог
`<run>/tmp-*` на каждый запуск bwrap (probe, сборка, тест), который после запуска удаляется. Внутри
путь остаётся коротким `/tmp`, поэтому сокеты базы данных укладываются в лимит AF_UNIX в 107 байт.
Общего кеша между запусками нет: через него тест подложил бы `.pyc` production-модуля следующему
запуску.

**Песочница.** Набор флагов из ADR 0014 не ослабляется:

```text
bwrap --ro-bind / / --dev /dev --proc /proc --bind <run>/tmp-* /tmp --tmpfs /run
      --bind <зона> <зона> ... --bind <run>/cache <run>/cache --bind <run>/reports <run>/reports
      --chdir <repo> --unshare-all --die-with-parent --new-session --cap-drop ALL
      --json-status-fd <fd> -- <test_runner.command с id вместо {test_id}>
```

Идентификатор runner подставляет одним элементом argv, шелл не используется. `bwrap` runner ищет в
`PATH`; что изоляция работает, доказывает probe, а не наличие бинарника. Из окружения вызывающего
тест получает только `PATH`, `LANG`, `LC_ALL`, `LC_CTYPE` и `TZ`. Runner добавляет `HOME=/tmp`,
`TMPDIR=/tmp`, `XDG_CACHE_HOME`, `PYTHONPYCACHEPREFIX`, `HARNESS_TEST_CACHE_DIR` (каталог `cache/`)
и `HARNESS_TEST_REPORT_DIR` (каталог `reports/`). Остальные переменные, включая токены, тест не
видит. Таймаут теста 300 секунд. По истечении runner завершает группу процессов, а
`--die-with-parent` завершает всё дерево внутри песочницы.

**Сокеты хоста.** Монтирование только для чтения не запрещает `connect()` к Unix-сокету. В `/run`
(на него ссылается `/var/run`) лежат сокеты сервисов хоста: системная и сессионная D-Bus, systemd
user manager в `/run/user/<uid>`, движки контейнеров. Через такой сокет тест запустил бы процесс
вне песочницы с полным правом записи. Поэтому поверх `/run` runner монтирует пустой tmpfs, как и
поверх `/tmp`. Абстрактные сокеты тесту недоступны: `--unshare-all` отделяет сетевое пространство
имён.

**Порядок проверок.** Runner проверяет идентификатор, затем настройки и зоны, затем хост: Linux,
`bwrap` в `PATH`, checkout и каталог запуска вне `/tmp`, `/run`, `/dev` и `/proc`, которые
песочница подменяет своими. Затем он создаёт каталог запуска и выполняет probe с тем же набором
монтирований. Probe требует трёх результатов: создание файла в корне checkout получает именно
`EROFS`, `/run` и `/var/run` пусты или отсутствуют, запись в `cache/` проходит. Оба артефакта probe
удаляются. Только после этого runner запускает тест. Если bwrap не сообщил `child-pid`, песочница
не поднялась, и результатом будет отказ `sandbox_failed`, а не провал теста. Diff-проверка файлов
защитой не служит, и runner её не выполняет.

**Локальные артефакты.** Каталог `.harness/.sandboxes/runs/isolated-test-<run_id>/` содержит
`log.txt` (stdout и stderr probe и теста, потолок 4 MiB с маркером обрезки; его пишет runner вне
песочницы), `cache/` и `reports/`. В песочницу монтируются только `cache/` и `reports/`. Старые
запуски удаляет `harness cleanup` по возрасту.

**Граница поддержки.** Поддержаны Linux и bubblewrap 0.9.0+ с непривилегированными
user-namespaces. На Windows и macOS runner отвечает `isolation_unavailable` с `platform`. Checkout
внутри `/tmp` или `/run` не поддерживается: тест его не увидит, и runner откажет с
`checkout_masked`. Если `/var/run` является отдельным непустым каталогом, а не ссылкой на `/run`,
runner откажет с `probe_failed`. Runner скрывает только сокеты в `/run` и `/tmp`. Сервис, который
слушает сокет в другом пути, видимом тесту (например, в домашнем каталоге), не должен по запросу
через этот сокет запускать процессы или писать файлы.
Поддержаны только зоны вида `<каталог>/**`: проект с тестами рядом с исходниками (например,
`**/*_test.go`) получит `write_zone_rejected`.

**Граница с другими компонентами.** Runner защищает checkout от процесса теста и его потомков, но
не от вызывающего агента вне песочницы. Субагента тест-автора ограничивает scoped guard
([test-author-guard](test-author-guard.md)), а включение проверяет
[test-author-preflight](test-author-preflight.md). Для preflight `--probe` даёт только статус
изоляции. Подготовку сборочных артефактов и отдельную тестовую БД описывает раздел ниже.

## 3. Контракты

- **Вход:** `run-test.sh <test-id>` или `run-test.sh --probe`; любые другие аргументы дают отказ
  `test_id_invalid`. Идентификатор соответствует `^[A-Za-z0-9_][A-Za-z0-9_.:/\[\]-]{0,199}$`
  (node id pytest, dotted id unittest): ведущий `-`, пробел, `;`, `$`, обратная кавычка и перевод
  строки отклоняются. Настройки: `test_paths` и `test_runner` из `.harness/project.json`.
- **Выход:** одна строка JSON не длиннее 512 байт с фиксированными ключами:
  - `test_id`: идентификатор или `null` для недопустимого;
  - `result`: `passed`, `failed`, `timeout` или `refused`;
  - `reason`: `test_passed`, `test_failed`, `timeout` или причина отказа;
  - `detail`: только для `isolation_unavailable`, иначе `null`;
  - `exit_code`: код теста или `null`;
  - `run_id`: hex-идентификатор каталога запуска или `null`.

  Вывод теста, абсолютные пути и переменные окружения в строку не попадают, stderr пуст.
- **Причины отказа (закрытый набор):**
  - `runner_unavailable`: нет Python, не загружается `.harness/health` или runner упал;
  - `test_id_invalid`: недопустимый идентификатор или лишние аргументы;
  - `config_invalid`: `project.json` нечитаем или поля не проходят проверку;
  - `test_paths_missing`, `test_runner_missing`: поле не задано;
  - `write_zone_rejected`: зона записи не прошла проверки;
  - `build_failed`, `build_timeout`: защищённая подготовка завершилась ошибкой или таймаутом;
  - `database_unavailable`: выбранному тесту не удалось подготовить отдельную БД;
  - `isolation_unavailable` с `detail`: `platform`, `bwrap_missing`, `checkout_masked`,
    `sandbox_failed` или `probe_failed`.
- **Коды выхода:** `0`, если тест прошёл; `1`, если тест упал или превысил таймаут; `3` при отказе,
  когда тест не запускался.
- **`--probe`:** проверяет существующий `project.json` и планы монтирований обеих фаз, но не
  выполняет сборку, сервер или тест. Без `project.json` остаётся только проверка хоста. Выводит
  `{"status":"ok"}` с кодом `0` или `status: unavailable` с кодом `3` и фиксированной причиной:
  причиной конфигурации или зоны, `isolation_unavailable` с `detail` или `runner_unavailable`.
  Каталог запуска probe удаляется.

## Источник

[run-test.sh](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/hooks/run-test.sh),
[isolated_runner.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/isolated_runner.py),
[project_files.py](https://github.com/PVMalove/agent-harness-next/blob/master/harness/health/project_files.py),
ADR 0014

### Сборка и тестовая БД

Необязательный `test_runner.build` содержит ровно `command` (непустой argv без `{test_id}`)
и `artifact_paths` (уникальные `<каталог>/**`). Каталоги заранее существуют и пусты. Runner
монтирует на эти пути свежие каталоги запуска: при сборке на запись, при тесте только на чтение.
Исходники и `test_paths` во время сборки доступны только на чтение; команда выполняется без
шелла внутри проверенной песочницы. Непустые каталоги runner отклоняет и не очищает.

Необязательный `test_runner.database` содержит ровно `engine`, `test_ids`, `command` и
`ready_command`. `engine` называет production-движок, `test_ids` задаёт уникальные селекторы
`fnmatchcase`. Только совпавшие тесты получают свежий экземпляр БД внутри песочницы, без TCP
и доступа к сервисам хоста. `command` запускает сервер в foreground, `ready_command` проверяет
готовность; обе команды задаются непустым argv без `{test_id}`. Они получают
`HARNESS_TEST_DATABASE_DIR` и `HARNESS_TEST_DATABASE_SOCKET_DIR` в приватном `/tmp`.
Проектный wrapper читает эти переменные напрямую; shell-подстановку в argv runner не выполняет.
SQL, транзакции и ограничения проверяют на production-движке; чистой доменной логике БД не нужна.

CLI добавляет эти группы только по полным наборам флагов `--test-build-command`,
`--test-artifact-path` и `--test-database-engine`, `--test-database-test-id`,
`--test-database-command`, `--test-database-ready-command`, вместе с `--test-runner-command`. Без
этих групп поведение прежнее. `test_paths` остаётся единственной зоной `Write`/`Edit` тест-автора.

Если подготовка вернула ненулевой код, runner отказывает с `build_failed`, при её таймауте с
`build_timeout`. Если сервер не запустился или не стал готов за 15 секунд, runner отвечает
`database_unavailable` и выбранный тест не запускает. Сервер, проверка готовности и тест работают в
одном изолированном окружении. Сервер и его потомки завершаются после теста или ошибки; внешний
таймаут runner ограничивает всю сессию БД вместе с тестом 300 секундами. Вывод всех команд
попадает в ограниченный локальный лог. Приватный канал результата helper недоступен дочерним
командам, поэтому вывод теста и его код 3 не могут подделать отказ БД.

Clean-room сценарий `scripts/clean_room/isolated_test_runner_build_db.py` вызывается существующим
сценарием runner и отдельно через `python -m scripts.clean_room.isolated_test_runner_build_db`.
Он проверяет настоящий C-компилятор и PostgreSQL (`postgres`, `initdb`, `psql`, `pg_isready` в
`PATH`): два свежих кластера, идентичность сервера, SQL, rollback, CHECK/PK и отсутствие TCP.
Если бинарников нет, сценарий явно отмечает, что доказательства нет.
`HARNESS_REQUIRE_TEST_DATABASE=1` делает отсутствие настоящей БД ошибкой;
`HARNESS_REQUIRE_TEST_SANDBOX=1` требует песочницу и компилятор. Подменные процессы в unit-тестах
проверяют только жизненный цикл и это доказательство не заменяют.

Сценарий `scripts/clean_room/fast_implement_route.py` прогоняет через тот же установленный runner
короткий маршрут `/fast-implement` со скриптованной заглушкой модели. Он проверяет цикл с автором
на согласованном seam, откат на обычный `/tdd` при упавшем hook, недоступной изоляции и проекте без
`test_paths`, а также отказы `build_failed` и `database_unavailable`, которые не считаются Red.
Сценарий не заменяет проверку на реальном Claude Code (`make test-author-probe`) и не измеряет
качество тестов, написанных моделью.
