# Роль rebaser: перенос кандидата на сдвинутую базу без повторного code-review

## Контекст системы

Пока batch идёт по конвейеру, `origin/<integration_ref>` может уйти вперёд от закреплённого
`integration_base_commit`. ADR 0012 переносит кандидата только внутри developer-retry
(`rebase-fix-forward`): сессия developer-а тратит `retry_policy.max_developer_retries`, затем
кандидат снова проходит code-review, хотя код ревьюера не менялся. Если база сдвинулась после
принятого review и до QA, у `approval_policy: auto` нет автоматического маршрута: нужен ручной
rewind, лишний QA на старой базе и retry, после которого batch навсегда выходит из `auto`.
`integration refresh` (ADR 0014) перебазирует ветку только после publish, а `conflict-resolver`
(ADR 0015) работает в отдельном resolver-batch. Нужен узкий перенос внутри batch до publish, который
не тратит developer-бюджет и не повторяет review.

## Действующий контракт

- **Роль.** `rebaser` — write-роль (`required_capabilities: conflict-resolution`, та же capability, что
  у `conflict-resolver`, поэтому существующие `provider_profiles` остаются валидными). Модель и
  усилие задаются отдельно в `assignment_plans.rebaser`. Роль переносит коммиты кандидата на
  `rebase_target_commit` (`git rebase --onto`), сохраняет их порядок, заголовки и сопоставление с
  commit plan, перегенерирует сгенерированные файлы генераторами репозитория внутри того коммита,
  которому они принадлежат, и не вносит новой функциональности. Новых коммитов, кроме перенесённых
  копий, нет.
- **Доступность.** Маршрут `rebase` предлагается, только если манифест роли установлен и роль
  назначаема: в конфиге без `assignment_plans` (zero-config) или с записью `assignment_plans.rebaser`.
  Иначе остаётся `rebase-fix-forward` из ADR 0012.
- **Когда маршрут `rebase`.** Coordinator вычисляет его сам; `route_preview` показывает его до решения.
  - Accept отчёта code-review или QA, когда `origin/<integration_ref>` ушёл вперёд от
    `integration_base_commit`, кандидат не содержит нового tip и accept не переносит incomplete items:
    `next_action` становится `rebase` вместо `qa` или `publish`. Routing record решения несёт
    `route: rebase`, `rebase_target_commit` и `integration_base_commit`; `route_preview.accept`
    показывает его заранее.
  - Retry отчёта code-review, QA или publish с `reason_category: candidate-change` без carried items
  при сдвинутой базе: `route: rebase`, `next_action: rebase`.
  - Retry с carried items, с дефектом кода или retry developer-отчёта остаётся `developer-retry`,
    `fix-forward` или `rebase-fix-forward`.
- **Бюджет и approval.** `rebase` не тратит `retry_policy.max_developer_retries`. Dispatch rebaser
  пересекает веху `rebase-target`: под любой политикой, кроме `auto`, его утверждает человек с digest
  транзиции, в `auto` веха снимается и записывается в `lifted_milestones`. Цикла нет: маршрут
  предлагается, только пока кандидат не содержит tip, а принятый rebase закрепляет tip как новую базу.
- **Brief.** Цель привязана к транзиции как `rebase_target_sha` и лежит в brief как
  `rebase_target_commit`; `snapshot_commit` — принятый кандидат. Секция `rebaser` перечисляет
  `previous_base_commit` (`git merge-base` кандидата и цели) и `previous_commits` — коммиты, которые
  нужно перенести.
- **Отчёт.** Completed-отчёт rebaser обязан нести верхнеуровневый блок `rebase_check`:
  `rebase_target_commit`, `previous_base_commit`, `rebased` (`rebased_from`, `commit_sha`,
  `patch_id_match`), `dropped` (`rebased_from`, `dropped` с причиной), `patch_id_mismatches`,
  `resolved_conflicts`, `generated_files` и `range_diff`. Coordinator сам пересчитывает пары по
  `git patch-id --stable` и отклоняет отчёт, если:
  - блока нет или он расходится с пересчётом;
  - какой-то коммит прежнего кандидата не учтён ровно один раз или есть коммит, который не является
    перенесённой копией;
  - у пары с несовпавшим patch-id меняется файл вне `resolved_conflicts` и `generated_files`;
  - при несовпавшем patch-id нет `range_diff`.
  Блок `rebase_check` у других ролей запрещён.
- **Контроль после конфликта (ответ на открытый вопрос #1010).** Отдельного review нет. Если patch-id
  хотя бы одной пары не совпал, отчёт прикладывает вывод
  `git range-diff <previous_base_commit>..<snapshot_commit> <rebase_target_commit>..<commit_sha>`
  как `range_diff`; он остаётся evidence решения. QA нового кандидата обязателен в обоих случаях.
- **После accept.** Accept отчёта rebaser закрепляет `integration_base_commit` на цели, пишет в batch
  связь `rebases[]` (dispatch, прежний и новый кандидат, цель, прежняя база, `rebase_check_sha256`) и
  ставит `next_action: risk-assessment`. Risk assessment нового кандидата считается от новой базы.
  Ранее принятое code-review прежнего кандидата покрывает новый кандидат, если его триггеры
  включают все новые: тогда `next_action` становится `qa`, повторного review нет.
- **Остановка.** Конфликт, который требует решения по смыслу, rebaser не решает: отчёт
  `outcome: blocked` с `blockers.details`. Retry такого отчёта с причиной, названной человеком
  (`code`, `requirements`), ведёт в developer-retry по маршруту `rebase-fix-forward` на текущий tip
  `origin/<integration_ref>`; QA не запускается, пока новый кандидат не принят. Под `auto` такой
  отчёт без структурной причины останавливает автоматический путь (`unknown-reason`): решение по
  смыслу принимает человек. Операционный сбой rebaser-а (`transport`, `tooling` и другие
  операционные причины) повторяет тот же rebase на ту же цель (`same-candidate-rerun` или
  `tooling-retry` с `next_action: rebase`). `conflict-resolver` остаётся маршрутом для batch после
  publish (ADR 0015).
- **Связь с ADR 0012 и 0014.** ADR 0012 по-прежнему действует для retry с исправлением кода; правило
  «rebase утверждает только человек» уточняется так же, как для `rebase-fix-forward`: `auto`
  утверждает его по политике. ADR 0014 не меняется: `integration refresh` остаётся финальным
  обновлением при подготовке PR, а сдвиг после publish закрывают refresh или resolver.

## Операционные последствия

- `RECOVERY_ROUTES` получает `rebase`; Python-словарь и `vocabulary.rs` runtime store меняются вместе.
  Store, собранный до этого изменения, отклоняет routing record с `route: rebase`, поэтому
  `harness-runtime` пересобирается вместе с обновлением harness.
- `NEXT_ACTION_DISPATCH_ROLE` получает `rebase → rebaser`; `system_fields.v1.json` описывает новые
  значения.
- `integration prepare` после publish сверяет пару с закреплённой базой: batch, перенесённый этим
  маршрутом, записывает пару без отказа `_verify_unmoved`.
- Ledger schema не меняется: связь лежит в batch как `rebases[]`, routing — в существующем поле
  решения.
- Проект, который назначает роли явно, получает маршрут только после добавления
  `assignment_plans.rebaser`.
