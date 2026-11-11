# Решения и повторы

Сначала прочитайте decision packet. Он связывает отчёт, candidate SHA и допустимые следующие действия. Повтор требует подходящего маршрута; смена причины не должна скрывать дефект проекта.

[Обзор оркестрации](../../backend-orchestration.md)

## Маршрутизация `retry` и решение `abandon` {#retry-abandon}

`batch decide --decision retry` больше не означает «снова developer». Coordinator сохраняет на
решении routing record: `route`, `previous_role`, `reason_category`, `next_role`, `next_action`,
`rationale` и `candidate_commit` (пока он не изменился). Coordinator определяет причину только по
структурированным данным report: outcome, findings, severity осей Standards/Spec, failed checks и
тому, изменился ли candidate. Свободный текст `blockers`/`output` coordinator не классифицирует. Явную причину
можно передать через `--reason-category` (`code`, `requirements`, `candidate-change`,
`verification-infrastructure`, `transport`, `context-pressure`, `tooling`, `block-bypass`,
`unknown`). Но она не отменяет найденный finding. Rate limit, недоступный Bash/WSL wrapper и
transport failure — это operational evidence (`verification-infrastructure` или `transport`), а не
code finding. Context limit даёт `context-pressure`, только если для отчитавшегося dispatch записано
`critical`-наблюдение `context_pressure` (см. ниже). Голое утверждение даёт `unknown`.

**Домены отказа.** Каждый routing record несёт `failure` — ровно один домен ADR 0019
(`environment_preparation`, `infrastructure`, `policy`, `tooling`, `code_test`, `timeout`,
`cancelled`, `unknown`) с доказательством, которое показывает этот домен: `domain`, `method`,
`matched` и `source`. `method` равен `structured` (поле отчёта, стадии или runtime), `heuristic`
(текстовый шаблон, который никогда не доказывает `code_test`), `approver` (домен назвал человек
или политика) или `fallback`, а `fallback` всегда означает `unknown`.

Домен `code_test` доказывают находка в review, severity warning/blocker на оси, явный retry, который
назначил reviewer, failed check, открытый carried item, подтверждённый дефект проекта при
подготовке QA, отчёт conflict-resolver-а с `resolver.cause: task-defect` и сдвинутый candidate (он
изменился после закрепления dispatch). Coordinator считает сдвинутый candidate `code_test`
намеренно: ledger доказывает, что изменилась сама работа, поэтому маршрут остаётся developer retry
и тратит бюджет, как до появления доменов. Подсказка `retry_reason_classifier` — не доказательство:
она не заменяет структурированный факт отчёта, и без такого факта домен остаётся `unknown`.

Остальные домены следуют из фактов. Структурированный `tooling_blocker` даёт `tooling`,
подтверждённый сбой окружения QA — `environment_preparation`, записанное `critical`-наблюдение
`context_pressure` — `infrastructure`, `block-bypass` — `policy`. Всё, что не подтверждает ни один
структурированный факт, — `unknown`, но никогда `code_test`.

Только retry с доменом `code_test` расходует `retry_policy.max_developer_retries`.
`infrastructure`, `environment_preparation`, `policy`, `tooling`, `timeout`, `cancelled` и `unknown`
не расходуют его никогда. Для остановки `budget-exhausted` coordinator тоже считает только developer retry
с доменом `code_test`.

Coordinator отказывает developer retry по отчёту code-review, qa, verification или publish, если
домен не `code_test`. Отказ типизирован как `UnprovenFailureError` и несёт `failure`; `batch decide
--decision retry` возвращает `failure` и remedy и ничего не пишет. При `approval_policy: auto` тот же
отказ становится остановкой `no-automatic-route`/`unknown-reason`, и её evidence сохраняет `failure`.
Эта же остановка завершает автоматический developer retry с доменом `unknown`, потому что такой
retry не тратил бы бюджет и остался бы без ограничения.

Approver доказывает домен `code_test` категориями `--reason-category code`, `requirements` или
`candidate-change`. Он может запросить developer retry и через `--retry-role developer`, в том числе
для отчёта code-review, qa или verification, заблокированного инструментом. Оба варианта доказывают
домен `code_test` как `approver` и расходуют бюджет. Исключение — `tooling-retry`: с
`--retry-role developer` такой retry стадии developer сохраняет домен `tooling` и ничего не
расходует; остальные `tooling-retry` тоже не расходуют. Решение, записанное до появления доменов,
не несёт `failure`, и для него действует прежнее правило.

| Стадия отчёта | `accept` | `retry` | `block` / `fail` | `abandon` |
| --- | --- | --- | --- | --- |
| architect | developer | новый architect | terminal | `abandoned` |
| developer | risk assessment | `developer-retry` продолжает непринятый candidate этого report (`snapshot_commit` — его `commit_sha`); retry создаёт новый candidate, и тот получает новую risk assessment; бюджет расходуется только при домене `code_test`; при непустом закрытом списке перенесённых пунктов маршрут — `fix-forward` | terminal | `abandoned` |
| verification | risk assessment | `developer-retry` при домене `code_test`, иначе отказ | terminal | `abandoned` |
| code-review | qa | новый code-review на том же `candidate_commit`, если report `blocked`, причина — `verification-infrastructure`/`transport`/`context-pressure`, findings пусты, обе оси без findings, нет failed check и candidate не менялся; в остальных случаях `developer-retry` при домене `code_test` (при непустом закрытом списке перенесённых пунктов — `fix-forward`), при другом домене — отказ | terminal | `abandoned` |
| qa | publish | новый qa на том же SHA при том же условии (QA остаётся read-only); defect или новый candidate — `developer-retry` при домене `code_test`, иначе отказ | terminal | `abandoned` |
| publish | `completed` | новый publish на том же принятом SHA при `verification-infrastructure`/`transport`/`context-pressure`; `developer-retry` при домене `code_test`, если candidate должен измениться; иначе отказ | terminal | `abandoned` |

