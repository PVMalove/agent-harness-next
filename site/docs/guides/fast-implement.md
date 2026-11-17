# /fast-implement

`/fast-implement` реализует задачу за один проход в текущей сессии, без coordinator, architect,
независимого QA и approval-гейтов. Маршрут подходит для мелкой задачи, направление которой не обсуждается.

## Когда использовать

- У тикета метки `afk` и `pipeline::fast`. Это мелкий объём, по умолчанию до трёх story points.
- Задача укладывается в одну проверяемую границу, и отдельная роль для независимой проверки не нужна.
- Тикет `hitl` этим маршрутом не идёт никогда. Для него есть `/to-guide`, где реализацию
  выполняет человек.

Если команда получила эпик вместо тикета, она берёт первый подходящий тикет фронтира, то есть списка
готовых к работе дочерних тикетов. Подходящий тикет открыт, не заблокирован, никем не занят и размечен
`pipeline::fast` вместе с `afk`. Если явно названный тикет не размечен `pipeline::fast`, команда
останавливается и предлагает `/implement`.

## Pre-flight

1. **Найти тикет.** Если явно назван `hitl`-тикет, агент останавливается и предлагает `/to-guide`.
   Если назван `afk`-тикет без `pipeline::fast`, агент останавливается и предлагает `/implement`.
2. **Проверить блокеры.** Если блокер открыт, агент останавливает работу и ставит тикету
   `status::blocked`.
3. **Пометить тикет как взятый в работу до ветки и правок.** Агент заменяет текущую `status::*` на `status::in-progress`:

   ```bash
   gh issue edit 102 --remove-label status::ready --remove-label status::blocked \
     --add-label status::in-progress
   ```

   Затем агент проверяет, что `status::in-progress` осталась единственной меткой состояния. Если
   записать метку не удалось, агент останавливается и без метки не продолжает.
4. **Ветка.** Агент создаёт issue-ветку от integration-ветки тикета. Имя должно соответствовать
   `branch_pattern` проекта и не совпадать с защищёнными ветками.

## Шаги

1. **Тест первым.** Новое поведение начинается с падающего теста по `/tdd` на согласованном шве.
2. **Реализация.** Агент пишет минимальный код до зелёного теста, затем рефакторит без изменения поведения.
3. **Ревью по согласию.** Агент предлагает `/code-review`. Если вы отказались, агент явно записывает отказ.
4. **Коммит и push.** После отдельного согласия агент делает semantic commit, пушит issue-ветку
   и сообщает хеш и результат push.
5. **Предложить публикацию.** Агент называет `/to-pull-requests` и останавливается: эту команду вызывает человек.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Выбор маршрута по меткам тикета и пять шагов однопроходного пути.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/fast-implement-route.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/fast-implement-route.html" title="/fast-implement: маршрут и шаги" loading="lazy"></iframe>
</figure>

## Чем отличается от /implement

| Аспект | `/fast-implement` | `/implement` |
| --- | --- | --- |
| Кто пишет код | текущая сессия | роли, которым coordinator отправил dispatch |
| Гейты | нет | architect → developer → code-review → qa → publish |
| Approval | согласие человека на review, commit и push | approval на каждом гейте по политике |
| Независимый QA | нет, полный прогон в конце сессии | да, clean-room на закреплённом кандидате |
| Артефакты | commit в issue-ветке | candidate commit, brief, отчёты, ledger |
| Требует capability | нет | `backend-orchestration` |

## Дальше

- [«/implement»](implement.md)
- [TDD](tdd.md)
- [Code review](code-review.md)
