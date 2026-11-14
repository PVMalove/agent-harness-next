# Восстановление

Перед восстановлением прочитайте состояние batch и причину остановки. Человек, который подтверждает восстановление, должен видеть действие, его последствия и нужные подтверждения. Не редактируйте записи хранилища вручную.

[Обзор оркестрации](../../backend-orchestration.md)

## Ручное восстановление и повтор этапа {#_8}

`batch auto-report` только читает состояние и возвращает найденную причину в `observed_stop`.
Чтобы записать остановку, явно вызовите `batch auto-decide`. Batch перейдёт в `paused`, даже если
воркер не успел отправить report. Повторный вызов в `paused` не изменит ledger.

```bash
python .harness/orchestration/coordinator.py --repo . ledger validate
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <id> --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'worker checkout fixed'
python .harness/orchestration/coordinator.py --repo . batch rewind \
  --batch <id> --to code-review --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'repeat review'
```

`resume-stop` подходит, если подтверждено расхождение worktree или модели либо ОС отказалась
запустить adapter. Команда перезапускает только worker с известным исходом: `absent`, `reported`,
`rejected-at-startup` или `stopped`. Для отклонённого self-report контракт прежний: одобрение
человека выводит dispatch из работы, а ledger отклоняет его поздние записи.

Если `dispatch status` показывает `live` или `unknown`, команда отказывает и ничего не меняет.
Остановите worker через его runtime и повторите команду с `--runtime-stopped`. Отсутствие
self-report `resume-stop` не подтверждает: остановите worker и запишите
`dispatch cancel --runtime-stopped`.

Если структурного доказательства нет, осторожная текстовая эвристика ищет инфраструктурную причину
(rate limit, timeout, сеть, падение runtime, ресурсы, недоступный сервис) в `blockers` отчёта
`blocked` и в ошибке runtime. Признаки проблемы с тестами, линтером, типами, конфликтом, scope или
требованиями перевешивают. Неизвестный текст остаётся неизвестным. Совпадение попадает в событие как
`classification` с `method: heuristic`. Эвристика только предлагает причину, решает человек своим
approval.

Повтор сохраняет роль, scope, candidate и fix-forward findings, но получает новый dispatch ID,
контекст и approval. Операционная попытка не расходует второй developer retry. Если пауза вызвана
бюджетом или неизвестной причиной, pending report можно вернуть для ручного решения.

Когда бюджет инфраструктурных повторов исчерпан, `resume-stop` отказывает, и batch стоит до решения
человека. Человек может подождать, исправить запуск, изменить attention policy, выполнить `rewind`
или отдельно решить `batch abandon`. Счётчики не сбрасываются. Грязные файлы, неизвестный SHA,
упавшие проверки и новые code findings идут обычным маршрутом исправления.

После восстановления действует `manual_all`, в том числе для продолжения после 429. Исходные
`auto_stop` и `auto_report` остаются в истории. Новый отчёт показывает текущий прогресс и
`historical_report`. Состояния `blocked` и `failed` удерживают тикет, ветку и worktree: пока они не
закрыты, новый batch по ним создать нельзя. Оба пути abandon записывают `abandoned` и
`last_accepted`. Старый `failed` можно заменить (supersede), только если человек явно сделал
abandon. Обычный `failed` не означает отказ от работы.

Rewind возвращает batch к уже достигнутой стадии: `architect`, `developer`, `code-review`, `qa` или
`publish`. Для `verification` нужен зарегистрированный candidate, для `resolve-conflict` нужна
граница resolver. Старые зависимые approvals, reports, risk и QA выпадают из активной цепочки, но не
удаляются. HEAD и commit objects остаются на месте. После возврата к architect нужен новый принятый
план. После возврата к writer новая попытка расходует developer retry budget. Ни один счётчик не
обнуляется. До первого accept по-прежнему нужен `batch approve`.

Бывает, что report стадии `blocked` только из-за сбоя инфраструктуры, а работа выглядит
завершённой. Например, коммиты developer соответствуют плану, но передача на review упала. Тогда
человек может принять стадию условно:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide --batch <id> \
  --decision accept-conditional --infrastructure-failure --note '<проверенная причина>' \
  --approved-by '<оператор>' --approved-at '<текущий UTC>'
