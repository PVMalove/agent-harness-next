# Замер производительности 2.0: команды coordinator на runtime store

Замер «после» для эпика Harness Next (#784). Замер «до» лежит в
[`../1.x-baseline/methodology.md`](../1.x-baseline/methodology.md). Здесь приведены только числа
из файлов `raw/`. Метрика, которую не удалось измерить, помечена `нет данных`.

## Что измерено

- **Код:** ветка `feature/issue-1144-pr787-review-fixes` поверх
  `integration/harness-runtime-reliability` (задача #1144), 2026-11-13. Бинарник `harness-runtime`
  собран из того же дерева дважды: `cargo build` (debug) и `cargo build --release`.
- **Окружение:** Linux 6.8 x86_64, 8 CPU, Python 3.12.3 — тот же хост, что у замера 1.x.
- **Данные:** побайтовая копия runtime store этого репозитория (`runtime.db`, `ledger.json`,
  `AUTHORITY.json`, `teardown.json` исполнений), снятая при остановленном runtime: 116 batch,
  694 dispatch, 1164 audit-записи. Это в 2,6 раза больше dispatch, чем в замере 1.x (44 batch,
  267 dispatch, 5044 audit-записи файлового ledger).
- **Инструмент:** `tests/orchestration/test_runtime_store_measure.py`. Тест копирует store во
  временный каталог, поднимает настоящий `harness-runtime serve` и запускает каждую команду
  30 раз как отдельный процесс CLI. Перцентили — nearest-rank, как в замере 1.x.

## Как воспроизвести

```bash
HARNESS_MEASURE_STATE_DIR=<копия state при остановленном runtime> \
HARNESS_RUNTIME_BIN=<путь к harness-runtime> \
HARNESS_MEASURE_RUNS=30 \
HARNESS_MEASURE_OUT=docs/perf/2.0-runtime/raw/<файл>.json \
.harness/.venv/bin/python -m pytest -q -p no:cacheprovider \
  "tests/orchestration/test_runtime_store_measure.py::test_dispatch_status_before_and_after_the_cutover_is_within_its_budget"
```

## Результаты

Секунды, 30 прогонов на команду. Бюджет — ADR 0020, раздел 3, по p95.

| Команда | 1.x, p50 | 2.0 debug, p50 / p95 | 2.0 release, p50 / p95 | Бюджет p95 |
| --- | --- | --- | --- | --- |
| `dispatch status` | 269,1 | 2,808 / 2,862 | 0,887 / 0,924 | 2,0 |
| `dispatch status --batch` | нет данных | 0,330 / 0,374 | 0,253 / 0,283 | 0,5 |
| `dispatch heartbeat` | 4,44 | нет данных | нет данных | — |
| `ledger validate` | 69,9 | нет данных | нет данных | — |

- `dispatch status` на release-сборке быстрее 1.x примерно в 300 раз при в 2,6 раза большем
  числе dispatch и укладывается в бюджет.
- На debug-сборке бюджет `dispatch status` не выполнен: 2,862 с при 2,0. Профиль показывает, что
  почти всё время уходит на `state.read dispatches` в runtime (кадр 14,4 МБ, 1,8 с на debug и
  0,3 с на release). Python-сторона занимает около 0,4 с, из них импорт coordinator — 0,2 с.

## Что изменено перед замером

- `dispatch status` держит одно соединение с runtime на всю команду, а чтения одного снимка store
  идут по одному соединению: число `hello` на команду упало с 6 до 2.
- Телеметрия batch группируется по dispatch один раз, а не для каждой записи.
- Копия store в тесте замера переносит `teardown.json` завершённых исполнений. Без него runtime
  копии на каждом `execution.observe` заново удалял 14 завершённых QA-контейнеров, и замер
  завышался примерно на 0,6 с.

## Риски

- Ответ `state.read dispatches` занимает 14,4 МБ — 86 % лимита кадра IPC (16 МиБ). При среднем
  размере записи около 20,7 КБ ещё примерно 115 dispatch, и `dispatch status` без `--batch` перестанет
  помещаться в кадр. Устраняет проекция полей в `state.read`: самой команде нужно около 8 полей
  dispatch и 3 поля batch.

## Чего нет в этом замере

- `dispatch heartbeat`, `ledger validate`, `ledger status`, `batch list`, `qa status` на store.
- Полный `make verify`, focused- и failed-only-прогоны: песочница сессии замера не даёт писать в
  `.harness/.sandboxes` основного checkout. Ожидание после параллельного clean-room — оценка, а не
  замер.
- Длительность `/implement` и число полных прогонов на 2.0: нужна история batch после cutover.
