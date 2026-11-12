# Диагностика и состояние

Начните с чтения статуса и диагностики. Записи меняйте только через coordinator CLI. У снятия блокировки, миграции и продолжения после остановки разные условия и подтверждения.

[Обзор оркестрации](../../backend-orchestration.md)

## Совместимость и миграция {#_5}

Все новые поля batch и четыре поля brief (`transition`, `transition_digest`, `retry_idempotency_key`,
`orchestration_policy`; либо все, либо ни одного) необязательны. Записи, созданные раньше, остаются
валидными, версия ledger не меняется, `ledger migrate` не нужен. Новые записи проходят ту же
целостностную проверку (`context_pressure` с hash, форма attention-полей, согласованность brief).
Изменилось поведение CLI: `dispatch create` с `--approved-by` теперь требует `--transition-digest`.
Brief без поля `commit_plan_divergence` и batch без `commit_plan` тоже остаются валидными. Entry
плана без `covers` покрывает пункт DoD по своей позиции. Brief без `carried_items`, transition без
`carried_items_sha256`, batch без `carried_items` и отчёт code-review без `review.carried_items`
тоже валидны. Пустой канал ничего не добавляет в transition, поэтому прежние digest не меняются.
Отчёт без `incomplete_items` и brief без вида `incomplete-item` тоже валидны. Новый вид источника,
поле отчёта и значение маршрута `narrowed-retry` введены без смены версии ledger и без миграции.
Routing record без `retry_item_ids`, поле отчёта `carried_item_closure` и значение маршрута
`fix-forward` тоже введены без смены версии ledger и без миграции. Brief developer-retry по
решению, записанному до них, получает раздел без сверки с `retry_item_ids`. Completed-отчёт
developer-retry, записанный до появления маршрута `fix-forward` без `carried_item_closure` для brief с перенесёнными пунктами,
по-прежнему решается через `batch decide`. Каждый пункт получает статус `omitted` и входит в
`carried_items_gap`. Поэтому `accept` и policy auto-accept отклоняются, а `override-warning` требует
`--note`, отличный от `none`. `retry`, `block`, `fail` и `abandon` доступны. Новый такой отчёт
`report submit` отклоняет. Brief без `rebase_target_commit`, transition без `rebase_target_sha` и
значение маршрута `rebase-fix-forward` тоже введены без смены версии ledger и без миграции:
переход без target сохраняет прежний digest. Brief без `delta_review_scope` и transition без
`delta_review_sha256` тоже валидны и введены без смены версии ledger и без миграции: переход
code-review без раздела сохраняет прежний digest. Ссылка `supersedes` в batch и plan и значение
маршрута `supersede` тоже введены без смены версии ledger и без миграции: batch и plan без
ссылки читаются как прежде.

Поле `route` в routing record и деталь `decision` в transition audit record batch тоже
необязательны и введены без смены версии ledger (остаётся 3). Решение, записанное до них, читается
как есть и остаётся валидным. `ledger migrate` не добавляет и не выводит для него route. Route
пишет только новое решение `batch decide`. Записанный `route` вне закрытого набора маршрутов
отклоняется при чтении batch.

## Инвентарь и закрытие тупикового batch {#batch}

Список заведённых и незакрытых batch:

```bash
python .harness/orchestration/coordinator.py --repo . batch list --open
python .harness/orchestration/coordinator.py --repo . batch list --ticket '#123'
```

Обычный путь к терминальному состоянию — `batch decide`, но он требует ровно один отчёт,
ожидающий решения, а отчёт требует живой dispatch с подтверждённой моделью. Worker, умерший до
self-report, никогда не отчитается, и такой batch не закрыть ни `fail`, ни `block`. Для этого
случая есть отдельная команда:

```bash
python .harness/orchestration/coordinator.py --repo . batch abandon \
  --batch <batch-id> --approved-by 'имя утверждающего' --approved-at <approval-time-utc> \
  --reason 'воркер умер до model self-report, решение недостижимо'
```

Она требует явного approval и непустой причины, переводит batch в `abandoned`, сохраняет `last_accepted`, помечает все незакрытые
dispatch как `abandoned` и записывает решение рядом с остальными. **Она ничего не удаляет**: immutable
brief, отчёты и QA-артефакты остаются на месте. Повторно применить её к уже терминальному batch
нельзя.

При подтверждённом сбое запуска продолжайте тот же batch после устранения причины:

```bash
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <batch-id> --approved-by 'имя оператора' --approved-at <текущее-время-UTC> \
  --note 'исправлен каталог запуска воркера'
```