`code`, `requirements` и `candidate-change` ведут в `developer-retry` при доказанном домене
`code_test`. `unknown`, противоречивая или неподтверждённая причина не доказывает дефект кода: в
ручном пути стадия developer повторяется через `developer-retry` без расхода бюджета, а в
автоматическом политика останавливает такой retry. Стадии code-review, qa, verification и publish
получают отказ (см. «Домены отказа»). Повторить read-only стадию на том же SHA могут только три
operational-категории, и лишь при пустых findings, неизменном candidate и отсутствии
scope/requirement blocker. Повтор на том же SHA — это новый immutable dispatch: новый
dispatch ID, повторная проверка свежести Context Package и собственное явное approval при
`manual_all`, а прежние brief, report и blocker остаются audit evidence. Фиктивные и пустые commit
не используются, и новый candidate всегда требует новой risk assessment. `block` и `fail` сами retry
не запускают. `--retry-role developer` принудительно выбирает developer retry там, где coordinator
иначе повторил бы ту же роль на том же SHA.

`tooling` — отдельная операционная категория: hook, классификатор безопасности или ledger
заблокировал законное действие роли. Coordinator присваивает её только по структурному полю
`tooling_blocker` (`tool`, точная `command`, `message`) в report с `outcome: blocked`. Категорию не
должны перекрывать finding, failed check, сдвинутый candidate или developer-категория. Явная
`--reason-category tooling` без этого поля даёт `unknown`. Другая названная операционная категория
идёт своим прежним маршрутом. Маршрут `tooling` на любой стадии — `tooling-retry`: новый dispatch той
же стадии на том же SHA (architect, verification, code-review, qa или publish). Для developer это
`developer-retry`, который продолжает его последний коммит. Этот коммит записывается в
`candidate_commit` routing record. В таблице выше «три operational-категории» по-прежнему означают
`verification-infrastructure`, `transport` и `context-pressure`.

Если hook заблокировал именно `git commit` developer, developer ничего не откатывает, а добавляет в
`tooling_blocker` поле `uncommitted_files` — непустой список без повторов, где каждый путь записан
так, как его печатает Git, и лежит внутри зоны записи. `commit_sha` при этом указывает на последний
коммит developer, и перезапуск `tooling-retry` наследует эти изменения. `dispatch preflight`
пинит HEAD на последний коммит developer и допускает грязный worktree, только если его
незакоммиченные пути (без состояния coordinator и sandbox-ов инструментов) точно совпадают со
списком из report и лежат в зоне batch. Лишний, недостающий или лежащий вне зоны файл preflight
отклоняет, а сообщение и remedy называют каждое расхождение. Чистый worktree без списка проходит, как
раньше, а для остальных dispatch preflight не проверяет worktree на незакоммиченные изменения.

`block-bypass` означает, что read-only роль (code-review, qa или verification) обошла блокировку
hook-а или инструмента вместо остановки с `tooling_blocker`. Эту категорию называет только
approver. Report с нарушением не считается evidence: его findings, failed checks и outcome не влияют
на маршрут, и лишь сдвинутый candidate по-прежнему ведёт в `developer-retry`. Маршрут —
`bypass-rerun`: новый dispatch той же стадии на том же SHA (для verification — на её
зарегистрированном candidate) без нового candidate commit. `batch decide` требует `--note` с
описанием нарушения, а сам report не принимается и не закрывается через override-warning. Новый
dispatch всегда требует явного approval (`--approved-by`) при любой `approval_policy`, кроме `auto`,
и `bypass-rerun` не расходует `retry_policy.max_developer_retries`. Для architect, developer и
publish `block-bypass` отклоняется: такой report по-прежнему получает `retry` с developer-категорией
(`code`, `requirements`, `candidate-change`) или `block`.

Retry непринятого developer report продолжает его историю. Пока batch ждёт этот `developer-retry`,
coordinator берёт candidate из immutable report (`commit_sha`, сверенный по hash) и пинит на него
`snapshot_commit` нового developer dispatch. Worktree не откатывается ни к base, ни к более старому
принятому candidate. `commit_map` retry считает только коммиты поверх `snapshot_commit`. Каждый
новый коммит закрывает ровно одну distinct entry плана, а `dod_coverage` и
`divergence_justification` в retry-отчёте отклоняются. Путь по умолчанию —
`dispatch propose`/`create` без `--candidate-commit`. Тогда brief получает `candidate_commit: null`
и не требует risk assessment, как developer retry после code-review. Чтобы привязать этот SHA к
transition digest, передайте `--candidate-commit <commit_sha>`. Тогда до
`dispatch propose`/`create`, пока batch в `awaiting-approval`, нужна `risk assess` для того же SHA.
Такая оценка — только evidence. `next_action` остаётся `developer-retry`, `required_next_role` и
требование нового candidate сохраняются, code-review и QA не открываются. `risk assess` для
другого SHA отклоняется. Retry-report с тем же SHA не принимается. Retry после code-review, qa или
publish по-прежнему пинит `snapshot_commit` на последний принятый developer candidate.

Fix-forward — маршрут существующего developer-retry, а не новый переход. Решение `retry`,
ведущее в `developer-retry`, записывает в routing record `retry_item_ids` — закрытый, возможно
пустой список перенесённых пунктов, который понесёт brief developer-retry. При retry code-review в
него входят открытые `coordinator-finding`, находки осей Standards и Spec этого review
(`review-finding`) и открытые `incomplete-item` для developer. При retry qa, publish или
verification входят те же пункты без находок review, а при retry developer work report — пункты его
собственного brief, ни один из которых не принят. Непустой список делает маршрут `fix-forward`;
`tooling-retry` developer сохраняет свой маршрут и пишет тот же список. Brief developer-retry несёт
ровно эти пункты, а расхождение с `retry_item_ids` отклоняется как нарушение инварианта.

