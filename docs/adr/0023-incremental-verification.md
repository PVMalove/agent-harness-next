# Инкрементальная проверка: ChangeImpact, выбор тестов и полный gate на финальном SHA

**Статус: ACCEPTED (2026-10-20).** Эпик #784, ADR 0019, ADR 0021, ADR 0026. Документ задаёт, какие
проверки запускает каждая роль, когда допустим запуск только упавших тестов и почему publish
разрешает только полный clean-room прогон на финальном SHA. Закрытые #756, #757 и #758 — основа, их
поведение не отменяется.

## Контекст системы

Сейчас (`master` 3556b16):

- `scripts/verify.py` выполняет статические проверки, затем `mypy`, `pytest` и clean-room
  (`_run_stages`, `:242`) и останавливается на первой ошибке.
  - `pytest` идёт с `-n min(8, cpu)` (#758) и `-p no:cacheprovider`. Флаг `--failed-first DIR`
    (`:321`) включает `--ff` — это порядок «упавшие первыми», а не отбор: запускается весь набор.
  - CI передаёт этот флаг на каждом прогоне (`verify.yml:60-63`).
  - Кэш `mypy` живёт в `run_tmp` и удаляется в конце прогона (`verify.py:275`), поэтому `mypy`
    всегда холодный.
- `scripts/test_clean_room.py` запускает 24 сценария по порядку с общим контекстом (`:57-85`);
  поздние сценарии читают то, что оставили ранние. Запустить подмножество нельзя.
- `related_tests` строит `context_builder._related_tests` (`:487-503`): один шаг по
  import-рёбрам, только по Python-именованию тестов и только от первых `max_starting_files` (10)
  изменённых файлов. Превышение `max_related_tests` — ошибка `ContextPackageError`. Используется
  только developer-retry (`retry_verification`, #757).
- Команды проверки замораживаются при `batch create` (`batch.py:404-448`, профили #756).
  `checks_run` отчёта сверяется с brief дословно (`reports.py:1578-1584`); результат —
  `pass`/`fail`/`not_run`.
- Gate runner запускает команды без таймаута, сливает stdout и stderr и не хранит длительность
  каждой команды (`gate_runner.py:317-387`). `not_run` для недошедших команд записывается только
  при заданном `qa_preparation` (`qa_lane.py:531-546`).

## Действующий контракт

### 1. ChangeImpact

ChangeImpact — функция Python поверх графа `harness/repo_map`. Вход — diff `base..candidate`
(`--name-status`, с переименованиями). Выход — `ImpactSet`:

- `changed` — изменённые, добавленные, удалённые и переименованные пути;
- `impacted_modules` — обратное транзитивное замыкание по import-рёбрам;
- `related_tests` — тесты, импортирующие любой модуль из `impacted_modules`, без отсечения по
  первым N изменённым файлам;
- `unknown` с причинами.

`unknown` выставляется консервативно. Тогда выбор расширяется до полного набора, а не сужается:

- изменён манифест или конфиг сборки и проверок: `pyproject.toml`, `uv.lock`, `Makefile`,
  `.github/**`, `scripts/verify.py`, `scripts/verification/**`, `conftest.py` любого уровня;
- изменён `harness/CAPABILITIES.json` или `skills/**` (AGENTS.md требует `scripts/verify.py`);
- удалён или переименован модуль, на который есть ссылки;
- файл не на Python или не покрыт графом;
- динамический импорт в затронутом модуле;
- число `related_tests` больше порога плана.

Context Package (#757) по-прежнему использует свой `related_tests` и свой лимит; ChangeImpact его не
заменяет, а `VerificationPlan` строится только по `ImpactSet`.

### 2. VerificationPlan

Python строит план при propose. План входит в brief, а его digest — в approval как
`verification_plan_sha256` в `OPTIONAL_TRANSITION_FIELDS`. Поле `verification_commands` в
`TRANSITION_FIELDS` остаётся: это команды, которые роль обязана отчитать в `checks_run`. Каждая
стадия плана задаёт:

- `stage_id` и `kind`: `lint`, `typecheck`, `pytest`, `clean-room` или `custom`;
- `argv` и `timeout_seconds`;
- `selection`: `full`, `focused` или `failed-only`;
- `nodeids` — для `focused` и `failed-only`;
- `environment_fingerprint`: sha256 версии интерпретатора, `uv.lock`, секций `[tool.*]`
  `pyproject.toml` и digest образа, если он есть.

Исполняет план Rust (ADR 0022). Роли:

| Роль | Выбор | Evidence для отчёта |
|---|---|---|
| Developer | `lint` + `typecheck` + `focused` по `ImpactSet`; при `unknown` — `full` | команды brief, дословно |
| Developer-retry | как #757; при наличии `ImpactSet` — `focused` по нему | команды brief, дословно |
| Review | независимый прогон того же `focused`-плана, не отчёт developer-а | команды brief, дословно |
| QA | `full`: весь `verification_commands` (`make verify`) в clean-room на `candidate_sha` | stage evidence |

### 3. Failed-only

Режим failed-only — диагностика внутри сессии developer-а, а не evidence:

- Источник — точные nodeid упавших тестов из JUnit предыдущего прогона того же worktree или
  `pytest --lf --lfnf=none` с кэшем этого worktree.
- `--ff` failed-only не считается.
- Прогон без единого выбранного теста (пустой кэш, `--lfnf=none`, исчезнувший nodeid) даёт
  `not_run`, а не `pass`. Переименованный или удалённый nodeid переводит выбор в `focused`.
- Зелёный failed-only доказывает только эти nodeid. Прежде чем отчитаться, developer выполняет
  команды brief; правило дословной сверки `checks_run` не меняется.

### 4. Кэши

- Кэш `pytest` и `mypy` для developer и review лежит в
  `.harness/.sandboxes/cache/<worktree-id>/<environment_fingerprint>/`. Кэши разных worktree и
  разных fingerprint не смешиваются; кэш с другим fingerprint игнорируется.
- QA-gate кэши не использует: clean-room стартует холодным, как сейчас.
- Ни один кэш не служит доказательством прохождения.

### 5. Полный clean-room gate на финальном SHA

- Publish разрешает только QA-evidence, где все стадии `verification_commands` выполнены с
  результатом `pass` на `candidate_sha`, совпадающем с публикуемым коммитом, при совпадающих
  digest плана, образа и `environment_fingerprint`.
- Новый SHA делает прежний полный QA недействительным. Focused-, failed-only- и кэшированные
  результаты publish не разрешают.
- QA-evidence привязан к паре `{candidate_sha, target_sha}` и к `candidate_tree_sha`. Merge
  squash-ом в целевую ветку разрешает только Release Gate ADR 0026 (раздел 4); перед push и merge
  Python получает вердикт `qa_evidence_verify` (ADR 0021, раздел 7).
- Повтор QA на том же SHA после `infrastructure` или `environment_preparation` (#615, #769)
  допустим без расхода бюджета developer-а и без нового approval, если план и окружение заново
  проверены. Такой повтор — новый `attempt` того же dispatch (ADR 0021, раздел 4), поэтому у него
  новый `operation_id`. Повтор после `code_test` требует нового кандидата. Так повторяется
  контейнерный QA; исторический хост-QA сохраняет отчёт `blocked` и policy-retry (ADR 0022,
  раздел «Решения реализации #810»).
- Каждая стадия и команда хранят `stage_id`, `candidate_sha`, digest-ы, `environment_fingerprint`,
  результат `pass`/`fail`/`not_run`, exit code, раздельные ссылки на stdout и stderr с sha256,
  длительность и упавшие nodeid из JUnit.
- Команда, до которой gate не дошёл, получает `not_run` всегда, а не только при `qa_preparation`.
- Сценарии clean-room не делятся, пока у каждого не объявлены `requires`/`provides` в контексте.
  До этого допустим только полный прогон всех 24 сценариев.

### 6. ChangeImpact-gate

`dispatch propose` для review и QA проверяет, что план покрывает `ImpactSet`: каждый
`related_tests` выбран, или стадия `pytest` — `full`. Непокрытый тест — отказ `impact_not_covered`
(код 2) с перечнем тестов. Это машинная проверка: текст отчёта роли её не заменяет. Профили hooks
(ADR 0024) используют тот же `ImpactSet` для предупреждений, но планированием проверок не
управляют.

### 7. Выбор тестов по diff тикета (`ticket-diff`)

Флаг `verification_plan_policy.ticket_diff_selection` (булев, по умолчанию выключен) включает
режим для батча, чья `integration_ref` начинается с `integration/`. `batch create` замораживает флаг
вместе с остальной политикой: правка конфига после создания батча план не меняет. Для цели
`master` (ветка по умолчанию) флаг не действует, а план QA остаётся `full`.

При включённом режиме план developer-retry, code-review и QA выбирает ровно тесты diff
`base..candidate` самого тикета. Выбор — чистая функция списка `--name-status` (`select_ticket_diff_tests`):

- добавленный или изменённый `test_*.py` (`*_test.py`) входит в стадию `pytest` с выбором
  `ticket-diff` и явными nodeid; переименованный модуль входит под новым путём;
- Rust `crates/X/tests/foo.rs` (или `tests/foo/main.rs`) даёт стадию `custom` с
  `cargo test -p X --test foo`, а любой файл `crates/X/src/**` — `cargo test -p X --lib`;
  crate без `src/lib.rs` (бинарный, как `harness-runtime`) получает `--bins`, потому что у него
  нет цели `--lib`;
- удалённый файл, изменённый хелпер или фикстура (`conftest.py`, `tests/common/**`,
  `tests/fixtures/**`) тестов не добавляют;
- стадии `lint`, `typecheck`, `cargo fmt` и `cargo clippy` остаются как в шаблоне политики.

Выбор никогда не расширяется до `full`: ни `unknown` из ChangeImpact, ни роль QA его не меняют.
Diff без тестов оставляет статические стадии, не запускает тесты, а стадия тестов пишется в
stage evidence как `not_run` со стадией `no-tests-in-diff` (`no tests in diff`), без команды и потоков.
План несёт раздел `ticket_diff` (`python_tests` и `cargo_targets`), а `impact` остаётся как есть, чтобы профиль
hooks `strict` видел те же причины `unknown`. Выбор `ticket-diff` — диагностика ветки тикета, а не Release Gate: полный `master`-QA
остаётся единственным evidence для publish (раздел 5).

Gate из раздела 6 для такого плана требует каждый тест выбора diff в планах code-review и QA и
отказывает `impact_not_covered`, перечисляя пропущенные тесты. Команды `verification_commands`
этих brief выводятся из плана: lint и typecheck шаблона плюс точные команды выбранных тестов.
`qa run` записывает в stage evidence выбор `ticket-diff` и явные nodeid в необязательном ключе
`nodeids` стадии `stage-evidence.v1` (Python и Rust-близнец; стадия без ключа пишется как раньше).

Тот же выбор лежит в основе лёгкого пути CI (#937). Pull request в `integration/**` запускает задание
`verify-light`, а `scripts/ci_light_tests.py` берёт `ticket_diff_selection` от общего предка PR и его
головы и запускает только эти тесты: pytest по добавленным и изменённым файлам, затем
`cargo test --locked` по выбранным целям. Diff без тестов проходит и ничего не запускает, а выбор не
расширяется ни до связанных тестов, ни до полного набора. Единственное исключение — правило корпуса
памяти (#1061): diff, который меняет, удаляет или переименовывает `CONTEXT.md` или `docs/adr/*.md`,
запускает и `tests/memory/test_eval.py`. FTS5 baseline хранит хэш каждого файла корпуса, и без этого
правила устаревший хэш видел бы только полный прогон. Полный `make verify` и полный
`cargo test` идут только для PR в `master` и других ветках, push в `master` и вызова из другого
workflow. Доказательство лёгкого задания не заменяет полный QA пары, которой нужен выбор `full`
(ADR 0016, дополнение #937).

### Поправка 2026-11-07 (#938): разделы 5 и 6 и политика тестов тикета

Поправка закрепляет политику «тикет гоняет тесты своего diff, полный прогон — только перед `master`»
в том виде, в каком её реализовали #935, #936 и #937. Разделы 5 и 6 выше описывают полный gate и
остаются правилом по умолчанию; поправка сужает их только при включённом флаге.

- **Флаг.** `verification_plan_policy.ticket_diff_selection` (по умолчанию выключен) замораживается
  в `batch create`. Выключенный флаг, batch без политики и цель `master` оставляют разделы 5 и 6
  без изменений.
- **Раздел 6 (ChangeImpact-gate).** Для цели `integration/*` при включённом флаге план
  developer-retry, code-review и QA выбирает тесты diff тикета (`selection` — `ticket-diff`), а gate
  требует каждый такой тест в планах code-review и QA. Выбор не расширяется до `full`.
- **Раздел 5 (полный gate).** Пару в `integration/*` подтверждают стадии `ticket-diff`: запись пары
  хранит требуемый `selection`, и его один раз решает писатель пары. Полный прогон остаётся
  обязательным для пары в ветку по умолчанию, при выключенном флаге и для записи старого контракта.
- **CI.** Pull request тикета в `integration/**` запускает задание `verify-light` с тестами его
  diff, а при правке корпуса памяти — и с тестом FTS5 baseline (#1061). Полный `make verify` и
  полный `cargo test` идут для PR в `master`. `integration collect-ci`
  принимает полный CI пары как доказательство, а `-light` проверка пару с выбором `full` не
  подтверждает (причина `light_check`). Если полного CI нет или он непригоден, запасной путь —
  полный локальный QA пары (`integration local-qa`).
- **Падение полного прогона перед `master`.** Его чинят обычные fix-тикеты с базой в integration-ветке:
  они проходят тот же путь с diff-прогоном, а PR в `master` ждёт зелёного полного прогона.
  Автоматического создания fix-тикетов нет.

## Операционные последствия

- **Approval.** `verification_plan_sha256` и `verification_commands` закрепляются при approval;
  изменение конфига или `ImpactSet` после approval не меняет запущенный dispatch. Новый план —
  новый propose.
- **Совместимость.** Без нового ключа плана batch работает по замороженным командам, как сейчас.
  Профили #756 и `retry_verification` #757 остаются. CI сохраняет `--ff` только как порядок
  прогона.
- **Негативные тесты (seam 1):**
  - изменение `conftest.py`, `pyproject.toml` или `uv.lock` → `full`;
  - переименованный модуль → `unknown` → `full`;
  - больше порога `related_tests` → `full`, а не ошибка;
  - пустой `--lf` → `not_run`, а не `pass`;
  - исчезнувший nodeid → `focused`;
  - кэш другого fingerprint игнорируется;
  - новый SHA после зелёного QA → publish отказан;
  - review не принимает evidence developer-а вместо своего прогона;
  - непокрытый impacted-тест → `impact_not_covered`;
  - таймаут команды → `timeout`;
  - недошедшие команды → `not_run` без `qa_preparation`;
  - офлайн `uv sync` → `environment_preparation`.
- **Замеры:** число полных прогонов на `/implement`, время failed-only и focused-прогонов, общее
  время `/implement` до и после. Числа без замера не публикуются.
- **Команды проверки:** `.harness/.venv/bin/python -m pytest -q
  tests/orchestration/test_verification_profiles.py tests/orchestration/test_retry_verification.py
  tests/core/test_gate_runner.py tests/orchestration/test_qa_lane.py
  tests/scripts/test_verify_temp.py`; `cargo test` в `native/harness-runtime`; `make verify`.
