# Типовые запросы для проверки срабатывания скиллов

Набор проверяет смысл описаний скиллов (`description` во frontmatter `SKILL.md`): вызывает ли
типовой запрос ожидаемый скилл и не уходит ли к соседу. Формат описаний проверяет
`scripts/check_skill_descriptions.py` в `scripts/verify.py`; набор дополняет его там, где формальные
правила бессильны. Прогон ручной (hitl): решение о том, какой скилл сработал, принимает человек по
журналу сессии.

Прогоняйте набор до и после каждой правки описания first-party скилла. Набор появился в эпике #846;
результаты прогонов записываются в комментарий к эпику или тикету, который меняет описания.

## 1. Что именно проверяем

Скиллы делятся на два класса, и «срабатывание» для них значит разное.

- **Вызываются моделью** (нет `disable-model-invocation`): `code-review`, `developer`,
  `diagnosing-bugs`, `grilling`, `qa-gate`, `tdd` и vendor-скиллы `codebase-design`, `domain-modeling`,
  `prototype`, `research`, `resolving-merge-conflicts`, `wizard`, `writing-for-agents`. Для них запрос
  проходит, если агент сам вызвал ожидаемый скилл первым и не вызвал запрещённый.
- **Ручные** (`disable-model-invocation: true`): `architect`, `ask-matt`, `delivery-stats`,
  `fast-implement`, `grill-me`, `grill-with-docs`, `implement`, `publish-epic`, `setup-labels`,
  `to-guide`, `to-pull-requests`, `to-spec`, `to-tickets`, `triage`, `wayfinder`. В Claude Code модель
  их описаний не видит и вызвать не может. Для них запрос проходит, если агент не начал делать работу
  ручного скилла своими силами или через другой скилл и назвал пользователю ожидаемую команду
  (`/to-spec` и т. п.) как следующий шаг. Агент находит её по `.harness/skills/REGISTRY.md` или через
  `/ask-matt`.

Встроенные скиллы среды выполнения тоже участвуют: в Claude Code это `simplify` и `security-review`.
Строки с ними помечены «Claude Code»; в Codex их пропускают.

## 2. Как запускать

1. Подготовить проект с актуальной установкой: в основном checkout выполнить `harness update .`
   (снимок `.harness/skills` основного checkout может отставать от `skills/`, и тогда прогон проверит
   старые описания) или поставить `engineering-suite` в чистый клон. Для строк про глобальные скиллы нужна глобальная установка
   (`bin/`).
2. Для каждого запроса открыть **новую** сессию в корне проекта, без истории и без пользовательских
   скиллов вне проекта (они конкурируют за срабатывание).
3. Вставить запрос дословно. Если агент задаёт уточняющий вопрос до вызова скилла, ответить «да,
   продолжай» один раз.
4. Записать первый вызванный скилл (в Claude Code — вызов инструмента `Skill` в журнале, в Codex —
   упоминание `$skill` или загрузка `SKILL.md`) и названную пользователю команду. Остановить сессию
   до того, как скилл начнёт менять файлы или трекер.
5. Заполнить таблицу результатов (раздел 5) для двух прогонов: до правки описаний и после.

Прогон в Claude Code обязателен. Прогон в Codex выполняется по возможности и записывается отдельными
строками с `Codex` в колонке «Среда выполнения»: поведение `allow_implicit_invocation: false` в Codex
пока не проверено.

Полуавтоматический вариант для открытого вопроса 2 эпика: `claude -p "<запрос>" --output-format
stream-json --verbose` и поиск события вызова инструмента `Skill` в выводе. Этот путь в работе не
проверялся; прежде чем на него полагаться, его нужно опробовать на двух-трёх строках.

## 3. Что считается прохождением

- Строка проходит, если выполнено условие колонки «Ожидание» и не нарушено условие «Не должно».
- Набор проходит, если проходят все строки с пометкой **К** (критичные соседи) и не меньше 90 %
  остальных. Каждую непрошедшую строку записывают с журналом и решением: исправить описание или
  принять расхождение с причиной.
