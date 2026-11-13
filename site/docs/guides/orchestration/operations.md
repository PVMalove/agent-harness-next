# Диагностика и состояние

Начните с чтения статуса и диагностики. Записи меняйте только через coordinator CLI. У снятия блокировки, миграции и продолжения после остановки разные условия и подтверждения.

[Обзор оркестрации](../../backend-orchestration.md)

## Совместимость и миграция {#_5}

Все новые поля batch и четыре поля brief (`transition`, `transition_digest`, `retry_idempotency_key`,
`orchestration_policy`: либо все, либо ни одного) необязательны. Старые записи остаются валидными,
версия ledger не меняется, `ledger migrate` не нужен. Новые записи проходят ту же проверку
целостности (`context_pressure` с hash, форма attention-полей, согласованность brief). Поведение CLI
изменилось в одном месте: `dispatch create` с `--approved-by` теперь требует `--transition-digest`.

Без смены версии ledger и без миграции введены также:

- brief без `commit_plan_divergence` и batch без `commit_plan` остаются валидными. Запись плана без
  `covers` покрывает пункт DoD по своей позиции;
- brief без `carried_items`, transition без `carried_items_sha256`, batch без `carried_items` и
  отчёт code-review без `review.carried_items` валидны. Пустой канал ничего не добавляет в
  transition, поэтому прежние digest не меняются;
- отчёт без `incomplete_items` и brief без вида `incomplete-item` валидны. Новый вид источника,
  поле отчёта и значение маршрута `narrowed-retry` введены без миграции;
- routing record без `retry_item_ids`, поле отчёта `carried_item_closure` и значение маршрута
  `fix-forward`. Brief developer-retry по решению, записанному до них, получает раздел без сверки с
  `retry_item_ids`;
- brief без `rebase_target_commit`, transition без `rebase_target_sha` и значение маршрута
  `rebase-fix-forward`. Переход без target сохраняет прежний digest;
- brief без `delta_review_scope` и transition без `delta_review_sha256`. Переход code-review без
  этого раздела сохраняет прежний digest;
- ссылка `supersedes` в batch и plan и значение маршрута `supersede`. Batch и plan без ссылки
  читаются как прежде.

Completed-отчёт developer-retry, записанный до появления маршрута `fix-forward` без
`carried_item_closure` для brief с перенесёнными пунктами, по-прежнему решается через
`batch decide`. Каждый пункт получает статус `omitted` и входит в `carried_items_gap`. Поэтому
`accept` и auto-accept по политике отклоняются, а `override-warning` требует `--note`, отличный от
`none`. `retry`, `block`, `fail` и `abandon` доступны. Новый такой отчёт `report submit` отклоняет.

Поле `route` в routing record и деталь `decision` в transition audit record batch тоже
необязательны и введены без смены версии ledger (она остаётся 3). Решение, записанное до них,
читается как есть и остаётся валидным. `ledger migrate` не добавляет и не выводит для него route.
Route пишет только новое решение `batch decide`. Если записанный `route` не входит в закрытый набор
маршрутов, coordinator отклоняет его при чтении batch.

## Инвентарь и закрытие тупикового batch {#batch}

Список заведённых и незакрытых batch:

```bash
python .harness/orchestration/coordinator.py --repo . batch list --open
python .harness/orchestration/coordinator.py --repo . batch list --ticket '#123'
```

Обычный путь к терминальному состоянию проходит через `batch decide`. Но ему нужен ровно один
отчёт, который ждёт решения, а отчёту нужен живой dispatch с подтверждённой моделью. Worker, который
умер до self-report, никогда не отчитается, и такой batch не закрыть ни `fail`, ни `block`. Для
этого случая есть отдельная команда:

```bash
python .harness/orchestration/coordinator.py --repo . batch abandon \
  --batch <batch-id> --approved-by 'имя утверждающего' --approved-at <approval-time-utc> \
  --reason 'воркер умер до model self-report, решение недостижимо'
```

Команде нужны явный approval и непустая причина. Она переводит batch в `abandoned`, сохраняет
`last_accepted`, помечает все незакрытые dispatch как `abandoned` и записывает решение рядом с
остальными. **Она ничего не удаляет**: неизменяемые brief, отчёты и QA-артефакты остаются на месте.
К уже терминальному batch её применить нельзя.

Если сбой запуска подтверждён, после устранения причины продолжайте тот же batch:

```bash
python .harness/orchestration/coordinator.py --repo . batch resume-stop \
  --batch <batch-id> --approved-by 'имя оператора' --approved-at <текущее-время-UTC> \
  --note 'исправлен каталог запуска воркера'
```