Developer продолжает от `snapshot_commit` новыми коммитами поверх него и в completion report
отчитывается полем `carried_item_closure` — по одной записи на каждый пункт brief:
`{"item_id": <id>, "commits": [<sha>, ...]}` с коммитами цепочки retry, которые закрывают пункт,
или `{"item_id": <id>, "not_closed": "<причина>"}`. Цепочка retry — это этот dispatch и предыдущие
попытки, передавшие ему тот же закрытый список. Retry developer-отчёта и `tooling-retry` developer
передают следующей попытке пункты своего brief, а `snapshot_commit` следующей попытки — это HEAD
предыдущей. Коммиты отсчитываются от `snapshot_commit` первой попытки цепочки, от которого ещё
происходит `snapshot_commit` этого dispatch; при утверждённом rebase target отсчёт идёт от него, а
после ещё не принятой попытки `rebase-fix-forward` в цепочке — от её target. Поэтому пункт, закрытый
предыдущей попыткой, указывает её коммит, а после rebase — его перенесённую копию.

После попытки `rebase-fix-forward` цепочке принадлежат коммиты двух видов: новые коммиты её попыток
и перенесённые копии, у которых `rebased_from` в `commit_map` отчёта попытки указывает на коммит
цепочки. Более ранний rebase учитывается: копия копии ведёт к исходному коммиту. Перенесённая копия
коммита, который существовал до цепочки (он лежит в `snapshot_commit` первой попытки или ниже),
отклоняется с тем же remedy, что и оригинал. Исключение одно: старый rebase stale-base не пишет
`rebased_from`, и его closure по-прежнему считает все коммиты выше batch target. Completed-отчёт
такого brief обязан нести поле, blocked или failed отчёт может его нести, а отчёты остальных brief —
не могут. `report submit` отклоняет с remedy пропущенный, неизвестный или повторный пункт, пустую
причину, пустой список коммитов, неразрешимый SHA и коммит, который не создала цепочка retry;
коммиты сверяются с Git, в том числе у brief без `commit_plan`. Пункт `not_closed` — carried gap, и
такой отчёт не clean: policy его автоматически не принимает, а `--decision accept` отклоняется.
`override-warning` требует `--note`, отличный от `none`, и записывает в решение
`carried_items_gap`. `commit_map` retry-отчёта сохраняет строгое правило сверки с commit plan, а
`batch decision-packet` показывает у пунктов developer-retry статус `closed` с SHA коммитов или
`open` с причиной.

Без утверждённого rebase target `commit_sha` retry-отчёта обязан быть потомком `snapshot_commit`.
Отчёт после amend, squash или reset отклоняется с сообщением `developer-retry candidate <sha> does
not descend from snapshot_commit <snapshot>: the retry rewrote the history it continues (amend,
squash or reset)`. Remedy: восстановить переписанные коммиты из `git reflog`, повторить исправление
новыми коммитами без amend и squash и отчитаться новым HEAD. Retry rebase-отчёта legacy-записи
stale-base (`base_rebase_required`, записанной до ADR 0014) по-прежнему проверяется от её rebase
target.

Rebase-fix-forward — тоже маршрут существующего developer-retry, а не новый переход. Решение
`retry`, которое ведёт в `developer-retry` или `fix-forward` (retry developer, verification,
code-review, qa или publish report; не `tooling-retry` и не `bypass-rerun`), делает `git fetch` для
`origin/<integration_ref>`. Маршрут становится `rebase-fix-forward`, если выполнены оба условия: tip
ушёл вперёд от закреплённой `integration_base_commit`; candidate, который продолжит retry
(собственный у retry developer-отчёта, иначе последний принятый), ещё не содержит этот tip. Routing
record дополнительно называет `rebase_target_commit` (новый tip) и `integration_base_commit` (база,
от которой он ушёл) и сохраняет `retry_item_ids`. `next_action` остаётся `developer-retry`, и такой
retry расходует один `retry_policy.max_developer_retries`, когда его домен отказа — `code_test`.
Ошибка fetch отклоняет `batch decide --decision retry` с remedy. `decision-packet` показывает её
в `route_preview.retry`.
Решение только предлагает target: `integration_base_commit` batch до accept не меняется.

