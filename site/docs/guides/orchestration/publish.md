# Публикация и PR

Принятый publish завершает pipeline для candidate. Подготовка PR отдельно сверяет integration-ветку и доказательства проверки. Открытие PR требует подтверждения, merge выполняет человек.

[Обзор оркестрации](../../backend-orchestration.md)

## Integration accounting после publish {#integration-accounting-publish}

Завершённый batch — история: его не переоткрывают и не переписывают. Связь, нужная следующему
шагу интеграции (тикет, issue-ветка, source batch, опубликованный candidate SHA и target SHA
integration ref), фиксирует отдельная immutable запись — Integration record. Её создаёт и читает
группа `integration`. Ни одна из команд не пишет batch, plan, dispatch и reports. Git меняет
только `refresh` (ниже):

```bash
python .harness/orchestration/coordinator.py --repo . integration prepare \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration status \
  --ticket '#123' --branch feature/issue-123-short-name
python .harness/orchestration/coordinator.py --repo . integration link-evidence \
  --record <integration_record_id> --kind ci --result passed \
  --candidate-commit <sha> --target-commit <sha> --reference <run-url> [--artifact-sha256 <hex>]
```

`prepare` запускают после accepted publish и до merge или удаления ветки. Он выбирает единственный
завершённый batch с accepted publish для пары ticket+branch. Опубликованный SHA он сверяет двумя
независимыми способами: по принятому отчёту publish (digest отчёта и brief) и по `ls-remote`
(ветка на remote — ровно candidate, integration ref — ровно закреплённый target). Evidence
берётся из accepted green QA того же SHA. Ответ содержит `integration_record_id`, пару
`candidate_sha`/`target_sha` и ссылки на исходное QA и publish по digest. Повторный `prepare` не
создаёт вторую запись и не теряет первую (`created: false`). Отказ всегда содержит remedy. Случаи
отказа: не найден batch для тикета и ветки; `--batch` чужой пары; batch не завершён или не
опубликован; несколько опубликованных batch без `--batch` (подмены одного batch другим нет);
`--candidate-commit` не равен опубликованному SHA; remote-ветка отсутствует или другая; нет accepted
green QA; integration ref уже ушёл вперёд, а записи ещё нет; remote недоступен; история batch
изменена после записи.

Запись лежит в `reports/integration/`, а evidence — в `reports/integration-evidence/` внутри
уже проверяемого каталога `reports`: версия схемы ledger и `ledger migrate` не меняются.

`status` — только наблюдение, под тем же read-only контрактом. Он не создаёт dispatch, ничего не
записывает и при повторе даёт тот же ответ. Состояния: `current` (integration ref всё ещё на
записанном target), `stale` (ref ушёл вперёд; `refresh_required: true`) и `unavailable` (remote не
ответил; подтвердить пару нельзя). Исходное QA относится только к записанной паре.
`source_evidence.applies_to_current_pair` равен `false` при `stale`, и старое QA не принимается для
новой пары candidate/target. `status` сам ничего не запускает. Обновить пару при `stale` позволяет
`integration refresh` (ниже). После refresh `status` показывает текущую пару (`candidate_sha`,
`target_sha`, исходные значения в `original_candidate_sha`/`original_target_sha`), список `refreshes`
и блок `verification`: `required: true`, пока нет passed CI или local-QA именно этой пары
(`resolver` не считается), и всегда `re_review_required: false`.

`refresh` — маршрут подготовки PR вместо обязательного developer-перезапуска из-за сдвига базы:

```bash
python .harness/orchestration/coordinator.py --repo . integration refresh \
  --ticket '#123' --branch feature/issue-123-short-name
```

Команда читает текущий SHA integration ref. Если он равен target пары, rebase не запускается
(`state: unchanged`, ничего не пишется). Иначе она перебазирует issue-ветку в worktree своего batch
на этот точный SHA и публикует ветку через `--force-with-lease` с ожидаемым старым SHA, так что
чужой коммит на remote не теряется. Команда отказывает с remedy, если worktree не на issue-ветке
на записанном candidate, если в worktree есть незакоммиченные изменения или операция в процессе или
если remote-ветка уже не равна записанному candidate. Stash, reset и обход не применяются, protected
и `integration/*` ветки целью записи не бывают, а чужие worktree не затрагиваются.

