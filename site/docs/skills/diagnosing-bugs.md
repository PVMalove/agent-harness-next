# diagnosing-bugs: диагностика ошибок

Источник: [`SKILL.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/SKILL.md).
В `engineering-suite` этот first-party override сохраняет upstream-цикл диагностики. От upstream он
отличается такими правками:

- добавлен шаг поиска по памяти проекта;
- из фазы построения цикла обратной связи убран призыв «Be aggressive. Be creative. Refuse to give
  up.»;
- описание называет границу со `/tdd`: диагностика ищет причину через красный цикл обратной связи, а
  `/tdd` берут, когда причина уже известна;
- в `SKILL.md` остаётся первый способ построить цикл, падающий тест. Остальные способы по порядку,
  ветки для нестабильного бага и для регрессии производительности вынесены в
  [`references/feedback-loops.md`](https://github.com/PVMalove/agent-harness-next/blob/master/skills/first-party/engineering/diagnosing-bugs/references/feedback-loops.md).
  Агент читает его, если падающий тест не даёт красного цикла;
- исправление применяется в issue-ветке тикета по правилу Issue First из `.claude/rules/git-delivery.md`.

Если память проекта включена, интерактивная сессия после фиксации симптома и до ранжирования гипотез
один раз выполняет `harness memory search . "<симптом, ошибка и модуль>"`, чтобы найти прошлые фиксы.
Если внешнего CLI нет, сессия использует установленный entry point из общего контракта.
Указатели помогают предложить гипотезу, но причину по-прежнему доказывает воспроизведение.
Если память выключена или недоступна, диагностика идёт обычным порядком.

Общий контракт [`project-memory.md`](https://github.com/PVMalove/agent-harness-next/blob/master/harness/project/instructions/project-memory.md) разделяет статус
поиска и статус источника. При `ok` и `stale_sources` можно рассматривать возвращённые указатели.
Источники со статусом `historical`, `unknown` и неподтверждённые требуют проверки, а superseded
исключаются. Источник открывают только при необходимости, сверяют его hash и считают недоверенным
свидетельством. Автоматического rebuild нет. В dispatch роли оркестрации поиск не вызывают: они
работают с Context Package и сообщают координатору, если свидетельств не хватает.

`mattpocock-suite` по-прежнему поставляет неизменённый
[vendor-снапшот](https://github.com/PVMalove/agent-harness-next/blob/master/skills/vendor/mattpocock/engineering/diagnosing-bugs/SKILL.md).
