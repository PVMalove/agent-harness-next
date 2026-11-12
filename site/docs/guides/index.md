# Руководства

Выберите маршрут для задачи или найдите главу по названию. Установка и настройки проекта — в разделе [Начало](../getting-started/index.md), переводы скиллов, hooks и агентов — в [Справочнике](../reference/index.md).

<div data-ah-directory>
  <div class="ah-ref-glossary">
    <div class="ah-ref-glossary-head">
      <div>
        <b>Все руководства</b>
        <span>Главы по маршрутам, командам и темам. Поиск фильтрует карточки ниже.</span>
      </div>
    </div>
    <form class="ah-ref-glossary-search" role="search">
      <input type="search" aria-label="Найти главу руководства" placeholder="Найти главу: implement, QA, worktree…" autocomplete="off" spellcheck="false">
      <button type="submit">Найти</button>
      <button type="button" data-ah-clear>Сбросить</button>
    </form>
    <p role="status" aria-live="polite"></p>
  </div>

  <section data-ah-group>
    <h2>Работа над задачей</h2>
    <div class="ah-cards ah-cards--four">
      <a class="ah-card" data-ah-entry href="workflow/">
        <span class="i">→</span>
        <b>Рабочий поток</b>
        <span>Выбор маршрута по состоянию задачи: этапы, артефакты и следующий шаг.</span>
      </a>
      <a class="ah-card" data-ah-entry href="implement/">
        <span class="i">⌘</span>
        <b>/implement</b>
        <span>Полный маршрут: спецификация, тикеты, роли, гейты и PR.</span>
      </a>
      <a class="ah-card" data-ah-entry href="fast-implement/">
        <span class="i">⚡</span>
        <b>/fast-implement</b>
        <span>Небольшой тикет в текущей сессии без отдельного batch.</span>
      </a>
      <a class="ah-card" data-ah-entry href="tdd/">
        <span class="i">✓</span>
        <b>TDD</b>
        <span>Красный-зелёный-рефакторинг и независимые ожидания.</span>
      </a>
      <a class="ah-card" data-ah-entry href="code-review/">
        <span class="i">◇</span>
        <b>Code review</b>
        <span>Ревью по стандартам и спецификации до QA.</span>
      </a>
      <a class="ah-card" data-ah-entry href="qa-gate/">
        <span class="i">◈</span>
        <b>QA gate и Release Gate</b>
        <span>Локальный QA, clean-room проверка и публикация.</span>
      </a>
      <a class="ah-card" data-ah-entry href="examples/">
        <span class="i">▣</span>
        <b>Примеры целиком</b>
        <span>Сквозные сценарии на конкретных задачах.</span>
      </a>
      <a class="ah-card" data-ah-entry href="troubleshooting/">
        <span class="i">⌁</span>
        <b>Troubleshooting</b>
        <span>Причины отказов и следующие действия.</span>
      </a>
      <a class="ah-card" data-ah-entry href="upgrade-2-0/">
        <span class="i">⇪</span>
        <b>Миграция на 2.0</b>
        <span>Обновление с 1.x, migrate и откат.</span>
      </a>
    </div>
  </section>

  <section data-ah-group>
    <h2>Оркестрация и концепции</h2>
    <div class="ah-cards ah-cards--four">
      <a class="ah-card" data-ah-entry href="../harness-guide/">
        <span class="i">✦</span>
        <b>Как устроен Harness</b>
        <span>Возможности, роли, проверки и границы harness.</span>
      </a>
      <a class="ah-card" data-ah-entry href="../backend-orchestration/">
        <span class="i">⊕</span>
        <b>Оркестрация</b>
        <span>Настройка, запуск, отчёты, чистый QA и восстановление.</span>
      </a>
      <a class="ah-card" data-ah-entry href="../console-configuration/">
        <span class="i">⌂</span>
        <b>Настройка в консоли</b>
        <span>Черновик, версии и применение конфигурации.</span>
      </a>
      <div class="ah-card" data-ah-entry>
        <span class="i">◫</span>
        <b>Концепции</b>
        <span>Hooks, worktrees и управление контекстом.</span>
        <span class="ah-card-links">
          <a href="../concepts/hooks/">Hooks</a>
          <a href="../concepts/worktrees/">Worktrees</a>
          <a href="../concepts/context/">Контекст</a>
        </span>
      </div>
    </div>
  </section>

  <div data-ah-directory-art>
    <p class="ah-core-hint">Полный маршрут от идеи к PR. Выберите этап для пояснения.</p>
    <div class="ah-flow" id="ah-guide-diagram"><div class="ah-core-flow" id="ah-guide-flow"></div><div class="ah-flow-note" id="ah-guide-note" aria-live="polite"></div></div>
  </div>
</div>