- Сравнение «до/после»: ни одна строка, прошедшая до правки, не должна упасть после.

## 4. Запросы

### 4.1. Прожарка: `grilling`, `grill-me`, `grill-with-docs`, `triage`, `domain-modeling`

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| G1 | Прожарь мой план миграции очереди на PostgreSQL | вызван `grilling` | правки `CONTEXT.md` и ADR | К |
| G2 | Grill me on this rollout plan before I commit to it | вызван `grilling` | вызов `domain-modeling` | К |
| G3 | Хочу проработать идею фичи и собрать Discovery Context для будущей спецификации | названа `/grill-me` (допустимо: начат `grilling` с упоминанием `/grill-me`) | правки `CONTEXT.md` и ADR | К |
| G4 | Stress-test this design and keep the glossary and ADRs updated as we go | названа `/grill-with-docs` | запись в `CONTEXT.md` без явного одобрения пользователя | К |
| G5 | Зафиксируй в глоссарии термин «производственная партия» | вызван `domain-modeling` | вызов `grilling` | |
| G6 | Разбери новые issues в трекере и расставь им метки | названа `/triage` | вызов `grilling` |  К |
| G7 | Look at external PR #301 and decide what to do with it | названа `/triage` | вызов `code-review` | |
| G8 | I can't decide the retention policy myself, prepare questions for the data owner | названа `/to-questionnaire` | вызов `grilling` | |

### 4.2. Реализация: `implement`, `fast-implement`, `developer`, `to-guide`

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| I1 | Реализуй согласованное изменение из этого обсуждения в текущей ветке | вызван `developer` | коммит, push, открытие PR | К |
| I2 | Implement the change we agreed on in the current issue branch and report what you checked | вызван `developer` | коммит, push | |
| I3 | Проведи тикет #42 (pipeline::full) через архитектора, разработчика, ревью и QA | названа `/implement` | вызов `developer`, правка кода | К |
| I4 | Do ticket #57 end to end, it is labeled pipeline::fast; commit and push when done | названа `/fast-implement` | вызов `developer` с коммитом | К |
| I5 | Тикет #31 помечен hitl, код буду писать сам — подготовь пошаговое руководство | названа `/to-guide` | вызов `developer`, `wizard` | К |
| I6 | Walk me through setting up the CI secrets for the deploy, I have to click it myself | вызван `wizard` | `/to-guide` | |
| I7 | Реализуй тикет #42 | агент читает метки тикета и называет `/fast-implement` или `/implement` по метке `pipeline::*`; `developer` вызван только для тикета без метки конвейера | вызов `developer` для тикета с меткой `pipeline::*`, коммит без подтверждения | К |

### 4.3. Ревью и проверки: `code-review`, `qa-gate`, `simplify`, `security-review`

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| R1 | Сделай ревью моей ветки относительно main | вызван `code-review` | правка кода | К |
| R2 | Review PR #88 against its issue | вызван `code-review` | правка кода | К |
| R3 | Проверь, соответствует ли реализация критериям тикета #12 | вызван `code-review` | вызов `qa-gate` | |
| R4 | Упрости код, который я поменял, убери дублирование и примени правки (Claude Code) | вызван `simplify` | вызов `code-review` | К |
| R5 | Clean up my diff for readability and apply the fixes (Claude Code) | вызван `simplify` | вызов `code-review` | К |
| R6 | Check my pending changes for security vulnerabilities (Claude Code) | вызван `security-review` | вызов `code-review` | |
| R7 | Прогони линтер и все тесты перед открытием PR | вызван `qa-gate` | вызов `code-review` | К |
| R8 | Run the full check suite | вызван `qa-gate` | — | |
| R9 | Запусти только tests/core/test_runtime_events.py | агент запускает тест сам | вызов `qa-gate` | К |

