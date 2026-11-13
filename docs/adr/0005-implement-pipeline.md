# Управляемый конвейер `/implement` и короткий маршрут `/fast-implement`

**Статус: ACCEPTED (2026-09-28). Частично заменён ADR 0012, ADR 0014 и ADR 0033.**

## Контекст системы

Один тикет должен пройти от принятого архитектурного решения до проверенного commit без потери
контекста между ролями. Изменение candidate, базы или условий проверки меняет смысл решения
оператора; разрешение должно быть привязано к конкретному переходу. Небольшая работа с заранее
ясным направлением может обходиться без полного ролевого конвейера.

## Действующий контракт

### Маршрут с coordinator

`/implement` обрабатывает один тикет и ведёт batch через `architect → developer → code-review →
qa → publish`. Перед `batch create` он проверяет тикет, блокеры, status, issue-ветку и
ограничения объёма; слишком крупный тикет возвращается на декомпозицию. Сессия coordinator не
пишет продуктовый код. `coordinator.py` запрещает developer-dispatch без принятого architect
report того же batch. Публикация завершённого batch не создаёт PR.

Перед handoff `dispatch preflight` проверяет проектный контракт. Context Builder детерминированно
собирает Context Package из закреплённых commit, отфильтрованных файлов и Repo Map. Пакет
регистрируется в ledger и повторно используется architect, developer и продолжениями того же
dispatch, пока candidate не изменился. Новый candidate для review получает новый общий пакет.
Immutable brief закрепляет package ID, scope, DoD, разрешённый model/effort, транспорт, зоны,
команды проверки и путь для отчёта. Writer brief также содержит упорядоченный commit plan;
completion report связывает каждый созданный commit с пунктом плана.

`dispatch propose` показывает decision packet и `transition_digest`. При явном approval
`dispatch create` сверяет digest с текущими данными ledger; изменённые candidate, scope,
Context Package или команды требуют нового предложения. Проект выбирает `manual_all`,
`low_risk`, `milestone` или `auto` policy: автоматическое принятие чистого отчёта возможно только
там, где это допускает policy. Кроме `auto`, риск, finding, сбой и publish сохраняют
соответствующие ручные решения. Policy `auto` описывает
`harness/orchestration/orchestration.schema.json`; PR и в ней открывает только человек.
In-process и external transport исполняют один brief и возвращают одинаковое evidence.
Model self-report и watchdog выявляют mismatch или потерю живости, не меняя brief.

`batch create` закрепляет integration base. Review, QA и publish проверяют закреплённый
candidate. Финальное обновление базы при подготовке PR задаёт ADR 0014, rebase внутри
developer-retry и delta-review задаёт ADR 0012. Стандарты и спецификация проверяются
независимыми отчётами. QA запускается в clean-room worktree через сериализованную lane и
привязывается к точному candidate SHA.

Writer-dispatch может оставить checkpoint на зелёной границе с commit SHA, оставшимся DoD и
результатами проверок и продолжиться в новой worker session после повторной self-report.
Read-only роли используют новый dispatch. Продолжения и retry ограничены проектным бюджетом;
429 не даёт бесконечного повтора. Наблюдаемое `needs_attention` — флаг batch: он блокирует
новый dispatch, пока оператор не разрешит причину, но не создаёт отдельного lifecycle state.

### Короткий маршрут

`/fast-implement` используется для `afk`-тикета с явным `pipeline::fast` и малым радиусом
изменений. Он реализует задачу в одной сессии через TDD и проверки, без architect шага,
независимой QA-роли и approval gates coordinator. Перед code review и перед commit/push этот
маршрут запрашивает отдельные решения разработчика. Для `hitl`-тикета предназначен `/to-guide`.
Оба маршрута после публикации своей issue-ветки лишь предлагают `/to-pull-requests`; открытие PR
и merge остаются отдельными действиями разработчика.

## Операционные последствия

Оператор видит decision packet и утверждает фактический переход, а не абстрактное намерение.
Отчёт роли является evidence, а не разрешением на следующий шаг. Candidate, base, Context
Package, review и QA должны совпадать по закреплённым идентификаторам. Локальный workflow
после принятых проверок публикует issue-ветку; PR требует отдельного подтверждения.

## Уточнение: тест-автор внутри шага developer (#555)

Конвейер `architect → developer → code-review → qa → publish` не меняется. Внутри одного
developer-dispatch, если `test-author-preflight.sh` вернул `{"status":"ok"}`, шаг реализации идёт
циклом Red → Green → Refactor с необязательным субагентом: developer передаёт требование и seam из
brief architect, получает один тест и санитизированное Red evidence, проверяет ожидание по
требованию, пишет минимальную реализацию и рефакторит на Green. Субагент не роль конвейера:
нового dispatch, состояния или записи ledger нет, независимая QA и её граница прежние. Не
согласованный в brief seam идёт по обычному пути blocker. Контракт цикла описывает раздел
«Red-Green-Refactor with the optional test author» в `harness/orchestration/roles/developer.md`.

В полном маршруте этот цикл доступен external и in-process developer в его worker worktree
после preflight `ok` и разрешения вызова автора в утверждённом brief. Корень проекта, доверие
worktree и вызов автора у in-process developer задаёт ADR 0033; guard, runner и выбор
исполнителя задаёт ADR 0035. Rust authority не меняется.