Target попадает в brief только через dispatch с явным approval при любой `approval_policy`, кроме
`auto`. Approval другой политики для него отклоняется. `dispatch propose` показывает переход с полем
`rebase_target_sha`, а brief получает `rebase_target_commit`. Кроме этого brief поле заполнено
только у developer-retry замещающего batch (см. «Замещающий batch» ниже). У остальных brief оно
равно `null`, в том числе у developer dispatch legacy-записи stale-base:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet --batch <batch-id>
python .harness/orchestration/coordinator.py --repo . batch decide --batch <batch-id> \
  --decision retry --reason-category code --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc>
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch <batch-id> --role developer --runtime claude
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch <batch-id> --role developer --runtime claude --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --transition-digest <transition_digest>
```

Developer переносит коммиты над старой базой ровно на этот target
(`git rebase --onto <rebase_target_commit> $(git merge-base <snapshot_commit> <rebase_target_commit>)`),
разрешает конфликты и добавляет fix-коммиты в том же dispatch. Его `commit_map` перечисляет каждый
коммит прежнего candidate (после `git merge-base` от `snapshot_commit` и target до
`snapshot_commit`) ровно один раз: `{"commit_sha": <копия>, "rebased_from": <оригинал>}` —
перенесённая копия наследует пункт плана оригинала, или `{"rebased_from": <оригинал>, "dropped":
"<причина>"}` — коммит, который rebase не перенёс. Каждый коммит после target встречается ровно
один раз: как перенесённая копия или как новый коммит `{commit_sha, plan_entry_id}` по строгому
правилу retry. `changed_files` и `carried_item_closure` считаются от target. Проверка «candidate —
потомок `snapshot_commit`» для такого brief не действует. `report submit` отклоняет с remedy
пропущенный, повторный и неизвестный коммит прежнего candidate, копию, совпадающую со своим
оригиналом (merge target вместо rebase), пустую причину `dropped`, коммит, который dispatch не
создал, и `rebased_from`/`dropped` в отчёте brief без target.

`report submit`, `batch decision-packet` и решение `accept`/`override-warning` возвращают
`rebase_check`: `rebase_target_commit`, `previous_base_commit`, пары `rebased` с `patch_id_match`
(сравнение `git patch-id --stable`), `dropped` и `patch_id_mismatches`. Расхождение patch-id
означает конфликт, разрешённый с изменениями: отчёт не отклоняется и не теряет clean-статус, а пара
показывается для delta-review. Accept такого отчёта закрепляет `integration_base_commit` = target,
и так же действует accept более позднего retry, чей candidate уже стоит на этом target. Retry ещё не
принятого rebase-отчёта, как и его `tooling-retry`, считает от target и `changed_files`, и коммиты
`carried_item_closure`. Если tip уйдёт ещё раз, review и QA проверяют закреплённый candidate, а ветку
обновляет `integration refresh` при подготовке PR (ADR 0014).

Batch, созданный на ветке с коммитами более раннего batch того же тикета (его `branch_start_commit`
строго потомок `integration_base_commit`), считает свои изменения от `branch_start_commit`. От него
считаются `changed_files` и `commit_map` отчётов developer и publish, их `scope_warnings`,
checkpoint и `risk assess` (`--base-commit`, `review_scope`). Замещающий batch считает от
`integration_base_commit`; так же считает batch, чей старт не потомок этой базы (после принятого
rebase и у resolver-batch). Бриф и Context Package (`--base-commit`) остаются на
`integration_base_commit`. Правило не отличает принятые коммиты от непроверенных: коммиты
оставленного (`abandon`) batch новый batch не ревьюит.

Delta-review после fix-forward — тоже не новый переход и не новое решение. Coordinator сам
выбирает объём следующего code-review в `dispatch propose` и `dispatch create --role code-review`
без `--delta-review-of`. Coordinator делает выбор, когда выполнены все условия: candidate —
`commit_sha` последнего принятого developer work report batch; этот report — developer-retry; его
цепочку подряд повторённых попыток developer-retry открыл маршрут `fix-forward` или
`rebase-fix-forward`; последний code-review перед цепочкой завершил отчёт на `snapshot_commit` её
первой попытки и был принят или повторён в developer. Этот code-review — прежний review. Brief
получает поле `delta_review_scope`: `mode` (`delta` или
`full`), `route`, `prior_review` (dispatch ID, `report_sha256`, проверенный candidate,
`review_base`, `risk_assessment_id`), `developer_dispatch_id`, `delta_base`, `delta_commits`,
`reviewed_copies`, `closure` (`carried_item_closure` принятого отчёта) и `escalations`. Transition
связывает раздел полем `delta_review_sha256`. `dispatch propose` показывает его как
`delta_review_scope`. У остальных brief поле равно `null`, в том числе при явном
`--delta-review-of`: test-only delta-review работает как раньше.

Delta — это `git diff <delta_base> <candidate_commit>`. Без rebase `delta_base` — candidate прежнего
review, а после rebase в цепочке берутся коммиты после последнего rebase target. Ведущие
перенесённые копии считаются проверенными (`reviewed_copies`), если по парам `rebased_from` из
`rebase_check` отчётов цепочки они ведут к коммиту из диапазона прежнего review и на каждом шаге
совпадает `git patch-id`; `delta_base` — родитель первого другого коммита. Coordinator выбирает режим
`full` автоматически, без ручного выбора, если найдена хотя бы одна эскалация `{reason, evidence}`:

- `new-risk-trigger` — триггер risk assessment candidate (вместе с триггерами developer) или
  коммитов и файлов delta, которого не было в assessment прежнего review;
- `file-outside-carried-items` — файл delta вне файлов перенесённых пунктов developer-retry (для
  `review-finding` это `review_scope` его review);
- `patch-id-mismatch` — пара из `patch_id_mismatches` любого отчёта цепочки;
- `dropped-commit` — запись `dropped` из `rebase_check` любого отчёта цепочки: candidate потерял
  изменение, которое проверял прежний review, а delta оставшихся коммитов этого не показывает;
- `no-new-commits` — новых коммитов для проверки нет.

В этом случае brief — обычный полный review, а раздел остаётся audit evidence. В режиме `delta`
`carried_items` brief дополнительно несёт `review-finding` и `incomplete-item` для developer из
brief принятого developer-retry. Reviewer проверяет обе оси только на delta, а для остального
candidate опирается на отчёт прежнего review; каждый пункт он учитывает в `review.carried_items`, и
пропуск, `open` или `unverified` — это carried gap. `review_scope` и `review.scope` остаются
полными. Accept любого review, delta или полного, ведёт в `qa`, а clean-room QA идёт на новом SHA с
полными `verification_commands`. Retry delta-review передаёт следующему developer-retry
перенесённые пункты, которые review не отметил `closed`, а собственные findings этого review
получают следующие номера `review-finding-N`.

Code-review `blocker` никогда не принимается. Пока `retry_policy.max_developer_retries` ещё допускает
developer retry, для него доступны `retry` или `abandon`. После исчерпания budget `retry`
отклоняется, а blocker закрывается через `block`, `fail` или `abandon`. Затем работа разбивается
или перепланируется в новом batch. `tooling-retry` не расходует этот budget и не отклоняется при его
исчерпании. Каждый такой retry по-прежнему решает человек, а серию ограничивает
attention `tooling-retry-repeated`. `--retry-role developer` на read-only стадии по-прежнему даёт
`developer-retry` с расходом budget.

Решение `abandon` доступно после любого completion report. Оно требует явного approval и непустого
`--reason`, переводит batch в терминальный `abandoned` и помечает незакрытые dispatch как
`abandoned`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide \
  --batch <batch-id> --decision abandon --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --reason 'план заменён, начинаем новый batch'
```