Чистый rebase возвращает `state: rebased`, `new_candidate_sha` и `verification_required: true`, не
вызывает resolver и не тратит его два цикла. Текстовый конфликт возвращает `state: conflict` и
`resolver` (`conflicting_files`, `candidate_sha`, `target_sha`, `worktree`, `cycles_spent: 0`);
rebase при этом отменяется, а ветка и worktree остаются как были. Rebase пишет immutable
`IntegrationRefreshRecord` в `reports/integration-refresh/` (прежний и новый candidate, target,
коммиты до и после). Старое QA остаётся историческим evidence, а новый candidate подтверждают CI
или local-QA пары через `link-evidence`; повторный review из-за refresh не нужен. Конфликт и работу,
которой нужен developer, ведёт маршрут rebase из ADR 0012, и `refresh` от него не зависит.

`resolve` — маршрут текстового конфликта (роль `conflict-resolver`, ADR 0015). Он ничего не пишет в
Git и отклоняет чистый rebase, потому что это работа `refresh`. Конфликт превращается в новый batch
вида `resolver` рядом с завершённым batch тикета, при этом его brief, отчёты и история не меняются:

```bash
python .harness/orchestration/coordinator.py --repo . integration resolve \
  --ticket '#123' --branch feature/issue-123-short-name
```

Ответ содержит `batch_id`, конфликтные файлы, candidate и target SHA, scope и остаток бюджета.
`next_action` batch — `resolve-conflict`. Дальше идёт обычный путь: `batch approve`, затем
`dispatch create --role conflict-resolver --purpose work` (сначала `--propose`). Brief несёт
неизменяемую секцию `resolver`: тикет, требования обеих сторон (`sides.candidate` — DoD исходного
batch; `sides.target` — plan-записи тикетов `(#N)` из subject коммитов цели, иначе subject и тело
коммита), SHA candidate и target, scope, запреты, план коммита, проверки, остаток бюджета и
`report_staging_path`. Роль открывает skill `resolving-merge-conflicts`, сохраняет требования обеих
сторон и не добавляет функциональность вне них.

Бюджет — два автоматических target SHA, а третий требует решения человека. Цикл тратит только
зафиксированный отчёт resolver-а по новому target SHA, тогда как чистый rebase, ответ человека и
правка на том же target цикл не тратят. Правки на одном target ограничены
`retry_policy.max_developer_retries`. Бюджет выводится из append-only событий
`reports/resolver-events/` (`cycle-spent`, `same-target-fix`, `human-decision`, `scope-change`,
`exhausted`), поэтому потеря сессии или resume его не сбрасывают.

Несовместимые требования resolver не угадывает: он пишет checkpoint (`blockers` — конкретное описание
и варианты) и завершает сессию. Ответ человека фиксируется отдельным событием до resume:

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
Изменение scope — обычное approval нового dispatch (`--kind scope-change` лишь фиксирует его).
Исходный brief не переписывается. Существующая проверка отклоняет resume с изменившимися фактами.
Потерянная runtime-сессия возобновляется через существующие checkpoint/resume или
`batch resume`. Счётчики берутся из событий.

После исчерпания бюджета (`exhausted`) останавливается только эта задача: ветка и evidence
сохраняются. Несовместимость интеграции продолжает тот же resolver после решения человека.
Собственный дефект тикета (`resolver.cause: task-defect`) возвращается обычному developer-у.

Отчёт resolver-а несёт верхнеуровневый блок `resolver`: `preserved_requirements` (каждое требование
обеих сторон дословно из brief), `human_decisions` (id только тех событий human-decision, что
отвечают на checkpoint этого dispatch), `target_sha`, `resolved_candidate_sha`, `cause`,
`changed_files` и `commits` с записью плана для каждого коммита. Автономный
`human-decision --extends-budget` без checkpoint фиксируется лишь событием ledger и в отчёт не
попадает. Кроме ещё одного автоматического target-цикла, он даёт ещё `max_developer_retries`
попыток исправления того же target. Принятая резолюция идёт узким маршрутом: повторный code-review
пропускается, но QA и CI либо local-QA новой пары candidate/target обязательны
(`integration status` держит `verification.required`).

`collect-ci` собирает CI-доказательство для комбинированного результата PR (ADR 0016):

```bash
python .harness/orchestration/coordinator.py --repo . integration collect-ci \
  --ticket '#123' --branch feature/issue-123-short-name --pull-request 45
```