### 4.4. Подготовка задач: `to-spec`, `publish-epic`, `to-tickets`, `wayfinder`

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| P1 | Прожарка закончена, напиши по ней спецификацию | названа `/to-spec` | вызов `grilling`, публикация в трекер | К |
| P2 | The spec is approved — publish it as an epic and create the integration branch | названа `/publish-epic` | названа `/to-tickets` первой | К |
| P3 | Эпик #900 опубликован, разбей его на тикеты | названа `/to-tickets` | названа `/publish-epic` | К |
| P4 | Recheck the published tickets of epic #900 against its acceptance criteria | названа `/to-tickets --review` | создание или правка тикетов | |
| P5 | Это миграция на квартал, в одну сессию не влезет — составь карту решений | названа `/wayfinder` | названа `/to-tickets` | К |
| P6 | Какой скилл взять, чтобы начать новую фичу с нуля? | названа `/ask-matt` или цепочка `/grilling` → `/to-spec` → `/publish-epic` → `/to-tickets` | — | |

### 4.5. Диагностика и TDD: `diagnosing-bugs`, `tdd`

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| D1 | Тест test_retry падает через раз, разберись почему | вызван `diagnosing-bugs` | вызов `tdd` | К |
| D2 | The export endpoint got three times slower since the last release | вызван `diagnosing-bugs` | вызов `research` | |
| D3 | Почему CI падает на этой ветке? | вызван `diagnosing-bugs` | вызов `qa-gate` | К |
| D4 | Почини баг #77 через TDD: сначала падающий тест | вызван `tdd` | вызов `diagnosing-bugs` | К |
| D5 | Add a discount rule test-first, red-green-refactor | вызван `tdd` | — | |
| D6 | Build the CSV export for the report page | — | вызов `tdd` | |

### 4.6. Публикация и прочее

| ID | Запрос | Ожидание | Не должно | К |
|---|---|---|---|---|
| O1 | Ветка запушена, открой по ней PR | названа `/to-pull-requests` | открытие PR без подтверждения | К |
| O2 | How much did epic #846 cost in tokens? | названа `/delivery-stats` | — | |
| O3 | Оцени, сколько токенов потребует следующий эпик | — | названа `/delivery-stats` | |
| O4 | Создай в репозитории метки status::* и hitl/afk | названа `/setup-labels` | названа `/setup-matt-pocock-skills` | К |
| O5 | Сравни варианты: очередь в Postgres или Redis для диспетчеризации, тикет #12 | названа `/architect` (допустимо: вызван `codebase-design` с упоминанием `/architect`) | правка файлов | |
| O6 | Where should the seam go to make this module testable? | вызван `codebase-design` | — | |
| O7 | Build a quick throwaway prototype to see if this state machine feels right | вызван `prototype` | — | |
| O8 | Хочу начать новый проект из идеи (глобальная установка) | вызван `start-project` | вызов `integrate-project` | |
| O9 | Integrate the harness into our existing monorepo with CI and conventions (глобальная установка) | вызван `integrate-project` | вызов `start-project` | |

## 5. Шаблон записи результата

| ID | Прогон | Среда выполнения | Первый вызванный скилл | Названная команда | Итог | Примечание |
|---|---|---|---|---|---|---|
| G1 | до | Claude Code | | | pass/fail | |

## 6. Принятые решения

1. **I7 «Реализуй тикет #42» — критичная строка.** Для тикета `afk` с меткой `pipeline::*` агент
   называет `/fast-implement` или `/implement`, а `developer` вызывает только для тикета без метки
   конвейера или по прямой просьбе. Эту границу задаёт описание `developer`: «for a labeled afk
   ticket, use /fast-implement or /implement».
2. **Порог для некритичных строк — 90 %.**
3. **Среды выполнения.** Claude Code — обязательно, Codex — по возможности (раздел 2).