`abandon` не удаляет worktree, candidate, brief, report, Context Package и audit evidence, не
закрывает issue и не создаёт PR. Команда убирает только то, что не относится к evidence: staged-копии
report в agent inbox и записи QA-очереди dispatch, которые уже не запустятся (живой QA lease
по-прежнему снимает только `qa clear-stale-lease`). Batch записывает `abandoned.last_accepted` —
последний принятый этап и его candidate. От него можно создать свежий batch на той же ветке и том
же candidate. `abandon` никогда не служит автоматическим fallback для `block`, `fail` или `retry`.
Команда `batch abandon` для batch, у которого не будет ни одного report, остаётся прежней. Она
завершает такой batch в `failed`.

### Замещающий batch: `batch create --supersedes`

Если batch закрыт решением `batch decide --decision abandon` после тупика (например, blocker
code-review при исчерпанном бюджете retry), работу продолжает замещающий batch. Он создаётся для
того же ticket и той же issue-ветки и начинает с `abandoned.last_accepted`, а не с нового architect
и ручного cherry-pick принятых коммитов:

```bash
python .harness/orchestration/coordinator.py --repo . batch create \
  --ticket '#443' --branch feature/issue-443-<slug> --worktree <тот же worktree> \
  --allowed-path '<scope>' --definition-of-done '<item>' --prohibited-change '<rule>' \
  --supersedes <abandoned-batch-id> --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc>
```

`--supersedes` требует approval человека. `--approved-by` и `--approved-at` проверяются так же, как
у `batch abandon`: TTL approval и подтверждение в терминале при `human_approval_gate: tty`.
Approver с префиксом `policy:` отклоняется. Флаги approval без `--supersedes` тоже отклоняются:
обычный batch утверждается через `batch approve`. Замещающий batch после создания тоже проходит
`batch approve`. Команда называет remedy и ничего не пишет в таких случаях: источника нет в текущем
поколении ledger; его состояние не `abandoned`; `abandoned.last_accepted` равен `null`; ticket или
issue-ветка отличаются; последний принятый candidate не резолвится в коммит. Batch, закрытый
`batch abandon`, остаётся в `failed` без `last_accepted`. При `null` ничего не было принято. В обоих
случаях нужен обычный batch. Исключение — источник с `null`, который сам замещал batch. Тогда
remedy предлагает снова передать в `--supersedes` тот batch (`supersedes.batch_id` источника), чей
`last_accepted` по-прежнему последний. Abandoned batch не держит ticket, ветку и worktree. Но
другой незавершённый batch с тем же ticket, веткой или worktree по-прежнему блокирует создание.

Новый batch и его immutable plan несут одну и ту же неизменяемую ссылку `supersedes`: `batch_id`,
`approved_by`, `approved_at`, копию `last_accepted`, `definition_of_done_matches`, `architect`,
`start_commit` и `rebase_target_commit`. Batch, чья ссылка разошлась с plan, не проходит проверку
целостности. В `coordinator_decisions` нового batch одна запись `supersede`. Её routing record
маршрута `supersede` называет `previous_role`, `next_role`, `next_action`, `candidate_commit`
(`start_commit`), `rebase_target_commit`, `superseded_batch_id`, `rationale` и `decided_at`.

Что переносится:

- при том же Definition of Done (списки совпадают поэлементно) — принятый architect источника по
  ссылке `supersedes.architect` (`batch_id`, `dispatch_id`, `report`, `report_sha256`,
  `commit_plan_sha256`) и commit plan, закреплённый при его accept через `--commit-plan-file`.
  Если источник сам перенёс architect, передаётся та же ссылка. Batch начинает с
  `next_action: developer`: developer dispatch создаётся сразу, а architect dispatch не допускается.
  При другом Definition of Done не переносится ничего, и стадия architect проходит заново;
- `start_commit` — candidate из `last_accepted` (`null`, если принят только architect). У
  замещающего batch без принятого developer этот candidate — его собственный `start_commit`.
  Поэтому следующий замещающий batch в цепочке не теряет принятый candidate. Первый developer
  dispatch берёт его как `snapshot_commit`. Brief, preflight и проверка свежести Context Package
  видят один и тот же SHA. Если `start_commit` — потомок integration base, закреплённой при create,
  это обычный initial developer: его `commit_map` покрывает все коммиты после base, включая
  коммиты `start_commit`;
- `rebase_target_commit` — эта base, если `start_commit` её не содержит. Тогда первый developer —
  developer-retry маршрута rebase внутри retry. Он перебазирует коммиты на target, исправляет
  поверх и сдаёт пары `rebased_from`. `report submit` возвращает `rebase_check`. Такой dispatch
  требует явного approval с transition digest при любой `approval_policy`, кроме `auto`. Target
  остаётся в brief, пока продолжаемый snapshot его не содержит. Так бывает, например, после retry
  ещё не перебазированного отчёта.