Команда работает только с трекером `github` и списком `ci_required_checks` из
`.harness/project.json`. CI принимается, если выполнены оба условия: проверки шли на merge commit
PR, родители которого — ровно текущие candidate и target; все обязательные проверки прошли. Тогда
команда пишет immutable запись с `verification: collector-accepted`. `integration status`
показывает блок `qa_replacement` (источник, репозиторий, PR, SHA пары, merge commit, id check run).
Если integration ref ушёл вперёд, `qa_replacement.applies` становится `false`, а
`re_refresh_required` — `true`: нужен новый refresh и новый сбор. Запасной путь — полный локальный
QA. Он нужен при `fallback` с причиной `unsupported_tracker`, `not_configured`, `unavailable`,
`unknown_checkout`, `head_only`, `stale_candidate`, `stale_target`, `missing_check`, `pending_check`,
`inconclusive_check` или `light_check`. В этом случае ничего не записывается. Причина `light_check`
означает, что в `ci_required_checks` стоит проверка с именем на `-light` (задание `verify-light`
для PR в `integration/**`), а пара требует полного QA: сохранённый выбор пары не `ticket-diff`,
записи пары нет, она старого контракта или повреждена. Такая проверка пару не подтверждает, поэтому
нужен полный локальный QA или полный CI. Недоступность CI не считается ни
находкой в коде, ни успехом. Завершённый `failure` на подтверждённой паре записывается как
`collector-failed`. Вручную привязанный через `link-evidence` CI остаётся `unverified` и проверку
пары не закрывает. CI не заменяет исходные QA-отчёты.

`local-qa` — запасной путь, когда CI комбинированного результата отсутствует, недоступен или
непригоден (`--ci-condition absent|unavailable|unusable`, обязательные `--reason` и `--record`):

```bash
python .harness/orchestration/coordinator.py --repo . integration local-qa \
  --record <integration-record-id> --ci-condition absent --reason 'CI не настроен для ветки'
```

Команда закрепляет immutable запрос (пара candidate/target, причина, полный список
`verification_commands`) и запускает существующий gate runner в изолированном clean-room checkout
точного candidate. Ветка задачи, terminal source batch и принятые отчёты при этом не меняются, и
код не чинится. Запуск идёт через общую FIFO-очередь QA (`qa status`): два тяжёлых QA не работают
одновременно, а остальные batch продолжают реализацию. Результат команда пишет отдельной immutable
записью с командами, санитизированным артефактом и checksum и привязывает его как evidence
`kind: local-qa` с `verification: verified`, но только если пара и remote-ветка не сдвинулись:
прежний результат не подтверждает другой SHA или движение target. Провал проверки — finding с
`state: failed`, который остаётся для маршрутизации PR-сессией. Недоступность инфраструктуры даёт
отдельный `state: unavailable` без findings. Повтор возможен только явным `--retry` и не более
`max_infrastructure_retries`, после чего наступает `state: exhausted`. Вручную привязанный
`local-qa` остаётся `unverified` и проверку пары не закрывает.

`next` — read-only шаг продолжения PR (ADR 0017). Он ничего не пишет в Git, ledger, dispatch и PR и
не обращается к трекеру. Он классифицирует `status`, evidence, открытые resolver batch и события
бюджета:

```bash
python .harness/orchestration/coordinator.py --repo . integration next \
  --ticket '#123' --branch feature/issue-123-short-name [--pull-request 45]
```

Шаги (`step`): `unavailable` (integration ref не читается — операционная остановка, не дефект кода),
`resolver-open` (открыт resolver batch; PR-сессия ждёт, цикл не тратится), `refresh`, `route-failure`
(провал проверки текущей пары), `human-decision` (бюджет resolver исчерпан), `confirm-pr` (до PR),
`verify` (с `--pull-request`: обновлённой паре нужны CI либо local-QA) и `handoff` (пара актуальна и
проверена: `candidate_sha`, `target_sha`, `qa_source` `original-qa|ci|local-qa`, `reference`,
`refreshed`). Старое evidence допускает вход в подготовку PR (`confirm-pr`), но не считается QA
нового candidate: `verify` и `handoff` требуют проверки именно обновлённой пары.

