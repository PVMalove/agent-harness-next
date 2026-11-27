# Метки

Метки разбиты на оси, и у каждой оси свои метки. Состояние в пайплайне и исполнитель работы лежат на
разных осях: тикет может нести `status::ready` и `hitl` одновременно, это два разных утверждения.

## Оси

| Ось | Значения | Кто применяет |
| --- | --- | --- |
| Тип | `type::bug`, `type::feature`, `type::refactoring`, `type::chore`, `type::security`, `type::performance`, `type::hotfix` | `/triage` |
| Режим исполнения | `hitl`, `afk` | `/triage`, `/to-tickets` |
| Состояние | `status::specs`, `status::ready`, `status::in-progress`, `status::blocked`, `status::done` | `/triage`, `/publish-epic`, `/to-tickets`, `/implement`, `/fast-implement`, `/to-pull-requests` |
| Маршрут | `pipeline::fast`, `pipeline::full` | `/to-tickets` |
| Контекст | `task-report::required`, `resolution::wontfix`, `rca::done` | `/publish-epic`, `/to-tickets`, `/triage`, фаза RCA `/diagnosing-bugs` |
| Вид PR | `pr::ticket`, `pr::integration` | `/to-pull-requests` |
| Wayfinder | `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` | `/wayfinder` |

`hitl` означает, что работу выполняет человек по руководству. `afk` означает, что задачу можно
отдать агенту. `/to-tickets` выводит `pipeline::fast` или `pipeline::full` из оценки объёма в story
points: мелкая задача идёт коротким путём, крупная проходит полный цикл с гейтами.

Ось `pr::*` ставится на PR, а не на тикет, и у каждого PR ровно одна такая метка. `pr::ticket`
получает PR одного тикета, в том числе PR тикета без эпика в `base_branch`; он наследует `type::*`
тикета. `pr::integration` получает любой PR, у которого head — ветка `integration/*`, в какую бы
ветку он ни шёл; `type::*` у него нет, потому что он собирает тикеты разных типов. `rca::done`
означает, что баг-тикет создан из завершённого RCA: метка ставится рядом с `type::bug` и не
заменяет её.

Необязательные информационные оси `priority::*`, `severity::*` и `env::*` (только в целевом проекте)
описаны в `.harness/instructions/triage-labels.md` целевого проекта.

## Правило одной метки

На оси состояния у тикета ровно одна метка. Переход `status::ready` → `status::in-progress`
заменяет метку, вторую метку он не добавляет; так же меняется `status::blocked`. Две метки состояния
считаются ошибкой: с ними неясно, какой маршрут выбрать и можно ли автоматически взять тикет.

Пока стоит `status::specs`, метку режима не ставят: на этапе проработки ещё не решено, кто будет
исполнять. `hitl`-тикетам метку маршрута `pipeline::*` не ставят, короткий путь к ним не применяется.

## State machine

1. **Нет метки состояния.** Issue по умолчанию ждёт триажа.
2. **`status::specs`.** Эпик или крупная задача: по ней пишут спецификацию и нарезают тикеты. В работу
   такой тикет не берут.
3. **`status::ready`.** Тикет полностью описан, его можно брать. Автоподбор выбирает только это
   состояние.
4. **`status::in-progress`.** По тикету идёт активная сессия. `/implement` и `/fast-implement` ставят
   метку до создания ветки и первой правки.
5. **`status::blocked`.** Тикет ждёт зависимость или ответ человека. Блокировку ставят за зависимость
   по результату, пересечение файлов к ней не относится.
6. **Обратно в `status::ready`.** Блокер снят, когда предшественник закрыт, а закрывают его только
   после подтверждённого мержа. Открытый PR, принятый QA и push блокер не снимают.

После подтверждённого мержа `/to-pull-requests` заменяет `status::in-progress` на `status::done` и закрывает
тикет; тикет, который трекер закрыл сам по `Closes #<ID>`, получает метку сразу после проверки закрытия.

Если тикет отклонён, с него снимают `status::*`, ставят `resolution::wontfix` и закрывают его.

## Где что применяется

| Шаг | Что применяет |
| --- | --- |
| `/triage` | Тип, режим исполнения, состояние; отклонение закрывает тикет с `resolution::wontfix` |
| `/publish-epic` | `type::*`, `status::specs` и `task-report::required` на эпик |
| `/to-tickets` | Режим, маршрут `pipeline::*`, `status::ready` или `status::blocked` |
| `/implement`, `/fast-implement` | `status::in-progress` вместо текущей метки состояния |
| `/to-pull-requests` | PR тикета: `pr::ticket` и `type::*` тикета; интеграционный PR: `pr::integration` без `type::*`. После merge: `status::done` вместо `status::in-progress`; `status::blocked` → `status::ready` у разблокированных зависимых. С `--release <epic>` после merge интеграционного PR в `base_branch`: `status::done` вместо `status::specs` у эпика |
| Фаза RCA `/diagnosing-bugs` | После явного «да» разработчика: `type::bug` и `rca::done` на новый баг-тикет; `status::blocked` у остановленного тикета, если баг его блокирует |

## Дальше

- [Рабочий поток](../guides/workflow.md)
- [«/implement»](../guides/implement.md)