Что не переносится никогда: risk assessment, code-review, QA, carried items, candidate registrations
и решения оператора. Они остаются evidence abandoned batch и доступны только по
`supersedes.batch_id`. Risk assessment, review и QA проходят заново на новом candidate. Запись
`supersede` — не retry и не расходует `retry_policy.max_developer_retries`: у замещающего batch
свой бюджет. Abandoned batch только читается. Worktree должен стоять на `start_commit`. Если
тупиковая попытка оставила выше непринятые коммиты, runtime attestation отклонит developer с
remedy. Вернуть ветку назад решает человек. Coordinator ищет источник только в текущем поколении
ledger.

### Поле `route`: routing record, decision packet и audit

Каждое решение `retry` и `abandon` в `batch decide` записывает выбранный маршрут восстановления в
`routing.route` — одно значение закрытого набора `RECOVERY_ROUTES`: `developer-retry`,
`same-candidate-rerun` (новый code-review, qa или publish на том же SHA), `verification`,
`architect-retry` и `abandon`. Остальные значения `batch decide` либо записывает при особых
условиях, либо не записывает вовсе:

- `report-completion` `batch decide` не записывает. Его называет `completion` у `report submit`,
  когда policy-цепочка после записанного report остановилась (см. [шаг 4](run.md#4-coordinator-cli-lifecycle) в главе «Запуск и отчёты» и
  [«Занятый ledger»](operations.md#ledger-report-complete-ledger-release-lock)).
- `carry-over` записывают `accept` или `override-warning` с `--findings-file` и `batch carry-over`
  (см. [шаг 4](run.md#4-coordinator-cli-lifecycle)). Это routing record с `previous_role: developer`, `next_role` и `next_action`
  `code-review`, `candidate_commit`, `carried_item_ids` и `rationale`, без `reason_category` и
  `decided_at`; к `next_action` он не применяется, а следующий шаг идёт через risk assessment, как
  при любом accept developer. Тот же маршрут записывает `accept` или `override-warning` read-only
  отчёта с `--carry-incomplete` (см. [шаг 4](run.md#4-coordinator-cli-lifecycle)): тогда `previous_role` — стадия отчёта, а `next_role` и
  `next_action` — обычный следующий шаг её accept.
- `tooling-retry` записывает `retry` с категорией `tooling` (см. выше), а также `retry --narrowed`,
  если пункт несёт `tooling_blocker`.
- `bypass-rerun` записывает `retry` с категорией `block-bypass` (см. выше).
- `narrowed-retry` записывает `retry --narrowed` по невыполненным пунктам read-only отчёта (см.
  [шаг 4](run.md#4-coordinator-cli-lifecycle)); его routing record дополнительно называет `carried_item_ids`.
- `fix-forward` записывает `retry`, который ведёт в `developer-retry` с непустым закрытым списком
  перенесённых пунктов (см. выше).
- `rebase-fix-forward` записывает `retry`, который ведёт в `developer-retry`, пока integration base
  ушла вперёд (см. выше); его routing record дополнительно называет `rebase_target_commit` и
  `integration_base_commit`.
- `supersede` `batch decide` не записывает: его записывает `batch create --supersedes` в
  `coordinator_decisions` нового batch (см. «Замещающий batch» выше).

Каждый routing record с `next_action: developer-retry` (`developer-retry`, `fix-forward`,
`rebase-fix-forward` и `tooling-retry` developer) дополнительно называет `retry_item_ids`. Маршрут
ставится там же, где `next_action`, по тем же структурированным данным и никогда по свободному
тексту. У `abandon` routing record той же формы, но `reason_category`, `next_role`, `next_action` и
`candidate_commit` равны `null`, а `rationale` содержит только структурные факты (`--reason`
остаётся в `note`). Нормативная таблица «ситуация → маршрут → кто утверждает → evidence» — раздел
«Recovery route table» в `.harness/orchestration/playbook.md`.

`batch decision-packet` показывает маршрут до записи решения: поле `route_preview` содержит
`retry` — routing record, вычисленный так же, как в `batch decide` (без `decided_at`), и `abandon` —
`{"route": "abandon"}`. Packet принимает те же `--reason-category`, `--retry-role developer` и
`--narrowed`, что и `batch decide`, и ничего не пишет. Для уже решённого report и для пакета
следующего dispatch `route_preview` равен `null`:

```bash
python .harness/orchestration/coordinator.py --repo . batch decision-packet \
  --batch <batch-id> --reason-category verification-infrastructure
```

Preview не проверяет `retry_policy.max_developer_retries`. При исчерпанном бюджете он по-прежнему
показывает маршрут `developer-retry`, `fix-forward` или `rebase-fix-forward`, а
`batch decide --decision retry` такое решение отклоняет. Как и `batch decide`, preview делает fetch
`origin/<integration_ref>` и потому показывает предложенный `rebase_target_commit`.
Если маршрут retry вычислить нельзя (например, упало настроенное расширение retry reason
classifier), packet всё равно строится. Тогда `route_preview.retry` равен
`{"route": null, "refused": ..., "remedy": ...}` с той ошибкой, которой откажет
`batch decide --decision retry`. С `--findings-file <path>` packet добавляет
`route_preview["carry-over"]`. Это запись, которую сделает `batch decide --findings-file` на
ожидающем developer report, а без такого report — `batch carry-over`. Либо это отказ той же формы
`{"route": null, "refused": ..., "remedy": ...}`. Без флага `route_preview` не меняется.

Каждое решение `batch decide` хранит в transition audit record batch деталь `decision`:
`dispatch_id`, `decision`, `route` (`carry-over` у `accept` и `override-warning` с
`--findings-file` или `--carry-incomplete`, `null` у решения без маршрута — остальных `accept`,
`override-warning`, `block`, `fail`), `evidence` (`dispatch_id`, путь `report` и `report_sha256`
immutable report), `approver` и `approved_at`. `approver` —
`{"kind": "policy", "name": "low_risk" | "milestone" | "auto"}` для policy auto-accept или
`{"kind": "human", "name": <--approved-by>}` для явного решения. Решение `batch carry-over` пишет ту
же деталь с `route: "carry-over"` и `{"kind": "policy", "name": "carry-over"}`.
`batch create --supersedes` пишет деталь с `"dispatch_id": null`, `decision` и `route` `supersede`,
ссылкой на abandoned batch в `evidence` (`batch_id`, `last_accepted`, `architect`) и
`{"kind": "human", ...}`. Вид определяется путём, которым решение утверждено, а не строкой имени.
Деталь входит в ту же audit-запись и ту же контрольную сумму, что и переход batch. Маршрут вне
`RECOVERY_ROUTES` отклоняется с remedy при записи и при чтении batch.

## Автоматический путь `approval_policy: auto` {#approval_policy-auto}

Политика `auto` действует, пока конфигурация проекта и план batch выбирают `auto` и в batch нет
`auto_stop`. Сессия не передаёт `--approved-by` и `--approved-at`. Политика согласует:

- `batch approve`: `coordinator_approval.approved_by` равен `policy:auto`;
- `dispatch create`, включая вехи `publish`, `risk-trigger`, `risk-reassessment-required`,
  `bypass-rerun`, `rebase-fix-forward` и `rebase-target`;
- `dispatch resume --trigger` для планового продолжения, кроме `human-decision`;
- `batch carry-over`: решение пишется как `policy:auto`, а не `policy:carry-over`.

Явный `--approved-by` при `auto` остаётся approval человека. Каждое согласование политики — одна
хешируемая запись в `batch.auto_decisions` (`sequence`, `kind`, `dispatch_id`, `approved_by`,
`approved_at`, `rationale`, `evidence`). Валидация ledger пересчитывает `record_sha256` и сверяет
запись с согласованием, которое она называет.

Чистый отчёт по-прежнему принимает цепочка `report submit` или `qa run`. Для остальных отчётов,
включая отчёт publish, сессия запускает:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-decide --batch <batch-id>
```

Команда вычисляет решение из фактов ledger, проводит его через проверки `batch decide` и пишет как
`policy:auto` с маршрутом, причиной и evidence. Сессия передаёт только входы, которые требуют
суждения:

- `--commit-plan-file` — план architect-а, если отчёт не несёт поле `commit_plan`; план из отчёта
  политика закрепляет без файла. Политика закрепляет план, если он лежит внутри `allowed_paths` и
  покрывает все пункты DoD. Иначе, а также при расхождении файла и плана из отчёта, путь
  останавливается. Если команда не может прочитать файл как JSON-объект, она отказывает и ничего
  не пишет.
- `--findings-file` — находки координатора для принятого отчёта developer-а.
- `--bug-ticket` — bug-тикет на инструмент для `tooling-retry`. Без него команда отказывает и
  ничего не пишет.
- `--block-bypass --note` — роль обошла блокировку hook-а или инструмента.

Политика принимает чистый отчёт и записывает его риски как `accepted_risks`. Отчёт review, в котором
ось Standards или Spec называет `blockers`, не считается чистым. Для остальных отчётов
политика выбирает `retry` по `route_preview`. Политика никогда не выбирает `override-warning`,
`block`, `fail` или `abandon`. Отчёт conflict-resolver-а вне автоматического пути: его решает человек.

Закрытый список остановок:

| `category` | `reason` |
| --- | --- |
| `integrity-failure` | `stale`, `model-mismatch`, `worktree-mismatch`, `harness-snapshot-changed`, `deterministic-gate-failed`, `ledger-validation-failed`, `operational-hold` |
| `budget-exhausted` | `retry_policy.max_developer_retries`, `continuation_policy.max_continuations`, `continuation_policy.max_rate_limit_resumes`, `attention_policy.max_infrastructure_retries`, `tooling-retry-repeated` |
| `no-automatic-route` | `unknown-reason`, `abandon-dead-end`, `supersede-dead-end`, `qa-environment-failure` |

`batch auto-decide` и `batch auto-report` находят остановку в порядке: целостность, бюджет, маршрут.
Coordinator пишет остановку один раз в `batch.auto_stop` вместе с итоговым отчётом.
`ledger-validation-failed` команда только выводит: ledger недостоверен. Остановку `operational-hold`
политика записывает, когда runtime store удерживает batch: она не решает отчёт и не делает abandon,
а удержание снимает только `recovery resume` (раздел [«Удержание batch и команды `recovery`»](recovery.md#batch-recovery)).
Остановка не создаёт решения и не ослабляет валидацию. После остановки каждый шаг batch требует `--approved-by`, а вернуться в
`auto` batch не может.

Остановку `no-automatic-route`/`unknown-reason` политика записывает и при отказе
`UnprovenFailureError` от read-only стадии или publish (см. «Домены отказа»): решение не
записывается, а evidence остановки сохраняет `failure`.

Coordinator пишет итоговый отчёт один раз в `batch.auto_report`: при accept отчёта publish или при
остановке.
Отчёт перечисляет решения `policy:auto`, принятые риски, findings, retry и потраченный бюджет,
покрытие DoD по commit plan, результаты review и QA и остановку. Команда выводит отчёт:

```bash
python .harness/orchestration/coordinator.py --repo . batch auto-report --batch <batch-id>
```

Без записанного отчёта команда записывает остановку, которую показывает ledger, или выводит
live-отчёт с `recorded: false`. Политика не открывает и не мерджит PR: PR открывается только после
явного подтверждения человека, а auto-merge запрещён.

## Approval, привязанный к digest перехода {#approval-digest}

`dispatch propose` принимает те же аргументы, что и `dispatch create`, но не пишет brief. Он
регистрирует shared Context Package, который brief закрепит. Затем он возвращает канонический
переход и его `transition_digest`. Это SHA-256 от batch ID, ID и роли предыдущего dispatch, reason
category, следующей роли/действия и purpose, candidate SHA, base SHA, review scope, verification
commands, Context Package ID и required gates. `dispatch create` с явным approval обязан получить
этот digest в `--transition-digest`. Coordinator пересчитывает переход из ledger и отклоняет любое
расхождение. Поэтому изменение scope, candidate, роли, verification command, reason category или
Context Package требует нового `propose` и нового approval. Coordinator сохраняет digest в approval
и в immutable brief вместе с самим переходом. Ledger-валидация пересчитывает его. Policy approval
(`milestone`, `low_risk`) выводится из создаваемого перехода и привязан к его собственному digest.
При `human_approval_gate: "tty"` запрос подтверждения показывает digest.

Если Repo Map у закрепляемого пакета имеет tier не `full`, результат `dispatch propose` дополнительно
содержит `context_package_quality_warning`: tier, причину деградации и parser provenance. Это
предупреждение для утверждающего человека, а не блокировка dispatch. Для `full` поле отсутствует.

Без `repo_map_policy.min_tier`/`min_tier_by_role` деградация Repo Map никогда не блокирует dispatch.
Остаётся только описанное выше необязывающее предупреждение. `repo_map_policy` может содержать
`min_tier` (общий минимум для репозитория) и/или `min_tier_by_role` (переопределение по роли, ключи
ровно `architect`/`developer`/`code-review`). Тогда порядок разрешения такой: override роли, затем
`min_tier`, затем отсутствие гейта. Если для роли задан минимум, а фактический tier закреплённого
Context Package хуже требуемого (порядок уровней по ADR 0008: `minimal` < `full`), coordinator
отклоняет и `dispatch propose`, и `dispatch create` ещё до какого-либо approval. Причина называет
роль, фактический и требуемый tier. Эта проверка выполняется в общем пути перед веткой
`propose`/`create`. Поэтому готовый `--transition-digest` её не обходит. Роль, не перечисленная в
`min_tier_by_role`, при отсутствии общего `min_tier` сохраняет поведение по умолчанию (без
блокировки).

Просроченное (`approval_ttl_seconds`) или отклонённое в терминале approval — fail-closed: coordinator
не повторяет вызов сам и не подставляет более старое approval.

## Idempotency read-only retry {#idempotency-read-only-retry}

Brief ролей `architect`, `code-review`, `qa` и publish хранит
`retry_idempotency_key = sha256(role + candidate SHA + base SHA + review scope + reason category +
digest verification commands)`. Пока в открытом batch есть активный (не решённый, не cancelled, не
abandoned) dispatch с тем же ключом, новый dispatch отклоняется. Завершённый retry не мешает новому
dispatch на том же candidate — он получает новый immutable ID. Смена candidate всегда меняет ключ.
Повторный review/QA никогда не правит прежние report и brief.

## Context pressure {#context-pressure}

`dispatch context-pressure --dispatch <id> --observed-tokens <N> --source probe|provider-usage|
runtime-adapter` пишет наблюдение `observed_tokens`, `context_limit`, `warning_threshold`, `level`
(`ok`/`warning`/`critical`) и `recorded_at`. Без `--observed-tokens` число берёт настроенный
`context_telemetry_provider`. Источник — только provider/runtime: self-report модели отклоняется.
Лимит и доля предупреждения — значения, зафиксированные в brief. Запись — чистое наблюдение: она не
меняет `next_action`, не создаёт retry и не снимает approval. При `critical` она сообщает обязанность
worker-а. Write-роль создаёт checkpoint на ближайшей зелёной границе TDD либо возвращает structured
blocker. Read-only роль возвращает blocker. Continuation создаётся только из checkpoint и только с
новым model self-report. Категория `context-pressure` у retry требует такой `critical`-записи для
отчитавшегося dispatch.

## Attention state {#attention-state}

`needs_attention` — флаг batch, а не lifecycle-состояние: он не меняет `state`, `next_action`,
candidate и evidence, но запрещает создание следующего dispatch. Флаг описывают поля
`needs_attention`, `attention_reason`, `attention_since`, `last_safe_action` и
`recommended_human_action`. Причины:

| `attention_reason` | Когда |
| --- | --- |
| `operational-hold` | runtime store удерживает batch записью `recovery/hold/<batch_id>.json`; после устранения причины человек разрешает attention, затем `recovery resume` снимает удержание |
| `unknown-reason` | retry с причиной `unknown` |
| `infrastructure-retry-repeated` | operational retry одного candidate больше `max_infrastructure_retries` |
| `tooling-retry-repeated` | третий подряд `tooling-retry` на одном candidate; снимается после исправления инструмента |
| `retry-queued-too-long` | принятый retry ждёт dispatch дольше `retry_queue_seconds` |
| `stale-evidence` | закреплённый в незавершённом dispatch Context Package расходится с base или текущим developer candidate (тем же, что выбирает `snapshot_commit`) |
| `stale-dispatch` | живой dispatch молчит дольше `stale_dispatch_seconds` |

Флаг ставят `batch decide --decision retry`, `dispatch wait` (событие `stale`) и
`batch attention check --batch <id>`. Последняя команда только оценивает текущее состояние batch. Снимает флаг
только человек: `batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …`
подтверждает открытые findings (то же событие повторно не поднимается) и пишет событие в
`attention_events`. Если настроен `human_notifier`, coordinator вызывает его, когда ставит флаг. Сбой
адаптера записывается как `failed` и не отменяет флаг.
