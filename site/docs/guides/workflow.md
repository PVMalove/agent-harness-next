# Рабочий поток {#workflow-guide}

Выбери маршрут по состоянию задачи. После реализации агент проверяет результат и публикует
issue-ветку. Открытие PR требует отдельного подтверждения, merge выполняет человек.

## С чего начать {#entries}

- **Есть баг или небольшой тикет.** Запусти `/triage`, чтобы уточнить требования, блокеры и режим работы.
  Для тикета `afk` с меткой `pipeline::fast` используй [/fast-implement](fast-implement.md).
- **Есть идея или требования ещё неясны.** Начни с [/grilling](../skills/grilling.md).
  В существующем репозитории [/grill-with-docs](../skills/grill-with-docs.md) также записывает договорённости.
- **Работа большая и путь ещё не выбран.** [/wayfinder](../skills/wayfinder.md) помогает разобрать решения
  по сессиям. После согласования передай результат в `/to-spec`.
- **Есть готовая спецификация.** `/to-tickets` разбивает её на независимые проверяемые задачи.

Если маршрут непонятен, [/ask-matt](../skills/ask-matt.md) поможет выбрать точку входа.

## Этапы и результат {#steps}

1. **Проработать идею.** Согласовать цель, границы и открытые вопросы.
2. **Записать спецификацию.** `/to-spec` собирает договорённости и публикует их после согласования.
3. **Подготовить тикеты.** `/to-tickets` предлагает разбивку, зависимости и оценки до публикации.
4. **Реализовать и проверить.** `/implement` ведёт роли через гейты оркестрации;
   `/fast-implement` выполняет небольшую задачу в текущей сессии; `/to-guide` готовит инструкцию для человека.
5. **Подготовить PR.** После публикации ветки отдельно вызови `/to-pull-requests`.
   Агент проверяет ветку и доказательства QA, спрашивает разрешение открыть PR. Человек выполняет merge.

Готовый тикет не требует повторно проходить проектирование и спецификацию.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Какие команды ведут от каждой точки входа к merge и что пропускается.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/workflow-entries.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/workflow-entries.html" title="Точки входа и пять шагов рабочего потока" loading="lazy"></iframe>
</figure>

## Проработка идеи {#idea}

`/grill-me` подходит для обсуждения без репозитория. `/grill-with-docs` работает в существующем
проекте и сохраняет термины и решения. `/domain-modeling` помогает уточнить предметную область
в `CONTEXT.md`; ADR нужен для согласованного архитектурного выбора, который трудно отменить.

Результат этапа: согласованные цель, границы и решения, на которые сможет опереться `/to-spec`.
Подробные вопросы и правила находятся в [каталоге скиллов](../skills/index.md).

## Спецификация {#spec}

`/to-spec` использует уже обсуждённые требования. Спецификация описывает проблему, решение,
пользовательские сценарии, границы модулей, план тестирования, исключённый объём и integration-ветку.
Проверь эти решения перед публикацией. Существующую integration-ветку агент не сбрасывает.

## Тикеты {#tickets}

Каждый тикет должен давать проверяемый результат. Зависимость нужна, если работа требует результата
другого тикета; пересечение файлов само по себе не означает блокировку.

`/to-tickets` согласовывает разбивку и оценки, затем публикует задачи. Метки `pipeline::fast` и
`pipeline::full` определяют маршрут, `hitl` и `afk` определяют исполнителя. Готовая задача получает
`status::ready`, задача с открытым блокером получает `status::blocked`.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Как тикет проходит метки <code>status::ready</code>, <code>status::in-progress</code> и <code>status::blocked</code>.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/ticket-status.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/ticket-status.html" title="Метка состояния тикета" loading="lazy"></iframe>
</figure>

## Контекст для ролей {#discovery}

При включённой `backend-orchestration` coordinator готовит Context Package, то есть закреплённый
набор исходников, тестов и решений для роли. Перед отправкой роли он проверяет свежесть пакета.
Порядок настройки и запуска описан в [руководстве по оркестрации](../backend-orchestration.md).

## Следующий шаг {#next}

- [/implement](implement.md): работа с независимыми ролями и гейтами.
- [/fast-implement](fast-implement.md): небольшой тикет в одной сессии.
- [TDD](tdd.md), [ревью](code-review.md), [QA](qa-gate.md): как проверяется результат.
