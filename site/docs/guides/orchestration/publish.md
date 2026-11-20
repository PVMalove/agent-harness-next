# Публикация и PR

Принятый publish завершает pipeline для candidate. Подготовка PR отдельно сверяет integration-ветку и доказательства проверки. Для открытия PR нужно подтверждение, merge выполняет человек.

[Обзор оркестрации](../../backend-orchestration.md)

## Integration accounting после publish {#integration-accounting-publish}

Завершённый batch остаётся историей: его не переоткрывают и не переписывают. Следующему шагу
интеграции нужна связь: тикет, issue-ветка, исходный batch, опубликованный candidate SHA и target
SHA integration ref. Её хранит отдельная неизменяемая запись, Integration record. Создаёт и читает
её группа команд `integration`. Ни одна из этих команд не пишет batch, plan, dispatch и reports.
Git меняет только `refresh` (см. ниже):

```bash
python .harness/orchestration/coordinator.py --repo . integration prepare \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration status \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration link-evidence \
  --record <integration_record_id> --kind ci --result passed \
  --candidate-commit <sha> --target-commit <sha> --reference <run-url> [--artifact-sha256 <hex>]
```

`prepare` запускают после accepted publish и до merge или удаления ветки. Команда выбирает
единственный завершённый batch с accepted publish для пары тикет и ветка. Опубликованный SHA она
сверяет двумя независимыми способами:

- по принятому отчёту publish (digest отчёта и brief);
- по `ls-remote`: ветка на remote указывает ровно на candidate, integration ref ровно на
  закреплённый target.

Evidence команда берёт из accepted green QA того же SHA. Ответ содержит `integration_record_id`,
пару `candidate_sha`/`target_sha` и ссылки по digest на исходные QA и publish. Повторный `prepare`
не создаёт вторую запись и не теряет первую (`created: false`). Отказ всегда содержит remedy.
`prepare` отказывает, если:

- для тикета и ветки не найден batch;
- `--batch` относится к другой паре;
- batch не завершён или не опубликован;
- опубликованных batch несколько, а `--batch` не задан (один batch другим не подменяется);
- `--candidate-commit` не равен опубликованному SHA;
- remote-ветки нет или она указывает на другой SHA;
- нет accepted green QA;
- integration ref уже ушёл вперёд, а записи ещё нет;
- remote недоступен;
- история batch изменилась после записи.

Запись лежит в `reports/integration/`, evidence лежит в `reports/integration-evidence/`. Оба
каталога находятся внутри `reports`, который coordinator уже проверяет, поэтому версия схемы ledger
и `ledger migrate` не меняются.

`status` только наблюдает и работает под тем же read-only контрактом. Он не создаёт dispatch,
ничего не записывает и при повторе даёт тот же ответ. Состояния:

- `current`: integration ref всё ещё на записанном target;
- `stale`: ref ушёл вперёд, `refresh_required: true`;
- `unavailable`: remote не ответил, подтвердить пару нельзя.

Исходное QA относится только к записанной паре. При `stale`
`source_evidence.applies_to_current_pair` равен `false`, и старое QA не засчитывается новой паре
candidate/target. `status` сам ничего не запускает. Обновить пару при `stale` можно через
`integration refresh` (см. ниже). После refresh `status` показывает текущую пару (`candidate_sha`,
`target_sha`, исходные значения в `original_candidate_sha`/`original_target_sha`), список
`refreshes` и блок `verification`. В нём `required: true`, пока нет passed CI или local-QA именно
этой пары (`resolver` не считается), и всегда `re_review_required: false`.

`refresh` готовит PR после сдвига базы без обязательного перезапуска developer:

```bash
python .harness/orchestration/coordinator.py --repo . integration refresh \
  --ticket '#123' --branch feature/issue-123-short-name
```

Команда читает текущий SHA integration ref. Если он равен target пары, команда не запускает rebase
и ничего не пишет (`state: unchanged`). Иначе она перебазирует issue-ветку в worktree своего batch
на этот SHA и пушит ветку через `--force-with-lease` с ожидаемым старым SHA. Так чужой коммит на
remote не теряется. Команда отказывает с remedy, если:

- worktree не на issue-ветке или не на записанном candidate;
- в worktree есть незакоммиченные изменения или незавершённая операция;
- remote-ветка уже не равна записанному candidate.

Команда не делает stash и reset, ничего не обходит, не пишет в protected-ветки и ветки
`integration/*` и не трогает чужие worktree.