Правило маршрута провала: провалом считается только `collector-failed` CI или `failed`
сгенерированного local-QA текущей пары, у которой нет passed проверенной проверки. Passed, verified
проверка текущей пары снимает провал независимо от порядка записи. Провал, записанный после неё, не
открывает маршрут, пока passed продолжает относиться к текущей паре. Если пара прошла refresh или
resolver, маршрут — `resolver` (поведенческая несовместимость после чистого rebase, следствие
правки resolver; бюджет `cycles_total`/`cycles_spent`/`remaining`/`internal_fix_budget` и
`fixes_on_target` в ответе; при исчерпании — `human-decision` с
`integration resolver-event --extends-budget`). Если пара исходная, маршрут — `developer`:
собственный дефект задачи идёт обычному developer с review и QA (ADR 0012). Завершённый исходный
batch терминален, и `batch decide` на нём отказывает. Поэтому подсказка `next` называет исполнимый
путь: новый batch того же тикета и issue-ветки обычным маршрутом `/implement`
(`batch create --ticket T --branch B --worktree W --integration-ref I`, затем architect, developer,
code-review, QA и publish; завершённый batch новый не блокирует). База нового batch — integration
tip. Поэтому developer-отчёт отображает в `commit_map` и уже опубликованные коммиты ветки (с `dod_coverage` и
`divergence_justification`). После принятого publish `integration prepare --ticket T --branch B --batch
<новый batch>` создаёт новую запись, `integration next --record <новая запись> --pull-request N`
продолжает PR, а упавшее evidence прежней записи остаётся историей. У одного тикета и ветки теперь
две записи, и `<ticket-branch>` отклоняется отказом «several integration records match».
`--record <новая запись>` заменяет `<ticket-branch>` в командах `integration` скила `to-pull-requests`.
Операционный fallback CI и `unavailable`/`exhausted` local-QA не создают failed-evidence и не
становятся провалом кода. Для провала обновлённой пары `integration resolve` создаёт resolver batch с
`resolver.trigger: verification-failure` (`failed_evidence_ids`, пустые `conflicting_files`) даже
при `tip == target`. Сторона `target` берётся из коммитов, которые легли в target после исходного
target записи (`identity.target_sha..tip`). Scope остаётся собственными файлами задачи (правка
других файлов — новый утверждённый dispatch `scope-change`). Бюджет и лимит правок на том же target
те же, что у конфликта. Ответ человека и ожидание CI бюджет не сбрасывают и не тратят.

Подсказка `next` в результате `collect-ci`: `pending_check` — `{action: wait}`; `not_configured` и
`unsupported_tracker` — `{action: local-qa, ci_condition: absent}`; `unavailable` — `local-qa` с
`unavailable`; остальные fallback — `local-qa` с `unusable`; `failed` — `{action: route}`. При `accepted`
подсказки нет: полный локальный QA пропускается (`qa_replacement.applies`).

`/to-pull-requests` ведёт этот процесс. До PR нужно отдельное подтверждение человека, привязанное
к точной паре `candidate_sha`/`target_sha`. Смена пары перед открытием делает его недействительным.
После открытия или обновления PR идёт ожидание CI, при непригодном CI — запасной `local-qa`, затем
`handoff` для ручного merge. Перед merge показываются проверенные пары SHA и источник QA. Handoff
не обещает неизменность до merge, а новый target повторяет актуализацию и проверку. Server branch
protection и merge queue автоматически не включаются. Merge остаётся ручным, тикет закрывается
только после подтверждённого merge.

`link-evidence` — единственный публичный способ привязать к записи будущие результаты CI, local-QA
или resolver (`--kind ci|local-qa|resolver`). Каждая привязка — отдельная immutable запись со своей
парой `candidate_sha`/`target_sha` и `verification: unverified`; исходное evidence записи никогда не
получает новую пару, а проверка новой пары не подменяет старую. Повтор той же привязки
идемпотентен (`linked: false`). Сами CI, local-QA и resolver эта операция не запускает. В `status`
каждая привязка показывает, относится ли её пара к текущему tip
(`pair_checks[].applies_to_current_pair`).

## Advisory tool call {#advisory-tool-call}

`.harness/orchestration/advisory.py` — дешёвый non-role CLI для чисто утилитарных подзадач:
ранжирование файлов по keyword, сводка лога и грубая риск-подсказка. Он выполняется вне
brief/report/self-report/heartbeat контракта. Это не dispatch: он не пишет ledger-запись и не
импортирует `ledger/`/`contract.py`/`coordinator.py`. Вывод эфемерен. Он печатается в stdout и
пересчитывается заново при каждом вызове. Он нигде не сохраняется как ground truth для другого
dispatch:

```bash
python .harness/orchestration/advisory.py rank-files --keyword payments -- services/payments/handler.py README.md
python .harness/orchestration/advisory.py summarize-log --file qa-output.log
python .harness/orchestration/advisory.py classify-risk --text "data migration for payments" --known-trigger data-migration
```

Вывод advisory не является авторизацией: coordinator/contract validation path не принимает его как
основание создать dispatch, понизить риск, принять QA или изменить scope. Единственным
авторитетным источником риска остаётся `coordinator.py risk assess`.
