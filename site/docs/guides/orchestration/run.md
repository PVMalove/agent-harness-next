# Запуск и отчёты

Coordinator ведёт batch, отдельную единицу работы над тикетом. Каждый dispatch передаёт роли неизменяемое задание. Пройдите планирование, отправку и приём отчёта по порядку.

[Обзор оркестрации](../../backend-orchestration.md)

## Выбрать роли и спланировать batch {#3-batch}

В базовом наборе четыре write-роли и четыре read-only роли.

| Роль | Режим | Когда назначать |
| --- | --- | --- |
| `developer` | write | Обычное backend-изменение внутри сервиса или bounded context. |
| `database-migrations` | write | Миграция схемы или данных, её rollout и rollback. |
| `messaging-integration` | write | Outbox, routing, схема сообщений, retry или DLQ. |
| `conflict-resolver` | write | Текстовый конфликт ветки тикета с integration SHA, который ушёл вперёд. Назначается только маршрутом `integration resolve`. |
| `architect` | read-only | Граничное решение, которое трудно отменить. |
| `qa` | read-only | Нужна независимая проверка через интерфейс, которым пользуется проект. |
| `code-review` | read-only | Обязателен для перечисленных high-risk triggers. Выдаёт отдельные отчёты Standards и Spec. |
| `verification` | read-only | Developer report остановился по операционной причине (`verification-infrastructure`, `transport`, `context-pressure`), а candidate уже есть и не менялся. Роль заново запускает утверждённые проверки на закреплённом candidate. |

Одна задача может пройти несколько ролей. Но handoff внутри batch всегда последовательный, и
активный writer в batch только один. Batch с пересекающимися файлами могут идти параллельно, каждый
в своих issue-ветке и worktree, пока хватает `concurrency_budget`. Пересечения разбираются при
интеграции и запуск не блокируют. Coordinator отклоняет второй batch на тот же незавершённый тикет,
ветку или worktree. Тяжёлые интеграционные проверки и проверки качества идут по одной
последовательной очереди quality gate.

Если задача затрагивает API или публичный контракт, миграцию схемы или данных, outbox и очереди,
транзакции, авторизацию и безопасность, конкурентность или retry, batch нельзя завершить, пока
coordinator не получит оба независимых отчёта `code-review`: Standards и Spec.

После developer dispatch coordinator детерминированно оценивает риски candidate commit по DoD,
изменённым файлам и триггерам, которые назвал developer. Оценка решает, когда составной read-only
`code-review` **обязателен**, но не когда он *разрешён*. Review можно создать для любого candidate,
и конвейер `/implement` делает это всегда. Оси Standards и Spec остаются отдельными evidence.
Отдельный QA dispatch coordinator создаёт только после принятого review, если review обязателен.
Обязательный полный QA gate в clean-room нельзя заменить локальной проверкой developer. Каждый новый
candidate commit после finding или упавшего QA снова проходит оценку риска.

## Coordinator CLI и lifecycle {#4-coordinator-cli-lifecycle}

Режим, независимый от runtime, не имеет команды «запустить всех». Coordinator CLI ведёт записи по
пути `planned → awaiting-approval ↔ active → completed`. Состояния `paused`, `blocked` и `failed`
восстановимы, `abandoned` означает окончательный отказ. После ручного восстановления действует
политика `manual_all`.

Что делает coordinator при каждой `approval_policy`:

- `manual_all`: каждый report оставляет dispatch в `reported` до решения человека.
- `low_risk`: coordinator сам принимает чистый завершённый report, если scope batch целиком лежит в
  `low_risk_paths`, и записывает решение в ledger. Blockers, упавшие проверки, раскрытые risks,
  risk triggers и findings любой оси review оставляют ручной gate. Для publish тоже нужно
  отдельное approval.
- `milestone`: coordinator тоже сам принимает чистый отчёт обычной роли. Но QA, publish и
  рискованные переходы остаются ручными вехами.
