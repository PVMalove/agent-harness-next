# Runtime store нового проекта без файловой эпохи ledger

**Статус: PROPOSED (2026-11-13).** Тикет #1146, эпик #784. Для проекта без состояния
оркестрации документ заменяет два места ADR 0020. Первое — правило раздела 1 «Эпохи authority и
единственный writer»: до cutover Python пишет файловый ledger. Второе — предусловие раздела 5:
`migrate` нужен любому проекту. Для существующего ledger 1.x ADR 0020 не меняется.

## Контекст системы

Спека #784 требует одного writer-а operational state — Rust runtime — и запрещает Python
fallback-writer. До #1146 coordinator на проекте без `.harness/orchestration/state/ledger.json`
сам создавал файловый ledger версии 3: `LifecycleLedger.ensure()` при `batch create` и
`LifecycleLedger.reset()` при `ledger reset`. Получить store новый проект мог только через
`harness-runtime migrate`, а `migrate` на пустом состоянии отказывает с `nothing_to_migrate`.
Поэтому каждый новый проект проходил файловую эпоху и cutover.

Ограничения действующих ADR:

- первая запись audit-цепочки store — `legacy-import` с human approval, которое `validate --full`
  сверяет с `AUTHORITY.json` (ADR 0020, раздел 4);
- Rust не создаёт approval (ADR 0021);
- `serve` запускает hook автозапуска без участия человека (ADR 0031).

## Действующий контракт

### 1. Команда `harness-runtime init`

```text
harness-runtime init --repo <repo> --approved-by <human> --approved-at <RFC 3339> --reason <text>
```

Команда создаёт runtime store проекта без состояния оркестрации одной операцией с human
approval:

1. Approval проверяется первым, той же `approval::check`, что у `migrate`: все три поля
   обязательны, approver с префиксом `policy:` получает `policy_denied`, время — RFC 3339 не в
   будущем. Агент `init` не выполняет.
2. Предусловие: в state-каталоге нет `ledger.json` и нет каталогов записей файлового ledger.
   Иначе код 2 без изменений, remedy — `harness-runtime migrate`.
3. Под legacy-замком (`owner.json` с `operation: runtime-init`) команда создаёт
   `runtime.db.importing` по текущей схеме. В него записываются `store_meta` (`store_id`,
   `selected_generation`, `manifest_sha256`) и якорь audit-цепочки.
4. Фиксация — та же, что у `migrate`: rename в `runtime.db`, `AUTHORITY.json`, затем
   `ledger.json` `{"version": 4, "generation": "generation-<hex8>", "selected_at": …}`. Точка
   фиксации — rename указателя. До неё любой сбой удаляет частичный store, и повтор начинает
   заново.
5. Повтор на проекте в эпохе store возвращает 0 и `already_initialized: true` без записи.

Коды выхода — как у `migrate`: 0 — выполнено или уже выполнено; 2 — отказ по approval или
предусловию без изменений; 3 — прервано после начала, частичный store удалён; 4 — нарушение
инварианта.

### 2. Якорь audit-цепочки

Якорь — запись `legacy-import` с пустым манифестом:
`{"generation", "manifest_sha256": <sha256 пустого манифеста>, "files": 0, "approved_by",
"approved_at", "reason"}`. Store нового проекта неотличим по форме от store, импортированного из
пустого ledger. Поэтому `audit::verify`, `validate --full`, откат `rollback --to-legacy` и
проверка approval якоря работают без изменений.

Отдельный action `store-init` отвергнут: он требует новых правил в `audit::verify` и
`validate --full`, а смысла не добавляет — `files: 0` уже говорит, что импортировать было нечего.

### 3. `serve` store не создаёт

`serve` на проекте без store запускается, как и раньше, но отвечает на `state.read` и
`state.write` отказом `not_found`. Создавать store при старте `serve` нельзя: hook
автозапуска (ADR 0031) запускает его без человека, а якорь store требует human approval.

### 4. Когда допустима файловая эпоха и когда coordinator отказывает