```

Coordinator записывает решение как `accept-conditional`. Пайплайн идёт дальше, как после `accept`,
а стадия остаётся открытым условием batch. Условие закрывает безусловный `accept` на более позднем
gate:

- для architect, developer и verification: code-review или qa;
- для code-review и qa: qa.

Пока условие открыто, publish и завершение отказывают. Условный qa не считается зелёным QA,
поэтому для publish всё равно нужен реальный QA. Условный publish принимается, только если
remote-ветка уже указывает на candidate. Report должен быть `blocked` без упавших проверок.
Остальные проверки обычного `accept` (план коммитов, scope, DoD) действуют. Rewind снимает условия
отменённых dispatch. Если стадию можно просто перезапустить, используйте `resume-stop`.

Живой worker сначала остановите средствами runtime. Затем оператор записывает
`dispatch cancel --runtime-stopped` с `approved_by`, `approved_at` и `reason`. Timeout не доказывает
остановку. После этого можно выполнить rewind. Старый dispatch больше не принимает heartbeat,
report и checkpoint.

Для старого pinned batch новые recovery-команды используют установленный runtime. Событие с
approval человека связывает исходный pin с новым control runtime и сохраняет его snapshot.
Исходный неизменяемый план и старые brief и report не меняются. `ledger validate` ничего не
исправляет.

Перед handoff передайте один абсолютный `--worktree` в preflight и в send. Для writer путь должен
совпадать с issue-worktree, веткой и startup SHA. Self-report проверяет настоящий каталог, даже
если два checkout стоят на одном SHA. Runtime должен уметь выбрать существующий каталог: одного
`isolation: worktree` недостаточно. Coordinator остаётся в main checkout.

Если writer-сессия завершилась до первого checkpoint, оператор может выполнить
`dispatch resume --trigger startup-failure --runtime-stopped` с новым approval и `--note`.
Файл `--file` содержит ровно поля `dispatch_id`, `definition_of_done`, `dependencies`,
`write_paths`, `prohibited_changes` из brief. Чистый worktree должен стоять на известном startup
SHA. Команда записывает отдельное startup evidence, расходует continuation budget и требует нового
self-report и heartbeat. Этот путь закрыт, если scope изменился, есть неизвестные коммиты или batch
на паузе.

### Удержание batch и команды `recovery` {#batch-recovery}

Неизвестные, отсутствующие или нечитаемые системные данные не становятся решением (ADR 0026).
Если строгое чтение отвергает запись batch, `recovery resume` удерживает batch записью
`recovery/hold/<batch_id>.json` по контракту `operationalHold.v1`. Запись получает состояние `held`
и отказ с шагом `hold:<причина>`. Причина: `unknown-value`, `missing-value` или
`unreadable-record`. Удержание не пишет lifecycle-запись, решение или approval. Терминальный batch
никогда не удерживается. Нечитаемая запись удержания тоже удерживает batch, но её не снимает ни одна
команда `recovery`: remedy называет `ledger validate --full` и передачу человеку.

Пока удержание действует, эти команды отказывают с кодом 2, ничего не пишут и называют в `REMEDY`
маршрут восстановления: `dispatch propose` и `dispatch create`, `dispatch send`,
`dispatch self-report`, `dispatch checkpoint`, `report submit`, `qa run`, `dispatch publish`,
`batch decide`, `batch resume`, `batch resume-stop` и `batch rewind`.

Реакция на завершённое исполнение supervised dispatch тоже ждёт. `dispatch status --dispatch`
показывает отказ как `reaction_error`, а отчёт остаётся в `pending_report`. Если активна политика
`auto`, `batch auto-decide` записывает остановку `integrity-failure`/`operational-hold`. Отчёт она
никогда не решает и abandon не делает. Без активной политики команда отказывает, как `batch decide`.

Доступными остаются `dispatch heartbeat`, `dispatch cancel`, `batch abandon`,
`batch attention check` и `resolve`, `batch decision-packet` и команды чтения.
`batch attention check` поднимает attention `operational-hold`. Decision packet удержанного batch
показывает поле `operational_hold`, пустые `options` и `recovery_route.commands`:
`recovery status`, `batch attention resolve` (если attention поднят) и `recovery resume`.

Recovery никогда не снимает attention, а `recovery resume` отказывает с `attention-open`, пока
attention открыт. Поэтому порядок такой: прочитать диагностику, устранить причину, снять attention,
снять удержание.

```bash
python .harness/orchestration/coordinator.py --repo . recovery status --batch <id> --json
python .harness/orchestration/coordinator.py --repo . recovery reload --batch <id>
python .harness/orchestration/coordinator.py --repo . batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …
python .harness/orchestration/coordinator.py --repo . recovery resume --batch <id>
```

Команды `recovery status|reload|resume|fix|abort --batch <id>` работают только на установленном
runtime в эпохе `runtime-store`. Они не читают stdin и не требуют TTY и Textual, поэтому консоль
вызывает их как процесс:

| Код | stdout | Когда |
| --- | --- | --- |
| 0 | документ `recoveryStatus.v1` с `outcome: done` | действие выполнено |
| 2 | документ `recoveryStatus.v1` с `outcome: refused` | политика отказала; `refusals` и `diagnostics` называют причину |
| 2 | пусто, `ERROR:` и `REMEDY:` в stderr | команда не может выполниться: эпоха файлового ledger (remedy `harness-runtime migrate`), отказ `runtime_client` (`[runtime_unavailable]`, `[store_busy]`, `[revision_conflict]`), неполное одобрение или прерывание |

Документ `recoveryStatus.v1` образует контракт консоли. Он содержит `contract`, `action`, `outcome`,
`batch_id`, `observed_at`, `resumable`, `lifecycle`, `hold`, `checks`, `diagnostics`,
`skipped_advisories`, `actions`, `intent` и `next`. Каждая из 13 проверок (`config`, `store`,
`ledger`, `batch`, `lifecycle`, `runtime`, `snapshot`, `context`, `compatibility`, `operation`,
`liveness`, `attention`, `approval`) показывает статус и диагностику: pointer, отредактированные
expected и received, подсказку и remedy. Секреты в документ не попадают.

- `status` только читает. `--skip <diagnostic-id>` (можно повторять) скрывает на один вызов
  advisory из закрытого списка (`config-normalized`) и ничего не пишет.
- `reload` заново читает и проверяет конфигурацию и hello runtime (протокол 1.5, `store_id`,
  features `state.read`, `state.write` и `state.recovery`). Это evidence команда возвращает под
  ключом `runtime`. Worker она не запускает.
- `resume` повторяет проверки `status` в одной единице записи. Если любая проверка отказала,
  команда ничего не меняет, кроме удержания batch, чью запись отвергло строгое чтение. Иначе она
  снимает удержание и реагирует на исполнение каждого открытого supervised dispatch:
    - завершённое исполнение получает реакцию (шаг `reconcile`);
    - исполнение `unknown` даёт отказ `ambiguous-effect`;
    - живой worker второй раз не запускается.

    Записанная остановка продолжается только через аудируемый `batch resume-stop`. Для него
    `resume` принимает `--approved-by`, `--approved-at` и `--note`: все три вместе или ни одного.
    Иначе нужен `batch rewind`. Документ добавляет `steps` (`hold`, `release`, `reconcile`,
    `resume-stop`), `refusals`, `dispatch_created: false`, `worker_started: false`, `status` и
    `next`. `resume` не создаёт dispatch, не переписывает brief и не меняет attention, бюджеты,
    `auto_stop` и терминальные отказы. Для следующего перехода нужен approval с актуальным digest.
- `fix` показывает безопасную нормализацию конфигурации. `fix --apply` применяет её транзакцией
  конфигурации и ничего не возобновляет.
- `abort` записывает выход из recovery. Он не делает abandon, ничего не останавливает и не
  очищает.

`reload`, `resume`, `fix` и `abort` сначала записывают durable intent
`recovery/intent/<batch_id>.json` (`recoveryIntent.v1`). После cancel, EOF или SIGINT intent
остаётся `interrupted`, и повтор команды завершает действие. Внутреннее исключение даёт диагностику
`internal-error` с correlation ID, а не ошибку конфигурации.

Консоль Harness (`harness console`, раздел «Оркестрация») показывает в группе `batch` все
recovery-команды. `recovery status`, `recovery reload`, превью `recovery fix` и `recovery abort`
выполняются без подтверждения. `recovery resume` записывает терминальное решение coordinator, а
`recovery fix --apply` перезаписывает конфигурацию, поэтому обе команды запрашивают подтверждение.

Записи восстановления подчиняются той же authority, что и lifecycle (ADR 0020, ADR 0021): Python
решает, Rust store пишет.

| Запись | Решает | Пишет | Правила записи |
| --- | --- | --- | --- |
| `recovery/hold/<batch_id>.json`, `recovery/intent/<batch_id>.json` | Python: `operational_hold` и `recovery_api` в единице записи команды | Rust store, `state.write` (протокол 1.5, feature `state.recovery`) | только `create`, затем `replace` по revision строки, `delete` отказывает; поле `batch_id` равно id пути; строка batch существует в той же транзакции; одна запись audit на мутацию; миграции схемы нет |

Граница гарантии. Recovery восстанавливает только durable подтверждённую работу: lifecycle,
записанный в ledger, принятые этапы с закреплённым evidence, intent и удержание в runtime store.
Принятый этап не запускается повторно. Если упал следующий этап, конфигурация невалидна или
runtime перезапустился, `recovery resume` называет следующий переход (например,
`dispatch propose --batch <id> --role developer`) и не создаёт dispatch. Recovery не восстанавливает
потерянный контекст модели, незакоммиченные файлы worktree и неотправленный отчёт. Для внешних
эффектов нет гарантии exactly-once: исполнение с неизвестным эффектом coordinator отклоняет как
`ambiguous-effect` и ждёт решения человека, второй worker не запускается. Эти случаи закрепляет
regression suite `tests/orchestration/recovery_regression_matrix.py`.
