# Миграция с 1.x на 2.0

Страница описывает переход проекта с Agent Harness Next 1.x на 2.0.0 и возврат на 1.x. Контракт
миграции и отката задаёт ADR 0020 «Переход operational state с файлового ledger на Rust SQLite WAL
store», разделы 1, 5 и 6.

## Что меняется

- **Rust runtime обязателен для оркестрации.** Operational state хранит runtime store
  `state/runtime.db`, а пишет в него только процесс `harness-runtime serve`. Недоступный runtime
  даёт `runtime_unavailable` и код 2.
- **`ledger.json` получает `version: 4`.** Его пишет `harness-runtime migrate` в точке фиксации
  cutover. После неё установка 1.x отказывает с кодом 2.
- **Coordinator 2.0.0 не работает на файловом ledger.** На `ledger.json` версий 1–3 он завершается
  с кодом 2, а remedy называет `harness-runtime migrate`.
- **Migrate и откат выполняет человек.** Обе команды требуют human approval. Агент их не запускает.

Проект без backend-оркестрации (нет `.harness/orchestration/state/`) не мигрирует: ему достаточно
`harness update`.

## Перед обновлением

1. Соберите `harness-runtime` (Rust 1.89+):
   `cargo build --release --manifest-path native/harness-runtime/Cargo.toml`.
2. Проверьте версию ledger в `.harness/orchestration/state/ledger.json`. `migrate` импортирует
   только версию 3. На версиях 1 и 2 он отказывает с кодом 2 и `protocol_unsupported`: сначала выполните
   `coordinator.py ledger migrate` установки 1.x, затем переходите к 2.0.
3. Завершите работу оркестрации. `migrate` отказывает с кодом 2 и ничего не меняет, если:
    - в QA-lane есть lease или очередь;
    - dispatch находится в `dispatched` или `working`. Дождитесь отчётов или переведите зависшие
      dispatch в `abandoned`;
    - ledger не проходит `coordinator.py ledger validate`;
    - в state-каталоге остался store прошлого отката (`AUTHORITY.json` называет `file-ledger`).
      `migrate` его не перезаписывает: архивируйте или удалите `runtime.db` и `AUTHORITY.json` сами
      и повторите команду.
4. Сохраните резервную копию каталога `.harness/orchestration/state/`. `migrate` сам делает снимок
   в `.harness/orchestration/state-snapshots/<utc>/`, но копия вне репозитория нужна для аварийного
   отката.

## Обновление

1. Обновите установку проекта:

    ```bash
    harness update <repo>
    ```

    `harness diff <repo>` заранее показывает изменения управляемых файлов, а `harness update` сохраняет
    локальные правки.

2. Проверьте установку:

    ```bash
    harness health <repo>
    ```

    `fail` в выводе нужно устранить до миграции. Часто health сам печатает команду исправления.

## Миграция state

Команду выполняет человек. Approval записывается в audit-цепочку store и в `AUTHORITY.json`.

```bash
harness-runtime migrate --repo <repo> \
  --approved-by <человек> \
  --approved-at <время RFC 3339> \
  --reason <причина>
```

Пустое поле approval, время не в формате RFC 3339 или из будущего — код 2 и `malformed_request`.
Approver с префиксом `policy:` — код 2 и `policy_denied`. Команда печатает одну JSON-строку, а
каждый отказ — строку `REMEDY:` с действием оператора.

| Код | Значение | Что делать |
| --- | --- | --- |
| 0 | Выполнено. Повтор после точки фиксации отвечает `already_cut_over: true` и ничего не меняет | Перейти к проверке |
| 2 | Отказ по approval или предусловию, состояние не изменено | Исправить причину из `REMEDY:` и повторить |
| 3 | Прервано после начала, частичный store удалён, authority осталась у файлового ledger | Повторить `migrate` или вернуться на 1.x |
| 4 | Нарушение инварианта: legacy-запись во время импорта или расхождение паритета. Authority осталась у файлового ledger | Разобрать причину из `REMEDY:` вручную, затем повторить `migrate` или вернуться на 1.x |

После кода 0:

```bash
harness health <repo>
```

## Запуск, остановка и перезапуск runtime

