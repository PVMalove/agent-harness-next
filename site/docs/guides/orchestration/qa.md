# Чистый QA

QA проверяет закреплённый candidate в чистой среде. Сначала отличи ошибку подготовки среды от дефекта проекта, затем выбирай повтор или возврат к developer.

[Обзор оркестрации](../../backend-orchestration.md)

## Clean-room QA lane {#clean-room-qa-lane}

Coordinator сам выполняет одобренный `qa` dispatch в отдельном temporary Git worktree,
отсоединённом ровно на `candidate_commit`. Команды он берёт буквально из `verification_commands`
immutable brief, а несовпадение HEAD или грязный worktree останавливает проверку. Запуск не
передают runtime adapter:

```bash
python .harness/orchestration/coordinator.py --repo . qa run \
  --dispatch <qa-dispatch-id> --lease-seconds 1800
```

В репозитории есть одна FIFO-полоса тяжёлых проверок. Если она занята, команда сохраняет
запрос и возвращает `state: queued` с позицией, а повторный вызов для того же dispatch запустит его,
только когда он станет первым. Состояние и текущий owner видны без запуска gate:

```bash
python .harness/orchestration/coordinator.py --repo . qa status
```

В эпохе runtime store lease содержит идентичность процесса владельца, fencing token и время
heartbeat. После истечения срока следующий `qa run` может снять lease только владельца,
чья смерть доказана runtime (`owner-dead`). Живой или недоступный для проверки владелец
не считается завершившим работу. В файловой эпохе просроченный lease требует ручного решения.

Для ручного восстановления сначала проверь владельца через `qa status`, затем используй
`qa clear-stale-lease` с ожидаемыми host/PID/expiry, подтверждением и причиной:

```bash
python .harness/orchestration/coordinator.py --repo . qa clear-stale-lease \
  --expected-host <host> --expected-pid <pid> --expected-expiry <ISO-8601> \
  --approved-by 'имя coordinator-а' --approved-at <approval-time-utc> \
  --reason 'проверено, что владелец больше не выполняется'
```

Если lease принадлежит dispatch, который остался `working` без записанного report, команда
возвращает его в `approved`. Поле `restored_dispatch_state` в ответе и в записи восстановления
равно `approved` или `null`.

### Подготовка окружения и категории провала

Необязательный `qa_preparation` в `.harness/orchestration.json` задаёт команды подготовки окружения
(например, `uv sync --locked`). Необязательные `qa_environment_probes` (например, проверка
доступности реестра пакетов) и `qa_project_file_checks` (например, `uv lock --check`) задают
независимые факты. Их команды выполняются в том же checkout только после упавшей подготовки.
`qa run` выполняет их и затем `verification_commands` в одном чистом checkout точного
`candidate_commit`. Он останавливается на первой упавшей команде. Без `qa_preparation`
(конфигурации только с `verification_commands`) поведение и форма report не меняются.

Report и артефакт с подготовкой несут `qa_stages`. На каждую выполненную команду там есть стадия
(`preparation`, `environment-probe`, `project-file-check` или `gate`), точная команда, результат,
exit code и санитизированная диагностика упавшей команды. Также они несут `failed_stage` и
`code_checks_started` (`started`, `not_started` или `unknown`). Записи сверяются с неизменяемым
артефактом: команды и exit codes должны совпасть с его блоками. Если подготовка упала, команды gate
в `checks_run` записываются как `not_run`. Это не выдуманная упавшая проверка кода.

Причину провала подготовки подтверждают независимые факты: ни exit code, ни ключевое слово в логе
не решают в одиночку, а сама стадия подготовки инфраструктурную причину не доказывает. Сигнатуры
лога лишь подкрепляют диагноз, и без настроенных проб и проверок файлов проекта инфраструктурная
причина не подтверждается. Тогда провал требует triage:

