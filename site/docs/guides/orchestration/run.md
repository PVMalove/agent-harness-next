# Запуск и отчёты

Coordinator ведёт batch, отдельную единицу работы над тикетом. Каждый dispatch передаёт роли неизменяемое задание. Пройди планирование, отправку и приём отчёта по порядку.

[Обзор оркестрации](../../backend-orchestration.md)

## Выбрать роли и спланировать batch {#3-batch}

В базовом наборе есть четыре write-роли и три read-only роли.

| Роль | Режим | Когда назначать |
| --- | --- | --- |
| `developer` | write | Обычное backend-изменение внутри service или bounded context. |
| `database-migrations` | write | Schema/data migration и её rollout/rollback. |
| `messaging-integration` | write | Outbox, routing, message schema, retry или DLQ. |
| `conflict-resolver` | write | Текстовый конфликт ветки тикета с сдвинувшимся integration SHA; назначается только маршрутом `integration resolve`. |
| `architect` | read-only | Труднообратимое граничное решение. |
| `qa` | read-only | Нужна независимая проверка через project-facing interface. |
| `code-review` | read-only | Обязателен для listed high-risk triggers; выдаёт отдельные Standards и Spec reports. |

Одна задача может пройти несколько ролей. Но handoff внутри одного batch всегда последовательный, и
в batch бывает только один active writer. Batch с пересекающимися файлами могут идти параллельно,
каждый в своих issue-ветке и worktree, пока хватает `concurrency_budget`. Пересечения разбираются
при интеграции и не блокируют запуск. Coordinator отклоняет два batch на один и тот же
незавершённый тикет, ветку или worktree. Тяжёлые integration/quality checks идут в одной
serialized quality-gate lane.

Для API/public contract, schema/data migration, outbox/queues, transactions,
authorization/security и concurrency/retry completion невозможен, пока coordinator не получил оба
независимых отчёта `code-review`: Standards и Spec.

После developer dispatch candidate commit получает детерминированную оценку рисков из DoD, changed
files и developer-reported triggers. Оценка решает, когда composite read-only `code-review`
**обязателен**, но не когда он *разрешён*. Review можно создать для любого candidate, и конвейер
`/implement` делает это всегда. Оси Standards и Spec остаются отдельными evidence. Отдельный QA
dispatch coordinator создаёт только после принятого review (если он обязателен): обязательный полный QA gate
в clean-room нельзя заменить локальной проверкой developer-а. Любой новый candidate commit после
finding или failed QA снова проходит оценку риска.

## Coordinator CLI и lifecycle {#4-coordinator-cli-lifecycle}