Команда сохраняет принятые отчёты, исходный stop и `next_action`, помечает сорванный dispatch как
`abandoned` и переводит batch в `awaiting-approval`. Следующий `dispatch create` требует нового
approval и сохраняет контракт прерванной роли. Подробные ограничения описаны в разделе
[«Ручное восстановление и повтор этапа»](recovery.md#_8). Для неизвестной причины или возврата к прежнему gate используйте
`batch rewind`. `completed` и `abandoned` окончательны.

Перед отправкой `dispatch send` сверяет флаги `--adapter-arg` с `dispatch --help` adapter и
отклоняет неподдерживаемый флаг до передачи brief: dispatch остаётся одобренным и неотправленным.
Если `--help` не отвечает, результат попадает в `adapter_preflight` как `limitation`.
`dispatch runtime-probe --dispatch <id> --runtime-command <runtime> --runtime-arg=app-server`
проверяет app-server runtime без worker: `model/list`, поля `thread/start` и один `turn/start` на
ephemeral read-only thread без инструментов. Ошибка capacity, rate-limit или недоступности после
`thread/start` даёт классифицированный сбой, а не READY. Probe ничего не пишет в ledger и не
заменяет model self-report.

Watchdog `stale` не доказывает завершение процесса. Сначала остановите воркера через его runtime,
затем запишите `dispatch cancel --runtime-stopped` с человеческим approval и выполните rewind.
Совместимая команда `batch resume` применяется только к прежнему ручному пути без auto/recovery.
Для stale она также требует `--runtime-stopped`, `--approved-by` и `--approved-at`.

Для незавершённого initial developer закрепите сохранённый HEAD через `--candidate-commit` при
следующих `dispatch preflight`, `dispatch propose` и утверждённом `dispatch create`. Это startup
snapshot, а не принятый completed candidate: risk assessment и последующие gates следуют за
принятием итогового report. Commit map initial work покрывает весь исходный план от batch base,
включая сохранённые коммиты до сбоя. Прежние риски остаются в report. Для `developer-retry`
сохраняется отдельный контракт: только новые коммиты после snapshot.

Batch закреплён за рантаймом, под которым его спланировали. `batch create` записывает хэш всего
пакета рантайма в `.harness/`: верхнеуровневых модулей и всех подпакетов (`orchestration/`,
`gate_runner/`, `context_builder/` и других). Кроме того, он сохраняет неизменяемый снимок этого
пакета в `.harness/orchestration/state/runtimes/`. Если рантайм после этого переустановили
(например, `harness update` с ветки другой задачи), команды этого batch (`--batch`, `--dispatch` или
`dispatch_id` в файле `--file` у `report submit`, `dispatch checkpoint` и `dispatch telemetry`)
автоматически выполняются кодом снимка. Описания ролей тоже берутся из снимка. Новые batch
получают новый рантайм. Так задачи идут параллельно и не блокируют друг друга. Изменённый вручную
снимок отклоняется. У batch, созданного до появления снимков, хэш покрывает только
`orchestration/`, а снимка нет. Его восстанавливают из пакета той ревизии, на которой batch
спланирован: подойдёт `.harness` из временного worktree с выполненным `harness update` или каталог
`harness/` из `git archive <ревизия> harness`:

```bash
python .harness/orchestration/coordinator.py --repo . batch restore-runtime \
  --batch <batch-id> --from <путь к пакету закреплённой ревизии>
```

Команда принимает каталог, только если его хэш совпадает с закреплённым. Снимок и новый рантайм
работают с одним ledger. Поэтому `ledger migrate` на новую версию схемы отказывается выполняться,
пока есть незавершённые batch, закреплённые за другим рантаймом. Сначала их доводят до конца или
отменяют на их собственном рантайме.

Если pinned snapshot уже удовлетворяет всем пунктам DoD, не создавайте фиктивный commit ради
write-role отчёта и не используйте `abandon`. Зафиксируйте отдельное терминальное решение:

```bash
python .harness/orchestration/coordinator.py --repo . batch not-required \
  --batch <batch-id> --approved-by 'имя утверждающего' --approved-at <approval-time-utc> \
  --reason 'pinned snapshot already satisfies every definition-of-done item'
```

Команда оставляет audit evidence, отменяет незакрытые dispatch, переводит batch в `completed` с `completion_kind: no-implementation` и
возвращает рекомендацию закрыть связанный issue с меткой `resolution::wontfix`. Обычный write-role
report по-прежнему обязан содержать реальный commit и exact changed files.

Если ошибка найдена **до** передачи brief runtime-у, не abandon batch. Отмените только этот
неотправленный dispatch: immutable brief останется в audit trail, а batch вернётся в
`awaiting-approval` и сможет получить исправленный dispatch.

```bash
python .harness/orchestration/coordinator.py --repo . dispatch cancel \
  --dispatch <dispatch-id> --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --reason 'исправить назначение до запуска worker'
```

Никогда не правьте файлы в `.harness/orchestration/state/` руками. Эти записи и есть
доказательство, ради которого существует весь маршрут. Если штатной команды для вашего случая нет —
это дефект инструмента, а не повод открыть редактор.

## Model self-report и dispatch watchdog {#model-self-report-dispatch-watchdog}

Отправленный dispatch не считается живым сам по себе. Первым действием после получения brief роль
подтверждает действительно активную модель:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch self-report \
  --dispatch <dispatch-id> --model <фактическая модель> \
  --worktree "$(git rev-parse --show-toplevel)"
```

Совпадение с `resolved_model` immutable brief переводит dispatch в `working`. Если включён
`worker_attestation_required`, coordinator также проверяет переданный Git top-level, issue branch
write-роли либо pinned SHA review-роли. Расхождение немедленно переводит dispatch в `blocked`,
помечает batch `blocked` и завершает команду ошибкой. После этого coordinator не принимает
`report submit` для такого dispatch. Починка — новый dispatch с новым brief, а не правка
отправленного. Без успешного self-report completion report не принимается вообще. Поэтому
подменённая или неверно настроенная модель видна сразу, а не после потраченного окна.

Для architect/developer `worker_attestation_required` также требует, чтобы Git-worktree HEAD в
момент первого `self-report` буквально совпадал с immutable `snapshot_commit` из brief. При
разрешённом `dispatch resume` write-роли свежий self-report проверяет точный `commit_sha`
последнего зарегистрированного checkpoint. Исходный brief и граница commit-plan evidence остаются
неизменными. Для architect, developer, verification и code-review `dispatch create` выбирает
`snapshot_commit` в таком порядке:

1. явный `--candidate-commit`;
2. `commit_sha` непринятого developer report, пока batch ждёт его `developer-retry`;
3. последний принятый developer candidate — например, `developer-retry` после code-review blocker,
   qa или publish (повтор на том же SHA developer dispatch не создаёт);
4. иначе `base_commit`.

`dispatch preflight` и проверка свежести Context Package используют то же правило. Retry продолжает
историю этого candidate и добавляет отдельные логические коммиты по immutable commit plan.
Coordinator не выполняет и не предлагает `git reset --soft`. Если HEAD worktree не совпадает с pinned
snapshot, исправляйте конфигурацию нового dispatch или выбирайте worktree на этом commit, не
переписывая существующую историю.

Для `developer-retry` `dispatch preflight` дополнительно возвращает `retry_start`: handoff, с
которого стартует новая developer-сессия, её стартовые файлы, `context_estimate` (порог, оценка до и
после компакта) и `warning`. Оценку и warning повторяет `decision_packet` как
`retry_context_estimate` и `retry_context_warning`. Состав handoff, порог smart zone и правила
компакта — раздел "Developer-retry handoff" в `playbook.md`.

`dispatch create` до записи brief выполняет над ним ту же проверку, что `dispatch send`. Brief,
который send отклонил бы, не создаётся: в ledger не появляются ни brief, ни его status. Пример —
`--candidate-commit` без связанной immutable risk assessment. Remedy называет
`risk assess --batch <batch-id> --candidate-commit <sha> --changed-file <path>...`. После неё нужны
новые `dispatch propose` и `create` (неотправленный brief сначала отменяется через
`dispatch cancel`). Проверка при `dispatch send` остаётся на месте.

Пока роль работает, она отбивает heartbeat, а coordinator-сессия опрашивает состояние. По умолчанию
dispatch допускает до часа тишины для долгой сборки или теста. Но immutable brief требует heartbeat
сразу после self-report и затем не реже раза в пять минут. Это сохраняет быстрый сигнал о живом
worker, и работающий developer не становится stale из-за одного долгого tool call:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch heartbeat --dispatch <dispatch-id>
python .harness/orchestration/coordinator.py --repo . dispatch status \
  --batch <batch-id> --stale-after 3600
```

`dispatch status` показывает для каждого dispatch роль, транспорт, `resolved_model`, результат
self-report, оценку `startup` (состояние worker, классификация сбоя, неизвестные), время
последнего heartbeat, `silent_seconds` и признак `stale`. Это обобщение
QA-lease-expiry на любой dispatch, а не только на clean-room QA lane. Stale — блокер, который
coordinator выносит человеку, а сам по таймауту состояние не меняет.

`dispatch heartbeat` принимает необязательную пару `--context-tokens <N> --context-source probe`.
Это число токенов, измеренное coordinator-ом в live-пробе контекста (см. «Отчётность и мониторинг
токенов» ниже), а не self-report роли. Так сохраняется [правило учёта токенов](../../backend-orchestration.md#language-evidence): токены берутся только
из наблюдаемой telemetry provider или runtime, и сама роль это значение не поставляет.
Значение попадает в открытое поле `extra` статуса dispatch-а. Схема ledger не меняется, новое
событие в `dispatch wait` не вводится.

`dispatch status` дополнительно отдаёт для каждого dispatch последнюю запись `telemetry`
(`dispatch telemetry`, см. ниже) и `context_advisory`. Это чистое чтение, и отсутствие телеметрии
ошибкой не считается: `telemetry` и `context_advisory.observed` тогда равны `null`, а
`context_advisory.level` остаётся `"ok"`.

## Занятый ledger, `report complete` и `ledger release-lock` {#ledger-report-complete-ledger-release-lock}

Каждая команда coordinator-а берёт эксклюзивный lock ledger-а (`.coordinator.lock` в каталоге
state). Lock записывает владельца — `pid`, `host` и `acquired_at`. На платформе с `/proc` запись
дополняют `pid_namespace` (ссылка `/proc/self/ns/pid`) и `boot_id`, а также `operation` — команда
coordinator-а, которая взяла lock. Старые записи без этих полей читаются как раньше. Держит lock
тот, кто первым эксклюзивно создал эту запись. Процесс получает отказ и не пишет в чужой lock,
если его ещё пустой каталог lock успели снять и занять снова. Пока lock держит другая операция, команда записи
завершается ошибкой `ledger is locked by another operation`. Её remedy предлагает повторить
команду и называет `ledger release-lock`, а не ручное удаление.

Опрос coordinator-а переживает занятый lock:

- `dispatch wait` считает занятый lock пропущенным опросом и опрашивает дальше до своего
  `--timeout`. Report возвращается, как только lock освобождён. Если lock занят до конца ожидания,
  результат — обычный `{"dispatch_id": ..., "event": "timeout"}`;
- `dispatch status` при занятом lock завершается с кодом 0 и отвечает структурно:
  `{"ledger_busy": true, "retry_after_seconds": ..., "lock": {...}, "remedy": ...}`. Здесь `lock`
  содержит владельца и `held_seconds`. Это не недоступность coordinator-а: повторите
  `dispatch status` через `retry_after_seconds`.

Терпимость касается только этих двух команд опроса, `report complete` и освобождения QA-lane в
`qa run`. Ни одна запись не идёт без lock. У остальных команд занятый lock остаётся ошибкой.
`report complete` при занятом lock останавливается на шаге, который не смог прочитать состояние.
Она ничего не пишет и в remedy называет себя для повтора.

`qa run` освобождает QA-lane после сбоя и после записи report. Если lock занят, освобождение ждёт
его до 30 секунд и повторяет попытку каждые 0,25 секунды. Когда lock освободился, `qa run` снимает
только lease и запись очереди своего dispatch. После сбоя он ещё возвращает dispatch в `approved`,
и тот же dispatch можно сразу запустить снова. Если lock занят все 30 секунд, ошибка
`QA dispatch <id> was not released` называет dispatch, владельца lease и время его истечения.
Тогда dispatch остаётся `working`. После истечения lease coordinator запускает
`qa clear-stale-lease`. Команда снимает lease и запись очереди и возвращает dispatch в `approved`,
если у него нет записанного report. После этого тот же dispatch запускается снова. Ответ команды и
запись `qa-lane/recoveries/*.json` содержат `restored_dispatch_state`: `approved` или `null`.
Откат запуска, который пережил свой lease, не снимает lease нового запуска того же dispatch и не
меняет его состояние.

Состояние lock показывает команда только для чтения. Она не берёт lock и поэтому работает, когда
ledger занят:

```bash
python .harness/orchestration/coordinator.py --repo . ledger lock-status
```

Ответ — `{"locked": false}` или объект с полями `acquired_at`, `held_seconds`, `owner`,
`operation`, `verdict` (вердикт из таблицы ниже), `stale_after_seconds`, `remaining_seconds` (сколько
осталось до снятия по таймауту, не меньше нуля) и `release_available` (снимет ли lock обычный
`release-lock` прямо сейчас). Те же сведения показывает панель «Lock ledger» в разделе оркестрации
консоли Harness; время удержания и остаток обновляются на живом экране.

Lock, который остаётся занятым, снимает только команда с проверкой владельца:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock
```

Вердикт зависит от владельца:

| Владелец lock | Вердикт |
| --- | --- |
| Процесс владельца жив (на этом host, в том же PID-пространстве и загрузке) | отказ `owner-alive` — при любом возрасте lock |
| Владелец на другом host | отказ `owner-on-another-host`: запустите команду на том host |
| Владелец из другого PID-пространства или другой загрузки, lock младше `LEDGER_LOCK_STALE_SECONDS` | отказ `owner-in-other-environment`: pid воркера из sandbox (`--unshare-pid`) указывает на чужой процесс, поэтому его не проверить |
| Владелец из другого PID-пространства или другой загрузки, lock старше `LEDGER_LOCK_STALE_SECONDS` | снимается, `owner-unknown-stale` |
| Процесс владельца завершился (на этом host) | снимается, `owner-dead` |
| Нет читаемой записи владельца, lock младше `LEDGER_LOCK_STALE_SECONDS` (3600 с) | отказ `owner-unknown-recent`; remedy называет, через сколько секунд lock можно снять |
| Нет читаемой записи владельца, lock старше `LEDGER_LOCK_STALE_SECONDS` | снимается, `owner-unknown-stale` |

Читаемой записи владельца нет в двух случаях. Первый: lock взят старым runtime, и записи нет вовсе.
Второй: владелец умер, создав `owner.json`, но не записав его; запись пустая или нечитаемая. Возраст
нечитаемой записи считается от mtime `owner.json`, а без записи — от mtime каталога lock. Пока lock
моложе порога, владелец может ещё записывать себя, поэтому команда отказывает. Владелец, который за
`LEDGER_LOCK_STALE_SECONDS` так и не записал созданную запись, считается завершившимся.

Успех возвращает `{"released": true, "reason": ..., "lock": {...}}`, а если lock нет —
`{"released": false, "lock": null}`. Отказ — это ошибка с причиной, владельцем и `held_seconds`, и
lock при этом не трогается. Объект `lock` описывает снятый lock:

| Поле | Значение |
| --- | --- |
| `path` | каталог lock |
| `owner` | запись владельца (`pid`, `host`, `acquired_at`) или `null`, если читаемой записи нет |
| `owner_record` | `readable` — запись прочитана; `unreadable` — `owner.json` есть, но пустой или нечитаемый; `absent` — записи нет |
| `acquired_at` | `acquired_at` из записи, иначе mtime `owner.json` для нечитаемой записи или каталога lock |
| `held_seconds` | сколько секунд lock держится к моменту проверки |

В эпохе runtime store (схема store 3) `ledger lock-status` сохраняет поля файлового lock и их
вердикты и добавляет объект `qa_lease`: владелец lease QA-lane, идентичность его процесса,
`fencing_token`, `expires_at`, `stale_heartbeat`, вердикт runtime и `release_available`. Если
файловый lock не занят, `ledger release-lock` без `--force` снимает истёкший lease только при
вердикте `owner-dead`. Живого владельца команда отклоняет кодом 2 и строкой
`REMEDY: [lease_held] stale_heartbeat=… verdict=…`. `--force` с approval и причиной снимает lease
при любом вердикте через `lease_clear`, и runtime записывает решение в audit.

### Параллельная запись, снимки чтения и lease QA-lane

Команды разных batch пишут параллельно. Команда читает store из одного снимка (`state.read` с
`snapshot`): коммит другого batch между двумя её чтениями не даёт ни отказа, ни половины двух
состояний. Команды чтения (`dispatch status`, `batch auto-report`, `batch decision-packet`,
`qa status`) не ждут писателя. Запись в один batch по-прежнему сериализует `revision` строки.
Решение по всем batch (`concurrency_budget` в `dispatch create`, дубль ticket, branch или worktree в
`batch create`) защищает ревизия строки `generation` из снимка этого решения. Из двух команд,
решивших по одному состоянию, коммитит одна, а другая получает `revision_conflict` по `generation`
и повторяется.

QA-lane в store — singleton lease с `fencing_token`. `qa run` и `integration local-qa` берут его
операцией `lease_acquire`. Runtime записывает идентичность процесса-владельца из ядра: host,
boot, PID-namespace, pid и время старта процесса. Каждый новый lease увеличивает `fencing_token`.
Владелец продлевает lease heartbeat каждую треть `lease_ttl_seconds` (по умолчанию 300 с;
`--lease-seconds` переопределяет срок). Release или heartbeat с чужим владельцем или токеном
получает `fencing_mismatch`. После `expires_at` runtime проверяет владельца только по
идентичности:

| Вердикт | Значение | Lease |
| --- | --- | --- |
| `owner-dead` | тот же host, boot и PID-namespace, процесса с этим pid нет | снимается без `--force` |
| `owner-alive` | pid занят процессом с записанным временем старта | остаётся |
| `owner-pid-reused` | pid занят процессом с другим временем старта | остаётся: это не доказывает смерть |
| `owner-in-other-environment` | другой boot или PID-namespace | остаётся |
| `owner-on-another-host` | другой host | остаётся |
| `owner-unknown` | идентичности нет (lease схемы 2, клиент вне видимости runtime) | остаётся |

Lease мёртвого владельца снимает следующий `qa run`, `integration local-qa` или `ledger
release-lock`. Запись audit содержит владельца, идентичность, наблюдение, вердикт и время. Как и
`qa clear-stale-lease`, снятие удаляет запись очереди владельца, возвращает его QA dispatch в
`approved` и пишет `qa-lane/recoveries`. При другом вердикте запрос завершается кодом 2 с
`[lease_held]` и `stale_heartbeat`. `qa status` показывает `stale_heartbeat`, а `dispatch status`
показывает lane в объекте верхнего уровня `qa_lane`. Живого владельца не снимает ни автоматика, ни
`ledger release-lock` без `--force`. Ручной override остаётся `ledger release-lock --force` или
`qa clear-stale-lease`. `harness-runtime serve` нужно запускать в PID-namespace, который видит
coordinator-ы (host или предок их песочниц). Runtime, который не видит клиента, не записывает его
идентичность, и такой lease автоматически не снимается.

Команда снимает только тот lock, который проверила: если владелец сменился во время снятия, она
отказывает и просит повторить. Запуски `ledger release-lock` не пересекаются, потому что их
сериализует файловая блокировка ОС (`.coordinator.lock.release` в каталоге state), которую система
снимает сама при выходе процесса. Второй параллельный запуск получает отказ
`another ledger release-lock is releasing the ledger lock` и повторяется после первого. Удалять lock
или другие файлы state вручную нельзя.

Если lock оставил остановленный воркер, а его pid совпал с живым процессом (старая запись без
`pid_namespace`, вердикт `owner-alive`), или ждать таймаута нельзя, оператор снимает lock
принудительно:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock --force \
  --approved-by "<оператор>" --approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --reason "<почему владелец не завершит операцию>"
```

Без `--approved-by`, `--approved-at` или `--reason` команда отказывает; одобрение `policy:...`
отвергается, а при `human_approval_gate: tty` его нужно подтвердить на терминале. Ни одна политика,
включая `auto`, эту команду не запускает. Перед снятием команда пишет запись аудита с контрольной
суммой (`record_sha256`) в `lock-audit/` каталога state: кто и когда одобрил, причину, вердикт
проверки и прежнее состояние lock. Если после записи снять lock не удалось, вторая запись
`ledger-lock-force-release-failed` называет первую. `ledger validate` проверяет контрольные суммы
этих записей; подмену записи вместе с её суммой или удаление файла он не обнаруживает. В консоли
то же действие — команда «Снять lock ledger» с подтверждением.

## Автозапуск runtime {#runtime-autostart}

В Claude Code `harness-runtime serve` запускает hook `runtime-autostart` (ADR 0031), а не
разработчик и не агент. Hook исполняется вне песочницы агента, поэтому serve видит Docker.

- **Старт.** Перед каждой командой `.harness/orchestration/coordinator.py` hook вызывает
  `harness-runtime ensure` для основного checkout. Если runtime не отвечает, ensure запускает свой
  serve и ждёт готовности до 40 с; разработчик видит сообщение с pid и журналом.
- **Переиспользование.** Работающий serve, ручной или запущенный другой сессией, переиспользуется
  молча; второй экземпляр не запускается.
- **Владельцы.** Свой serve хранит владельцев: сессию (`<session_id>`) и субагентов
  (`<session_id>/<agent_id>`). `Stop` и `SubagentStop` освобождают владельца. Владелец уходит и тогда,
  когда процесс Claude Code (`CLAUDE_PID`) завершился или владелец не обновлялся час (TTL).
- **Остановка.** Свой serve останавливается сам, когда владельцев нет, соединений нет и store
  простаивает: нет dispatch в `dispatched` или `working`, удерживаемого lease QA, очереди QA и
  незавершённого исполнения. Нечитаемый store считается занятым. Ручной serve сам не
  останавливается никогда.
- **Журнал.** `<каталог runtime>/<repo-id>.serve.log` (права `0600`); путь называет сообщение hook-а.
- **Устаревшая сборка.** Hook запускает только `native/harness-runtime/target/release/harness-runtime`,
  свежий по dep-info `harness-runtime.d`, `Cargo.lock` и `Cargo.toml`. Устаревшую сборку hook не
  запускает: он только подключается к работающему serve, иначе предупреждает «сборка устарела».
  Пересоберите: `cargo build --release --manifest-path native/harness-runtime/Cargo.toml`.
- **Окружение.** Serve получает окружение Claude Code без переменных, которые приложение добавляет
  только hook-ам (`CLAUDECODE`, `CLAUDE_PID`, `CLAUDE_PROJECT_DIR` и другие из ADR 0031).
- **Отказ.** Отказ serve (код 2), таймаут, отсутствие бинарника или песочница дают предупреждение
  `[runtime-autostart-failed]` с причиной и журналом. Hook ничего не блокирует.

Codex и Windows автозапуска не получают: запустите `harness-runtime serve --repo <repo>` вручную вне
песочницы агента. Так же говорит remedy ошибки `[runtime_unavailable]`. Hook появляется в проекте
после `harness update`, который выполняет человек.

## Запись lifecycle в эпохе runtime store {#lifecycle-runtime-store}

После `harness-runtime migrate` (`ledger.json` версии 4) каждую мутацию batch и dispatch принимает
Rust runtime, а не файловая запись и не lock `.coordinator.lock` (ADR 0020, ADR 0021, раздел 4).
Python не открывает `runtime.db` и не имеет запасного пути записи: без запущенного runtime команда
записи отказывает кодом 2 и `[runtime_unavailable]`, ничего не создаёт и не меняет.

- **Единица записи.** Блок `_ledger_lock` команды стал её единицей записи. Примитивы ledger
  (`write_immutable`, `write_artifact`, `replace`, `delete`) только накапливают мутации, а команда
  читает собственные записи из своего view. При чистом выходе из блока coordinator отправляет одну
  операцию `state.write` на каждый batch; исключение внутри блока не отправляет ничего, кроме
  записей, которые отказ сохраняет сам (запись попытки при отказе доступа `qa run` и флаг
  `needs_attention` при отказе `dispatch create`: перед исключением они вызывают `persist_writes`,
  как их держал файловый ledger). Каждый внешний блок `_ledger_lock` и каждый `read_state` читает
  свежий снимок store, поэтому опрос `dispatch wait` видит новый `reported` и новые heartbeat;
  чтения команды до блока видят снимок её начала. Вложенный блок присоединяется к внешней единице. Если мутации касаются двух batch, они уходят двумя
  транзакциями: каждая атомарна, но не обе вместе.
- **CAS по revision.** `state.read` отдаёт `revision` каждой строки (`batch`, `dispatch`,
  `dispatch-status`, `qa-lane`, очередь QA, запись `record`). Первое касание существующей строки
  несёт ту ревизию, которую команда прочитала; конверт запроса несёт ревизию строки batch
  (0 при создании). Зафиксированная транзакция увеличивает ревизию каждой затронутой строки ровно
  на 1. Устаревшая ревизия даёт `revision_conflict`, и ничего не записывается.
- **Транзакция.** `BEGIN IMMEDIATE`, затем строки в порядке `batch` → `qa_lane` → `generation`
  (строки batch, строки QA-lane, затем audit и строка `operations`); одна запись audit на мутацию
  в порядке запроса. Неизменяемые записи (план, brief, отчёт, checkpoint, evidence) не заменяются
  и не удаляются (`invariant_violation`). Инварианты схемы проверяет SQLite: CHECK для batch и
  CHECK состояния исполнения (`DispatchState` терминален при исполнении `unknown`, `launching`
  или `running`).
- **Идемпотентность.** Строка `operations` (`intent`, `committed` или `failed`) пишется в той же
  транзакции. Повтор с тем же `operation_id` и тем же digest запроса возвращает сохранённый
  результат; тот же `operation_id` с другим запросом — `idempotency_conflict`. `operation_id`
  равен `sha256(batch_id, expected_revision, operation, payload_digest)` (ADR 0021, раздел 4).
  Полезная нагрузка содержит времена, поэтому команда, перезапущенная после SIGKILL coordinator,
  строит новый ключ, и CAS по `revision` отвечает `revision_conflict`, а не сохранённым
  результатом: команду нужно повторить.

| Код | Когда | Повтор | REMEDY (первая строка) |
|---|---|---|---|
| `revision_conflict` | другая команда изменила строку после чтения | да | `[revision_conflict]` повторить команду: она заново читает store и применяет политику к текущему состоянию |
| `store_busy` | store занят дольше 5 секунд | да | `[store_busy]` повторить команду |
| `runtime_unavailable` | runtime не отвечает | да | `[runtime_unavailable]` запустить `harness-runtime serve --repo <repo>` |
| `idempotency_conflict` | `operation_id` уже занят другим запросом | нет | `[idempotency_conflict]` повторить команду: она выведет новый id из текущей ревизии |
| `invariant_violation` | изменение нарушает инвариант store или цепочка audit не сходится | нет | `[invariant_violation]` остановить писателей и выполнить `ledger validate --full` |

Каждый отказ завершает команду кодом 2 и начинает первую строку `REMEDY:` кодом в скобках. Команды,
которые ждали занятый ledger, считают `store_busy` занятым ledger: `dispatch status` отвечает
`ledger_busy`, а опрос `dispatch wait` пропускает занятый такт и повторяет его. В эпохе store
блок `_ledger_lock` не ждёт замка: `store_busy` приходит из `state.read` или из отправки записи,
то есть уже внутри блока. Поэтому освобождение QA-lane после `qa run` не ждёт 30 секунд, как при
файловом lock, а пробрасывает `store_busy` сразу; lease и запись очереди остаются до истечения lease, и их
снимает `qa clear-stale-lease`.

### Цепочка audit и `ledger validate --full`

Цепочка audit хранится в таблице `audit`: каждая запись связана хешем с предыдущей, первая запись —
`legacy-import` с якорем манифеста импорта. Таблица `audit_checkpoint` помнит последнюю
проверенную запись. Обычная команда (чтение и запись) проверяет только записи после checkpoint;
запись двигает checkpoint в своей транзакции. Отсутствующий или повреждённый checkpoint означает
полную проверку, и следующая запись или `ledger validate` его перестраивает без ошибки. Запись
строит недостающий checkpoint до транзакции `BEGIN IMMEDIATE` (полная проверка идёт в снимке
чтения, не блокирующем писателей), так что внутри транзакции проверяется только хвост цепочки
(ADR 0020, раздел 3). Нечитаемый store при проверке даёт `store_busy` (занят замок) или `internal`,
а не `invariant_violation`: отправлять оператора к восстановлению снимка нужно только при
несошедшейся цепочке.

`coordinator.py ledger validate --full` не использует checkpoint. Команда пересчитывает цепочку от
genesis (последовательность `seq`, хеши записей и связей, закрытый словарь действий), сверяет
запись 1 с `store_meta` и `AUTHORITY.json`, пересчитывает манифест импорта и хеши legacy audit и
поколений, запускает `PRAGMA integrity_check` и `foreign_key_check` и сверяет каждую строку,
записанную командой, с последней записью audit её пути. Так находятся удаление, вставка и
перестановка записей и строка, изменённая вне runtime. Строки, импортированные и не
переписанные после импорта, проверяет только паритет `migrate`. Провал ничего не записывает;
успех перестраивает checkpoint. В эпохе файлового ledger `--full` принимается и равен обычной
проверке (кэша нет).

В эпохе runtime store `ledger migrate`, `ledger clean` и `ledger reset` отказывают кодом 2:
история уже импортирована, store не держит осиротевших записей, а сбросить его команда не может.
`ledger status` показывает эпоху и число записей audit.

## Отчётность и мониторинг токенов: `dispatch telemetry` {#dispatch-telemetry}

```bash
python .harness/orchestration/coordinator.py --repo . dispatch telemetry --file telemetry.json
```

Команда записывает source-observed метрики (worker- или coordinator-сессии) в audit trail batch-а:
`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `max_context_tokens`,
`tool_calls`, `tool_output_bytes`, `poll_turns`, `restart_reason`, `recorded_at`. Недостающее
provider-поле остаётся `null`, а не оценочным нулём. Команда намеренно работает только с данными: она лишь
пишет запись телеметрии и не может изменить состояние роли, планирование, approvals или model
routing.

В **возвращаемом значении** (не в сохранённой ledger-записи) команда добавляет
`context_advisory: {"level": "ok"|"warn"|"over", "limit", "warn_at", "observed"}`. Это
advisory-оценка `max_context_tokens` против порога `adaptive_continuation_policy.context_limit` в
проектной `.harness/orchestration.json`. Долю порога для предупреждения задаёт
`adaptive_continuation_policy.context_warn_ratio` (доля от `context_limit`, по умолчанию `0.8`;
`warn_at = round(context_limit * context_warn_ratio)`). `level` — `"ok"`, пока `observed` (или его
отсутствие) ниже `warn_at`; `"warn"` — в диапазоне `[warn_at, context_limit)`; `"over"` — на
`context_limit` и выше. Это чистая оценка: она не триггерит checkpoint автоматически. Решение о
checkpoint остаётся за coordinator-ом, как и для любого другого сигнала, кроме auto-resume по 429
(см. [«Checkpoint и новая worker session»](#checkpoint-worker-session) ниже). Baseline из `playbook.md` («Baseline metrics») тем же образом
остаётся ориентиром, а не скрытым лимитом.

## Checkpoint и новая worker session {#checkpoint-worker-session}

Write-роль (developer, database-migrations, messaging-integration, conflict-resolver) может
растянуть один dispatch на несколько worker session, если весь TDD-цикл в одну сессию раздувает её
контекст. Read-only роль (architect, qa, code-review) — не может: попытка checkpoint для неё
отклоняется сразу.

Вместо completion report текущая worker session фиксирует неитоговый checkpoint — отдельную,
hashed ledger-запись, которую нельзя перепутать с отчётом:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch checkpoint \
  --file checkpoint.json
```

`checkpoint.json` обязан содержать ровно: `dispatch_id`, `commit_sha`, `changed_files`,
`remaining_definition_of_done` (подмножество DoD approved dispatch), `passing_checks` (в формате
`checks_run` completion report, команды — из approved `verification_commands`), `risks`, `blockers`
и `context_package_id` — ссылку на последний зарегистрированный для batch Context Package, либо
литеральный `not applicable — no context package registered`, если для batch его пока нет. Никаких
чужих полей: ни сырой истории чата, ни логов прежних неудачных попыток. `checkpoint` требует уже
подтверждённого self-report. Команда переводит dispatch-status в `checkpointed` и не трогает outcome
enum (`completed`/`blocked`/`failed`). Этот enum остаётся только у completion report.

Новая worker session для того же dispatch ID стартует командой `dispatch resume`. Авторизация
зависит от того, почему закончилась прежняя сессия:

```bash
# runtime adapter сообщил rate-limit termination — авторизация автоматическая
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --termination-reason rate_limit

# планируемый trigger (context limit / N TDD-циклов / большой failure log / законченный vertical
# slice) — требуется явное coordinator decision
python .harness/orchestration/coordinator.py --repo . dispatch resume --dispatch <dispatch-id> \
  --trigger context-limit --measured-value 162000 --file continuation-facts.json \
  --approved-by "project coordinator" --approved-at <approval-time-utc>
```

`--termination-reason`, распознанный как rate limit (`rate_limit`/`rate-limit`/`429`), авторизует
новую сессию автоматически. Новое решение человека/coordinator-а не требуется. Любая другая
причина, включая отсутствующую или нераспознанную, трактуется как planned trigger. Так по умолчанию
coordinator требует approval, а не пропускает его:

- `--trigger` обязателен и должен быть одним из `context-limit`, `tdd-cycles`, `failure-log`,
  `vertical-slice`.
- для `context-limit`/`tdd-cycles`/`failure-log` `--measured-value` обязан быть не меньше
  своего порога `adaptive_continuation_policy` (`context_limit`/
  `tdd_cycle_count`/`failure_log_bytes`) из `.harness/orchestration.json`. Без явной конфигурации
  используются задокументированные значения по умолчанию (150000 / 3 / 20000), а не зашитые
  внутри порознь для каждого места.
- `--file` обязан содержать JSON с `dispatch_id`, `remaining_definition_of_done`, `risks` и
  `dependencies`, буквально совпадающими с последним checkpoint (первые два поля) и с dispatch
  (`dependencies`). `blockers` в сравнение не входит: их формулировка может измениться между
  сессиями без реального дрейфа scope/DoD/risks/dependencies. Расхождение — сигнал, что они реально
  изменились. Тогда coordinator обязан закрыть текущий dispatch и открыть новый через обычный
  approval, а не продолжать этот.
- авторизация записывается тем же `coordinator_decisions`, что accept/retry/block/fail/abandon/
  cancel — новый тип записи не вводится.

`resume` принимает только `checkpointed` dispatch, возвращает его в `dispatched` и отбрасывает
предыдущий model self-report. Это значит, что новая сессия обязана заново пройти `dispatch
self-report` и `dispatch heartbeat` — ровно так же, как при первом контакте, — прежде чем следующий
checkpoint или completion report будет принят. Круг замыкается тем же dispatch ID: checkpoint →
`dispatch resume` → новая self-report/heartbeat → в итоге один completion report.

Обновление installed runtime не меняет runtime snapshot активного batch. Если старый snapshot
содержит ошибку continuation, сохраните checkpoint и Git history, затем выберите штатный recovery
на исправленном runtime с новым approval. Новый batch должен закрепить исходную integration base,
полный DoD/commit plan и сохранённый writer HEAD. Review и QA проверяют весь итоговый candidate.
Записанные briefs, reports и runtime snapshots старого batch остаются audit evidence.