| Диагноз | Подтверждение | Report | Маршрут `batch decide --decision retry` |
| --- | --- | --- | --- |
| `infrastructure` | упала проба окружения, а все проверки файлов проекта прошли (и их задано не меньше одной); в выводе нет сигнатуры дефекта проекта; код не проверялся | `blocked`, «код не проверен» | `same-candidate-rerun` без `--reason-category`: новый qa dispatch на тот же SHA, бюджет developer retry не тратится |
| `project-defect` | упала проверка файлов проекта (проба при этом не упала), либо сигнатура дефекта (например, несовместимый lock-файл), согласованная с отслеживаемым манифестом или lock-файлом, названным в выводе; проверки файлов проекта её не опровергают | `failed` | `developer-retry`, причина `code` |
| `unknown` | пробы и проверки не заданы, не подтверждают причину или противоречат друг другу (например, упали и проба, и проверка) | `blocked`, нужен triage | `retry` без `--reason-category` отклоняется; coordinator называет причину или блокирует batch |

Провал самого gate остаётся обычным провалом проверок кода и идёт по прежнему маршруту
`developer-retry`.

**Восстановление на том же SHA.** После подтверждения готовности окружения coordinator выполняет
`batch decide --decision retry`. Затем он создаёт новый qa dispatch для того же `candidate_commit` с
теми же командами и границами. Прежние brief, report, артефакт и approval сохраняются как audit
evidence. Сбой подготовки или записи report не оставляет lease, запись очереди или состояние
`working`: тот же approved dispatch можно запустить заново без правки ledger и без нового batch.
Исключение — ledger, занятый другой операцией дольше 30 секунд (см. [«Занятый ledger»](operations.md#ledger-report-complete-ledger-release-lock)).

### Ограниченные инфраструктурные повторы

Проект может отдельно разрешить policy-повтор подтверждённого инфраструктурного отказа:

```json
{
  "infrastructure_retry_policy": {"enabled": true},
  "attention_policy": {"max_infrastructure_retries": 2}
}
```

Без opt-in действуют ручные gates. Политика не выдаёт права платформы, не подменяет native
approval и не принимает failed QA. Бюджет использует существующий
`attention_policy.max_infrastructure_retries`: default — 2, а `0` запрещает повторы.
Developer retry budget не расходуется. Opt-in, бюджет и команды preparation/probe/project-file-check
сохраняются в `orchestration_policy.infrastructure_retry` и связаны с approval digest.
Исторические briefs без этой секции остаются в ручном режиме. Правка live config не включает
повтор для старого approval и не меняет команды нового уже утверждённого brief.

После QA preparation failure policy продолжает только маршрут `same-candidate-rerun` с
подтверждённым `infrastructure`, `code_checks_started: not_started` и неизменным SHA. Перед
решением coordinator проверяет доступ и заново выполняет закреплённые независимые пробы окружения и
проверки файлов проекта в чистом checkout; если среда ещё не готова, новый dispatch он не создаёт. После
устранения причины в прежних границах выполните:

```bash
python .harness/orchestration/coordinator.py --repo . report complete --dispatch <qa-dispatch-id>
```

Каждый состоявшийся повтор получает новый immutable dispatch и источник решения
`policy:infrastructure-retry`, а прежние brief/report/artifact сохраняются. Повтор `report complete`
возвращает уже созданный dispatch, а прерывание после решения докатывает недостающий шаг. Команда
не запускает worker и не открывает PR.

Отказ доступа до запуска QA или publish не создаёт report о проверке кода. Для opt-in dispatch
coordinator сохраняет structured access attempt и checksum. Когда тот же ресурс стал доступен,
запросите проверку и новое policy-утверждённое задание:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch retry-infrastructure --dispatch <dispatch-id>
```

Этот путь разрешён только для отказа, подтверждённого probe (`denied`), при свежем подтверждении
готовности. Coordinator отменяет старый неотправленный brief и записывает причину в audit, а новый brief сохраняет этап, SHA, команды,
runtime/model/effort, scope и доступ; повтор команды возвращает прежний результат. Publish remote
тоже должен остаться тем же. Затем запускайте `qa run` или `dispatch publish` с новым ID.
Неподтверждённый сетевой отказ (`unverified`), неподдержанный режим (`unsupported`), отказ самим
планом и произвольная ошибка Git требуют ручного разбора. Git-операции без утверждённого dispatch
сохраняют ручной маршрут: opt-in не разрешает произвольную команду Git.

Смена candidate, команд или доступа, неизвестная причина и исчерпание бюджета останавливают
policy и поднимают `needs_attention`. Снимает attention человек. Это не увеличивает бюджет
и не разрешает изменённый контракт. Новые требования проходят обычные proposal и approval.
Не редактируйте ledger и не переписывайте candidate ради инфраструктурного восстановления.

**Native smoke.** Проверка поддержки требует реальной coding-среды. Создайте отдельный smoke-проект,
локальный bare remote и новый пустой cache внутри разрешённого shared storage. Зафиксируйте полный
SHA harness и candidate, чистоту checkout и точные preparation/gate команды. Через публичный CLI
пройдите batch/dispatch approval, native handoff роли, preparation/clean-room QA и publish
accepted SHA, а затем подтвердите отказ доступа, отсутствие retry до готовности, ограниченный
повтор и сохранение evidence. Dynamic IDs и digest берите из JSON команд. Native approval принимает
coding-runtime согласно действующей политике пользователя, и orchestration policy её не заменяет.
Не меняйте machine/global профили, не очищайте пользовательский cache, не создавайте PR и не
выполняйте merge. Внешний push требует разрешения на конкретный smoke remote, а push в локальный
bare remote проверяет Git/publish, но не внешний Git-доступ.

Первые шаги из source checkout (пути и actual model задаёт человек):

```bash
python harness/bin/harness.py init "$SMOKE_REPO" --capability backend-orchestration \
  --base-branch integration/smoke --language ru --tracker-type local \
  --qa-gate-command "$SMOKE_GATE"
python "$SMOKE_REPO/.harness/orchestration/coordinator.py" --repo "$SMOKE_REPO" batch create \
  --ticket local:619 --branch feature/issue-619-native-smoke --worktree "$SMOKE_REPO" \
  --integration-ref integration/smoke --allowed-path smoke.py --expected-file smoke.py \
  --expected-service smoke --expected-changed-lines 2 \
  --goal 'Change answer to 42 and verify the native smoke' \
  --definition-of-done 'answer returns 42; exact candidate passes QA and local publish' \
  --prohibited-change 'global config, other projects, secrets, PR, merge'
```

Перед этим локальный `origin` должен содержать `integration/smoke`, а checkout — чистую issue branch.
Создайте tracked `smoke.py`, manifest/lock и реальные project-owned команды подготовки, независимой
пробы сети/cache и offline проверки файлов. Настройте opt-in до proposal, создайте отдельный cache и
зафиксируйте его пустоту. Для QA используется, например,
`UV_CACHE_DIR=<новый-cache> UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`, а developer
использует другой cache. Runner выбирает Python из `.harness/.venv` текущего clean-room checkout.
Команда gate должна проверять фактическое изменение в `smoke.py`, а также расположение `sys.prefix`
и импортируемого пакета в этом checkout. Сохраните фактический `executed_command` из stage evidence.

Выберите transport до создания batch. Для отдельной native CLI-сессии задайте
`assignment_plans.<role>.transport: "external"` и реальные `runtimes`, `provider_profiles` и команды
проверок. В authored assignment plan обязательны architect, developer, code-review и qa, и health
проверяет этот набор. Подготовьте project-owned adapter, который получает `dispatch --repo --brief` и
действительно запускает coding CLI в approved worktree с моделью и effort из brief; он
возвращается после запуска worker и не управляет ledger. Для `in-process` роль запускают как
субагента текущей coordinator-сессии, и отдельную CLI-сессию таким субагентом считать нельзя.

Из JSON `batch create` возьмите `batch_id`, после чего человек или явно назначенный им coordinator
выполняет `batch approve` с `--approved-by` и фактическим `--approved-at`. В том же smoke checkout:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT"
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT" \
  --transition-digest "$DIGEST" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"
python .harness/orchestration/coordinator.py --repo . dispatch send --dispatch "$DISPATCH"
```

Для выбранного `external` последняя команда содержит реальный adapter:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch "$DISPATCH" --adapter "$SMOKE_REPO/scripts/native_codex_adapter.py"
```

`DIGEST` берётся из просмотренного proposal, `DISPATCH` — из create. Handoff выводит путь brief,
report staging path и ожидаемую модель. При `external` роль запускает adapter, при `in-process` —
coordinator в своей coding-сессии. Роль выполняет
`dispatch self-report --dispatch "$DISPATCH" --model "$ACTUAL_MODEL" --worktree "$SMOKE_REPO"`,
затем `dispatch heartbeat --dispatch "$DISPATCH"` и настоящий `report submit --file <report>`.
Architect не меняет код и не запускает full gate. После проверки report coordinator сохраняет
его план как `{"commit_plan": [...]}` в `$COMMIT_PLAN` и выполняет
`batch decide --batch "$BATCH" --decision accept --commit-plan-file "$COMMIT_PLAN" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"`.
Повторите proposal/create/send для developer: его commit/report задают полный candidate SHA.
`risk assess --batch "$BATCH" --candidate-commit "$SHA" --changed-file smoke.py` определяет,
нужен ли review, и требуемый review пропустить нельзя; его send использует checkout точного SHA.

Для нового qa proposal/create добавьте `--candidate-commit "$SHA"` и используйте `qa run`,
не `dispatch send`. Вызовите отказ записи только в созданном cache (в POSIX fixture —
`chmod u-w "$SMOKE_CACHE"`). Сохраните `qa_stages` и отказ `report complete` до готовности.
Восстановите `chmod u+w "$SMOKE_CACHE"`. `report complete` должен вернуть новый ID на тот же SHA,
а replay — тот же ID. Запустите `qa run` нового ID и вручную примите только успешный report.
Publish proposal/create задаёт `--role developer --purpose publish --candidate-commit "$SHA"`.
Для POSIX metadata fixture ограничьте запись только в smoke `.git`. Сохраните отказ
`dispatch publish --dispatch "$PUBLISH" --remote origin` и отказ `dispatch retry-infrastructure`
до восстановления. После восстановления получите новый ID и повторите publish в тот же `origin`.
`git ls-remote --heads origin refs/heads/feature/issue-619-native-smoke` должен вернуть ровно `$SHA`.
При прерывании восстановите write bit только своего fixture. Неполный или иной диагноз — blocker,
а не разрешение продолжать сценарий. Авторизованный inherit coordinator операций не доказывает
применение authored прав worker. Запускайте только режим, подтверждённый действующим extension.

В evidence сохраняйте runtime, версию, transport и режим, полные SHA, native параметры и proof
фактического доступа, команды с exit codes, readiness, dispatch IDs и checksum, предварительно
удалив secrets. Health-конфиг и checkout attestation сетевые права не доказывают.

Проверки этой реализации покрывают настоящие Git/ledger, preparation/gate, same-SHA retry,
budget, attention, metadata refusal и локальный publish. Это контролируемые проверки: они не
доказывают native handoff и всю runtime-матрицу. Для native handoff с authored планом доступа нужна
реализация `extensions.runtime_access`, которая наблюдает и применяет фактический доступ worker;
`none` такого proof не даёт, а явно выбранный непроверенный режим блокируется. `legacy-inherit`
сохраняет прежнюю передачу задания, но права worker не подтверждает.

Проверенный 2026-10-08 native smoke установлен из harness
`cca45e172c7b3685c012e7e6c077356d6cbd6722`: Linux, Codex CLI 0.160.1, настоящий project adapter и
две отдельные роли `architect`/`developer`. Candidate `1dba1785bc809971981129c747e85bffd9b29c51`
прошёл preparation и gate в новом clean-room checkout с пустым QA cache, свежей `.harness/.venv` и
скачанными зависимостями, после чего был опубликован в local bare remote. Отказ cache и отказ записи
`.git` остановили продолжение до readiness. Восстановление израсходовало два общих infrastructure
retry, replay сохранил successor IDs, а прежние records сохранили checksum. Batch завершён через
публичный CLI. Это подтверждает только границы из таблицы ниже.

Таблица фиксирует исторический smoke-прогон указанных версий и не подтверждает совместимость установленного сейчас CLI.

| Runtime / transport / режим | Результат native smoke | Граница evidence |
| --- | --- | --- |
| Codex CLI 0.160.1 / `external` / worker `legacy-inherit` | PASS: реальные роли, self-report, heartbeat, commit и report | Native CLI работал с `workspace-write`; authored worker access plan не проверен |
| Coordinator / `inherit` / QA и publish | PASS: fresh dependencies, exact-SHA gate, cache/Git denial, readiness, budget и replay | Фактические операции в одной разрешённой среде coordinator; publish только в local bare remote |
| Worker с authored `inherit`, `sandbox` или `unsandboxed` / `runtime_access: none` | Blocker | Нужен действующий extension с proof наблюдения и применения плана; attestation его не заменяет |
| `in-process`, Claude и другие runtime, внешний Git push | Не проверено | Для каждого сочетания нужен отдельный фактический запуск |

CLI flags, host execution coordinator и POSIX `chmod` fixture не доказывают всю permission-матрицу.
Для другого runtime, transport или authored режима поддержки требуют собственного native evidence.

После выполнения coordinator создаёт immutable completion report с командами, exit codes и кратким
санитизированным evidence. Полный санитизированный stdout/stderr сохраняется вне Git в
`.harness/orchestration/state/qa-artifacts/<sha256>.log`. Report ссылается на этот путь и checksum.
Провал gate остаётся QA finding и требует нового одобренного developer dispatch. Runner не правит
код и не перезапускает проверку самостоятельно.

После accepted QA evidence coordinator создаёт, но не запускает, publish dispatch для того же
candidate SHA. Этот SHA отправляет только developer publish, а ни QA, ни review, ни adapter не
создают и не мержат PR. После publish человек вручную запускает `/to-pull-requests <ticket>`: он
проверяет accepted QA evidence текущего SHA и ведёт обычный ручной PR workflow без повторного
тяжёлого gate. Хук `require-qa-gate.sh` принимает то же evidence сам, поэтому повторный gate и
маркер не нужны для чистого checkout с `HEAD`, равным accepted `candidate_commit`, и с `pass` по
каждой команде `qa_gate_commands`. Иначе остаётся прежний путь с маркером.

Обычная точка входа — `/implement <ticket>`. Эта сессия сама становится coordinator-ом и ведёт
описанный цикл. Она останавливается на пяти approval-гейтах (architect, developer, code-review, qa,
publish) и наблюдает за heartbeat каждого dispatch. Сессия доводит batch одного тикета до терминального
состояния и только потом берёт следующий. Ручной запуск по этому руководству тоже работает. Запрос
для управляющей сессии в этом случае может выглядеть так:

```text
Выступи coordinator-ом backend batch для issue #123. Прочитай .harness/orchestration/roles/
и .harness/orchestration/playbook.md. Не запускай роль до моего явного approval. Предложи
explicit allowed paths, последовательность ролей, immutable brief и требуемые risk gates;
не меняй protected или integration branch.
```
