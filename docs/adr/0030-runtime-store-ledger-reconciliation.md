# Operational store восстановления и сверка с authority lifecycle

**Статус: ACCEPTED (2026-11-06).** Тикет #685. Документ дополняет ADR 0020 (раздел 2), ADR 0021
(раздел 1) и ADR 0026 (раздел 1) и не повторяет их: он фиксирует, где хранятся записи
восстановления, кто принимает решения lifecycle и как восстановление сверяет одно с другим.

## Контекст системы

Batch может остановиться между подтверждёнными шагами: worker упал на следующем этапе, live
конфигурация стала невалидной, runtime перезапустился или строгое чтение отвергло запись batch.
Восстановлению нужны собственные durable записи: удержание batch (`operationalHold.v1`) и intent
прерываемой команды (`recoveryIntent.v1`). Ledger lifecycle при этом остаётся единственным
источником решений: принятые этапы, решения, approval и route.

Python store `runtimeState.v1` и durable intent из `integration/orchestration-system-fields` были
вторым writer operational state, поэтому ADR 0026 (раздел 1) заменил их Rust runtime store. Задача
#685 строит regression suite восстановления только на Rust store и командах `recovery`, а не на
этих модулях.

## Действующий контракт

### 1. Два вида записей, один writer

Записи восстановления (`recovery/hold/<batch_id>.json`, `recovery/intent/<batch_id>.json`) лежат
в том же Rust runtime store, что и записи lifecycle, но не являются частью lifecycle: удержание не
меняет состояние batch, решения и approval, а intent описывает только команду `recovery`. Решает обе
записи Python (`operational_hold`, `recovery_api`), пишет Rust store через `state.write` в единице
записи команды. Второго writer и второго хранилища нет.

Компромисс выбран сознательно. Отдельные записи позволяют удержать batch и завершить прерванную
команду, не придумывая переход lifecycle, которого человек не одобрял. Цена — обязательная сверка:
запись восстановления может расходиться с зафиксированным lifecycle, и восстановление обязано
обнаружить и разрешить это расхождение до любого действия.

### 2. Сверка при `recovery resume`

`recovery resume` повторяет все проверки в одной единице записи store и сверяет запись
восстановления с lifecycle:

- прерванная команда оставляет intent `interrupted`, и её повтор завершает действие;
- уже выполненный шаг повтор не выполняет снова: повторный `resume` возвращает пустой `steps`;
- принятый этап не запускается повторно: после сбоя следующего этапа, невалидной конфигурации или
  перезапуска runtime `resume` снимает удержание и называет следующий переход, но не создаёт
  dispatch;
- исполнение с неизвестным внешним эффектом отклоняется как `ambiguous-effect` и ждёт решения
  человека, второй worker не запускается;
- нечитаемая запись восстановления удерживает batch, но ни одна команда `recovery` её не снимает:
  нужен `ledger validate --full` и человек.

### 3. Граница гарантии

Восстанавливается только durable подтверждённая работа: lifecycle в ledger, принятые этапы с
закреплённым evidence, intent и удержание. Потерянный контекст модели, незакоммиченные файлы
worktree и неотправленный отчёт не восстанавливаются; exactly-once для внешних эффектов не
гарантируется.

### 4. Реестр словарей

Реестр `systemFields.v1` содержит только словари Rust store (ADR 0021, раздел 3). Словари
заменённого Python store (`runtime.state`, `runtime.operation_kind`, `runtime.operation_phase`,
`runtime.effect_state`, `runtime.failure_code`) в реестр не возвращаются.

## Операционные последствия

- `cargo test -p contracts` (`registry_drift.rs`) и `tests/orchestration/test_system_fields_contract.py`
  сверяют реестр с Rust и Python в обе стороны и падают, если словарь заменённого store вернулся или
  модуль `runtime_state_store`/`runtime_intent` появился в пакете.
- `tests/orchestration/recovery_regression_matrix.py` закрепляет закрытый список сценариев
  восстановления, а `test_recovery_regression.py` проверяет, что каждый сценарий указывает на
  существующий тест и что принятый этап не перезапускается.
- Clean-room сценарий `scripts/clean_room/recovery_regression.py` проверяет установленный payload:
  реестр совпадает с исходным, пример конфигурации canonical, `recovery --help` перечисляет
  `status`, `reload`, `resume`, `fix` и `abort`, модулей заменённого store нет.
