# /implement

`/implement` — конвейер с явными гейтами и approval: реализацию пишут dispatched-роли, а сессия
координирует. Маршрут включается только capability `backend-orchestration`; без неё используйте
`/fast-implement`. Команда запускается вручную и в новой чистой сессии.

## Когда использовать

| Ситуация | Команда |
| --- | --- |
| Задача с независимыми границами или обязательной независимой проверкой | `/implement` |
| Мелкая задача, направление не обсуждается | `/fast-implement` |
| Реализацию выполняет человек по готовому руководству | `/to-guide` |

Маршрут строго связан с меткой тикета: тикеты `pipeline::fast` автоподбором пропускаются, а тикет,
названный явно, выполняется по полному циклу независимо от метки. Между ревью и QA нет
сокращённого пути — сокращённый путь называется `/fast-implement`.

## Pre-flight

1. **Блокеры.** Проверить, что у тикета нет открытых блокеров; иначе работа останавливается.
2. **Метка состояния.** Заменить текущую `status::*` на `status::in-progress` до создания ветки и
   правок и убедиться, что она единственная.
3. **Integration ref.** Взять ветку из раздела тикета `## Integration Branch`, а если его нет — из
   родительского эпика или из `base_branch` проекта.
4. **Issue-worktree.** Создать worktree тикета от integration-ветки: `batch create` отказывается
   работать с worktree, которого нет в `git worktree list`.
5. **Scope.** Выполнить `batch preflight` с теми же флагами, что пойдут в `batch create`, включая
   `--allowed-path` и пункты Definition of Done. Требование TDD записывается отдельным пунктом DoD.

## Гейты

| Гейт | Что происходит | Решение | Артефакт |
| --- | --- | --- | --- |
| architect | План: шов, границы, порядок правок | по `approval_policy` | принятый architect-отчёт |
| developer | Реализация по плану, тесты до кода | по `approval_policy` | candidate commit |
| code-review | Две оси, Standards и Spec, независимо | по `approval_policy` | отчёт review по обеим осям |
| qa | Полный прогон на закреплённом кандидате, Release Gate | по `approval_policy` | QA evidence для SHA |
| publish | Принятый SHA объявляется опубликованным | по `approval_policy` | запись публикации |

Порядок жёсткий: coordinator отклоняет `dispatch create --role developer`, пока у batch нет принятого
architect-отчёта. Политика approval задаётся в конфигурации оркестрации: гейты можно проходить
вручную, а можно разрешить автоматическое принятие по политике `approval_policy: auto` — при этом
список остановок (целостность, бюджет, маршрут восстановления) остаётся закрытым и обходится только
человеком.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Пять гейтов конвейера. Схема показывает ручной вариант согласования.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/implement-gates.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/implement-gates.html" title="/implement: гейты и approval" loading="lazy"></iframe>
</figure>

## Гибридный контракт публикации

Это строго opt-in маршрут: он включается только выбранной capability, и никакая другая сборка его
не активирует. Developer создаёт candidate commit; отчёт о работе остаётся `reported` до решения
по `approval_policy`. Принятый SHA публикует только developer через publish, после чего человек отдельно вызывает
`/to-pull-requests`. Агент открывает PR только после явного подтверждения. Команда `integration next` называет следующий шаг по записи интеграции.
Adapter лишь транспортирует уже утверждённое: он не решает, что публиковать, и не открывает PR.

## Живость и восстановление

- **Model self-report.** Первым действием роль подтверждает активную модель. Расхождение с моделью
  из brief переводит dispatch в `blocked`, и отчёт не принимается.
- **Heartbeat и watchdog.** Роль шлёт heartbeat, а coordinator опрашивает статус; молчащий dispatch
  выносится человеку как блокер.
- **Ранний blocked-отчёт.** Developer может сообщить о блокере до коммита, указав маршрут
  восстановления; координатор не выдумывает коммит за него.
- **Остановка и отмена — решение человека.** `batch resume-stop` ставит и снимает паузу,
  `batch rewind` возвращает batch к предыдущему шагу, `batch abandon` закрывает тупиковый batch.
  Все три требуют approval и причины.
- **Человеческий след не правится.** Состояние в `.harness/orchestration/state/` читается только
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
| После publish | `/to-pull-requests` — PR и wrap-up: проверка ветки, тело PR, закрытие тикета |
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

`batch decision-packet` собирает компактные доказательства для approval, `dispatch status` показывает
живость ролей, `ledger validate` проверяет целостность аудиторской цепочки. Все три команды
read-only.

## Дальше

- [«/fast-implement»](fast-implement.md)
- [QA gate и Release Gate](qa-gate.md)
- [Примеры](examples.md)