- **Проект без состояния оркестрации** — нет store, нет `ledger.json`, нет записей файлового
  ledger. Ни одна команда coordinator не создаёт ledger версий 1–3. `batch create`, `batch plan`,
  цель консоли `batch-create` и `ledger reset` завершаются с кодом 2: `ERROR:` называет причину,
  а `REMEDY:` даёт строку `harness-runtime init --repo <repo> …` и запуск `serve`. Отказ
  происходит до записи снимка runtime и до legacy-замка, поэтому state-каталог не меняется.
- **Существующий ledger 1.x** (`version ∈ {1,2,3}`) — файловая эпоха допустима до `migrate`, как
  описывает ADR 0020. Python пишет только такой ledger.
- **Эпоха store** — без изменений (ADR 0020, 0021).

Python-примитивы создания поколения (`_new_generation`, `_select`) вызываются только для
существующего ledger: `ledger migrate` 1.x → 3 и `ledger reset` с указателем. Тесты миграции
получают ledger 1.x из `tests/orchestration/legacy_state.py` — это единственный источник
файлового ledger в тестах.

### 5. Тесты coordinator на runtime store

Тест, которому нужно состояние нового проекта, получает store так же, как проект:
`tests/orchestration/runtime_store_support.py` один раз на процесс выполняет `harness-runtime
init` для эталона (`store_template`), а каждый тест копирует `runtime.db`, `AUTHORITY.json` и
`ledger.json` в свой repo и запускает свой `serve` (`serve_new_project`,
`serve_new_project_for` для `unittest`). Центральная фикстура `CoordinatorRetryRoutingTests`
работает на store по умолчанию. Записи тест читает из снимка store в обычном каталоге
(`StoreRecords`): один `state.read` всех коллекций и текстовые артефакты из `runtime.db` только на
чтение.

На ledger установки 1.x из `tests/orchestration/legacy_state.py` (`seed_file_ledger`, отметка
`@file_ledger_source`, атрибут `file_ledger` фикстуры) остаются тесты шести видов:

1. Тесты, которые доходят до publish или Release Gate. В эпохе store publish требует полного
   QA-прогона, записанного runtime, а фикстуры только кладут отчёт QA.
2. Тесты самого файлового ledger: файлы поколения, audit-файлы, замок, `ledger migrate|reset|clean`,
   файловая QA-lane.
3. Тесты, которые правят файлы записей или вносят записи, нарушающие внешние ключи и CHECK store.
4. Тесты конкуренции за файловый замок.
5. Тесты, у которых state-каталог вне repo — суть проверки.
6. Тесты синхронного запуска адаптера `dispatch send --adapter` (receipt адаптера, его старт и
   выход). В эпохе store внешний dispatch запускает и ведёт supervisor runtime (ADR 0022), так что
   этого пути там нет по замыслу.

Каждый такой выбор помечен в коде комментарием с номером вида. Перевод тестов publish на store с
настоящим QA-прогоном — отдельная задача.

Один общий `serve` на сессию отвергнут. Сокет `serve` привязан к repo (`repo-id` — sha256
common git dir), а у тестов разные временные repo. Замер: старт и остановка `serve` — около 10 мс,
`init` — около 0,23 с, копия эталона — единицы миллисекунд. Свой `serve` на тест дешевле подмены
store под общим процессом и сохраняет изоляцию тестов.

Перевод выявил задержку `serve`: цикл accept спал 25 мс между проверками неблокирующего сокета,
поэтому каждый запрос клиента ждал до одного такта. Теперь цикл ждёт соединение через `poll(2)` с
тем же таймаутом и принимает его сразу, а флаг остановки проверяется не реже, чем раньше. Запрос
`state.read` на пустом store занимает около 3,4 мс вместо 25 мс.

Тесты на runtime используют Unix-сокет и на Windows пропускаются.

## Операционные последствия

- Новый проект — один шаг человека после `harness init`: `harness-runtime init` с approval. Skills
  `start-project` и `integrate-project` показывают команду человеку, а не выполняют её.
- `harness health` на проекте без состояния оркестрации отвечает `warn` с командой
  `harness-runtime init`.
- Remedy `migrate` на пустом состоянии (`nothing_to_migrate`) ведёт к `harness-runtime init`.
- Тест `tests/orchestration/test_runtime_store_init.py` закрепляет: на проекте без
  `ledger.json` `batch create` и `ledger reset` не создают ledger и не меняют state-каталог, а
  после `init` `batch create` пишет в store.
