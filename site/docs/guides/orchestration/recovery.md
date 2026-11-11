# Восстановление

Перед восстановлением прочитайте состояние batch и причину остановки. Человек, который подтверждает восстановление, должен видеть действие, его последствия и нужные подтверждения. Не редактируйте записи хранилища вручную.

[Обзор оркестрации](../../backend-orchestration.md)

## Ручное восстановление и повтор этапа {#_8}

`batch auto-report` только читает состояние. Найденную причину он возвращает в `observed_stop`.
Чтобы записать остановку, явно вызовите `batch auto-decide`: batch перейдёт в `paused`, даже если
воркер не успел отправить report. Повторный вызов в paused не изменит ledger.

```bash
python .harness/orchestration/coordinator.py --repo . ledger validate
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <id> --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'worker checkout fixed'
python .harness/orchestration/coordinator.py --repo . batch rewind \
  --batch <id> --to code-review --approved-by '<оператор>' --approved-at '<текущий UTC>' --note 'repeat review'
```

`resume-stop` подходит для подтверждённого worktree/model mismatch или отказа ОС запустить adapter,
но перезапускает только worker с известным исходом: `absent`, `reported`, `rejected-at-startup`
или `stopped`. Для отклонённого self-report контракт прежний: одобрение человека выводит dispatch из
обращения, а ledger отклоняет его поздние записи. Если `dispatch status` показывает `live` или
`unknown`, команда отказывает и ничего не меняет: остановите worker через его runtime и повторите
её с `--runtime-stopped`. Отсутствующий self-report `resume-stop` не подтверждает: остановите worker
и запишите `dispatch cancel --runtime-stopped`. Если структурного доказательства нет, осторожная текстовая эвристика ищет инфраструктурную причину
(rate limit, timeout, сеть, падение runtime, ресурсы, недоступный сервис) в `blockers` blocked
report и в ошибке runtime. Признак проблемы с тестами, линтером, типами, конфликтом, scope или
требованиями перевешивает; неизвестный текст остаётся неизвестным. Совпадение записывается в
событие как `classification` с `method: heuristic`; оно лишь предлагает причину, а решает
человеческий approval. Повтор сохраняет роль, scope, candidate и fix-forward findings, но получает новый dispatch ID,
context и approval. Операционная попытка не расходует второй developer retry. При паузе из-за
бюджета или неизвестной причины можно вернуть pending report для ручного решения. Когда бюджет
инфраструктурных повторов исчерпан, `resume-stop` отказывает, а batch остаётся в состоянии остановки
до решения человека: ждать, исправить запуск, изменить attention policy, выполнить `rewind` или
отдельно решить `batch abandon`; счётчики не сбрасываются. Грязные файлы, неизвестный SHA, failed
checks и новые code findings требуют обычного маршрута исправления.

После восстановления действует `manual_all`, включая продолжение после 429. Исходные `auto_stop`
и `auto_report` остаются историей. Новый отчёт показывает текущий прогресс и `historical_report`.
`blocked` и `failed` удерживают ticket/branch/worktree; повторный batch до их закрытия запрещён.
Оба abandon-пути записывают `abandoned` и `last_accepted`. Старый `failed` можно supersede только
при доказанном человеческом abandon; обычный failed — не отказ от работы.

Rewind выбирает достигнутую стадию `architect`, `developer`, `code-review`, `qa` или `publish`.
`verification` требует зарегистрированного candidate, `resolve-conflict` — resolver boundary.
Старые зависимые approvals/reports/risk/QA исключаются из активной цепочки, но не удаляются.
HEAD и commit objects остаются на месте. После возврата к architect нужен новый принятый план;
после возврата к writer новая попытка расходует developer retry budget. Ни один счётчик не
обнуляется. До первого accept сохраняется требование `batch approve`.

Если report стадии `blocked` только из-за сбоя инфраструктуры, а работа по report выглядит
завершённой (например, коммиты developer соответствуют плану, но передача на review упала),
человек может принять стадию условно:

```bash
python .harness/orchestration/coordinator.py --repo . batch decide --batch <id> \
  --decision accept-conditional --infrastructure-failure --note '<проверенная причина>' \
  --approved-by '<оператор>' --approved-at '<текущий UTC>'
```

Решение записывается как `accept-conditional`, пайплайн идёт дальше, как после `accept`, а стадия
остаётся открытым условием batch. Условие независимо закрывает безусловный `accept` более
позднего gate: code-review или qa для architect, developer и verification; qa для code-review и
qa. Пока условие открыто, publish и завершение отказывают. Условный qa не считается зелёным QA,
поэтому publish всё равно требует реального QA. Условный publish принимается, только если remote
branch уже указывает на candidate. Report должен быть `blocked` без failed checks, остальные
проверки обычного `accept` (план коммитов, scope, DoD) сохраняются. Rewind снимает условия
отменённых dispatch. Если стадию можно просто перезапустить, лучше подходит `resume-stop`.