Команда сохраняет принятые отчёты, исходную остановку и `next_action`, помечает сорванный dispatch
как `abandoned` и переводит batch в `awaiting-approval`. Следующему `dispatch create` нужно новое
approval, и он сохраняет контракт прерванной роли. Ограничения описаны в разделе
[«Ручное восстановление и повтор этапа»](recovery.md#_8). Если причина неизвестна или нужно
вернуться к прежнему gate, используйте `batch rewind`. Состояния `completed` и `abandoned`
окончательны.

Перед отправкой `dispatch send` сверяет флаги `--adapter-arg` с `dispatch --help` адаптера и
отклоняет неподдерживаемый флаг до передачи brief. Dispatch остаётся одобренным и неотправленным.
Если `--help` не отвечает, результат попадает в `adapter_preflight` как `limitation`.

`dispatch runtime-probe --dispatch <id> --runtime-command <runtime> --runtime-arg=app-server`
проверяет app-server runtime без worker: `model/list`, поля `thread/start` и один `turn/start` на
временном read-only thread без инструментов. Ошибка capacity, rate-limit или недоступности после
`thread/start` даёт классифицированный сбой, а не READY. Probe ничего не пишет в ledger и не
заменяет model self-report.

Watchdog `stale` не доказывает, что процесс завершился. Сначала остановите воркера через его
runtime, затем запишите `dispatch cancel --runtime-stopped` с approval человека и выполните rewind.
Совместимая команда `batch resume` подходит только для прежнего ручного пути без auto и recovery.
Для stale она тоже требует `--runtime-stopped`, `--approved-by` и `--approved-at`.

Если initial developer не завершил работу, закрепите сохранённый HEAD через `--candidate-commit`
в следующих `dispatch preflight`, `dispatch propose` и утверждённом `dispatch create`. Это startup
snapshot, а не принятый completed candidate: оценка риска и следующие gates идут после принятия
итогового report. Commit map initial work покрывает весь исходный план от base batch, включая
коммиты, сохранённые до сбоя. Прежние риски остаются в report. Для `developer-retry` действует
отдельный контракт: только новые коммиты после snapshot.

Batch закреплён за рантаймом, под которым его спланировали. `batch create` записывает хэш всего
пакета рантайма в `.harness/`: верхнеуровневых модулей и всех подпакетов (`orchestration/`,
`gate_runner/`, `context_builder/` и других). Ещё он сохраняет неизменяемый снимок этого пакета в
`.harness/orchestration/state/runtimes/`. Если рантайм потом переустановили (например,
`harness update` с ветки другой задачи), команды этого batch выполняются кодом снимка
автоматически. Это команды с `--batch`, `--dispatch` или с `dispatch_id` в файле `--file` у
`report submit`, `dispatch checkpoint` и `dispatch telemetry`. Описания ролей тоже берутся из
снимка. Новые batch получают новый рантайм, поэтому задачи идут параллельно и не блокируют друг
друга. Изменённый вручную снимок coordinator отклоняет.

У batch, созданного до появления снимков, хэш покрывает только `orchestration/`, а снимка нет. Снимок
восстанавливают из пакета той ревизии, на которой batch спланирован. Подойдёт `.harness` из
временного worktree с выполненным `harness update` или каталог `harness/` из
`git archive <ревизия> harness`:

```bash
python .harness/orchestration/coordinator.py --repo . batch restore-runtime \
  --batch <batch-id> --from <путь к пакету закреплённой ревизии>
```

Команда принимает каталог, только если его хэш совпадает с закреплённым. Снимок и новый рантайм
работают с одним ledger. Поэтому `ledger migrate` на новую версию схемы отказывает, пока есть
незавершённые batch, закреплённые за другим рантаймом. Сначала их доводят до конца или отменяют на
их собственном рантайме.

Если закреплённый snapshot уже выполняет все пункты DoD, не создавайте фиктивный коммит ради
отчёта write-роли и не используйте `abandon`. Запишите отдельное терминальное решение:

```bash
python .harness/orchestration/coordinator.py --repo . batch not-required \
  --batch <batch-id> --approved-by 'имя утверждающего' --approved-at <approval-time-utc> \
  --reason 'pinned snapshot already satisfies every definition-of-done item'
```

Команда оставляет audit evidence, отменяет незакрытые dispatch, переводит batch в `completed` с
`completion_kind: no-implementation` и советует закрыть связанный issue с меткой
`resolution::wontfix`. Обычный report write-роли по-прежнему обязан содержать настоящий коммит и
точный список изменённых файлов.

Если ошибка найдена **до** передачи brief runtime, не отменяйте batch. Отмените только этот
неотправленный dispatch. Неизменяемый brief останется в audit trail, а batch вернётся в
`awaiting-approval` и сможет получить исправленный dispatch.

```bash
python .harness/orchestration/coordinator.py --repo . dispatch cancel \
  --dispatch <dispatch-id> --approved-by 'имя утверждающего' \
  --approved-at <approval-time-utc> --reason 'исправить назначение до запуска worker'
```

Никогда не правьте файлы в `.harness/orchestration/state/` руками. Эти записи и есть
доказательство, ради которого существует весь маршрут. Если штатной команды для вашего случая нет,
это дефект инструмента, а не повод открыть редактор.

## Model self-report и dispatch watchdog {#model-self-report-dispatch-watchdog}

Отправленный dispatch сам по себе не считается живым. Получив brief, роль первым делом
подтверждает модель, которая действительно работает:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch self-report \
  --dispatch <dispatch-id> --model <фактическая модель> \
  --worktree "$(git rev-parse --show-toplevel)"
```

Если модель совпала с `resolved_model` неизменяемого brief, dispatch переходит в `working`. Если
включён `worker_attestation_required`, coordinator также проверяет переданный Git top-level,
issue-ветку write-роли или закреплённый SHA review-роли. При расхождении dispatch сразу переходит в
`blocked`, batch помечается `blocked`, а команда завершается ошибкой. После этого coordinator не
принимает `report submit` для такого dispatch. Чинят это новым dispatch с новым brief, а не правкой
отправленного. Без успешного self-report completion report не принимается совсем. Поэтому
подменённая или неверно настроенная модель видна сразу, а не после потраченного окна.

Для architect и developer `worker_attestation_required` также требует, чтобы HEAD Git-worktree при
первом `self-report` в точности совпадал с неизменяемым `snapshot_commit` из brief. При разрешённом
`dispatch resume` write-роли свежий self-report проверяет точный `commit_sha` последнего
зарегистрированного checkpoint. Исходный brief и граница evidence плана коммитов не меняются. Для
architect, developer, verification и code-review `dispatch create` выбирает `snapshot_commit` в
таком порядке:

1. явный `--candidate-commit`;
2. `commit_sha` непринятого developer report, пока batch ждёт его `developer-retry`;
3. последний принятый developer candidate, например для `developer-retry` после blocker на
   code-review, qa или publish (повтор на том же SHA developer dispatch не создаёт);
4. иначе `base_commit`.

`dispatch preflight` и проверка свежести Context Package используют то же правило. Retry
продолжает историю этого candidate и добавляет отдельные логические коммиты по неизменяемому плану
коммитов. Coordinator не выполняет и не предлагает `git reset --soft`. Если HEAD worktree не
совпадает с закреплённым snapshot, исправьте конфигурацию нового dispatch или выберите worktree на
этом коммите. Существующую историю не переписывайте.

Для `developer-retry` `dispatch preflight` дополнительно возвращает `retry_start`: handoff, с
которого стартует новая developer-сессия, её стартовые файлы, `context_estimate` (порог, оценка до и
после компакта) и `warning`. Оценку и warning повторяет `decision_packet` как
`retry_context_estimate` и `retry_context_warning`. Состав handoff, порог smart zone и правила
компакта описаны в разделе "Developer-retry handoff" файла `playbook.md`.

`dispatch create` до записи brief проверяет его так же, как `dispatch send`. Brief, который send
отклонил бы, не создаётся: в ledger не появляются ни brief, ни его status. Пример:
`--candidate-commit` без связанной неизменяемой оценки риска. Remedy называет
`risk assess --batch <batch-id> --candidate-commit <sha> --changed-file <path>...`. После оценки
нужны новые `dispatch propose` и `create` (неотправленный brief сначала отменяют через
`dispatch cancel`). Проверка при `dispatch send` остаётся.

Пока роль работает, она отправляет heartbeat, а coordinator-сессия опрашивает состояние. По
умолчанию dispatch допускает до часа тишины для долгой сборки или теста. Но неизменяемый brief
требует heartbeat сразу после self-report и потом не реже раза в пять минут. Так coordinator быстро
видит, что worker жив, а работающий developer не становится stale из-за одного долгого tool call:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch heartbeat --dispatch <dispatch-id>
python .harness/orchestration/coordinator.py --repo . dispatch status \
  --batch <batch-id> --stale-after 3600
```

`dispatch status` показывает для каждого dispatch роль, транспорт, `resolved_model`, результат
self-report, оценку `startup` (состояние worker, классификация сбоя, неизвестные), время последнего
heartbeat, `silent_seconds` и признак `stale`. Это тот же механизм, что истечение lease в
clean-room QA lane, но для любого dispatch. Stale считается блокером, который coordinator передаёт
человеку. Сам по таймауту coordinator состояние не меняет.

`dispatch heartbeat` принимает необязательную пару `--context-tokens <N> --context-source probe`.
Это число токенов, которое coordinator измерил живой пробой контекста (см. «Отчётность и мониторинг
токенов» ниже), а не self-report роли. Так соблюдается
[правило учёта токенов](../../backend-orchestration.md#language-evidence): токены берутся только из
наблюдаемой телеметрии провайдера или runtime, и роль это значение не поставляет. Значение
попадает в открытое поле `extra` статуса dispatch. Схема ledger не меняется, новое событие в
`dispatch wait` не появляется.

`dispatch status` также отдаёт для каждого dispatch последнюю запись `telemetry`
(`dispatch telemetry`, см. ниже) и `context_advisory`. Команда только читает, и отсутствие
телеметрии ошибкой не считается: `telemetry` и `context_advisory.observed` тогда равны `null`, а
`context_advisory.level` остаётся `"ok"`.

## Занятый ledger, `report complete` и `ledger release-lock` {#ledger-report-complete-ledger-release-lock}

Каждая команда coordinator берёт эксклюзивный lock ledger (`.coordinator.lock` в каталоге state).
Lock записывает владельца: `pid`, `host` и `acquired_at`. На платформе с `/proc` запись дополняют
`pid_namespace` (ссылка `/proc/self/ns/pid`), `boot_id` и `operation`, то есть команда coordinator,
которая взяла lock. Старые записи без этих полей читаются как раньше. Lock держит тот, кто первым
эксклюзивно создал эту запись. Если ещё пустой каталог lock успели снять и занять снова, процесс
получает отказ и в чужой lock не пишет. Пока lock держит другая операция, команда записи
завершается ошибкой `ledger is locked by another operation`. Её remedy предлагает повторить команду
и называет `ledger release-lock`, а не ручное удаление.

Опрос coordinator переживает занятый lock:

- `dispatch wait` считает занятый lock пропущенным опросом и опрашивает дальше до своего
  `--timeout`. Report возвращается, как только lock освобождён. Если lock занят до конца ожидания,
  результат обычный: `{"dispatch_id": ..., "event": "timeout"}`;
- `dispatch status` при занятом lock завершается с кодом 0 и отвечает структурно:
  `{"ledger_busy": true, "retry_after_seconds": ..., "lock": {...}, "remedy": ...}`. Здесь `lock`
  содержит владельца и `held_seconds`. Coordinator при этом доступен: повторите `dispatch status`
  через `retry_after_seconds`.

Эта терпимость касается только двух команд опроса, `report complete` и освобождения QA-lane в
`qa run`. Ни одна запись не идёт без lock. У остальных команд занятый lock остаётся ошибкой.
`report complete` при занятом lock останавливается на шаге, который не смог прочитать состояние,
ничего не пишет и в remedy называет себя для повтора.

`qa run` освобождает QA-lane после сбоя и после записи report. Если lock занят, освобождение ждёт
до 30 секунд и повторяет попытку каждые 0,25 секунды. Когда lock освободился, `qa run` снимает
только lease и запись очереди своего dispatch. После сбоя он ещё возвращает dispatch в `approved`,
и тот же dispatch можно сразу запустить снова.

Если lock занят все 30 секунд, ошибка `QA dispatch <id> was not released` называет dispatch,
владельца lease и время истечения lease. Dispatch тогда остаётся в `working`. После истечения lease
coordinator запускает `qa clear-stale-lease`. Команда снимает lease и запись очереди и возвращает
dispatch в `approved`, если у него нет записанного report. После этого тот же dispatch можно
запустить снова. Ответ команды и запись `qa-lane/recoveries/*.json` содержат
`restored_dispatch_state`: `approved` или `null`. Откат запуска, который пережил свой lease, не
снимает lease нового запуска того же dispatch и не меняет его состояние.

Состояние lock показывает команда только для чтения. Она не берёт lock, поэтому работает и при
занятом ledger:

```bash
python .harness/orchestration/coordinator.py --repo . ledger lock-status
```

Ответ: `{"locked": false}` или объект с полями `acquired_at`, `held_seconds`, `owner`,
`operation`, `verdict` (вердикт из таблицы ниже), `stale_after_seconds`, `remaining_seconds`
(сколько осталось до снятия по таймауту, не меньше нуля) и `release_available` (снимет ли обычный
`release-lock` lock прямо сейчас). Те же сведения показывает панель «Lock ledger» в разделе
оркестрации консоли Harness. Время удержания и остаток обновляются на живом экране.

Если lock остаётся занятым, снимите его только командой с проверкой владельца:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock
```

Вердикт зависит от владельца:

| Владелец lock | Вердикт |
| --- | --- |
| Процесс владельца жив (на этом host, в том же PID-пространстве и загрузке) | отказ `owner-alive` при любом возрасте lock |
| Владелец на другом host | отказ `owner-on-another-host`: запустите команду на том host |
| Владелец из другого PID-пространства или другой загрузки, lock младше `LEDGER_LOCK_STALE_SECONDS` | отказ `owner-in-other-environment`: pid воркера из sandbox (`--unshare-pid`) указывает на чужой процесс, поэтому его не проверить |
| Владелец из другого PID-пространства или другой загрузки, lock старше `LEDGER_LOCK_STALE_SECONDS` | снимается, `owner-unknown-stale` |
| Процесс владельца завершился (на этом host) | снимается, `owner-dead` |
| Нет читаемой записи владельца, lock младше `LEDGER_LOCK_STALE_SECONDS` (3600 с) | отказ `owner-unknown-recent`; remedy называет, через сколько секунд lock можно снять |
| Нет читаемой записи владельца, lock старше `LEDGER_LOCK_STALE_SECONDS` | снимается, `owner-unknown-stale` |

Читаемой записи владельца нет в двух случаях. Первый: lock взял старый runtime, и записи нет
совсем. Второй: владелец создал `owner.json`, но умер, не записав его, и запись пустая или
нечитаемая. Возраст нечитаемой записи считается от mtime `owner.json`, а без записи от mtime
каталога lock. Пока lock моложе порога, владелец ещё может записывать себя, поэтому команда
отказывает. Владелец, который за `LEDGER_LOCK_STALE_SECONDS` так и не заполнил созданную запись,
считается завершившимся.

Успех возвращает `{"released": true, "reason": ..., "lock": {...}}`, а если lock нет,
`{"released": false, "lock": null}`. Отказ приходит ошибкой с причиной, владельцем и
`held_seconds`, и lock при этом не трогается. Объект `lock` описывает снятый lock:

| Поле | Значение |
| --- | --- |
| `path` | каталог lock |
| `owner` | запись владельца (`pid`, `host`, `acquired_at`) или `null`, если читаемой записи нет |
| `owner_record` | `readable`: запись прочитана; `unreadable`: `owner.json` есть, но пустой или нечитаемый; `absent`: записи нет |
| `acquired_at` | `acquired_at` из записи, иначе mtime `owner.json` для нечитаемой записи или mtime каталога lock |
| `held_seconds` | сколько секунд lock держится к моменту проверки |

В эпохе runtime store (схема store 3) `ledger lock-status` сохраняет поля файлового lock и их
вердикты и добавляет объект `qa_lease`: владелец lease QA-lane, идентичность его процесса,
`fencing_token`, `expires_at`, `stale_heartbeat`, вердикт runtime и `release_available`. Если
файловый lock свободен, `ledger release-lock` без `--force` снимает истёкший lease только при
вердикте `owner-dead`. Живого владельца команда отклоняет с кодом 2 и строкой
`REMEDY: [lease_held] stale_heartbeat=… verdict=…`. `--force` с approval и причиной снимает lease
при любом вердикте через `lease_clear`, и runtime записывает решение в audit.

### Параллельная запись, снимки чтения и lease QA-lane

Команды разных batch пишут параллельно. Команда читает store из одного снимка (`state.read` с
`snapshot`). Поэтому коммит другого batch между двумя её чтениями не даёт ни отказа, ни смеси двух
состояний. Команды чтения (`dispatch status`, `batch auto-report`, `batch decision-packet`,
`qa status`) не ждут писателя. Запись в один batch по-прежнему упорядочивает `revision` строки.
Решения по всем batch (`concurrency_budget` в `dispatch create`, дубль тикета, ветки или worktree
в `batch create`) защищает ревизия строки `generation` из снимка этого решения. Из двух команд,
которые решали по одному состоянию, коммитит одна. Другая получает `revision_conflict` по
`generation` и повторяется.

QA-lane в store устроена как singleton lease с `fencing_token`. `qa run` и `integration local-qa`
берут его операцией `lease_acquire`. Runtime записывает идентичность процесса-владельца из ядра:
host, boot, PID-namespace, pid и время старта процесса. Каждый новый lease увеличивает
`fencing_token`. Владелец продлевает lease heartbeat каждую треть `lease_ttl_seconds` (по умолчанию
300 с, `--lease-seconds` меняет срок). Release или heartbeat с чужим владельцем или токеном
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

Lease мёртвого владельца снимает следующий `qa run`, `integration local-qa` или
`ledger release-lock`. Запись audit содержит владельца, идентичность, наблюдение, вердикт и время.
Как и `qa clear-stale-lease`, снятие удаляет запись очереди владельца, возвращает его QA dispatch в
`approved` и пишет `qa-lane/recoveries`. При другом вердикте запрос завершается с кодом 2,
`[lease_held]` и `stale_heartbeat`. `qa status` показывает `stale_heartbeat`, а `dispatch status`
показывает lane в объекте верхнего уровня `qa_lane`. Живого владельца не снимает ни автоматика, ни
`ledger release-lock` без `--force`. Ручной override: `ledger release-lock --force` или
`qa clear-stale-lease`. Запускайте `harness-runtime serve` в PID-namespace, который видит
coordinator (host или предок их песочниц). Runtime, который не видит клиента, не записывает его
идентичность, и такой lease автоматически не снимается.

Команда снимает только тот lock, который проверила: если владелец сменился во время снятия, она
отказывает и просит повторить. Запуски `ledger release-lock` не пересекаются: их упорядочивает
файловая блокировка ОС (`.coordinator.lock.release` в каталоге state), которую система снимает сама
при выходе процесса. Второй параллельный запуск получает отказ
`another ledger release-lock is releasing the ledger lock` и повторяется после первого. Удалять lock
или другие файлы state вручную нельзя.

Бывает, что lock оставил остановленный воркер, а его pid совпал с живым процессом (старая запись
без `pid_namespace`, вердикт `owner-alive`), или ждать таймаута нельзя. Тогда оператор снимает lock
принудительно:

```bash
python .harness/orchestration/coordinator.py --repo . ledger release-lock --force \
  --approved-by "<оператор>" --approved-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --reason "<почему владелец не завершит операцию>"
```

Без `--approved-by`, `--approved-at` или `--reason` команда отказывает. Одобрение `policy:...` она
отвергает, а при `human_approval_gate: tty` одобрение нужно подтвердить на терминале. Ни одна
политика, включая `auto`, эту команду не запускает. Перед снятием команда пишет запись аудита с
контрольной суммой (`record_sha256`) в `lock-audit/` каталога state: кто и когда одобрил, причина,
вердикт проверки и прежнее состояние lock. Если после записи снять lock не удалось, вторая запись
`ledger-lock-force-release-failed` ссылается на первую. `ledger validate` проверяет контрольные
суммы этих записей, но подмену записи вместе с её суммой или удаление файла не обнаруживает. В
консоли то же действие называется «Снять lock ledger» и требует подтверждения.

## Автозапуск runtime {#runtime-autostart}

В Claude Code `harness-runtime serve` запускает hook `runtime-autostart` (ADR 0031), а не
разработчик и не агент. Hook работает вне песочницы агента, поэтому serve видит Docker.

- **Старт.** Перед каждой командой `.harness/orchestration/coordinator.py` hook вызывает
  `harness-runtime ensure` для основного checkout. Если runtime не отвечает, ensure запускает свой
  serve и ждёт готовности до 40 с. Разработчик видит сообщение с pid и журналом.
- **Переиспользование.** Работающий serve, ручной или запущенный другой сессией, hook молча
  переиспользует. Второй экземпляр не запускается.
- **Владельцы.** Свой serve хранит владельцев: сессию (`<session_id>`) и субагентов
  (`<session_id>/<agent_id>`). `Stop` и `SubagentStop` освобождают владельца. Владелец уходит и
  тогда, когда процесс Claude Code (`CLAUDE_PID`) завершился или владелец не обновлялся час (TTL).
- **Остановка.** Свой serve останавливается сам, когда нет владельцев, нет соединений и store
  простаивает: нет dispatch в `dispatched` или `working`, удерживаемого lease QA, очереди QA и
  незавершённого исполнения. Нечитаемый store считается занятым. Ручной serve сам не
  останавливается никогда.
- **Журнал.** `<каталог runtime>/<repo-id>.serve.log` (права `0600`). Путь называет сообщение
  hook.
- **Устаревшая сборка.** Hook запускает только `native/harness-runtime/target/release/harness-runtime`,
  свежий по dep-info `harness-runtime.d`, `Cargo.lock` и `Cargo.toml`. Устаревшую сборку hook не
  запускает: он только подключается к работающему serve, а если serve нет, предупреждает «сборка
  устарела». Пересоберите: `cargo build --release --manifest-path native/harness-runtime/Cargo.toml`.
- **Окружение.** Serve получает окружение Claude Code без переменных, которые приложение добавляет
  только hook (`CLAUDECODE`, `CLAUDE_PID`, `CLAUDE_PROJECT_DIR` и другие из ADR 0031).
- **Отказ.** Отказ serve (код 2), таймаут, отсутствие бинарника или песочница дают предупреждение
  `[runtime-autostart-failed]` с причиной и журналом. Hook ничего не блокирует.
- **Чужой checkout.** Hook запускает только бинарник основного checkout проекта сессии
  (`CLAUDE_PROJECT_DIR`). Если coordinator из другого репозитория, путь к нему только упомянут в
  команде или `CLAUDE_PROJECT_DIR` пуста, hook выдаёт предупреждение `[runtime-autostart-failed]
  coordinator репозитория … не относится к основному checkout проекта сессии` и бинарник не
  запускает. Запустите serve этого репозитория вручную.
- **Доверие к сборке.** Hook исполняет `native/harness-runtime/target/release/harness-runtime`
  основного checkout вне песочницы агента. Проверка по dep-info отсекает устаревшую сборку, но не
  подмену файла. Не разрешайте агенту запись в `target/release` основного checkout (ADR 0031,
  раздел 5).

Codex и Windows автозапуска не получают: запустите `harness-runtime serve --repo <repo>` вручную вне
песочницы агента. То же говорит remedy ошибки `[runtime_unavailable]`. Hook появляется в проекте
после `harness update`, который выполняет человек.

## Запись lifecycle в эпохе runtime store {#lifecycle-runtime-store}

После `harness-runtime migrate` (`ledger.json` версии 4) каждую мутацию batch и dispatch принимает
Rust runtime, а не файловая запись и не lock `.coordinator.lock` (ADR 0020, ADR 0021, раздел 4).
Python не открывает `runtime.db` и не имеет запасного пути записи. Если runtime не запущен, команда
записи отказывает с кодом 2 и `[runtime_unavailable]` и ничего не создаёт и не меняет.

- **Единица записи.** Блок `_ledger_lock` команды стал её единицей записи. Примитивы ledger
  (`write_immutable`, `write_artifact`, `replace`, `delete`) только накапливают мутации, а команда
  читает свои записи из своего view. При чистом выходе из блока coordinator отправляет одну
  операцию `state.write` на каждый batch. Исключение внутри блока не отправляет ничего, кроме
  записей, которые отказ сохраняет сам: запись попытки при отказе доступа `qa run` и флаг
  `needs_attention` при отказе `dispatch create`. Перед исключением они вызывают `persist_writes`,
  как их держал файловый ledger. Каждый внешний блок `_ledger_lock` и каждый `read_state` читает
  свежий снимок store, поэтому опрос `dispatch wait` видит новый `reported` и новые heartbeat.
  Чтения команды до блока видят снимок её начала. Вложенный блок присоединяется к внешней единице.
  Если мутации касаются двух batch, они уходят двумя транзакциями: каждая атомарна, но не обе
  вместе.
- **CAS по revision.** `state.read` отдаёт `revision` каждой строки (`batch`, `dispatch`,
  `dispatch-status`, `qa-lane`, очередь QA, запись `record`). Первое касание существующей строки
  несёт ревизию, которую команда прочитала. Конверт запроса несёт ревизию строки batch (0 при
  создании). Зафиксированная транзакция увеличивает ревизию каждой затронутой строки ровно на 1.
  Устаревшая ревизия даёт `revision_conflict`, и ничего не записывается.
- **Транзакция.** `BEGIN IMMEDIATE`, затем строки в порядке `batch` → `qa_lane` → `generation`
  (строки batch, строки QA-lane, затем audit и строка `operations`). Одна запись audit на мутацию в
  порядке запроса. Неизменяемые записи (план, brief, отчёт, checkpoint, evidence) не заменяются и
  не удаляются (`invariant_violation`). Инварианты схемы проверяет SQLite: CHECK для batch и CHECK
  состояния исполнения (`DispatchState` терминален при исполнении `unknown`, `launching` или
  `running`).
- **Идемпотентность.** Строка `operations` (`intent`, `committed` или `failed`) пишется в той же
  транзакции. Повтор с тем же `operation_id` и тем же digest запроса возвращает сохранённый
  результат. Тот же `operation_id` с другим запросом даёт `idempotency_conflict`. `operation_id`
  равен `sha256(batch_id, expected_revision, operation, payload_digest)` (ADR 0021, раздел 4).
  Полезная нагрузка содержит время, поэтому команда, перезапущенная после SIGKILL coordinator,
  строит новый ключ. Тогда CAS по `revision` отвечает `revision_conflict`, а не сохранённым
  результатом, и команду нужно повторить.

| Код | Когда | Повтор | REMEDY (первая строка) |
|---|---|---|---|
| `revision_conflict` | другая команда изменила строку после чтения | да | `[revision_conflict]` повторить команду: она заново читает store и применяет политику к текущему состоянию |
| `store_busy` | store занят дольше 5 секунд | да | `[store_busy]` повторить команду |
| `runtime_unavailable` | runtime не отвечает; это же показывают проверка `orchestration.runtime` в `harness health` и индикатор «Runtime» веб-консоли | да | `[runtime_unavailable]` запустить `harness-runtime serve --repo <repo>`, см. [«Runtime» быстрого старта](../../getting-started/index.md#runtime) |
| `idempotency_conflict` | `operation_id` уже занят другим запросом | нет | `[idempotency_conflict]` повторить команду: она выведет новый id из текущей ревизии |
| `invariant_violation` | изменение нарушает инвариант store или цепочка audit не сходится | нет | `[invariant_violation]` остановить писателей и выполнить `ledger validate --full` |

Каждый отказ завершает команду с кодом 2, а первая строка `REMEDY:` начинается с кода в скобках.
Команды, которые ждали занятый ledger, считают `store_busy` занятым ledger: `dispatch status`
отвечает `ledger_busy`, а опрос `dispatch wait` пропускает занятый такт и повторяет его. В эпохе
store блок `_ledger_lock` не ждёт замка: `store_busy` приходит из `state.read` или из отправки
записи, то есть уже внутри блока. Поэтому освобождение QA-lane после `qa run` не ждёт 30 секунд,
как при файловом lock, а сразу пробрасывает `store_busy`. Lease и запись очереди остаются до
истечения lease, и их снимает `qa clear-stale-lease`.

### Цепочка audit и `ledger validate --full`

Цепочка audit хранится в таблице `audit`: каждая запись связана хешем с предыдущей, первая запись
`legacy-import` содержит якорь манифеста импорта. Таблица `audit_checkpoint` помнит последнюю
проверенную запись. Обычная команда (чтение и запись) проверяет только записи после checkpoint, а
запись двигает checkpoint в своей транзакции. Если checkpoint нет или он повреждён, проверка идёт
полностью, и следующая запись или `ledger validate` перестраивает его без ошибки. Запись строит
недостающий checkpoint до транзакции `BEGIN IMMEDIATE`: полная проверка идёт в снимке чтения,
который не блокирует писателей. Поэтому внутри транзакции проверяется только хвост цепочки
(ADR 0020, раздел 3). Если store не читается при проверке, команда получает `store_busy` (занят
замок) или `internal`, а не `invariant_violation`. Отправлять оператора восстанавливать снимок нужно
только при несошедшейся цепочке.

`coordinator.py ledger validate --full` не использует checkpoint. Команда:

- пересчитывает цепочку от genesis (последовательность `seq`, хеши записей и связей, закрытый
  словарь действий);
- сверяет запись 1 с `store_meta` и `AUTHORITY.json`;
- пересчитывает манифест импорта и хеши legacy audit и поколений;
- запускает `PRAGMA integrity_check` и `foreign_key_check`;
- сверяет каждую строку, записанную командой, с последней записью audit её пути.

Так находятся удаление, вставка и перестановка записей и строка, изменённая вне runtime. Строки,
которые импортированы и после импорта не переписывались, проверяет только паритет `migrate`.
Провал ничего не записывает, успех перестраивает checkpoint. В эпохе файлового ledger `--full`
принимается и работает как обычная проверка (кэша нет).

В эпохе runtime store `ledger migrate`, `ledger clean` и `ledger reset` отказывают с кодом 2:
история уже импортирована, store не держит осиротевших записей, а сбросить его команда не может.
`ledger status` показывает эпоху и число записей audit.

## Отчётность и мониторинг токенов: `dispatch telemetry` {#dispatch-telemetry}

```bash
python .harness/orchestration/coordinator.py --repo . dispatch telemetry --file telemetry.json
```

Команда записывает в audit trail batch метрики, которые наблюдал источник (сессия worker или
coordinator): `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
`max_context_tokens`, `tool_calls`, `tool_output_bytes`, `poll_turns`, `restart_reason`,
`recorded_at`. Если провайдер не дал поле, оно остаётся `null`, а не оценочным нулём. Команда
работает только с данными: она пишет запись телеметрии и не может изменить состояние роли,
планирование, approvals или выбор модели.

В **возвращаемом значении** (не в сохранённой записи ledger) команда добавляет
`context_advisory: {"level": "ok"|"warn"|"over", "limit", "warn_at", "observed"}`. Это
рекомендательная оценка `max_context_tokens` относительно порога
`adaptive_continuation_policy.context_limit` из `.harness/orchestration.json` проекта. Долю порога
для предупреждения задаёт `adaptive_continuation_policy.context_warn_ratio` (доля от
`context_limit`, по умолчанию `0.8`; `warn_at = round(context_limit * context_warn_ratio)`).
`level` равен `"ok"`, пока `observed` ниже `warn_at` или отсутствует, `"warn"` в диапазоне
`[warn_at, context_limit)` и `"over"` от `context_limit` и выше. Оценка checkpoint автоматически не
запускает. Решение о checkpoint принимает coordinator, как и для любого другого сигнала, кроме
auto-resume после 429 (см. [«Checkpoint и новая worker session»](#checkpoint-worker-session) ниже).
Baseline из `playbook.md` («Baseline metrics») так же остаётся ориентиром, а не скрытым лимитом.

## Checkpoint и новая worker session {#checkpoint-worker-session}

Write-роль (developer, database-migrations, messaging-integration, conflict-resolver) может
растянуть один dispatch на несколько worker session, если весь TDD-цикл в одной сессии раздувает
её контекст. Read-only роль (architect, verification, qa, code-review) так не может: попытку
checkpoint для неё coordinator сразу отклоняет.

Вместо completion report текущая worker session записывает промежуточный checkpoint. Это отдельная
запись ledger с хэшем, которую нельзя перепутать с отчётом:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch checkpoint \
  --file checkpoint.json
```

`checkpoint.json` содержит ровно эти поля:

- `dispatch_id`;
- `commit_sha`;
- `changed_files`;
- `remaining_definition_of_done`: подмножество DoD утверждённого dispatch;
- `passing_checks` в формате `checks_run` completion report, команды из утверждённых
  `verification_commands`;
- `risks`;
- `blockers`;
- `context_package_id`: ссылка на последний Context Package, зарегистрированный для batch, или
  литерал `not applicable — no context package registered`, если пакета пока нет.

Других полей нет: ни сырой истории чата, ни логов прежних неудачных попыток. Для `checkpoint`
нужен уже подтверждённый self-report. Команда переводит dispatch-status в `checkpointed` и не
трогает enum outcome (`completed`/`blocked`/`failed`). Этот enum есть только у completion report.

Новую worker session для того же dispatch ID запускает `dispatch resume`. Авторизация зависит от
того, почему закончилась прежняя сессия:

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

`--termination-reason`, распознанный как rate limit (`rate_limit`/`rate-limit`/`429`), разрешает
новую сессию автоматически, без нового решения человека или coordinator. Любую другую причину,
включая отсутствующую или нераспознанную, coordinator считает планируемым trigger. Поэтому по
умолчанию он требует approval, а не пропускает его:

- `--trigger` обязателен. Планируемые trigger: `context-limit`, `tdd-cycles`, `failure-log`,
  `vertical-slice` и `human-decision` (ответ человека resolver, см.
  [«Публикация и PR»](publish.md#integration-accounting-publish)). Отдельный trigger
  `startup-failure` работает по своим правилам (см. [«Восстановление»](recovery.md#_8)).
- Для `context-limit`, `tdd-cycles` и `failure-log` значение `--measured-value` должно быть не меньше
  порога `adaptive_continuation_policy` (`context_limit`, `tdd_cycle_count`, `failure_log_bytes`)
  из `.harness/orchestration.json`. Без явной конфигурации действуют документированные значения по
  умолчанию (150000 / 3 / 20000), заданные в одном месте.
- `--file` должен содержать JSON с полями `dispatch_id`, `remaining_definition_of_done`, `risks` и
  `dependencies`. `remaining_definition_of_done` и `risks` должны в точности совпадать с последним
  checkpoint, а `dependencies` с dispatch. `blockers` в сравнение не входят: их формулировка может
  меняться между сессиями, хотя scope, DoD, risks и dependencies не менялись. Расхождение значит,
  что они действительно изменились. Тогда coordinator обязан закрыть текущий dispatch и открыть
  новый через обычный approval, а не продолжать этот.
- Авторизация записывается в те же `coordinator_decisions`, что и
  accept/retry/block/fail/abandon/cancel. Новый тип записи не вводится.

`resume` принимает только dispatch в состоянии `checkpointed`, возвращает его в `dispatched` и
сбрасывает прежний model self-report. Поэтому новая сессия должна заново пройти
`dispatch self-report` и `dispatch heartbeat`, как при первом контакте, прежде чем coordinator
примет следующий checkpoint или completion report. Цикл идёт на одном dispatch ID: checkpoint,
затем `dispatch resume`, затем новые self-report и heartbeat, в итоге один completion report.

Обновление установленного runtime не меняет runtime snapshot активного batch. Если в старом
snapshot есть ошибка continuation, сохраните checkpoint и историю Git, затем выберите штатный
маршрут восстановления на исправленном runtime с новым approval. Новый batch должен закрепить
исходную integration base, полный DoD и план коммитов и сохранённый HEAD writer. Review и QA
проверяют весь итоговый candidate. Записанные brief, reports и runtime snapshots старого batch
остаются audit evidence.
