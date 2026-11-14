# Консолидация integration-веток Harness Next и Release Gate

**Статус: ACCEPTED (2026-10-20).** Эпик #784, ADR 0019–0024. Документ определяет, какие
integration-ветки входят в `integration/harness-runtime-reliability`, какие их части заменяет
Harness Next и какое evidence разрешает влить кандидата в целевую ветку.

## Контекст системы

Работа Harness Next собрана из четырёх integration-веток, которые отходили от `master`:
`integration/orchestration-ledger`, `integration/container-executor`,
`integration/orchestration-system-fields` (эпик #681) и `integration/console-redesign`.
ADR 0019–0024 учитывали только первые две. Python store `runtimeState.v1` из
`integration/orchestration-system-fields` — второй writer operational state, который запрещают
ADR 0020 и ADR 0021.

PR в integration-ветки и релизы вливаются squash-merge (так влиты #785 и релиз 1.5.1 #755).
Поэтому SHA коммита в целевой ветке никогда не равен SHA кандидата, на котором прошёл QA.

## Действующий контракт

### 1. Что входит в Harness Next

Все четыре ветки входят в `integration/harness-runtime-reliability` и выходят в `master` только
релизом 2.0.0 (ADR 0020, раздел 6). В Harness Next входит только то, чем по матрице authority
ADR 0021 владеет Python и что не пишет operational state:

- `integration/orchestration-ledger`, `integration/container-executor` и
  `integration/console-redesign` входят целиком. Правило #780 выполняет fencing QA-lane
  (ADR 0020, раздел 3). Границей движка владеет Rust (ADR 0022).
- Из `integration/orchestration-system-fields` входят реестр `systemFields.v1`, normalizer
  конфигурации и pinned configuration snapshot (#690).
- Python store `runtimeState.v1`, durable intent, reconcile и effect (#699, #701, #703), а также
  доработки файлового ledger (#712, #728, #735) имеют статус Superseded-by-Harness-Next. Их
  критерии выполняют Rust store (ADR 0020), идемпотентность (ADR 0021, раздел 4) и reconcile
  (ADR 0022, раздел 5). Repair импорта заменяет quarantine неизвестных значений, audit-цепочка
  store заменяет цепочку хэшей (ADR 0020, разделы 4–5).
- Recovery policy (`recovery_api.py`, `operational_hold.py`) остаётся на Python и работает поверх
  Rust store; Rust заменяет только store (#746). Тесты заменённых коммитов служат
  acceptance-сценариями store, supervisor и recovery.
- Критерии #685 (canonical CI) остаются: CI проверяет реестр против Python и Rust (ADR 0021,
  раздел 3).

Реестр `systemFields.v1` не содержит словарей Python store: `runtime.state`,
`runtime.operation_kind`, `runtime.operation_phase`, `runtime.effect_state`,
`runtime.failure_code`. Они несовместимы с состояниями и кодами ADR 0021 (разделы 3–4). Словари
Rust runtime реестр получает по ADR 0021, раздел 3.

Модуль, который пишет operational state или читает `runtime_state_store`/`runtime_intent`, в
Harness Next не входит.

### 2. Процедура импорта

Все четыре источника импортированы. Номер 0025 принадлежит контейнерному исполнителю
(`0025-container-executor.md`), а номер 0018 принадлежит `0018-ci-windows-subset.md`. Исходные
integration-ветки не переписываются; force push запрещён.

### 3. Тикеты Harness Next

Дочерние тикеты #784 создаются от `integration/harness-runtime-reliability` и направляют PR в неё
(`Related to #<ID>`).

### 4. Release Gate

Решение владельца D4 («tree SHA при неизменной базе») реализуется так: evidence привязан к паре
коммитов, а дерево подтверждает, что squash-merge не изменил проверенное содержимое. Release Gate
расширяет существующую проверку пары `integration next --pull-request <n>`
(`harness/orchestration/workflow/integration.py`): пара `{candidate_sha, target_sha}`, источник QA
`original-qa`, `local-qa` или `ci` и обязательная новая проверка при новом `target_sha`.

- Пару подтверждает только полный прогон `qa_gate_commands`: clean-room QA (ADR 0023, раздел 5)
  или CI, принятый `integration collect-ci` для этой же пары. Focused-, failed-only- и
  кэшированные результаты пару не подтверждают.
- Запись пары дополнительно хранит `candidate_tree_sha` (`git rev-parse <candidate>^{tree}`).
- Запись пары контракта 2 дополнительно хранит `selection` — выбор тестов, который требуется от QA
  этой пары: `full` или `ticket-diff`. Значение один раз решает писатель пары в Python по цели пары
  и замороженному в batch флагу `ticket_diff_selection` (ADR 0023, раздел 7): `ticket-diff` — только
  для цели `integration/*` при включённом флаге, иначе `full` (цель — ветка по умолчанию, флаг
  выключен или batch без политики). Запись неизменяема и создаётся один раз; повторная запись той
  же пары возвращает сохранённую запись и не понижает `ticket-diff` до `full`. Запись контракта 1
  (пять полей, без `selection`) остаётся допустимой и читается как `full`.
- `qa.evidence.verify` берёт требование только из сохранённой записи пары. Запрос по-прежнему
  `{candidate_sha, target_sha}`: поля `requirement` в нём нет, любое лишнее поле — `malformed_request`,
  поэтому клиент не может запросить более слабую проверку. Для записи контракта 2 со `selection`
  `ticket-diff` пару подтверждают и стадии `full`, и стадии `ticket-diff`, а pytest-стадия без
  тестов в diff (`not_run`, id `no-tests-in-diff...`, без кода выхода и node id) не нарушает вердикт.
  Для любой другой пары — `full` из записи, запись контракта 1, отсутствующая запись или неизвестное
  значение — стадия `ticket-diff` даёт `selection_not_full` (проверка закрывается в сторону `full`).
  Стадии `focused` и `failed-only` не подтверждают пару никогда.
- Push ветки разрешён, только если её голова равна `candidate_sha`.
- Merge в целевую ветку разрешён, только если её текущая голова равна `target_sha` пары и входит
  в историю кандидата. Тогда squash-merge даёт дерево, равное `candidate_tree_sha`.
- После подтверждённого merge `to-pull-requests` сверяет дерево нового коммита целевой ветки с
  `candidate_tree_sha`. Расхождение — блокер: следующий merge от этой ветки требует нового полного
  QA на её голове.
- Если целевая ветка ушла вперёд, кандидат обновляется merge-ем целевой ветки; это новая пара и
  новый полный прогон.
- Релиз 2.0.0 — тот же контракт для PR `integration/harness-runtime-reliability` → `master`.
- После cutover запись пары хранит Rust store (ADR 0021, раздел 1); решение о merge остаётся у
  человека, а проверку пары — у Python.

#### Поправка 2026-11-07 (#938): раздел 4 и политика тестов тикета

- **Требуемый выбор.** Пара в `integration/*` при включённом флаге `ticket_diff_selection` (ADR 0023,
  раздел 7) подтверждается стадиями `ticket-diff`, а пара в ветку по умолчанию — только полным
  прогоном (`full`). Полный CI пары принимает `integration collect-ci`; задание `verify-light` пару с
  выбором `full` не подтверждает (причина `light_check`), и тогда остаётся запасной полный локальный QA.
  Падение полного прогона перед `master` чинят fix-тикеты с базой в integration-ветке.
- **Решения #812.**
  - **D2.** Запись пары создают `dispatch publish`, `integration prepare` и refresh. `integration next`
    запись только читает.
  - **D4.** `qa.evidence.verify` спрашивается только в эпохе runtime store. В эпохе file-ledger
    действуют Python-проверки Git пары (голова цели, `candidate_tree_sha`, источник QA).
- Сверка дерева после squash-merge остаётся для каждого merge, в том числе для пары в `integration/*`.

## Операционные последствия

- **Approval.** Merge каждого PR выполняет человек; auto-merge запрещён.
- **Негативные проверки Release Gate:** голова целевой ветки ушла вперёд после QA → merge отказан;
  дерево после squash-merge не равно `candidate_tree_sha` → блокер; QA на SHA, отличном от головы
  push → push отказан; CI, привязанный вручную без `integration collect-ci`, пару не подтверждает;
  стадии `ticket-diff` для пары в ветку по умолчанию или при выключенном флаге → `selection_not_full`.
  Сверка дерева после squash-merge остаётся для каждого merge, в том числе для пары в `integration/*`.