Runtime-neutral режим не имеет команды «запустить всех». Coordinator CLI ведёт записи по
`planned → awaiting-approval ↔ active → completed`, с восстановимыми состояниями `paused`,
`blocked`, `failed` и окончательным отказом `abandoned`. После ручного восстановления эффективной политикой
становится `manual_all`. При `manual_all` каждый
report оставляет dispatch в `reported` до решения человека. При `low_risk` coordinator
автоматически принимает чистый завершённый report batch, если scope batch целиком лежит в
`low_risk_paths`. Решение он записывает в ledger. Blockers, failed checks, раскрытые risks, risk
triggers и findings любой оси review сохраняют ручной gate. Publish тоже требует отдельного
approval. При `milestone` coordinator также автоматически принимает чистый отчёт обычной роли. Но
QA, publish и рискованные переходы остаются ручными вехами. При `auto` coordinator проходит путь
от `batch approve` до принятого publish без человека. Политика согласует каждый шаг, а
`batch auto-decide` принимает решения по отчётам (см. [«Автоматический путь `approval_policy: auto`»](decisions.md#approval_policy-auto)
в главе «Решения и повторы»). Ручными остаются открытие PR и merge.

1. Создать planned batch и затем отдельно утвердить его:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch create \
     --ticket '#123' --branch feature/issue-123-payment-validation \
     --worktree issue-123-payment-validation \
     --allowed-path 'services/payments/**' \
     --definition-of-done 'Добавить валидацию платежа' \
     --prohibited-change 'Не менять migration или публичный API' \
     --required-gate review --required-gate qa
   python .harness/orchestration/coordinator.py --repo . batch approve \
     --batch <batch-id> --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc>
   ```

   `batch create` сначала выполняет `git fetch origin <ref>` — `--integration-ref`, если он передан,
   иначе `base_branch` проекта (для epic-less задач) — и фиксирует полученную вершину как
   `base_commit`/`integration_base_commit`; необновлённый локальный HEAD её никогда не заменяет.
   Полный маршрут `/implement` требует явно указать `--required-gate review --required-gate qa`
   (независимые Standards/Spec review и full clean-room QA), и coordinator сверяет их наличие в
   `required_gates` до отправки write-role (`developer`) worker-а. В допустимых прямых CLI-сценариях
   `--required-gate` можно опустить (по умолчанию `["none"]`). Дальше review, QA и publish проверяют
   закреплённый candidate, даже если `origin/<ref>` ушёл вперёд: обязательной проверки свежести базы
   и принудительного developer-перезапуска нет, и другие batch это не останавливает. Финальное
   обновление базы выполняет `integration refresh` при подготовке PR (раздел [«Integration accounting
   после publish»](publish.md#integration-accounting-publish)).
2. Сверить активные batch, `concurrency_budget`, writer и quality-gate lane. Пересечение файлов
   другого batch не повод откладывать запуск, а занятая serialized quality-gate lane не мешает
   параллельной реализации. Если batch упёрся в бюджет, дождитесь завершения активного batch или
   поднимите `concurrency_budget`.
3. Создать и отдельно утвердить architect dispatch, принять его отчёт и только потом создать
   developer dispatch. Порядок жёсткий: coordinator отклоняет `dispatch create --role developer`,
   пока для того же batch нет architect-отчёта, принятого через `batch decide --decision accept`.
   Правило живёт в `coordinator.py`, поэтому действует и для ручного CLI, и для `/implement`. CLI
   сохраняет immutable brief до передачи:

   ```bash
   # сначала dry run: показывает канонический переход и его digest, brief не пишет
   python .harness/orchestration/coordinator.py --repo . dispatch propose \
     --batch <batch-id> --role developer --runtime codex
   # approval действует только для показанного digest
   python .harness/orchestration/coordinator.py --repo . dispatch create \
    --batch <batch-id> --role developer --runtime codex --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --transition-digest <transition_digest>
   python .harness/orchestration/coordinator.py --repo . dispatch send \
     --dispatch <dispatch-id> --adapter <project-runtime-adapter>
   ```

   Для роли с `transport: "in-process"` adapter не передаётся вовсе. `dispatch send --dispatch <id>`
   возвращает путь к brief. После этого coordinator **немедленно** запускает роль как субагента
   текущей сессии. Между этими действиями coordinator не читает предыдущие dispatch, report и template. Без
   `.harness/orchestration.json` к `dispatch create` добавляются `--model` и `--effort` вызывающей
   сессии. Для coordinator и architect выбирайте `medium`, если разработчик явно не одобрил иное.

   Architect кладёт предложенный commit plan в поле `commit_plan` отчёта. `report submit` проверяет
   его теми же правилами, что файл плана ниже, и отказывает, если путь плана лежит вне
   `allowed_paths` batch: brief каждой роли называет их в поле `allowed_paths`. Accept такого
   отчёта закрепляет план без файла. Если отчёт плана не несёт, accept может закрепить план из
   файла:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --commit-plan-file .harness/.sandboxes/scratch/commit-plan.json
   ```

   Файл лежит в репозитории или одном из его worktree, например в
   `.harness/.sandboxes/scratch/inbox/`; внешний `/tmp` отклоняется. Файл рядом с планом из отчёта
   должен содержать тот же план. Файл содержит ровно один ключ
   `{"commit_plan": [...]}`. Каждая entry содержит ровно четыре поля: уникальный `id`
   (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`), непустой `summary`, непустой список `expected_paths`
   (относительные пути или glob без ведущего `/` и сегмента `..`) и `covers` — номера пунктов DoD
   `1..n`, которые реализует entry. Порядок entries — порядок коммитов. Accept отклоняется с
   remedy, если какой-то пункт DoD не покрыт ни одной entry, entry называет несуществующий пункт
   или флаг передан не с `--decision accept` на отчёте architect. Тогда отчёт остаётся ожидающим
   решения, а batch не меняется. Coordinator сохраняет проверенный план в batch как `commit_plan`.
   Решение architect получает `commit_plan_sha256`. Этот план становится `commit_plan` каждого
   developer brief batch-а, включая `developer-retry`. Если план в batch не совпадает с digest
   принятого решения, developer brief не создаётся. Brief developer также несёт `accepted_design`:
   id dispatch architect-а, `report_sha256` и `output` принятого отчёта, поэтому coordinator не
   пересказывает дизайн в промпте. Без файла brief содержит по одной entry `step-N`
   на пункт DoD с `covers: [N]`. При `low_risk` и `milestone` coordinator автоматически принимает
   чистый architect report с планом по умолчанию. Поэтому architect, который предлагает другой план,
   указывает это в `risks`, и report ждёт ручного решения.

   `dispatch send` для роли code-review — единственный случай, когда нужен ещё один обязательный флаг:
   `--checkout <путь>`. Он указывает на worktree, реально зачекаученный на `candidate_commit`
   dispatch-а (см. [Clean-room QA lane](qa.md#clean-room-qa-lane): та же изоляция нужна и для review). Все остальные роли
   не передают `--checkout`. Без него coordinator отклоняет `dispatch send` и показывает точный текст
   ожидаемого флага.
4. Принять один schema-validated completion report с evidence. Coordinator сохраняет его как
   canonical JSON и детерминированную Markdown-проекцию. После этого dispatch остаётся `reported`, а
   batch ждёт следующего решения:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report submit \
     --file developer-report.json
   ```
   В `checks_run[*].result` канонические значения — `pass`, `fail` и `not_run`; только architect
   может использовать `not_run_architect_read_only` для совместимости со старыми brief.
   Architect work без verification gate сохраняет пустой `checks_run`.
   `pass` и `passed` равнозначны; старое `not-run` равнозначно `not_run`. Новые отчёты
   сохраняются с каноническими значениями; старые immutable report читаются без перезаписи.
   Неизвестные результаты отклоняются с `remedy` до записи canonical report. Исправьте
   staging-файл по evidence и повторите отправку для того же dispatch: `pass` означает
   успешную команду, `fail` — неуспешную, `not_run` — незапущенную. Автоматическое принятие
   одинаково учитывает `pass` и `passed`.
   Если результат допустим как evidence, это ещё не значит, что отчёт примут автоматически.
   Перед решением coordinator снова проверяет report, поэтому старый записанный отчёт
   с неизвестным результатом также получит отказ. Immutable report не редактируют;
   для уже записанного отчёта или остановленного batch оператор отдельно выбирает
   существующий маршрут восстановления. После `resume-stop` политика `auto` не возвращается.

   До следующего dispatch coordinator записывает отдельное решение. При `manual_all` или нечистом
   report человек принимает report, override-ит warning либо требует retry. При `low_risk` и чистом
   report coordinator сам записывает `accept` с rationale
   `Auto-accepted due to low_risk policy and clean report`, вычисляет `next_action` и готовит
   следующий допустимый dispatch. При `milestone` чистый отчёт вне вехи также получает `accept`.
   После developer coordinator оценивает риск, а QA-dispatch ждёт отдельного approval. Чистый
   QA-report при `milestone` ждёт решения человека.

   Policy-цепочка (`policy-decide`, `risk-assess`, `next-dispatch`) идёт отдельными командами уже
   после записи report. Каждая команда может остановиться: ledger занят, поднят `needs_attention`,
   изменилось состояние batch. Тогда `report submit` всё равно завершается с кодом 0. Report
   записан, ответ называет его (`report`, `report_sha256`) и несёт объект `completion`. Объект
   содержит `route: "report-completion"`, `failed_step`, состояние каждого шага (`done`,
   `already-done`, `not-applicable`, `failed`, `not-run`), `error`, `remedy` и точную команду
   `command`. Её выполняет сам coordinator (`run_by: "coordinator"`), а не worker:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report complete --dispatch <dispatch-id>
   ```

   `report complete` идемпотентна: каждый шаг выводится из ledger, поэтому уже записанное решение,
   risk assessment или следующий dispatch не повторяются, а повторный запуск ничего не пишет.
   Команда повторяет только policy, записанную при `report submit` (`auto_accept_policy` в статусе
   dispatch), никогда не записывает report заново и не создаёт dispatch для роли, сдавшей report.
   Шаг `risk-assess` оценивает candidate report-а: у developer это его `commit_sha` и
   `changed_files`, а у read-only verification — candidate, закреплённый в её dispatch, с файлами из
   diff от base batch, как их считает `risk assess`. Шаг, которому нужен человек, останавливается с
   remedy этого шага. Для report, оставленного человеку, все шаги — `not-applicable`. Повторно
   отправлять report нельзя: он уже записан.

   Ручное решение выглядит так:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc>
   ```

   Developer report против brief с `commit_plan` несёт `commit_map`. Это пары
   `{commit_sha, plan_entry_id}` для каждого коммита после `snapshot_commit` (у rebase — после
   `rebase_target`). В initial и rebase отчёте это отношение. Коммит, закрывающий несколько
   entries, даёт по паре на каждую entry. Entry, закрытая несколькими коммитами, даёт по паре на
   каждый коммит. Если отображение не one-to-one (объединённый коммит, разделённая или незакрытая entry),
   это расхождение. Тогда отчёт обязан нести `dod_coverage` — ровно по записи на каждый пункт DoD:
   `{"dod_item": <n>, "commits": [<sha>, ...]}` из коммитов этого dispatch или
   `{"dod_item": <n>, "not_covered": "<причина>"}`. Также отчёт обязан нести непустой
   `divergence_justification`: что объединено, разделено или добавлено и почему. При one-to-one
   `dod_coverage` необязателен (coordinator выводит покрытие из `covers` плана), а
   `divergence_justification` отклоняется.
   `report submit` и `batch decide` отклоняют структурные ошибки, каждую с remedy:
   неотображённый созданный коммит, коммит не из этого dispatch, неизвестная entry, повтор пары,
   расхождение без `dod_coverage` или без обоснования, покрытие без пункта, с чужим пунктом или
   чужим коммитом, `not_covered` без причины. В `developer-retry` и в отчётах других ролей эти два
   поля отклоняются.

   `report submit` также сверяет `dod_coverage` с `commit_map` и `covers` плана. Команда отклоняет
   пункт DoD, заявленный покрытым набором коммитов, если `commit_map` не сопоставляет ни один из
   них с entry, у которой этот пункт есть в `covers`. Remedy называет пункт, заявленные коммиты и
   entries плана, покрывающие этот пункт. Обратное направление допустимо. `not_covered` с причиной
   валиден и для пункта, который сопоставление формально покрывает. Как любой `not_covered`, он
   требует ручного решения. One-to-one отчёт без `dod_coverage` получает покрытие из `covers` и не
   требует этой сверки.

   Обоснованное расхождение с полным покрытием само по себе не делает отчёт нечистым. При
   `low_risk` и `milestone` coordinator автоматически принимает отчёт, чистый в остальном. Запись
   решения получает `commit_plan_divergence` (`developer_dispatch_id`, `justification`,
   `merged_commits`, `split_entries`, `unclosed_entries`). Ту же запись получает и ручное принятие.
   Любой пункт `not_covered` делает отчёт нечистым при любой policy. Auto-accept не срабатывает,
   `--decision accept` отклоняется. Принять отчёт можно только через `--decision override-warning` с
   `--note`, отличным от `none` (решение получает `dod_not_covered` с причинами). Иначе отчёт можно
   вернуть через `retry`. Выход за scope — предупреждение, а не отказ. Completed-отчёт
   developer с `changed_files` вне `write_paths` `report submit` записывает. `batch decision-packet`
   показывает эти пути в `scope_warnings`. Такой отчёт coordinator не принимает автоматически ни при одной
   policy, а `--decision accept` отклоняется. Принять его можно только через
   `--decision override-warning` с `--note`, отличным от `none`, и явным `--approved-by`. Решение
   получает `scope_warnings`, а override добавляет coordinator finding. Следующий brief code-review
   несёт эти пути как пункт, который review должен закрыть. Принятие architect-отчёта с
   `--commit-plan-file` проходит, если `expected_paths` плана выходят за `allowed_paths` batch-а.
   Тогда packet (с тем же `--commit-plan-file`) и решение содержат те же `scope_warnings`. Запрет
   записи вне `write_paths` для самого worker-а, проверка `changed_files` в checkpoint и отчёты
   других write-ролей остаются строгими.
   `batch decision-packet` показывает `dod_coverage`, `dod_coverage_source` (`report` или
   `derived`) и `commit_plan_divergence`. Brief code-review несёт `commit_plan_divergence`
   последнего принятого initial или rebase developer report (у остальных ролей поле `null`). По
   нему reviewer проверяет, что границы коммитов остались reviewable.

   Дефект, который coordinator нашёл в чистом developer report, не тратит developer-retry до review
   (маршрут `carry-over`). Retry developer report без accept — исключение только для невыполненного
   пункта DoD или изменения вне scope. В остальных случаях report принимают с находками:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   Файл лежит в репозитории или одном из его worktree и содержит ровно один ключ
   `{"findings": [...]}`. Каждая находка содержит ровно три поля: непустой `summary`, `files` —
   непустой список уникальных путей от корня репозитория в POSIX-форме (без ведущего `/`, обратной
   косой черты и сегмента `..`) — и непустой `expected_evidence`: чем review подтвердит закрытие.
   Coordinator передаёт текст находки роли, поэтому пишите его на английском. Флаг допустим только с `accept` или
   `override-warning` на completed developer work report. Иначе решение отклоняется с remedy, и
   batch не меняется. Coordinator записывает каждую находку в batch append-only как запись
   `carried_items`: `item_id` `coordinator-finding-<n>` (порядковый номер в batch), `source` (`kind`,
   `dispatch_id` и `report_sha256` принятого report, `candidate_commit`), `summary`, `files`,
   `expected_evidence`, `attached_at`, `attached_by` и `record_sha256`. Coordinator сверяет
   этот hash при каждом чтении batch.

   Policy auto-accept не принимает файл находок. После него находки добавляет `batch carry-over`:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch carry-over \
     --batch <batch-id> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   Команда не создаёт dispatch и не меняет candidate, поэтому человек её не утверждает. Она
   записывает решение coordinator `carry-over` с `approved_by: policy:carry-over`. Находки она
   прикрепляет к последнему принятому developer work report. Batch с `next_action: qa` переходит в
   `code-review`. Команда отклоняется с remedy: пока какой-либо report ждёт решения; если в batch нет
   принятого developer work report; если после него уже создан dispatch, не отменённый и не
   переведённый `batch resume` в `abandoned`. Для неотправленного code-review (или qa, созданного
   low_risk-цепочкой) remedy — `dispatch cancel` и повтор `batch carry-over`. Для отправленного —
   сообщить дефект при решении его report. Для уже решённого report — приложить находку через
   `batch decide --findings-file` при accept следующего developer report.

   Пока находка открыта, risk assessment ведёт candidate в `code-review`, даже если ни один триггер
   не совпал (`review_required` записи оценки не меняется). Находка закрыта, когда принят (`accept`
   или `override-warning`) code-review, чей brief её нёс. Retry review оставляет её открытой.

   Каждый brief несёт секцию `carried_items` — общий канал переносимых пунктов. Это объект: ключ —
   вид источника (`coordinator-finding`, `review-finding`, `incomplete-item`), значение — список
   `{item_id, source, summary, files, expected_evidence}`. Пустой канал — `{}`. Brief code-review и
   developer work несёт все открытые `coordinator-finding`. Developer brief, отвечающий на `retry`
   code-review с маршрутом `fix-forward`, несёт ещё находки осей Standards и Spec этого review
   как `review-finding` (`item_id` `review-finding-<n>`; `source` — `dispatch_id`, `report_sha256`,
   `axis`, `severity`; `files: []`; `expected_evidence` — evidence находки). Поэтому единственный
   developer-retry закрывает обе группы и тратит `retry_policy.max_developer_retries` один раз.
   Accept с находками и `batch carry-over` бюджет не тратят. Непустая секция входит в transition как
   `carried_items_sha256`. Поэтому находка, добавленная после `dispatch propose`, требует нового
   approval.

   Отчёт code-review отчитывается по каждому пункту brief в необязательном `review.carried_items`:
   `[{"item_id": ..., "status": "closed" | "open" | "unverified", "evidence": ...}]`. `report submit`
   отклоняет пункт, которого brief не нёс, повтор пункта, неизвестный статус и пустое evidence.
   Пропуск пункта структурно допустим, но пропуск, как и `unverified` и `open`, — это carried gap, и
   такой отчёт не clean: policy его автоматически не принимает, а `--decision accept` отклоняется.
   `override-warning` требует `--note`, отличный от `none`, и записывает в решение
   `carried_items_gap`. Отчёт можно и вернуть через `retry`. Правила blocker и warning сохраняют
   приоритет. Пункт `open` — структурное evidence категории `code`, поэтому такой retry ведёт в
   developer-retry маршрутом `fix-forward`. `batch decision-packet` показывает `carried_items`
   (каждый пункт с `source`, `summary`, `status` — у отчёта code-review `omitted` для пропущенного
   пункта — и `evidence`) и `carried_items_gap`.

   Read-only роль (architect, verification, code-review или qa), не выполнившая часть brief,
   перечисляет невыполненные пункты в необязательном поле отчёта `incomplete_items`:
   `[{"brief_item": ..., "reason": ..., "target_role": ...}]`. Текст пишется на английском, потому что
   пункт уходит в brief следующей роли как agent-to-agent текст. Каждая строка непустая и не длиннее
   1600 символов. `target_role` — сама роль отчёта (для суженного retry) или более поздняя роль:
   architect → architect, developer, code-review или qa; verification → verification, code-review
   или qa; code-review → code-review или qa; qa → qa. Пункт, который не дал выполнить инструмент
   (например, классификатор безопасности), несёт собственный `tooling_blocker` той же формы, что и у
   отчёта, при любом outcome. `report submit` с remedy отклоняет поле у write-роли, пункт без
   `reason`, неизвестную или недопустимую `target_role`, кириллицу и некорректный `tooling_blocker`.

   Отчёт с непустым `incomplete_items` не принимается автоматически ни при одной `approval_policy`, а
   простой `accept` или `override-warning` отклоняется. Человек выбирает одно из двух решений:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --carry-incomplete
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision retry --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --narrowed
   ```

   `--carry-incomplete` (с `accept` или `override-warning`) записывает routing record `carry-over` с
   `carried_item_ids` (`incomplete-item-<n>`, сквозная нумерация в batch). `next_action` меняется как
   при любом accept этой стадии. Batch не хранит пункты. Work brief целевой роли читает их из
   immutable отчёта и несёт в `carried_items` под видом `incomplete-item`. Так продолжается, пока не
   принят (`accept` или `override-warning`) dispatch этой роли, чей brief их нёс. Retry оставляет
   пункт открытым. Открытый пункт для code-review ведёт candidate в code-review, даже если risk
   assessment не нашла триггеров. Флаг отклоняется без пунктов, с другим решением и тогда, когда хоть
   один пункт нацелен на саму роль отчёта. Такой пункт закрывает только суженный retry.

   `--narrowed` (только с `retry`) повторяет ту же стадию на том же SHA. Brief нового dispatch несёт
   только пункты отчёта. Definition of Done в brief остаётся полным DoD batch. Маршрут —
   `narrowed-retry` с `reason_category: null`. Если хоть один пункт несёт `tooling_blocker`, маршрут —
   `tooling-retry` с категорией `tooling` (подтвердить ложное срабатывание, завести bug-тикет на
   инструмент; серию ограничивает attention `tooling-retry-repeated`). Бюджет
   `retry_policy.max_developer_retries` не тратится, а новый dispatch утверждается по
   `approval_policy`. `--narrowed` отклоняется: для developer и publish; для отчёта без пунктов;
   вместе с `--reason-category` или `--retry-role developer`; при структурном evidence другого
   маршрута. Такое evidence — finding или severity warning/blocker на оси, открытый carried item,
   failed check, сдвинутый candidate. Retry без `--narrowed` игнорирует пункты и маршрутизируется как
   раньше.

   `source` пункта `incomplete-item` содержит `dispatch_id` и `report_sha256` отчёта, его `role`,
   `target_role` (роль, чей brief несёт пункт), `route` (`carry-over`, `narrowed-retry` или
   `tooling-retry`), `reason` и `reason_category` (`tooling` у пункта с `tooling_blocker`, иначе
   `null`). `summary` — это `brief_item`, `files` пуст. `batch decision-packet` показывает
   `incomplete_items` отчёта; без `--findings-file` он добавляет `route_preview["carry-over"]` —
   запись, которую сделает `--carry-incomplete`, либо отказ. `batch decision-packet --narrowed`
   показывает маршрут суженного retry.

Минимальный ручной brief хранит ticket и dispatch ID, роль и её access, выбранный
profile/model/effort, allowed paths (scope записи), issue-ветку/worktree, DoD, запреты, команды,
dependencies, approval. Для write-роли completion report обязан включать commit SHA, exact changed
files, результаты всех checks, risks, blockers и следующее решение coordinator-а. Write-роль может
остановиться до изменений (например, из-за risk trigger при отсутствии необходимого gate). Тогда
coordinator принимает честный отчёт с `outcome: blocked`, пустым `changed_files` и `commit_sha`,
привязанным к проверенному checkout (`snapshot_commit`). Coordinator регистрирует отчёт и
возвращает `decision_packet` с `recovery_route` (`retry`, `block`, `abandon`). Незавершённый
candidate он не регистрирует. Для read-only роли вместо SHA указывается
`not applicable — read-only role`.

Новые факты не меняют отправленный brief: coordinator добавляет отдельное решение с evidence. Если
изменились scope, DoD, assignment или proof, текущий dispatch заканчивается и создаётся новый.
Повтор после `blocked` или `failed` — тоже новый dispatch с новым ID и brief.

## Наблюдение запуска и готовый несданный отчёт {#_4}

Поставляемый пример — `.harness/orchestration/adapters/claude_code.py`; `claude` или `codex`
сами по себе не адаптеры. Консоль Harness сначала открывает выбранную сессию,
затем выполняет подтверждённую отправку. Для намеренно скрытого запуска передают
`--adapter-arg=--visibility=background`. Пример сохраняет native permissions и hooks.
Проверка родителя не подтверждает доступ Bash-инструментов внутри worker: native probe должен
пройти до реализации. Если доступ отказывает постоянно, подготовьте среду: одинаковые retry не помогут.
Смена sandbox-профиля делается до propose/approval; глобальные настройки не отключаются.

`dispatch observe --dispatch <id> --offset <next_offset>` читает существующие события локально.
Для worker под надзором runtime (brief с `execution`) события берутся из журнала запуска:
runtime пишет stdout worker в `executions/<operation_id>/stdout.log`, а stderr — в `stderr.log`
рядом, в state-каталоге оркестрации. `dispatch logs --dispatch <id>` возвращает страницу тех же
событий, а с `--follow` печатает каждое событие строкой JSON, пока worker работает, и
заканчивается итоговой строкой после его выхода. Цикл `--follow` не держит замок ledger, поэтому
не мешает self-report, heartbeat и сдаче отчёта. Экран worker в веб-консоли показывает этот же
журнал во время работы.
Открытие панели, обновление и reconnect не вызывают модель; окно можно закрыть без остановки
worker. Запрос native-разрешения подтверждает человек; он не даёт dispatch approval.
Первый self-report coordinator по умолчанию ждёт 120 секунд, независимо от порога stale для heartbeat.
Если ранний выход worker доказан, порядок такой: auto-report → auto-decide → resume-stop --restart,
который выполняет человек. Повторный
запуск сохраняет исходный контракт; при drift нужен новый propose.

Для готового отчёта, который worker не смог сдать, coordinator использует исходный staging-файл:
`report submit --file <path> --relayed-by <sender> --relay-reason <exact-error>
--source-sha256 <hash-original-bytes>`. Coordinator не редактирует JSON worker и записывает provenance отдельно.
Fail/not_run остаются такими; make lint не заменяет make verify. При уже записанном отчёте
используют report complete, когда результат submit указывает этот маршрут. Сравнение падения
с базовым SHA — отдельное evidence, не исправление исходного отчёта задним числом.

## Необязательный внешний adapter {#5-adapter}

Capability `backend-orchestration` поставляет два стандартных адаптера:
`.harness/adapters/claude_worker.py` для Claude Code и `.harness/adapters/codex_worker.py` для Codex.
Их устанавливают `harness init`/`adopt`, а обычный `harness update <repo>` восстанавливает
отсутствующие файлы и обновляет управляемые версии. В настройках консоли доступны состояния,
просмотр плана и явное подтверждение; текущий состав capability сохраняется.

Для уже одобренного dispatch с выбранным `external` используйте адаптер назначенного runtime:

```bash
python /path/to/project/.harness/orchestration/coordinator.py --repo /path/to/project dispatch send --dispatch <dispatch-id> --adapter /path/to/project/.harness/adapters/claude_worker.py
```

Для Codex замените путь адаптера на `/path/to/project/.harness/adapters/codex_worker.py`.
Coordinator запускает `.py` через свой Python в checkout worker. Модель и effort адаптер
берёт из immutable brief. Под надзором runtime (brief с `execution`) адаптер живёт столько же,
сколько worker: держит его в своей группе процессов, свой stdin не читает и возвращает код выхода
worker (`128 + N` при сигнале N). Claude получает промпт аргументом после `-p`, Codex — запросом
протокола `app-server`. Это правило обязательно и для нового адаптера: адаптер, который
завершается раньше worker, переводит dispatch в `blocked` с `worker-exited-without-report`. Без
`execution` адаптер передаёт lifecycle-промпт отсоединённому worker через stdin. Claude ограничивает
дополнительный доступ каталогом входящих отчётов и использует нативный `allowed_tools`;
read-only роль (не `developer` и без `Edit`/`Write`) дополнительно получает `Edit(//<report_staging_path>)`
и может записать только свой отчёт. Если `--claude-bin` задан именем, а не путём, Claude ищется в `PATH`,
затем в `~/.local/bin`.
Codex передаёт этот список в промпте, а sandbox выбирает по `access`: `read-only` или
`workspace-write`. Это не нативный фильтр инструментов Codex.
Оба адаптера отклоняют `qa`, `purpose: publish`, другой transport и отсутствующий `allowed_tools`.
Ранний выход отсоединённого worker, даже с кодом `0`, возвращает ошибку запуска и конец лога.
`harness health` сверяет установленные адаптеры с версией harness (`orchestration.adapters`) и
ищет `claude` и `codex` в PATH окружения `harness-runtime serve` (`orchestration.worker_binaries`):
runtime запускает worker в этом окружении, а не в окружении coordinator.
Для проверки команды без модели есть `dispatch --dry-run`, для тестового executable —
`--claude-bin`/`--codex-bin`, для строк developer-retry — `--extra-prompt-file`.

Для `transport: "external"` проект передаёт `--adapter <path>` в `dispatch send`. Это transport-only
граница. Coordinator передаёт этому исполняемому файлу одобренный immutable brief через `--repo` и
`--brief`.
Adapter отвечает за запуск worker в выбранной среде. Он не выбирает scope, не принимает report,
не планирует следующий dispatch и не мержит PR. После запуска worker возвращает completion report
по общим правилам раздела [«Coordinator CLI и lifecycle»](#4-coordinator-cli-lifecycle). Доступ и среду запуска проверяет проектный adapter.

## Первый pilot и источник правил {#6-pilot}

Не задавайте лимиты токенов или «правильный» уровень параллелизма на глаз. В первом периоде pilot
записывайте по каждому закрытому ticket agent starts, tokens per batch, quality-gate wall time и
post-integration defects, включая источник и отсутствующие данные. Форма и единые правила подсчёта
лежат в `.harness/orchestration/pilot.md`.

Полный нормативный источник — `.harness/orchestration/playbook.md`, а границы отдельных ролей лежат
в `.harness/orchestration/roles/`. При противоречии между удобством конкретного runtime и этим
контрактом приоритет у manifest'а, immutable brief и явного approval.

Архитектурный контракт маршрута целиком зафиксирован в
[ADR 0003](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0003-orchestration-core.md): opt-in capability, отдельное
approval для dispatch, review и QA для одного SHA, локальное санитизированное evidence и adapter
только для транспорта. Превращение `/implement` в coordinator-driven конвейер по умолчанию, model
self-report, dispatch watchdog, per-role transport и zero-config дефолты зафиксированы в
[ADR 0005](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0005-implement-pipeline.md).
