# /implement

`/implement` ведёт тикет через конвейер с явными гейтами и approval. Код пишут роли, которым
coordinator отправил dispatch, а сама сессия только координирует. Маршрут включает только capability
`backend-orchestration`, без неё используйте `/fast-implement`. Команду вы запускаете вручную в новой
чистой сессии.

## Когда использовать

| Ситуация | Команда |
| --- | --- |
| Задача с независимыми границами или обязательной независимой проверкой | `/implement` |
| Мелкая задача, направление не обсуждается | `/fast-implement` |
| Реализацию выполняет человек по готовому руководству | `/to-guide` |

Метка тикета влияет только на автоподбор: тикеты `pipeline::fast` автоподбор пропускает. Тикет,
названный явно, проходит полный цикл при любой метке. Между ревью и QA короткого пути нет,
короткий путь называется `/fast-implement`.

## Pre-flight

1. **Блокеры.** Coordinator проверяет, что у тикета нет открытых блокеров. Если блокер открыт, работа
   останавливается.
2. **Метка состояния.** До создания ветки и правок coordinator заменяет текущую `status::*` на
   `status::in-progress` и проверяет, что другой `status::*` у тикета нет.
3. **Integration ref.** Coordinator берёт ветку из раздела тикета `## Integration Branch`. Если его нет,
   из раздела `## Git base`, если нет и его, из того же раздела родительского эпика. Если у тикета
   есть эпик, но значения нет, это блокер. Тикет без эпика использует `base_branch` проекта.
4. **Issue-worktree.** Coordinator создаёт worktree тикета от integration-ветки. `batch create` не
   работает с worktree, которого нет в `git worktree list`.
5. **Scope.** Coordinator выполняет `batch preflight` с теми же флагами, что пойдут в `batch create`,
   включая `--allowed-path` и пункты Definition of Done. Требование TDD записывается отдельным пунктом DoD.

## Гейты

| Гейт | Что происходит | Решение | Артефакт |
| --- | --- | --- | --- |
| architect | План: шов, границы, порядок правок | по `approval_policy` | принятый architect-отчёт |
| developer | Реализация по плану, тесты до кода | по `approval_policy` | candidate commit |
| code-review | Две оси, Standards и Spec, независимо | по `approval_policy` | отчёт review по обеим осям |
| qa | Полный прогон на закреплённом кандидате, Release Gate | по `approval_policy` | QA evidence для SHA |
| publish | Принятый SHA объявляется опубликованным | по `approval_policy` | запись публикации |

Порядок жёсткий: coordinator отклоняет `dispatch create --role developer`, пока у batch нет принятого
architect-отчёта. Политику approval задаёт конфигурация оркестрации. Гейты можно проходить вручную
или разрешить автоматическое принятие через `approval_policy: auto`. Но и тогда список остановок
(целостность, бюджет, маршрут восстановления) закрыт, и снять остановку может только человек.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Пять гейтов конвейера. Схема показывает ручной вариант согласования.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/implement-gates.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/implement-gates.html" title="/implement: гейты и approval" loading="lazy"></iframe>
</figure>

## Гибридный контракт публикации

Маршрут включается только явно выбранной capability, другие сборки его не включают.
Developer создаёт candidate commit. Отчёт о работе остаётся `reported`, пока не принято решение
по `approval_policy`. Принятый SHA публикует только developer в dispatch с назначением `publish`. После этого человек
отдельно вызывает `/to-pull-requests`. Агент открывает PR только после явного подтверждения.
`integration next` называет следующий шаг по записи интеграции.
Adapter только передаёт уже утверждённое: он не решает, что публиковать, и не открывает PR.

## Живость и восстановление

- **Model self-report.** Первым действием роль сообщает свою активную модель. Если модель не совпадает
  с моделью из brief, dispatch переходит в `blocked`, и отчёт не принимается.
- **Heartbeat и watchdog.** Роль шлёт heartbeat, coordinator опрашивает статус. Если dispatch молчит,
  coordinator передаёт это человеку как блокер.
- **Ранний blocked-отчёт.** Developer может сообщить о блокере до коммита и указать маршрут
  восстановления. Coordinator не придумывает коммит за него.
- **Остановку и отмену решает человек.** `batch resume-stop` возобновляет batch после записанной
  остановки, `batch rewind` выбирает более ранний гейт без изменения истории Git, `batch abandon`
  закрывает тупиковый batch. Все три команды требуют approval и причины.
- **Состояние не правится вручную.** Состояние в `.harness/orchestration/state/` читайте только
  через CLI: это аудиторский след, а не рабочий файл.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Как dispatch переходит между состояниями и где нужно решение человека.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/dispatch-lifecycle.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/dispatch-lifecycle.html" title="Жизненный цикл dispatch и batch" loading="lazy"></iframe>
</figure>

## Надстройки поверх конвейера

| Когда | Что |
| --- | --- |
| После publish | `/to-pull-requests`: PR и wrap-up, то есть проверка ветки, тело PR, закрытие тикета |
| Нужно тело PR | субагент `pr-composer` заполняет шаблон и возвращает путь к файлу |
| Тикет `hitl` | `/to-guide` готовит руководство с промптами для ручной реализации |
| Перед первым запуском пайплайна | `/setup-labels` создаёт метки в трекере один раз |
| Закрытый эпик | `/delivery-stats` показывает стоимость работы по эпику |

`/to-pull-requests` и `/to-guide` не запускаются автоматически: их вызывает человек.

## Команды coordinator

```bash
python3 .harness/orchestration/coordinator.py --repo . batch list --open --ticket '#102'
python3 .harness/orchestration/coordinator.py --repo . batch decision-packet --batch <batch-id>
python3 .harness/orchestration/coordinator.py --repo . dispatch status --batch <batch-id> --stale-after 3600
python3 .harness/orchestration/coordinator.py --repo . ledger validate --full
```

`batch decision-packet` собирает компактные доказательства для approval, `dispatch status` показывает,
живы ли роли, `ledger validate` проверяет целостность аудиторской цепочки. Все три команды
только читают состояние.

## Дальше

- [«/fast-implement»](fast-implement.md)
- [QA gate и Release Gate](qa-gate.md)
- [Примеры](examples.md)
