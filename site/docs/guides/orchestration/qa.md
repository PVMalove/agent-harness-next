# Чистый QA

QA проверяет закреплённый candidate в чистой среде. Сначала отличите ошибку подготовки среды от дефекта проекта, затем выбирайте повтор или возврат к developer.

[Обзор оркестрации](../../backend-orchestration.md)

## Clean-room QA lane {#clean-room-qa-lane}

Одобренный `qa` dispatch coordinator выполняет сам, во временном Git worktree, отсоединённом ровно
на `candidate_commit`. Команды он берёт дословно из `verification_commands` неизменяемого brief.
Если HEAD не совпадает или worktree грязный, проверка останавливается. Запуск не передаётся
runtime adapter:

```bash
python .harness/orchestration/coordinator.py --repo . qa run \
  --dispatch <qa-dispatch-id> --lease-seconds 1800
```

В репозитории одна FIFO-очередь тяжёлых проверок. Если она занята, команда сохраняет запрос и
возвращает `state: queued` с позицией. Повторный вызов для того же dispatch запустит проверку,
только когда запрос станет первым. Состояние очереди и текущего владельца можно посмотреть без
запуска gate:

```bash
python .harness/orchestration/coordinator.py --repo . qa status
```

В эпохе runtime store lease содержит идентичность процесса владельца, fencing token и время
heartbeat. После истечения срока следующий `qa run` может снять lease только того владельца, чью
смерть доказал runtime (`owner-dead`). Живой владелец или владелец, которого нельзя проверить, не
считается завершившим работу. В файловой эпохе просроченный lease требует ручного решения.

Для ручного восстановления сначала проверьте владельца через `qa status`. Затем вызовите
`qa clear-stale-lease` с ожидаемыми host, PID и сроком, подтверждением и причиной:

```bash
python .harness/orchestration/coordinator.py --repo . qa clear-stale-lease \
  --expected-host <host> --expected-pid <pid> --expected-expiry <ISO-8601> \
  --approved-by 'имя coordinator-а' --approved-at <approval-time-utc> \
  --reason 'проверено, что владелец больше не выполняется'
```

Если lease принадлежит dispatch, который остался в `working` без записанного report, команда
возвращает его в `approved`. Поле `restored_dispatch_state` в ответе и в записи восстановления
равно `approved` или `null`.

### Подготовка окружения и категории провала

Необязательное поле `qa_preparation` в `.harness/orchestration.json` задаёт команды подготовки
окружения (например, `uv sync --locked`). Необязательные `qa_environment_probes` (например,
проверка доступности реестра пакетов) и `qa_project_file_checks` (например, `uv lock --check`)
дают независимые факты. Их команды выполняются в том же checkout и только после упавшей подготовки.
`qa run` выполняет подготовку, затем `verification_commands` в одном чистом checkout точного
`candidate_commit` и останавливается на первой упавшей команде. Без `qa_preparation` (только с
`verification_commands`) поведение и форма report не меняются.

Report и артефакт с подготовкой содержат `qa_stages`. Для каждой выполненной команды там есть
стадия (`preparation`, `environment-probe`, `project-file-check` или `gate`), точная команда,
результат, exit code и очищенная от секретов диагностика упавшей команды. Ещё они содержат
`failed_stage` и `code_checks_started` (`started`, `not_started` или `unknown`). Coordinator сверяет
записи с неизменяемым артефактом: команды и exit codes должны совпасть с его блоками. Если
подготовка упала, команды gate попадают в `checks_run` как `not_run`. Это не выдуманная упавшая
проверка кода.

Причину провала подготовки подтверждают только независимые факты. Ни exit code, ни ключевое слово
в логе не решают в одиночку, и сама стадия подготовки инфраструктурную причину не доказывает.
Сигнатуры лога только подкрепляют диагноз. Без настроенных проб и проверок файлов проекта
инфраструктурная причина не подтверждается, и провал требует разбора (triage):

