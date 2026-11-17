# Метки

Метки разбиты на оси, и у каждой оси свои метки. Состояние в пайплайне и исполнитель работы лежат на
разных осях: тикет может нести `status::ready` и `hitl` одновременно, это два разных утверждения.

## Оси

| Ось | Значения | Кто применяет |
| --- | --- | --- |
| Тип | `type::bug`, `type::feature`, `type::refactoring`, `type::chore`, `type::security`, `type::performance`, `type::hotfix` | `/triage` |
| Режим исполнения | `hitl`, `afk` | `/triage`, `/to-tickets` |
| Состояние | `status::specs`, `status::ready`, `status::in-progress`, `status::blocked` | `/triage`, `/to-spec`, `/to-tickets`, `/implement`, `/fast-implement`, `/to-pull-requests` |
| Маршрут | `pipeline::fast`, `pipeline::full` | `/to-tickets` |
| Контекст | `task-report::required`, `resolution::wontfix` | `/to-spec`, `/to-tickets`, `/triage` |
| Wayfinder | `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` | `/wayfinder` |

`hitl` означает, что работу выполняет человек по руководству. `afk` означает, что задачу можно
отдать агенту. `/to-tickets` выводит `pipeline::fast` или `pipeline::full` из оценки объёма в story
points: мелкая задача идёт коротким путём, крупная проходит полный цикл с гейтами.

Необязательные информационные оси `priority::*`, `severity::*` и `env::*` (только в целевом проекте)
описаны в `docs/agents/triage-labels.md` целевого проекта.

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

После мержа и закрытия тикет сохраняет `status::in-progress`: закрытое состояние и означает «готово».

Если тикет отклонён, с него снимают `status::*`, ставят `resolution::wontfix` и закрывают его.

## Где что применяется

| Шаг | Что применяет |
| --- | --- |
| `/triage` | Тип, режим исполнения, состояние; отклонение закрывает тикет с `resolution::wontfix` |
| `/to-spec` | `status::specs` на эпик и `task-report::required` |
| `/to-tickets` | Режим, маршрут `pipeline::*`, `status::ready` или `status::blocked` |
| `/implement`, `/fast-implement` | `status::in-progress` вместо текущей метки состояния |
| `/to-pull-requests` | После merge: `status::blocked` → `status::ready` у разблокированных зависимых |

## Дальше

- [Рабочий поток](../guides/workflow.md)
- [«/implement»](../guides/implement.md)