Живой worker нужно сначала остановить средствами runtime. Затем оператор записывает
`dispatch cancel --runtime-stopped` с approved_by/approved_at/reason. Timeout не доказывает остановку.
После этого можно выполнить rewind. Старый dispatch больше не принимает heartbeat/report/checkpoint.

Для старого pinned batch новые recovery-команды используют установленный runtime. Событие с
человеческим approval связывает исходный pin с новым control runtime и сохраняет его snapshot.
Исходный immutable plan и старые brief/report не меняются. `ledger validate` ничего не исправляет.

Перед handoff передайте один абсолютный `--worktree` в preflight и send. Для writer путь должен
совпадать с issue-worktree, branch и startup SHA. Self-report проверяет фактический каталог даже
при одинаковом SHA двух checkout. Runtime должен уметь выбрать существующий каталог; одного
`isolation: worktree` недостаточно. Coordinator остаётся в main checkout.

Если writer-сессия завершилась до первого checkpoint, оператор может выполнить
`dispatch resume --trigger startup-failure --runtime-stopped` с новым approval и `--note`.
Файл `--file` содержит ровно `dispatch_id`, `definition_of_done`, `dependencies`, `write_paths`,
`prohibited_changes` из brief. Чистый worktree должен оставаться на известном startup SHA.
Команда записывает отдельное startup evidence, расходует continuation budget и требует новой
self-report/heartbeat. Изменённый scope, неизвестные коммиты или paused batch исключают этот путь.

### Удержание batch и команды `recovery` {#batch-recovery}

Неизвестные, отсутствующие или нечитаемые системные данные не становятся решением (ADR 0026).
Если строгое чтение отвергает запись batch, `recovery resume` удерживает batch записью
`recovery/hold/<batch_id>.json` контракта `operationalHold.v1`: состояние `held` и отказ с шагом
`hold:<причина>`, где причина — `unknown-value`, `missing-value` или `unreadable-record`. Удержание
не пишет lifecycle-запись, решение или approval, а терминальный batch никогда не удерживается.
Запись удержания, которую нельзя прочитать, тоже удерживает batch, но её не снимает ни одна команда
`recovery`: remedy называет `ledger validate --full` и эскалацию человеку.

Пока удержание действует, эти команды отказывают кодом 2, ничего не пишут и называют в `REMEDY`
маршрут восстановления: `dispatch propose` и `dispatch create`, `dispatch send`,
`dispatch self-report`, `dispatch checkpoint`, `report submit`, `qa run`, `dispatch publish`,
`batch decide`, `batch resume`, `batch resume-stop` и `batch rewind`. Реакция на завершённое
исполнение supervised dispatch тоже ждёт: `dispatch status --dispatch` показывает отказ как
`reaction_error`, а отчёт остаётся в `pending_report`. `batch auto-decide` при активной политике
`auto` записывает остановку `integrity-failure`/`operational-hold` и никогда не решает отчёт и не
делает abandon; без активной политики команда отказывает, как `batch decide`. Доступными остаются
`dispatch heartbeat`, `dispatch cancel`, `batch abandon`, `batch attention check` и `resolve`,
`batch decision-packet` и команды чтения. `batch attention check` поднимает attention
`operational-hold`. Decision packet удержанного batch показывает поле `operational_hold`, пустые
`options` и `recovery_route.commands`: `recovery status`, `batch attention resolve` (если attention
поднят) и `recovery resume`.

Recovery никогда не разрешает attention, а `recovery resume` отказывает с `attention-open`, пока
attention открыт. Поэтому порядок такой: прочитать диагностику, устранить причину, разрешить
attention, затем снять удержание.

```bash
python .harness/orchestration/coordinator.py --repo . recovery status --batch <id> --json
python .harness/orchestration/coordinator.py --repo . recovery reload --batch <id>
python .harness/orchestration/coordinator.py --repo . batch attention resolve --batch <id> --note '…' --approved-by … --approved-at …
python .harness/orchestration/coordinator.py --repo . recovery resume --batch <id>
```

Команды `recovery status|reload|resume|fix|abort --batch <id>` работают только на установленном
runtime в эпохе `runtime-store`, не читают stdin и не требуют TTY и Textual, поэтому консоль
вызывает их как процесс:

| Код | stdout | Когда |
| --- | --- | --- |
| 0 | документ `recoveryStatus.v1` с `outcome: done` | действие выполнено |
| 2 | документ `recoveryStatus.v1` с `outcome: refused` | политика отказала; `refusals` и `diagnostics` называют причину |
| 2 | пусто, `ERROR:` и `REMEDY:` в stderr | команда не может выполниться: эпоха файлового ledger (remedy `harness-runtime migrate`), отказ `runtime_client` (`[runtime_unavailable]`, `[store_busy]`, `[revision_conflict]`), неполное одобрение или прерывание |