| Диагноз | Подтверждение | Report | Маршрут `batch decide --decision retry` |
| --- | --- | --- | --- |
| `infrastructure` | упала проба окружения, а все проверки файлов проекта прошли (и задана хотя бы одна); в выводе нет сигнатуры дефекта проекта; код не проверялся | `blocked`, «код не проверен» | `same-candidate-rerun` без `--reason-category`: новый qa dispatch на тот же SHA, бюджет developer retry не тратится |
| `project-defect` | упала проверка файлов проекта (проба при этом не упала) или есть сигнатура дефекта (например, несовместимый lock-файл), которая согласуется с отслеживаемым манифестом или lock-файлом из вывода; проверки файлов проекта её не опровергают | `failed` | `developer-retry`, причина `code` |
| `unknown` | пробы и проверки не заданы, не подтверждают причину или противоречат друг другу (например, упали и проба, и проверка) | `blocked`, нужен triage | `retry` без `--reason-category` отклоняется; coordinator называет причину или блокирует batch |

Провал самого gate остаётся обычным провалом проверок кода и идёт прежним маршрутом
`developer-retry`.

**Восстановление на том же SHA.** Когда окружение готово, coordinator выполняет
`batch decide --decision retry`. Затем он создаёт новый qa dispatch для того же `candidate_commit`
с теми же командами и границами. Прежние brief, report, артефакт и approval остаются как audit
evidence. Сбой подготовки или записи report не оставляет lease, запись очереди или состояние
`working`, поэтому тот же approved dispatch можно запустить заново без правки ledger и без нового
batch. Исключение: ledger занят другой операцией дольше 30 секунд (см.
[«Занятый ledger»](operations.md#ledger-report-complete-ledger-release-lock)).

### Ограниченные инфраструктурные повторы

Проект может отдельно разрешить повтор по политике после подтверждённого инфраструктурного отказа:

```json
{
  "infrastructure_retry_policy": {"enabled": true},
  "attention_policy": {"max_infrastructure_retries": 2}
}
```

Без этого opt-in действуют ручные gates. Политика не выдаёт права платформы, не подменяет нативное
approval и не принимает упавший QA. Бюджет берётся из `attention_policy.max_infrastructure_retries`:
по умолчанию 2, а `0` запрещает повторы. Developer retry budget не расходуется. Opt-in, бюджет и
команды preparation, probe и project-file-check coordinator сохраняет в
`orchestration_policy.infrastructure_retry` и связывает с approval digest. Старые brief без этой
секции остаются в ручном режиме. Правка живого конфига не включает повтор для старого approval и не
меняет команды уже утверждённого brief.

После провала QA preparation политика продолжает только маршрут `same-candidate-rerun`, и только при
подтверждённом `infrastructure`, `code_checks_started: not_started` и неизменном SHA. Перед решением
coordinator проверяет доступ и заново выполняет закреплённые пробы окружения и проверки файлов
проекта в чистом checkout. Если среда ещё не готова, новый dispatch он не создаёт. Когда причина
устранена в прежних границах, выполните:

```bash
python .harness/orchestration/coordinator.py --repo . report complete --dispatch <qa-dispatch-id>
```

Каждый состоявшийся повтор получает новый неизменяемый dispatch и источник решения
`policy:infrastructure-retry`, а прежние brief, report и артефакт сохраняются. Повторный
`report complete` возвращает уже созданный dispatch. Если команду прервали после решения, повтор
доделывает недостающий шаг. Команда не запускает worker и не открывает PR.

Отказ доступа до запуска QA или publish не создаёт report о проверке кода. Для dispatch с opt-in
coordinator сохраняет структурированную попытку доступа и checksum. Когда ресурс снова доступен,
запросите проверку и новое задание, утверждённое политикой:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch retry-infrastructure --dispatch <dispatch-id>
```

Этот путь открыт только для отказа, который подтвердила проба (`denied`), и при свежем
подтверждении готовности. Coordinator отменяет старый неотправленный brief и записывает причину в
audit. Новый brief сохраняет этап, SHA, команды, runtime, model, effort, scope и доступ. Повтор
команды возвращает прежний результат. Remote для publish тоже должен остаться прежним. Затем
запустите `qa run` или `dispatch publish` с новым ID. Неподтверждённый сетевой отказ
(`unverified`), неподдерживаемый режим (`unsupported`), отказ самим планом и произвольная ошибка Git
требуют ручного разбора. Git-операции без утверждённого dispatch идут ручным маршрутом: opt-in не
разрешает произвольную команду Git.

Смена candidate, команд или доступа, неизвестная причина и исчерпанный бюджет останавливают
политику и поднимают `needs_attention`. Attention снимает человек. Это не увеличивает бюджет и не
разрешает изменённый контракт. Новые требования проходят обычные proposal и approval. Не
редактируйте ledger и не переписывайте candidate ради инфраструктурного восстановления.

### Native smoke {#native-smoke}

Поддержку проверяют только в реальной coding-среде. Создайте отдельный smoke-проект, локальный bare
remote и новый пустой cache внутри разрешённого shared storage. Запишите полный SHA харнесса и
candidate, чистоту checkout и точные команды preparation и gate. Через публичный CLI пройдите
approval batch и dispatch, нативный handoff роли, preparation и clean-room QA, publish принятого SHA.
Затем подтвердите отказ доступа, отсутствие retry до готовности, ограниченный повтор и сохранность
evidence. Динамические ID и digest берите из JSON-вывода команд. Нативное approval принимает
coding-runtime по действующей политике пользователя, и orchestration policy его не заменяет.

Не меняйте machine- и global-профили, не очищайте пользовательский cache, не создавайте PR и не
делайте merge. Для внешнего push нужно разрешение на конкретный smoke remote. Push в локальный bare
remote проверяет Git и publish, но не внешний доступ к Git.

Первые шаги из source checkout (пути и фактическую модель задаёт человек):

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

До этого локальный `origin` должен содержать `integration/smoke`, а checkout должен стоять на
чистой issue-ветке. Создайте отслеживаемый `smoke.py`, manifest и lock и настоящие команды проекта:
подготовку, независимую пробу сети и cache, offline-проверку файлов. Настройте opt-in до proposal,
создайте отдельный cache и убедитесь, что он пуст. Для QA подходит, например,
`UV_CACHE_DIR=<новый-cache> UV_PROJECT_ENVIRONMENT=.harness/.venv uv sync --locked`, а developer
использует другой cache. Runner выбирает Python из `.harness/.venv` текущего clean-room checkout.
Команда gate должна проверять изменение в `smoke.py`, а также то, что `sys.prefix` и
импортируемый пакет находятся в этом checkout. Сохраните фактический `executed_command` из stage
evidence.

Выберите transport до создания batch. Для отдельной нативной CLI-сессии задайте
`assignment_plans.<role>.transport: "external"` и настоящие `runtimes`, `provider_profiles` и
команды проверок. В заданном вручную assignment plan обязательны architect, developer, code-review
и qa, и health проверяет этот набор. Подготовьте adapter проекта. Он получает
`dispatch --repo --brief`, запускает coding CLI в approved worktree с моделью и effort из brief,
возвращается после запуска worker и не управляет ledger. При `in-process` роль запускают как
субагента текущей coordinator-сессии. Отдельную CLI-сессию таким субагентом считать нельзя.

Возьмите `batch_id` из JSON `batch create`. Затем человек или назначенный им coordinator выполняет
`batch approve` с `--approved-by` и фактическим `--approved-at`. В том же smoke checkout:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch propose \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT"
python .harness/orchestration/coordinator.py --repo . dispatch create \
  --batch "$BATCH" --role architect --runtime "$RUNTIME" --model "$MODEL" --effort "$EFFORT" \
  --transition-digest "$DIGEST" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"
python .harness/orchestration/coordinator.py --repo . dispatch send --dispatch "$DISPATCH"
```

Для `external` последняя команда указывает настоящий adapter:

```bash
python .harness/orchestration/coordinator.py --repo . dispatch send \
  --dispatch "$DISPATCH" --adapter "$SMOKE_REPO/scripts/native_codex_adapter.py"
```

`DIGEST` берётся из просмотренного proposal, `DISPATCH` из вывода create. Handoff выводит путь
brief, путь report staging и ожидаемую модель. При `external` роль запускает adapter, при
`in-process` её запускает coordinator в своей coding-сессии. Роль выполняет
`dispatch self-report --dispatch "$DISPATCH" --model "$ACTUAL_MODEL" --worktree "$SMOKE_REPO"`,
затем `dispatch heartbeat --dispatch "$DISPATCH"` и настоящий `report submit --file <report>`.
Architect не меняет код и не запускает полный gate. Проверив report, coordinator сохраняет план
architect как `{"commit_plan": [...]}` в `$COMMIT_PLAN` и выполняет
`batch decide --batch "$BATCH" --decision accept --commit-plan-file "$COMMIT_PLAN" --approved-by "$APPROVER" --approved-at "$APPROVED_AT"`.
Повторите proposal, create и send для developer: его коммит и report задают полный candidate SHA.
`risk assess --batch "$BATCH" --candidate-commit "$SHA" --changed-file smoke.py` определяет, нужен
ли review. Обязательный review пропустить нельзя, и его send использует checkout точного SHA.

Для нового qa proposal и create добавьте `--candidate-commit "$SHA"` и запускайте `qa run`, а не
`dispatch send`. Сымитируйте отказ записи только в созданном cache (в POSIX-фикстуре:
`chmod u-w "$SMOKE_CACHE"`). Сохраните `qa_stages` и отказ `report complete` до готовности среды.
Верните права: `chmod u+w "$SMOKE_CACHE"`. `report complete` должен вернуть новый ID на тот же SHA,
а повторный вызов (replay) тот же ID. Запустите `qa run` с новым ID и вручную примите только
успешный report.

Для publish proposal и create задайте `--role developer --purpose publish --candidate-commit "$SHA"`.
В POSIX-фикстуре метаданных запретите запись только в `.git` smoke-проекта. Сохраните отказ
`dispatch publish --dispatch "$PUBLISH" --remote origin` и отказ `dispatch retry-infrastructure` до
восстановления. После восстановления получите новый ID и повторите publish в тот же `origin`.
`git ls-remote --heads origin refs/heads/feature/issue-619-native-smoke` должен вернуть ровно
`$SHA`. Если сценарий прервался, верните права на запись только своей фикстуре. Неполный или иной
диагноз считается blocker, а не разрешением продолжать сценарий. Авторизованный `inherit` для
операций coordinator не доказывает, что права worker применены. Запускайте только режим, который
подтверждает действующий extension.

В evidence сохраните runtime, версию, transport и режим, полные SHA, нативные параметры и
доказательство фактического доступа, команды с exit codes, готовность среды, ID dispatch и
checksum. Секреты из evidence удалите заранее. Health-конфиг и checkout attestation сетевые права не
доказывают.

Проверки этой реализации покрывают настоящие Git и ledger, preparation и gate, повтор на том же
SHA, бюджет, attention, отказ записи метаданных и локальный publish. Это контролируемые проверки:
они не доказывают нативный handoff и всю матрицу runtime. Для нативного handoff с заданным планом
доступа нужна реализация `extensions.runtime_access`, которая наблюдает и применяет фактический
доступ worker. `none` такого доказательства не даёт, а явно выбранный непроверенный режим
блокируется. `legacy-inherit` сохраняет прежнюю передачу задания, но права worker не подтверждает.

Проверенный 2026-10-08 native smoke установлен из харнесса
`cca45e172c7b3685c012e7e6c077356d6cbd6722`: Linux, Codex CLI 0.160.1, настоящий adapter проекта и
две отдельные роли `architect` и `developer`. Candidate `1dba1785bc809971981129c747e85bffd9b29c51`
прошёл preparation и gate в новом clean-room checkout с пустым QA cache, свежей `.harness/.venv` и
скачанными зависимостями и был опубликован в локальный bare remote. Отказ cache и отказ записи в
`.git` остановили продолжение до готовности среды. Восстановление израсходовало два общих
infrastructure retry, replay сохранил ID преемников, а прежние записи сохранили checksum. Batch
завершён через публичный CLI. Это подтверждает только границы из таблицы ниже.

Таблица описывает исторический smoke-прогон указанных версий и не подтверждает совместимость CLI,
установленного сейчас.

| Runtime / transport / режим | Результат native smoke | Граница evidence |
| --- | --- | --- |
| Codex CLI 0.160.1 / `external` / worker `legacy-inherit` | PASS: реальные роли, self-report, heartbeat, commit и report | Нативный CLI работал с `workspace-write`; заданный план доступа worker не проверен |
| Coordinator / `inherit` / QA и publish | PASS: свежие зависимости, gate на точном SHA, отказ cache и Git, готовность среды, бюджет и replay | Операции шли в одной разрешённой среде coordinator; publish только в локальный bare remote |
| Worker с заданным `inherit`, `sandbox` или `unsandboxed` / `runtime_access: none` | Blocker | Нужен действующий extension, который доказывает наблюдение и применение плана; attestation его не заменяет |
| `in-process`, Claude и другие runtime, внешний Git push | Не проверено | Для каждого сочетания нужен отдельный реальный запуск |

CLI flags, выполнение coordinator на хосте и POSIX-фикстура с `chmod` не доказывают всю матрицу
прав. Для другого runtime, transport или заданного режима нужен собственный нативный evidence.

### Отчёт QA и переход к PR {#qa-report-pr}

После выполнения coordinator создаёт неизменяемый completion report с командами, exit codes и
кратким очищенным evidence. Полный очищенный stdout и stderr хранится вне Git в
`.harness/orchestration/state/qa-artifacts/<sha256>.log`. Report ссылается на этот путь и checksum.
Провал gate остаётся QA finding и требует нового одобренного developer dispatch. Runner не правит
код и не перезапускает проверку сам.

После принятого QA evidence coordinator создаёт, но не запускает publish dispatch для того же
candidate SHA. Этот SHA пушит только developer publish. Ни QA, ни review, ни adapter не создают и
не мержат PR. После publish человек сам запускает `/to-pull-requests <ticket>`. Скилл проверяет
принятое QA evidence текущего SHA и ведёт обычный ручной PR workflow без повторного тяжёлого gate.
Хук `require-qa-gate.sh` сам принимает то же evidence. Повторный gate и маркер не нужны, если
checkout чистый, `HEAD` равен принятому `candidate_commit`, а каждая команда `qa_gate_commands`
имеет `pass`. Иначе действует прежний путь с маркером.

Обычная точка входа: `/implement <ticket>`. Эта сессия сама становится coordinator и ведёт
описанный цикл. Она проводит тикет через пять стадий (architect, developer, code-review, qa,
publish), запрашивает approval по действующей `approval_policy` и следит за heartbeat каждого
dispatch. Сессия доводит batch одного тикета до терминального состояния и только потом берёт
следующий. Ручной запуск по этому руководству тоже работает. Запрос для управляющей сессии тогда
может выглядеть так:

```text
Выступи coordinator-ом backend batch для issue #123. Прочитай .harness/orchestration/roles/
и .harness/orchestration/playbook.md. Не запускай роль до моего явного approval. Предложи
explicit allowed paths, последовательность ролей, immutable brief и требуемые risk gates;
не меняй protected или integration branch.
```