- `auto`: coordinator проходит путь от `batch approve` до принятого publish без человека. Политика
  согласует каждый шаг, а `batch auto-decide` решает по отчётам (см.
  [«Автоматический путь `approval_policy: auto`»](decisions.md#approval_policy-auto) в главе
  «Решения и повторы»). Открытие PR и merge остаются ручными.

1. Создайте batch в состоянии `planned`, затем отдельно утвердите его:

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

   `batch create` сначала выполняет `git fetch origin <ref>`. Ref берётся из `--integration-ref`,
   а без него из `base_branch` проекта (для задач без эпика). Полученную вершину команда
   записывает как `base_commit`/`integration_base_commit`. Необновлённый локальный HEAD её никогда
   не заменяет.

   Полный маршрут `/implement` требует явно указать `--required-gate review --required-gate qa`
   (независимые review Standards и Spec и полный clean-room QA). Coordinator проверяет, что они
   есть в `required_gates`, до отправки worker write-роли (`developer`). В допустимых прямых
   CLI-сценариях `--required-gate` можно не указывать (по умолчанию `["none"]`).

   Review, QA и publish проверяют закреплённый candidate, даже если `origin/<ref>` ушёл вперёд.
   Обязательной проверки свежести базы и принудительного перезапуска developer нет, и другие batch
   это не останавливает. Базу в последний раз обновляет `integration refresh` при подготовке PR
   (раздел [«Integration accounting после publish»](publish.md#integration-accounting-publish)).
2. Сверьте активные batch, `concurrency_budget`, writer и очередь quality gate. Пересечение файлов
   с другим batch не повод откладывать запуск, а занятая очередь quality gate не мешает
   параллельной реализации. Если batch упёрся в бюджет, дождитесь завершения активного batch или
   поднимите `concurrency_budget`.
3. Создайте и отдельно утвердите architect dispatch, примите его отчёт и только потом создавайте
   developer dispatch. Порядок жёсткий: coordinator отклоняет `dispatch create --role developer`,
   пока в том же batch нет architect-отчёта, принятого через `batch decide --decision accept`.
   Правило проверяет `coordinator.py`, поэтому оно действует и для ручного CLI, и для
   `/implement`. CLI сохраняет неизменяемый brief до передачи:

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

   Для роли с `transport: "in-process"` adapter не передаётся. `dispatch send --dispatch <id>`
   возвращает путь к brief, и coordinator **сразу** запускает роль как субагента текущей сессии.
   Между этими действиями coordinator не читает прежние dispatch, report и шаблоны. Если
   `.harness/orchestration.json` нет, к `dispatch create` добавляются `--model` и `--effort`
   вызывающей сессии. Для coordinator и architect выбирайте `medium`, если разработчик явно не
   одобрил другое.

   Architect кладёт предложенный план коммитов в поле `commit_plan` отчёта. `report submit`
   проверяет его по тем же правилам, что и файл плана ниже. Команда отказывает, если путь плана
   лежит вне `allowed_paths` batch. Brief каждой роли называет эти пути в поле `allowed_paths`.
   Accept такого отчёта закрепляет план без файла. Если в отчёте плана нет, accept может закрепить
   план из файла:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --commit-plan-file .harness/.sandboxes/scratch/commit-plan.json
   ```

   Файл должен лежать в репозитории или в одном из его worktree, например в
   `.harness/.sandboxes/scratch/inbox/`. Внешний `/tmp` coordinator отклоняет. Если план есть и в
   отчёте, файл должен содержать тот же план. Файл содержит ровно один ключ
   `{"commit_plan": [...]}`. Каждая запись (entry) содержит ровно четыре поля:

   - уникальный `id` (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`);
   - непустой `summary`;
   - непустой список `expected_paths`: относительные пути или glob без ведущего `/` и без
     сегмента `..`;
   - `covers`: номера пунктов DoD `1..n`, которые реализует запись.

   Порядок записей задаёт порядок коммитов. Accept отклоняется с remedy, если пункт DoD не покрыт
   ни одной записью, запись называет несуществующий пункт или флаг передан не с
   `--decision accept` на отчёте architect. Тогда отчёт ждёт решения, а batch не меняется.

   Coordinator сохраняет проверенный план в batch как `commit_plan`, а решение по architect
   получает `commit_plan_sha256`. Этот план попадает в `commit_plan` каждого developer brief
   batch, включая `developer-retry`. Если план в batch не совпадает с digest принятого решения,
   developer brief не создаётся. Developer brief также содержит `accepted_design`: id dispatch
   architect, `report_sha256` и `output` принятого отчёта. Поэтому coordinator не пересказывает
   дизайн в промпте. Без файла brief содержит по одной записи `step-N` на каждый пункт DoD с
   `covers: [N]`. При `low_risk` и `milestone` coordinator сам принимает чистый architect report с
   планом по умолчанию. Поэтому architect, который предлагает другой план, пишет об этом в
   `risks`, и report ждёт ручного решения.

   `dispatch send` для роли code-review требует ещё один обязательный флаг: `--checkout <путь>`.
   Других таких ролей нет. Флаг указывает на worktree, в котором действительно выгружен
   `candidate_commit` dispatch (см. [Clean-room QA lane](qa.md#clean-room-qa-lane): review нужна та
   же изоляция). Остальные роли `--checkout` не передают. Без флага coordinator отклоняет
   `dispatch send` и показывает точный текст нужного флага.
4. Примите один completion report с evidence, проверенный по схеме. Coordinator сохраняет его как
   канонический JSON и детерминированную Markdown-проекцию. После этого dispatch остаётся в
   `reported`, а batch ждёт следующего решения:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report submit \
     --file developer-report.json
   ```
   Канонические значения `checks_run[*].result`: `pass`, `fail` и `not_run`. Только architect
   может использовать `not_run_architect_read_only` для совместимости со старыми brief. Работа
   architect без verification gate оставляет `checks_run` пустым. `pass` и `passed` равнозначны,
   старое `not-run` равнозначно `not_run`. Новые отчёты coordinator сохраняет с каноническими
   значениями, старые неизменяемые report читает без перезаписи. Неизвестный результат
   отклоняется с `remedy` до записи канонического report. Исправьте staging-файл по evidence и
   отправьте его ещё раз для того же dispatch: `pass` означает успешную команду, `fail`
   неуспешную, `not_run` незапущенную. Автоматическое принятие одинаково учитывает `pass` и
   `passed`.

   Допустимый как evidence результат ещё не значит, что отчёт примут автоматически. Перед решением
   coordinator снова проверяет report, поэтому старый записанный отчёт с неизвестным результатом
   тоже получит отказ. Неизменяемый report не редактируют. Для уже записанного отчёта или
   остановленного batch оператор отдельно выбирает существующий маршрут восстановления. После
   `resume-stop` политика `auto` не возвращается.

   До следующего dispatch coordinator записывает отдельное решение. При `manual_all` или нечистом
   report человек принимает report, делает override предупреждения или требует retry. При
   `low_risk` и чистом report coordinator сам записывает `accept` с rationale
   `Auto-accepted due to low_risk policy and clean report`, вычисляет `next_action` и готовит
   следующий допустимый dispatch. При `milestone` чистый отчёт вне вехи тоже получает `accept`.
   После developer coordinator оценивает риск, а QA-dispatch ждёт отдельного approval. Чистый
   QA-report при `milestone` ждёт решения человека.

   Цепочка политики (`policy-decide`, `risk-assess`, `next-dispatch`) идёт отдельными командами
   уже после записи report. Каждая команда может остановиться: ledger занят, поднят
   `needs_attention`, изменилось состояние batch. Тогда `report submit` всё равно завершается с
   кодом 0. Report записан, ответ называет его (`report`, `report_sha256`) и содержит объект
   `completion`. В объекте есть `route: "report-completion"`, `failed_step`, состояние каждого шага
   (`done`, `already-done`, `not-applicable`, `failed`, `not-run`), `error`, `remedy` и точная
   команда `command`. Её выполняет сам coordinator (`run_by: "coordinator"`), а не worker:

   ```bash
   python .harness/orchestration/coordinator.py --repo . report complete --dispatch <dispatch-id>
   ```

   `report complete` идемпотентна: каждый шаг она выводит из ledger. Поэтому уже записанные
   решение, оценка риска или следующий dispatch не повторяются, а повторный запуск ничего не пишет.
   Команда повторяет только политику, записанную при `report submit` (`auto_accept_policy` в
   статусе dispatch). Она никогда не записывает report заново и не создаёт dispatch для роли,
   которая сдала report. Шаг `risk-assess` оценивает candidate из report. У developer это его
   `commit_sha` и `changed_files`. У read-only verification это candidate, закреплённый в её
   dispatch, с файлами из diff от base batch, как их считает `risk assess`. Шаг, которому нужен
   человек, останавливается с remedy этого шага. Для report, оставленного человеку, все шаги
   получают `not-applicable`. Отправлять report повторно нельзя: он уже записан.

   Ручное решение выглядит так:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc>
   ```

   Developer report по brief с `commit_plan` содержит `commit_map`: пары
   `{commit_sha, plan_entry_id}` для каждого коммита после `snapshot_commit` (у rebase после
   `rebase_target`). В initial и rebase отчёте это отношение «многие ко многим». Коммит, который
   закрывает несколько записей, даёт пару на каждую запись. Запись, которую закрывают несколько
   коммитов, даёт пару на каждый коммит.

   Если отображение не один к одному (объединённый коммит, разделённая или незакрытая запись),
   это расхождение. Тогда отчёт обязан содержать:

   - `dod_coverage`: ровно одна запись на каждый пункт DoD, либо
     `{"dod_item": <n>, "commits": [<sha>, ...]}` из коммитов этого dispatch, либо
     `{"dod_item": <n>, "not_covered": "<причина>"}`;
   - непустой `divergence_justification`: что объединено, разделено или добавлено и почему.

   При отображении один к одному `dod_coverage` необязателен (coordinator выводит покрытие из
   `covers` плана), а `divergence_justification` отклоняется. `report submit` и `batch decide`
   отклоняют структурные ошибки, каждую с remedy: неотображённый новый коммит, коммит не из этого
   dispatch, неизвестная запись плана, повтор пары, расхождение без `dod_coverage` или без
   обоснования, покрытие без пункта, с чужим пунктом или чужим коммитом, `not_covered` без
   причины. В `developer-retry` и в отчётах других ролей эти два поля отклоняются.

   `report submit` также сверяет `dod_coverage` с `commit_map` и `covers` плана. Команда отклоняет
   пункт DoD, который отчёт называет покрытым набором коммитов, если `commit_map` не сопоставляет ни
   один из них с записью, у которой этот пункт есть в `covers`. Remedy называет пункт, заявленные
   коммиты и записи плана, которые покрывают этот пункт. Обратное направление допустимо:
   `not_covered` с причиной валиден и для пункта, который сопоставление формально покрывает. Как
   любой `not_covered`, он требует ручного решения. Отчёт один к одному без `dod_coverage` получает
   покрытие из `covers`, и эта сверка ему не нужна.

   Обоснованное расхождение с полным покрытием само по себе не делает отчёт нечистым. При
   `low_risk` и `milestone` coordinator сам принимает отчёт, если он чист в остальном. Запись
   решения получает `commit_plan_divergence` (`developer_dispatch_id`, `justification`,
   `merged_commits`, `split_entries`, `unclosed_entries`). Ту же запись получает и ручное принятие.

   Любой пункт `not_covered` делает отчёт нечистым при любой политике. Auto-accept не срабатывает,
   `--decision accept` отклоняется. Принять отчёт можно только через `--decision override-warning`
   с `--note`, отличным от `none`. Решение тогда получает `dod_not_covered` с причинами. Иначе отчёт
   можно вернуть через `retry`.

   Выход за scope даёт предупреждение, а не отказ. Completed-отчёт developer с `changed_files` вне
   `write_paths` команда `report submit` записывает, а `batch decision-packet` показывает эти пути в
   `scope_warnings`. Такой отчёт coordinator не принимает сам ни при одной политике, и
   `--decision accept` отклоняется. Принять его можно только через `--decision override-warning` с
   `--note`, отличным от `none`, и явным `--approved-by`. Решение получает `scope_warnings`, а
   override добавляет coordinator finding. Следующий brief code-review передаёт эти пути как пункт,
   который review должен закрыть.

   Принятие architect-отчёта с `--commit-plan-file` проходит, даже если `expected_paths` плана
   выходят за `allowed_paths` batch. Тогда packet (с тем же `--commit-plan-file`) и решение
   содержат те же `scope_warnings`. Строгими остаются: запрет worker писать вне `write_paths`,
   проверка `changed_files` в checkpoint и отчёты других write-ролей.

   `batch decision-packet` показывает `dod_coverage`, `dod_coverage_source` (`report` или
   `derived`) и `commit_plan_divergence`. Brief code-review содержит `commit_plan_divergence`
   последнего принятого initial или rebase developer report (у остальных ролей поле равно `null`).
   По нему reviewer проверяет, что границы коммитов остались удобными для review.

   Дефект, который coordinator нашёл в чистом developer report, не тратит developer-retry до
   review (маршрут `carry-over`). Retry developer report без accept допустим только для
   невыполненного пункта DoD или изменения вне scope. В остальных случаях report принимают с
   находками:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   Файл лежит в репозитории или в одном из его worktree и содержит ровно один ключ
   `{"findings": [...]}`. Каждая находка содержит ровно три поля:

   - непустой `summary`;
   - `files`: непустой список уникальных путей от корня репозитория в POSIX-форме (без ведущего
     `/`, обратной косой черты и сегмента `..`);
   - непустой `expected_evidence`: чем review подтвердит, что находка закрыта.

   Coordinator передаёт текст находки роли, поэтому пишите его на английском. Флаг допустим только
   с `accept` или `override-warning` на completed developer work report. Иначе решение отклоняется
   с remedy, и batch не меняется. Каждую находку coordinator дописывает в batch (append-only) как
   запись `carried_items`: `item_id` `coordinator-finding-<n>` (порядковый номер в batch), `source`
   (`kind`, `dispatch_id` и `report_sha256` принятого report, `candidate_commit`), `summary`,
   `files`, `expected_evidence`, `attached_at`, `attached_by` и `record_sha256`. Этот hash
   coordinator сверяет при каждом чтении batch.

   Auto-accept по политике файл находок не принимает. После auto-accept находки добавляет
   `batch carry-over`:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch carry-over \
     --batch <batch-id> --findings-file .harness/.sandboxes/scratch/findings.json
   ```

   Команда не создаёт dispatch и не меняет candidate, поэтому человек её не утверждает. Она
   записывает решение coordinator `carry-over` с `approved_by: policy:carry-over` и прикрепляет
   находки к последнему принятому developer work report. Batch с `next_action: qa` переходит в
   `code-review`. Команда отклоняется с remedy, если:

   - какой-то report ждёт решения;
   - в batch нет принятого developer work report;
   - после него уже создан dispatch, который не отменён и не переведён `batch resume` в
     `abandoned`.

   Для неотправленного code-review (или qa, который создала цепочка `low_risk`) remedy такой:
   `dispatch cancel` и повтор `batch carry-over`. Для отправленного: сообщить о дефекте при решении
   по его report. Для уже решённого report: приложить находку через `batch decide --findings-file`
   при accept следующего developer report.

   Пока находка открыта, оценка риска ведёт candidate в `code-review`, даже если ни один триггер не
   совпал (`review_required` в записи оценки не меняется). Находка закрыта, когда принят (`accept`
   или `override-warning`) code-review, чей brief её содержал. Retry review оставляет её открытой.

   Каждый brief содержит секцию `carried_items`, общий канал переносимых пунктов. Это объект:
   ключ задаёт вид источника (`coordinator-finding`, `review-finding`, `incomplete-item`), значение
   содержит список `{item_id, source, summary, files, expected_evidence}`. Пустой канал равен `{}`.
   Brief code-review и developer work содержит все открытые `coordinator-finding`. Developer brief,
   который отвечает на `retry` code-review с маршрутом `fix-forward`, содержит ещё находки осей
   Standards и Spec этого review как `review-finding`: `item_id` `review-finding-<n>`, `source`
   (`dispatch_id`, `report_sha256`, `axis`, `severity`), `files: []`, `expected_evidence` из
   evidence находки. Поэтому один developer-retry закрывает обе группы и тратит
   `retry_policy.max_developer_retries` один раз. Accept с находками и `batch carry-over` бюджет не
   тратят. Непустая секция входит в transition как `carried_items_sha256`. Поэтому для находки,
   добавленной после `dispatch propose`, нужно новое approval.

   Отчёт code-review отвечает по каждому пункту brief в необязательном `review.carried_items`:
   `[{"item_id": ..., "status": "closed" | "open" | "unverified", "evidence": ...}]`.
   `report submit` отклоняет пункт, которого не было в brief, повтор пункта, неизвестный статус и
   пустое evidence. Пропуск пункта структурно допустим. Но пропуск, как `unverified` и `open`,
   считается carried gap, и такой отчёт нечистый: политика его сама не принимает, а
   `--decision accept` отклоняется. `override-warning` требует `--note`, отличный от `none`, и
   записывает в решение `carried_items_gap`. Отчёт можно и вернуть через `retry`. Правила blocker
   и warning сохраняют приоритет. Пункт `open` считается структурным evidence категории `code`,
   поэтому такой retry ведёт в developer-retry маршрутом `fix-forward`. `batch decision-packet`
   показывает `carried_items` (каждый пункт с `source`, `summary`, `status` и `evidence`; у отчёта
   code-review пропущенный пункт получает `omitted`) и `carried_items_gap`.

   Read-only роль (architect, verification, code-review или qa), которая не выполнила часть brief,
   перечисляет невыполненные пункты в необязательном поле отчёта `incomplete_items`:
   `[{"brief_item": ..., "reason": ..., "target_role": ...}]`. Текст пишется на английском, потому
   что пункт уходит в brief следующей роли как сообщение между агентами. Каждая строка непустая и
   не длиннее 1600 символов. `target_role` называет саму роль отчёта (для суженного retry) или
   более позднюю роль:

   - architect: architect, developer, code-review или qa;
   - verification: verification, code-review или qa;
   - code-review: code-review или qa;
   - qa: qa.

   Пункт, который не дал выполнить инструмент (например, классификатор безопасности), содержит
   собственный `tooling_blocker` той же формы, что и у отчёта, при любом outcome. `report submit`
   отклоняет с remedy: поле у write-роли, пункт без `reason`, неизвестную или недопустимую
   `target_role`, кириллицу и неверный `tooling_blocker`.

   Отчёт с непустым `incomplete_items` не принимается автоматически ни при одной
   `approval_policy`, а простой `accept` или `override-warning` отклоняется. Человек выбирает одно
   из двух решений:

   ```bash
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision accept --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --carry-incomplete
   python .harness/orchestration/coordinator.py --repo . batch decide \
     --batch <batch-id> --decision retry --approved-by 'имя утверждающего' \
     --approved-at <approval-time-utc> --narrowed
   ```

   `--carry-incomplete` (с `accept` или `override-warning`) записывает routing record `carry-over` с
   `carried_item_ids` (`incomplete-item-<n>`, сквозная нумерация в batch). `next_action` меняется
   так же, как при любом accept этой стадии. Batch пункты не хранит. Work brief целевой роли читает
   их из неизменяемого отчёта и передаёт в `carried_items` под видом `incomplete-item`. Так
   продолжается, пока не принят (`accept` или `override-warning`) dispatch этой роли, чей brief их
   содержал. Retry оставляет пункт открытым. Открытый пункт для code-review ведёт candidate в
   code-review, даже если оценка риска не нашла триггеров. Флаг отклоняется, если пунктов нет, если
   решение другое или если хоть один пункт нацелен на саму роль отчёта. Такой пункт закрывает
   только суженный retry.

   `--narrowed` (только с `retry`) повторяет ту же стадию на том же SHA. Brief нового dispatch
   содержит только пункты отчёта, а Definition of Done в brief остаётся полным DoD batch. Маршрут
   `narrowed-retry` с `reason_category: null`. Если хоть один пункт содержит `tooling_blocker`,
   маршрут становится `tooling-retry` с категорией `tooling`. Тогда нужно подтвердить ложное
   срабатывание и завести bug-тикет на инструмент. Серию таких повторов ограничивает attention
   `tooling-retry-repeated`. Бюджет `retry_policy.max_developer_retries` не тратится, а новый
   dispatch утверждается по `approval_policy`. `--narrowed` отклоняется:

   - для developer и publish;
   - для отчёта без пунктов;
   - вместе с `--reason-category` или `--retry-role developer`;
   - при структурном evidence другого маршрута: finding или severity warning/blocker на оси,
     открытый carried item, упавшая проверка, сдвинутый candidate.

   Retry без `--narrowed` пункты игнорирует и маршрутизируется как раньше.

   `source` пункта `incomplete-item` содержит `dispatch_id` и `report_sha256` отчёта, его `role`,
   `target_role` (роль, чей brief содержит пункт), `route` (`carry-over`, `narrowed-retry` или
   `tooling-retry`), `reason` и `reason_category` (`tooling` у пункта с `tooling_blocker`, иначе
   `null`). `summary` берётся из `brief_item`, `files` пуст. `batch decision-packet` показывает
   `incomplete_items` отчёта. Без `--findings-file` он добавляет `route_preview["carry-over"]`:
   запись, которую сделает `--carry-incomplete`, или отказ. `batch decision-packet --narrowed`
   показывает маршрут суженного retry.

Минимальный ручной brief хранит тикет и dispatch ID, роль и её доступ, выбранные profile, model и
effort, allowed paths (scope записи), issue-ветку и worktree, DoD, запреты, команды, dependencies и
approval. Completion report write-роли обязан содержать commit SHA, точный список изменённых
файлов, результаты всех проверок, risks, blockers и следующее решение coordinator.

Write-роль может остановиться до изменений (например, из-за risk trigger без нужного gate). Тогда
coordinator принимает честный отчёт с `outcome: blocked`, пустым `changed_files` и `commit_sha`,
привязанным к проверенному checkout (`snapshot_commit`). Coordinator регистрирует отчёт и
возвращает `decision_packet` с `recovery_route` (`retry`, `block`, `abandon`). Незавершённый
candidate он не регистрирует. Read-only роль вместо SHA указывает
`not applicable — read-only role`.

Новые факты не меняют отправленный brief: coordinator добавляет отдельное решение с evidence. Если
изменились scope, DoD, назначение или доказательства, текущий dispatch заканчивается и создаётся
новый. Повтор после `blocked` или `failed` тоже создаёт новый dispatch с новым ID и brief.

## Наблюдение запуска и готовый несданный отчёт {#_4}

Пример адаптера в поставке: `.harness/orchestration/adapters/claude_code.py`. Сами `claude` и
`codex` не адаптеры. Консоль Harness сначала открывает выбранную сессию, затем выполняет
подтверждённую отправку. Для намеренно скрытого запуска передайте
`--adapter-arg=--visibility=background`. Пример сохраняет нативные разрешения и хуки. Проверка
родительской сессии не подтверждает доступ Bash-инструментов внутри worker: нативная проба должна
пройти до реализации. Если доступ отказывает постоянно, подготовьте среду: одинаковые retry не
помогут. Sandbox-профиль меняют до propose и approval, глобальные настройки не отключают.

`dispatch observe --dispatch <id> --offset <next_offset>` читает уже записанные события локально.
Для worker под надзором runtime (brief с `execution`) события берутся из журнала запуска. Runtime
пишет stdout worker в `executions/<operation_id>/stdout.log`, а stderr в `stderr.log` рядом, в
state-каталоге оркестрации. `dispatch logs --dispatch <id>` возвращает страницу тех же событий. С
`--follow` команда печатает каждое событие строкой JSON, пока worker работает, и после его выхода
заканчивает итоговой строкой. Цикл `--follow` не держит замок ledger, поэтому не мешает
self-report, heartbeat и сдаче отчёта. Экран worker в веб-консоли показывает тот же журнал во
время работы.

Открытие панели, обновление и переподключение не вызывают модель. Окно можно закрыть, worker при
этом не остановится. Запрос нативного разрешения подтверждает человек, и это подтверждение не даёт
dispatch approval. Первый self-report coordinator по умолчанию ждёт 120 секунд, независимо от
порога stale для heartbeat. Если доказано, что worker вышел рано, порядок такой: auto-report,
затем auto-decide, затем `resume-stop --restart`, который выполняет человек. Повторный запуск
сохраняет исходный контракт. Если контракт разошёлся (drift), нужен новый propose.

Если worker подготовил отчёт, но не смог его сдать, coordinator берёт исходный staging-файл:
`report submit --file <path> --relayed-by <sender> --relay-reason <exact-error>
--source-sha256 <hash-original-bytes>`. Coordinator не редактирует JSON worker и записывает
provenance отдельно. `fail` и `not_run` остаются как есть, `make lint` не заменяет `make verify`.
Если отчёт уже записан, используйте `report complete`, когда результат submit указывает этот
маршрут. Сравнение падения с базовым SHA остаётся отдельным evidence и не исправляет исходный
отчёт задним числом.

## Необязательный внешний adapter {#5-adapter}

Capability `backend-orchestration` поставляет два стандартных адаптера:
`.harness/adapters/claude_worker.py` для Claude Code и `.harness/adapters/codex_worker.py` для
Codex. Их устанавливают `harness init` и `adopt`, а обычный `harness update <repo>` восстанавливает
отсутствующие файлы и обновляет управляемые версии. В настройках консоли есть состояния, просмотр
плана и явное подтверждение. Текущий состав capability сохраняется.

Для одобренного dispatch с транспортом `external` используйте адаптер назначенного runtime:

```bash
python /path/to/project/.harness/orchestration/coordinator.py --repo /path/to/project dispatch send --dispatch <dispatch-id> --adapter /path/to/project/.harness/adapters/claude_worker.py
```

Для Codex замените путь адаптера на `/path/to/project/.harness/adapters/codex_worker.py`.
Coordinator запускает `.py` своим Python в checkout worker. Модель и effort адаптер берёт из
неизменяемого brief.

Под надзором runtime (brief с `execution`) адаптер живёт столько же, сколько worker. Он держит
worker в своей группе процессов, свой stdin не читает и возвращает код выхода worker (`128 + N`
при сигнале N). Claude получает промпт аргументом после `-p`, Codex получает его запросом протокола
`app-server`. Это правило обязательно и для нового адаптера: если адаптер завершается раньше
worker, dispatch переходит в `blocked` с `worker-exited-without-report`. Без `execution` адаптер
передаёт lifecycle-промпт отсоединённому worker через stdin.

Адаптер Claude ограничивает дополнительный доступ каталогом входящих отчётов и использует нативный
`allowed_tools`. Read-only роль (не `developer` и без `Edit`/`Write`) дополнительно получает
`Edit(//<report_staging_path>)` и может записать только свой отчёт. Если `--claude-bin` задан
именем, а не путём, адаптер ищет Claude в `PATH`, затем в `~/.local/bin`. Адаптер Codex передаёт
список инструментов в промпте, а sandbox выбирает по `access`: `read-only` или `workspace-write`.
Это не нативный фильтр инструментов Codex.

Оба адаптера отклоняют `qa`, `purpose: publish`, другой transport и отсутствующий `allowed_tools`.
Если отсоединённый worker вышел рано, даже с кодом `0`, адаптер возвращает ошибку запуска и конец
лога. `harness health` сверяет установленные адаптеры с версией харнесса (`orchestration.adapters`)
и ищет `claude` и `codex` в PATH окружения `harness-runtime serve`
(`orchestration.worker_binaries`): runtime запускает worker в этом окружении, а не в окружении
coordinator. Для проверки команды без модели есть `dispatch --dry-run`, для тестового исполняемого
файла `--claude-bin`/`--codex-bin`, для строк developer-retry `--extra-prompt-file`.

Для `transport: "external"` проект передаёт `--adapter <path>` в `dispatch send`. Adapter отвечает
только за транспорт. Coordinator передаёт этому исполняемому файлу одобренный неизменяемый brief
через `--repo` и `--brief`. Adapter запускает worker в выбранной среде. Он не выбирает scope, не
принимает report, не планирует следующий dispatch и не мержит PR. После запуска worker сдаёт
completion report по общим правилам раздела
[«Coordinator CLI и lifecycle»](#4-coordinator-cli-lifecycle). Доступ и среду запуска проверяет
adapter проекта.

## Первый pilot и источник правил {#6-pilot}

Не задавайте лимиты токенов или «правильный» уровень параллелизма на глаз. В первом периоде pilot
записывайте по каждому закрытому тикету число запусков агентов, токены на batch, время quality gate
и дефекты после интеграции, вместе с источником и пропущенными данными. Форма и единые правила
подсчёта лежат в `.harness/orchestration/pilot.md`.

Полный нормативный источник: `.harness/orchestration/playbook.md`. Границы отдельных ролей лежат в
`.harness/orchestration/roles/`. Если удобство конкретного runtime противоречит этому контракту,
приоритет у manifest, неизменяемого brief и явного approval.

Архитектурный контракт маршрута целиком зафиксирован в
[ADR 0003](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0003-orchestration-core.md):
opt-in capability, отдельное approval для dispatch, review и QA одного SHA, локальное очищенное от
секретов evidence и adapter только для транспорта.
[ADR 0005](https://github.com/PVMalove/agent-harness-next/blob/master/docs/adr/0005-implement-pipeline.md)
фиксирует, что `/implement` по умолчанию стал конвейером под управлением coordinator, а также model
self-report, dispatch watchdog, transport для каждой роли и дефолты без конфигурации.