Документ `recoveryStatus.v1` — контракт консоли. Он содержит `contract`, `action`, `outcome`,
`batch_id`, `observed_at`, `resumable`, `lifecycle`, `hold`, `checks`, `diagnostics`,
`skipped_advisories`, `actions`, `intent` и `next`. Каждая из 13 проверок (`config`, `store`,
`ledger`, `batch`, `lifecycle`, `runtime`, `snapshot`, `context`, `compatibility`, `operation`,
`liveness`, `attention`, `approval`) показывает статус и диагностику: pointer, отредактированные
expected и received, подсказку и remedy. Секреты в документ не попадают.

- `status` только читает. `--skip <diagnostic-id>` (повторяемый) на один вызов скрывает advisory из
  закрытого списка (`config-normalized`) и ничего не пишет.
- `reload` заново читает и проверяет конфигурацию и hello runtime (протокол 1.5, `store_id`,
  features `state.read`, `state.write` и `state.recovery`), возвращает это evidence ключом
  `runtime` и не запускает worker.
- `resume` в одной единице записи повторяет проверки `status`. Отказ любой проверки ничего не
  меняет, кроме удержания batch, чью запись отвергает строгое чтение. Иначе команда снимает
  удержание и реагирует на наблюдаемое исполнение каждого открытого supervised dispatch:
  завершённое исполнение получает реакцию (шаг `reconcile`), исполнение `unknown` даёт отказ
  `ambiguous-effect`, а живой worker второй раз не запускается. Записанная остановка продолжается
  только через аудируемый `batch resume-stop`, для которого `resume` принимает `--approved-by`,
  `--approved-at` и `--note` (все три вместе или ни одного); иначе нужен `batch rewind`. Документ
  добавляет `steps` (`hold`, `release`, `reconcile`, `resume-stop`), `refusals`,
  `dispatch_created: false`, `worker_started: false`, `status` и `next`. `resume` не создаёт
  dispatch, не переписывает brief и не меняет attention, бюджеты, `auto_stop` и терминальные
  отказы; следующий переход требует approval с актуальным digest.
- `fix` показывает безопасную нормализацию конфигурации, а `fix --apply` применяет её транзакцией
  конфигурации и ничего не возобновляет.
- `abort` записывает выход из recovery: не делает abandon, ничего не останавливает и не очищает.

`reload`, `resume`, `fix` и `abort` сначала записывают durable intent
`recovery/intent/<batch_id>.json` (`recoveryIntent.v1`). После cancel, EOF или SIGINT intent
остаётся `interrupted`, и повтор команды завершает действие. Внутреннее исключение даёт диагностику
`internal-error` с correlation ID, а не ошибку конфигурации.

Консоль Harness (`harness console`, раздел Orchestration) показывает три записи каталога в группе
`batch`: `recovery status` и `recovery reload` выполняются без подтверждения, а `recovery resume` —
терминальное действие coordinator и запрашивает подтверждение. `recovery fix` и `recovery abort`
доступны только из CLI.

Записи восстановления подчиняются той же authority, что и lifecycle (ADR 0020, ADR 0021): Python
решает, Rust store пишет.

| Запись | Решает | Пишет | Правила записи |
| --- | --- | --- | --- |
| `recovery/hold/<batch_id>.json`, `recovery/intent/<batch_id>.json` | Python: `operational_hold` и `recovery_api` в единице записи команды | Rust store, `state.write` (протокол 1.5, feature `state.recovery`) | только `create`, затем `replace` по revision строки, `delete` отказывает; поле `batch_id` равно id пути; строка batch существует в той же транзакции; одна запись audit на мутацию; миграции схемы нет |

Граница гарантии восстановления. Recovery восстанавливает только durable подтверждённую работу:
lifecycle, записанный в ledger, принятые этапы с закреплённым evidence, intent и удержание в runtime
store. Принятый этап не запускается повторно: после сбоя следующего этапа, невалидной конфигурации
или перезапуска runtime `recovery resume` называет следующий переход (например,
`dispatch propose --batch <id> --role developer`) и не создаёт dispatch. Recovery не восстанавливает
потерянный контекст модели, незакоммиченные файлы worktree и неотправленный отчёт. Для внешних
эффектов нет гарантии exactly-once: исполнение с неизвестным эффектом отклоняется как
`ambiguous-effect` и ждёт решения человека, второй worker не запускается. Эти случаи закрепляет
regression suite `tests/orchestration/recovery_regression_matrix.py`.