В Claude Code `serve` запускает hook `runtime-autostart` перед командой coordinator и
останавливает, когда runtime больше не нужен. Подробности — в разделе
[Автозапуск runtime](orchestration/operations.md#runtime-autostart). В Codex и на Windows
автозапуска нет: запустите `serve` вручную вне песочницы агента.

```bash
harness-runtime serve --repo <repo>
harness-runtime stop --repo <repo>
harness-runtime restart --repo <repo>
```

`stop` останавливает runtime тем же путём, что SIGTERM, и ждёт освобождения lock экземпляра до
30 с. `restart` выполняет `stop`, затем `serve` в том же процессе.

| Код | `stop` |
| --- | --- |
| 0 | `stopped` или `not_running`; повтор безопасен |
| 1 | Runtime не ответил или не отпустил lock за 30 с |
| 2 | Отказ, ничего не остановлено |

Runtime версии без операции `shutdown` один раз останавливают сигналом SIGTERM (на Windows —
Ctrl+Break), дальше работают `stop` и `restart`.

Полная таблица кодов и ответов — в разделе «Остановка и перезапуск» страницы
[Rust runtime](../architecture/runtime.md).

## Откат на 1.x

Откат возвращает state-каталог установке 1.x. Его тоже выполняет человек.

1. Остановите runtime: `harness-runtime stop --repo <repo>`. Работающий `serve` держит замок
   экземпляра, и откат отказывает с кодом 2 (`lease_held`). Пока идёт откат, не запускайте
   команды coordinator: в Claude Code автозапуск снова поднимет `serve`.
2. Дождитесь пустой QA-lane и завершения исполнений. Откат отказывает с кодом 2, если в QA-lane
   есть lease или очередь либо исполнение dispatch находится в `launching`, `running`, `stopping`
   или `unknown`. Dispatch в `dispatched` или `working` с остановленным исполнением экспортируется
   как есть.
3. Выполните откат:

    ```bash
    harness-runtime rollback --to-legacy --repo <repo> \
      --approved-by <человек> \
      --approved-at <время RFC 3339> \
      --reason <причина>
    ```

    Коды выхода те же, что у `migrate`. Повтор после завершения отвечает
    `already_rolled_back: true` с кодом 0, повтор после сбоя продолжает с последнего завершённого
    шага.

4. Верните проект на последний релиз 1.x — `v1.5.1`. В checkout harness переключитесь на тег
   `v1.5.1` (или распакуйте архив этого релиза из GitHub Releases) и выполните из него
   `python3 harness/bin/harness.py update <repo>`.
5. Проверьте state командой `coordinator.py ledger validate` установки 1.x. Успешная проверка
   завершает откат. Провал означает, что остаётся только аварийный откат снимком (ниже).

Что остаётся после отката:

- `ledger.json` снова имеет `version: 3`, а `AUTHORITY.json` — `authority: file-ledger`.
- Архив `state/runtime-export/<store_id>.tar` хранит audit-цепочку, operations и состояние QA-lane.
  Его sha256 записан в audit-записи `runtime-rollback` и в `AUTHORITY.json`.
- `runtime.db` остаётся read-only для разбора, версия его схемы не понижается.

## Аварийный откат снимком

Если `rollback --to-legacy` недоступен или `ledger validate` 1.x не принимает его результат,
state-каталог возвращают из резервной копии или снимка `state-snapshots/<utc>/`, сделанного
`migrate`. Команды для такого отката нет: его выполняют вручную и только с отдельного одобрения
владельца проекта, потому что он теряет всё, что runtime записал после cutover:

- batch, dispatch, отчёты, решения и approvals, созданные после миграции;
- audit-записи store, включая запись cutover;
- состояние QA-lane и исполнений.

Порядок:

1. Получите одобрение владельца и запишите его вместе с причиной там, где проект хранит решения.
2. Остановите runtime: `harness-runtime stop --repo <repo>`.
3. Перенесите текущий `.harness/orchestration/state/` в архив вне репозитория. `runtime.db` в нём не
   удаляйте: он остаётся единственной копией записей после cutover.
4. Скопируйте содержимое снимка или резервной копии на место `.harness/orchestration/state/`.
5. Верните проект на `v1.5.1` и выполните `coordinator.py ledger validate`, как в шагах 4 и 5
   обычного отката.

## Дальше

- [Восстановление](orchestration/recovery.md) — команды `recovery` для остановленного batch.
- [Troubleshooting](troubleshooting.md) — сообщения CLI, hooks и runtime.
- [Платформы](../project/platforms.md) — что проверяет CI на каждой платформе.
