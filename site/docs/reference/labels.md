# Метки

У каждой оси своя метка, и они не смешиваются. Состояние пайплайна — отдельная ось от того, кто
выполняет работу: тикет может быть `status::ready` и `hitl`, и это два разных утверждения.

## Оси

| Ось | Значения | Кто применяет |
| --- | --- | --- |
| Тип | `type::bug`, `type::feature`, `type::refactoring`, `type::chore`, `type::security`, `type::performance`, `type::hotfix` | `/triage` |
| Режим исполнения | `hitl`, `afk` | `/triage`, `/to-tickets` |
| Состояние | `status::specs`, `status::ready`, `status::in-progress`, `status::blocked` | `/triage`, `/to-spec`, `/to-tickets`, `/implement`, `/fast-implement`, `/to-pull-requests` |
| Маршрут | `pipeline::fast`, `pipeline::full` | `/to-tickets` |
| Контекст | `task-report::required`, `resolution::wontfix` | `/to-spec`, `/to-tickets`, `/triage` |
| Wayfinder | `wayfinder:map`, `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, `wayfinder:task` | `/wayfinder` |

`hitl` означает, что работу выполняет человек по руководству; `afk` — что задачу можно отдать агенту.
`pipeline::fast` и `pipeline::full` — производная оценки объёма: мелкая задача идёт коротким путём,
значимая — полным циклом с гейтами.

## Правило одной метки

Ось состояния держит ровно одну метку. Переход `status::ready` → `status::in-progress` заменяет
метку, а не добавляет вторую; то же касается `status::blocked`. Две метки состояния — ошибка,
которая делает неопределённым выбор маршрута и автоподбор тикета.

Ось режима не заполняется, пока стоит `status::specs`: на этапе проработки ещё не решено, кто будет
исполнять. Маршрут `pipeline::*` не ставится `hitl`-тикетам: короткий путь для них не применяется.

## State machine

1. **Нет метки состояния.** Issue неявно считается «нужен триаж».
2. **`status::specs`.** Эпик или крупная задача: пишется спецификация и нарезаются тикеты. В работу
   такой тикет не берут.
3. **`status::ready`.** Тикет полностью описан, его можно брать. Именно это состояние выбирает
   автоподбор.
4. **`status::in-progress`.** По тикету идёт активная сессия. Метка ставится до создания ветки и
   правок, а не после.
5. **`status::blocked`.** Тикет ждёт зависимость или ответа человека. Блокировка ставится за
   зависимость по результату, а не за пересечение файлов.
6. **Обратно в `status::ready`.** Метку снимает тот, кто закрыл блокер: подтверждённый merge и
   закрытие предшественника. Открытый PR, принятый QA и push блокер не снимают.

Тикет, закрытый как невыполнимый, не оставляет за собой ось состояния: с него снимают `status::*` и
ставят `resolution::wontfix`.

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