Чистый rebase возвращает `state: rebased`, `new_candidate_sha` и `verification_required: true`. Он
не вызывает resolver и не тратит его два цикла. Текстовый конфликт возвращает `state: conflict` и
блок `resolver` (`conflicting_files`, `candidate_sha`, `target_sha`, `worktree`, `cycles_spent: 0`).
Rebase при этом отменяется, ветка и worktree остаются как были. После rebase команда пишет
неизменяемую запись `IntegrationRefreshRecord` в `reports/integration-refresh/`: прежний и новый
candidate, target, коммиты до и после. Старое QA остаётся историческим evidence. Новый candidate
подтверждают CI или local-QA пары через `link-evidence`. Повторный review из-за refresh не нужен.
Конфликт и работу, которой нужен developer, ведёт маршрут rebase из ADR 0012, и `refresh` от него
не зависит.

`resolve` открывает маршрут текстового конфликта (роль `conflict-resolver`, ADR 0015). Команда
ничего не пишет в Git и отклоняет чистый rebase, потому что это работа `refresh`. Для конфликта она
создаёт новый batch вида `resolver` рядом с завершённым batch тикета. Brief, отчёты и история
завершённого batch не меняются:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolve \
  --ticket '#123' --branch feature/issue-123-short-name
```

Ответ содержит `batch_id`, конфликтные файлы, candidate и target SHA, scope и остаток бюджета.
`next_action` нового batch равен `resolve-conflict`. Дальше путь обычный: `batch approve`, затем
`dispatch create --role conflict-resolver --purpose work` (сначала с `--propose`). Brief содержит
неизменяемую секцию `resolver`:

- тикет;
- требования обеих сторон: `sides.candidate` берёт DoD исходного batch, `sides.target` берёт
  plan-записи тикетов `(#N)` из subject коммитов цели, а без них subject и тело коммита;
- SHA candidate и target, scope, запреты, план коммита, проверки, остаток бюджета и
  `report_staging_path`.

Роль открывает скилл `resolving-merge-conflicts`, сохраняет требования обеих сторон и не добавляет
функциональность сверх них.

Бюджет составляет два автоматических target SHA. Для третьего нужно решение человека. Цикл тратит
только зафиксированный отчёт resolver по новому target SHA. Чистый rebase, ответ человека и правка
на том же target цикл не тратят. Число правок на одном target ограничивает
`retry_policy.max_developer_retries`. Coordinator считает бюджет по append-only событиям
`reports/resolver-events/` (`cycle-spent`, `same-target-fix`, `human-decision`, `scope-change`,
`exhausted`), поэтому потеря сессии или resume его не сбрасывают.

Несовместимые требования resolver не угадывает. Он пишет checkpoint, где в `blockers` описывает
проблему и варианты, и завершает сессию. Ответ человека coordinator записывает отдельным событием
до resume:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolver-event \
  --record <id> --kind human-decision --dispatch <dispatch-id> \
  --decided-by <имя> --option <вариант> --note '<решение>' [--extends-budget]
python .harness/orchestration/coordinator.py --repo . dispatch resume \
  --dispatch <dispatch-id> --trigger human-decision --file <facts.json> \
  --approved-by <имя> --approved-at <время>
```

Та же сессия продолжает тот же dispatch: новый developer не создаётся, соседние batch не
останавливаются. `--extends-budget` даёт ещё один автоматический target после двух потраченных.
Изменение scope проходит как обычное approval нового dispatch, а `--kind scope-change` только
записывает его. Исходный brief не переписывается. Resume с изменившимися фактами отклоняет уже
существующая проверка. Потерянную runtime-сессию возобновляют через checkpoint и resume или
`batch resume`. Счётчики coordinator берёт из событий.

Если бюджет исчерпан (`exhausted`), останавливается только эта задача, ветка и evidence
сохраняются. Несовместимость интеграции после решения человека продолжает тот же resolver.
Собственный дефект тикета (`resolver.cause: task-defect`) возвращается обычному developer.

Отчёт resolver содержит верхнеуровневый блок `resolver`:

- `preserved_requirements`: каждое требование обеих сторон дословно из brief;
- `human_decisions`: id только тех событий human-decision, которые отвечают на checkpoint этого
  dispatch;
- `target_sha`, `resolved_candidate_sha`, `cause`, `changed_files`;
- `commits` с записью плана для каждого коммита.

Отдельный `human-decision --extends-budget` без checkpoint остаётся только событием ledger и в отчёт
не попадает. Кроме ещё одного автоматического target-цикла, он даёт ещё `max_developer_retries`
попыток исправления на том же target. Принятая резолюция идёт узким маршрутом: повторный
code-review пропускается, но QA и CI или local-QA новой пары candidate/target обязательны
(`integration status` держит `verification.required`).

`collect-ci` собирает CI-доказательство для комбинированного результата PR (ADR 0016):

```bash
python .harness/orchestration/coordinator.py --repo . integration collect-ci \
  --ticket '#123' --branch feature/issue-123-short-name --pull-request 45
```

Команда работает только с трекером `github` и списком `ci_required_checks` из
`.harness/project.json`. Она принимает CI при двух условиях:

- проверки шли на merge commit PR, родители которого ровно текущие candidate и target;
- все обязательные проверки прошли.

Тогда команда пишет неизменяемую запись с `verification: collector-accepted`. `integration status`
показывает блок `qa_replacement`: источник, репозиторий, PR, SHA пары, merge commit, id check run.
Если integration ref ушёл вперёд, `qa_replacement.applies` становится `false`, а
`re_refresh_required` становится `true`: нужны новый refresh и новый сбор.

Запасной путь даёт полный локальный QA. Он нужен при `fallback` с причиной
`unsupported_tracker`, `not_configured`, `unavailable`, `wrong_repository`, `wrong_pull_request`,
`wrong_base`, `unknown_checkout`, `head_only`, `stale_candidate`, `stale_target`, `missing_check`,
`pending_check`, `inconclusive_check` или `light_check`. В этом случае команда ничего не
записывает.

Причина `light_check` означает: в `ci_required_checks` есть проверка с именем на `-light` (задание
`verify-light` для PR в `integration/**`), а пара требует полного QA. Полный QA нужен, если
сохранённый выбор пары не `ticket-diff`, записи пары нет, она старого контракта или повреждена.
Такая проверка пару не подтверждает, поэтому нужен полный локальный QA или полный CI.

Недоступность CI не считается ни находкой в коде, ни успехом. Завершённый `failure` на
подтверждённой паре coordinator записывает как `collector-failed`. CI, привязанный вручную через
`link-evidence`, остаётся `unverified` и проверку пары не закрывает. CI не заменяет исходные
QA-отчёты.

`local-qa` служит запасным путём, когда CI комбинированного результата нет, он недоступен или
непригоден (`--ci-condition absent|unavailable|unusable`, обязательные `--reason` и `--record`):

```bash
python .harness/orchestration/coordinator.py --repo . integration local-qa \
  --record <integration-record-id> --ci-condition absent --reason 'CI не настроен для ветки'
```

Команда закрепляет неизменяемый запрос: пару candidate/target, причину и полный список
`verification_commands`. Затем она запускает существующий gate runner в изолированном clean-room
checkout точного candidate. Ветка задачи, terminal source batch и принятые отчёты не меняются, код
команда не чинит. Запуск идёт через общую FIFO-очередь QA (`qa status`): два тяжёлых QA не работают
одновременно, а остальные batch продолжают реализацию.

Результат команда пишет отдельной неизменяемой записью с командами, очищенным от секретов
артефактом и checksum. Она привязывает его как evidence `kind: local-qa` с
`verification: verified`, но только если пара и remote-ветка не сдвинулись: прежний результат не
подтверждает другой SHA или движение target. Провал проверки становится finding с `state: failed`,
и его маршрутизирует PR-сессия. Недоступность инфраструктуры даёт отдельный `state: unavailable` без
findings. Повтор возможен только с явным `--retry` и не больше `max_infrastructure_retries` раз,
затем наступает `state: exhausted`. Вручную привязанный `local-qa` остаётся `unverified` и проверку
пары не закрывает.

`next` возвращает read-only шаг продолжения PR (ADR 0017). Он ничего не пишет в Git, ledger,
dispatch и PR и не обращается к трекеру. Он классифицирует `status`, evidence, открытые resolver
batch и события бюджета:

```bash
python .harness/orchestration/coordinator.py --repo . integration next \
  --ticket '#123' --branch feature/issue-123-short-name [--pull-request 45]
```

Шаги (`step`):

- `unavailable`: integration ref не читается. Это операционная остановка, а не дефект кода.
- `resolver-open`: открыт resolver batch. PR-сессия ждёт, цикл не тратится.
- `refresh`.
- `route-failure`: провал проверки текущей пары.
- `human-decision`: бюджет resolver исчерпан.
- `confirm-pr`: до открытия PR.
- `verify` (с `--pull-request`): обновлённой паре нужны CI или local-QA.
- `handoff`: пара актуальна и проверена. Ответ содержит `candidate_sha`, `target_sha`,
  `qa_source` (`original-qa|ci|local-qa`), `reference`, `refreshed`.

Старое evidence пускает в подготовку PR (`confirm-pr`), но не считается QA нового candidate:
для `verify` и `handoff` нужна проверка именно обновлённой пары.

Правило маршрута провала. Провалом считается только `collector-failed` CI или `failed`
сгенерированного local-QA текущей пары, если у пары нет passed проверенной проверки. Passed и
verified проверка текущей пары снимает провал независимо от порядка записи. Провал, записанный
после неё, не открывает маршрут, пока passed относится к текущей паре.

Если пара прошла refresh или resolver, маршрут ведёт к `resolver`: это поведенческая
несовместимость после чистого rebase или следствие правки resolver. Ответ содержит бюджет
`cycles_total`/`cycles_spent`/`remaining`/`internal_fix_budget` и `fixes_on_target`. Если бюджет
исчерпан, шаг будет `human-decision` с `integration resolver-event --extends-budget`.

Если пара исходная, маршрут ведёт к `developer`: собственный дефект задачи идёт обычному developer
с review и QA (ADR 0012). Завершённый исходный batch терминален, и `batch decide` на нём
отказывает. Поэтому подсказка `next` называет исполнимый путь: новый batch того же тикета и
issue-ветки обычным маршрутом `/implement`
(`batch create --ticket T --branch B --worktree W --integration-ref I`, затем architect, developer,
code-review, QA и publish). Завершённый batch новому не мешает. База нового batch: integration tip.
Поэтому developer-отчёт отображает в `commit_map` и уже опубликованные коммиты ветки (с
`dod_coverage` и `divergence_justification`).

После принятого publish `integration prepare --ticket T --branch B --batch <новый batch>` создаёт
новую запись. `integration next --record <новая запись> --pull-request N` продолжает PR, а упавшее
evidence прежней записи остаётся историей. У одного тикета и ветки теперь две записи, и
`<ticket-branch>` получает отказ «several integration records match». В командах `integration`
скилла `to-pull-requests` вместо `<ticket-branch>` используйте `--record <новая запись>`.

Операционный fallback CI и `unavailable`/`exhausted` у local-QA не создают failed-evidence и не
становятся провалом кода. Для провала обновлённой пары `integration resolve` создаёт resolver batch
с `resolver.trigger: verification-failure` (`failed_evidence_ids`, пустые `conflicting_files`), даже
если `tip == target`. Сторона `target` берётся из коммитов, которые попали в target после исходного
target записи (`identity.target_sha..tip`). Scope остаётся в пределах собственных файлов задачи.
Для правки других файлов нужен новый утверждённый dispatch `scope-change`. Бюджет и лимит правок на
том же target такие же, как у конфликта. Ответ человека и ожидание CI бюджет не сбрасывают и не
тратят.

Подсказка `next` в результате `collect-ci`:

- `pending_check`: `{action: wait}`;
- `not_configured` и `unsupported_tracker`: `{action: local-qa, ci_condition: absent}`;
- `unavailable`: `local-qa` с `unavailable`;
- остальные fallback: `local-qa` с `unusable`;
- `failed`: `{action: route}`.

При `accepted` подсказки нет: полный локальный QA пропускается (`qa_replacement.applies`).

`/to-pull-requests` ведёт этот процесс. Перед PR нужно отдельное подтверждение человека,
привязанное к точной паре `candidate_sha`/`target_sha`. Если пара сменилась до открытия,
подтверждение теряет силу. После открытия или обновления PR скилл ждёт CI. Если CI непригоден,
скилл запускает запасной `local-qa`, затем делает `handoff` для ручного merge. Перед merge он
показывает проверенные пары SHA и источник QA. Handoff не обещает, что до merge ничего не изменится:
при новом target актуализация и проверка повторяются. Server branch protection и merge queue скилл
не включает. Merge остаётся ручным, тикет закрывается только после подтверждённого merge.

`link-evidence` единственный публичный способ привязать к записи будущие результаты CI, local-QA
или resolver (`--kind ci|local-qa|resolver`). Каждая привязка создаёт отдельную неизменяемую запись
со своей парой `candidate_sha`/`target_sha` и `verification: unverified`. Исходное evidence записи
никогда не получает новую пару, а проверка новой пары не подменяет старую. Повтор той же привязки
идемпотентен (`linked: false`). Сами CI, local-QA и resolver эта операция не запускает. В `status`
каждая привязка показывает, относится ли её пара к текущему tip
(`pair_checks[].applies_to_current_pair`).

## Advisory tool call {#advisory-tool-call}

`.harness/orchestration/advisory.py` даёт дешёвый CLI вне ролей для утилитарных подзадач:
ранжирует файлы по ключевому слову, сводит лог и грубо оценивает риск. Он работает вне контракта
brief, report, self-report и heartbeat. Это не dispatch: он не пишет запись в ledger и не
импортирует `ledger/`, `contract.py` и `coordinator.py`. Вывод одноразовый: CLI печатает его в
stdout, пересчитывает при каждом вызове и нигде не сохраняет как ground truth для другого dispatch:

```bash
python .harness/orchestration/advisory.py rank-files --keyword payments -- services/payments/handler.py README.md
python .harness/orchestration/advisory.py summarize-log --file qa-output.log
python .harness/orchestration/advisory.py classify-risk --text "data migration for payments" --known-trigger data-migration
```

Вывод advisory ничего не авторизует. Путь проверки coordinator и contract не принимает его как
основание создать dispatch, понизить риск, принять QA или изменить scope. Единственный
авторитетный источник риска: `coordinator.py risk assess`.
