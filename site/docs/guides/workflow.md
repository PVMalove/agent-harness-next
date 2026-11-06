# Рабочий поток {#workflow-guide}

Harness ведёт работу от идеи до merge по пяти шагам. Не каждая задача проходит все пять: точка
входа определяет, какие шаги пропускаются совсем, а какие выполняются один раз для целого эпика.

## Пять шагов {#steps}

### Точки входа {#entries}

<div class="ah-scenarios" role="radiogroup" aria-label="Точка входа в рабочий поток">
  <button class="ah-scenario is-active" type="button" data-scenario="full" role="radio" aria-checked="true" tabindex="0">
    <span class="ah-scenario-kicker">Сценарий</span>
    <b>Все этапы (Полный цикл)</b>
    <span class="ah-scenario-desc">Идея → спецификация → тикеты → реализация → публикация. Ничего не пропускается.</span>
    <span class="ah-scenario-skip">Пропускается: ничего</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="single" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">1</span>
    <b>Один тикет извне (Баг / Малая фича)</b>
    <span class="ah-scenario-desc">Баг-репорт или небольшая фича, объём укладывается в одну сессию. <code>/triage</code> доводит issue до <code>status::ready</code> и режима <code>hitl</code>/<code>afk</code>, дальше один шаг реализации.</span>
    <span class="ah-scenario-skip">Пропускается: проектирование, спецификация, декомпозиция</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="epic" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">2</span>
    <b>Задача масштаба эпика (Состав известен)</b>
    <span class="ah-scenario-desc">Состав работ известен, нужна декомпозиция. Прорабатывается за одну сессию, затем <code>/to-spec</code> → <code>/to-tickets</code> → реализация по каждому тикету.</span>
    <span class="ah-scenario-skip">Пропускается: Wayfinder</span>
  </button>
  <button class="ah-scenario" type="button" data-scenario="large" role="radio" aria-checked="false" tabindex="-1">
    <span class="ah-scenario-kicker">3</span>
    <b>Крупный объём (Неопределённый путь)</b>
    <span class="ah-scenario-desc"><code>/wayfinder</code> ведёт карту решений, пока не останутся открытые вопросы, затем передаёт работу <code>/to-spec</code>. Работа идёт сессиями.</span>
    <span class="ah-scenario-skip">Пропускается: ничего</span>
  </button>
</div>

<div class="ah-route">
  <span class="ah-route-label">Маршрут</span>
  <span class="ah-route-flow" id="ah-workflow-route" aria-live="polite">
    <a class="ah-command" href="#idea">/grilling</a><span class="ah-route-or">или</span><a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>
  </span>
</div>

<ol class="ah-pipeline" aria-label="Пять шагов рабочего потока">
  <li class="ah-step is-active" data-step="design">
    <span class="ah-step-num" aria-hidden="true">01</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Проектирование</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>Снимается неопределённость, фиксируются решения и границы.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Кто ведёт</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#idea" title="Проработка идеи: ядро этапа">/grilling</a>
      <a class="ah-command" href="#idea" title="Проработка идеи в существующем репозитории">/grill-with-docs</a>
      <a class="ah-command" href="../../skills/wayfinder/" data-command="wayfinder" title="Wayfinder: карта решений для крупного объёма">/wayfinder</a>
    </div>
      <span class="ah-wayfinder-note" id="ah-wayfinder-note" hidden>Wayfinder не нужен: состав работ уже известен</span>
    </div>
  </li>
  <li class="ah-step is-active" data-step="spec">
    <span class="ah-step-num" aria-hidden="true">02</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Спецификация</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>Обсуждение становится единым источником правды и публикуется в трекер.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Кто ведёт</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#spec" title="Спецификация: /to-spec">/to-spec</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="tickets">
    <span class="ah-step-num" aria-hidden="true">03</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Тикеты</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>Спецификация режется на вертикальные слайсы со связями блокировки.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Кто ведёт</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="#tickets" title="Декомпозиция: /to-tickets">/to-tickets</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="implementation">
    <span class="ah-step-num" aria-hidden="true">04</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Реализация</h3><span class="ah-step-skip" hidden>SKIPPED</span></div>
      <p>Тест первым, реализация, независимое ревью, QA.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Кто ведёт</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="../implement/" title="Полный маршрут реализации">/implement</a>
      <a class="ah-command" href="../fast-implement/" title="Короткий маршрут реализации">/fast-implement</a>
      <a class="ah-command" href="../../skills/to-guide/" title="Руководство для человека на маршруте hitl">/to-guide</a>
    </div>
    </div>
  </li>
  <li class="ah-step is-active" data-step="publish">
    <span class="ah-step-num" aria-hidden="true">05</span>
    <div class="ah-step-body">
      <div class="ah-step-head"><h3>Публикация</h3><span class="ah-step-guard">merge — человек</span></div>
      <p>PR в integration-ветку, merge руками человека, закрытие тикета.</p>
    </div>
    <div class="ah-step-side">
      <span class="ah-step-label">Кто ведёт</span>
      <div class="ah-step-commands">
      <a class="ah-command" href="../../skills/to-pull-requests/" title="Подготовка PR и передача человеку">/to-pull-requests</a>
    </div>
    </div>
  </li>
</ol>

<div class="ah-guardrail" role="note">
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 3l8 4v5c0 5-3.4 8-8 9-4.6-1-8-4-8-9V7l8-4Z"></path><path d="M9 12h6M12 9v6"></path></svg>
  <div><b>Merge всегда выполняет человек.</b> Ни один шаг не открывает и не мержит PR сам.</div>
</div>

<div class="ah-askmatt">
  <span class="ah-askmatt-icon" aria-hidden="true">?</span>
  <div>
    <b>Не уверены, с какого шага начать?</b> Запустите
    <a class="ah-command" href="../../skills/ask-matt/">/ask-matt</a> — агент определит точку входа
    для issue или сложного бага. Он описывает основной путь, входы для входящих issue и трудных
    багов, и ветки вне этой схемы.
  </div>
</div>

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Какие команды ведут от каждой точки входа к merge и что пропускается.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/workflow-entries.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/workflow-entries.html" title="Точки входа и пять шагов рабочего потока" loading="lazy"></iframe>
</figure>

## Проработка идеи {#idea}

<div class="ah-tool-grid">
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grilling</code><span class="ah-tool-tag">Ядро этапа</span></header>
    <p><code>/grilling</code> — ядро этапа: агент моделирует план как дерево решений и задаёт вопросы по фронтиру,
      то есть только те, чьи предпосылки уже закрыты. Каждый раунд начинается с краткой сводки того, что
      устоялось. Когда фронтир пуст, агент показывает сводку решений и спрашивает подтверждение, после
      чего работа переходит к <code>/to-spec</code>.</p>
    <footer class="ah-tool-foot"><b>Артефакты:</b> сводка решений; передача в <code>/to-spec</code>.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grill-me</code><span class="ah-tool-tag">С нуля без репо</span></header>
    <p><code>/grill-me</code> — тонкая обёртка для проектирования с нуля, когда репозитория ещё нет в игре. После неё
      остаётся сводка решений.</p>
    <footer class="ah-tool-foot"><b>Артефакты:</b> сводка решений.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/grill-with-docs</code><span class="ah-tool-tag">Предпочтительно для проекта</span></header>
    <p><code>/grill-with-docs</code> — та же оболочка для работы в существующем репозитории. Она предпочтительна,
      потому что параллельно ведёт глоссарий и архитектурные решения.</p>
    <footer class="ah-tool-foot"><b>Артефакты:</b> глоссарий + ADR.</footer>
  </article>
  <article class="ah-tool-card">
    <header class="ah-tool-head"><code>/domain-modeling</code><span class="ah-tool-tag">Усиление домена</span></header>
    <p><code>/domain-modeling</code> усиливает проектирование в существующем коде: сверяет термины с глоссарием,
      уточняет размытые понятия, проверяет утверждения по коду и сразу записывает договорённости в
      <code>CONTEXT.md</code>. Архитектурное решение предлагается только тогда, когда оно труднообратимо,
      неочевидно без контекста и было реальным выбором между альтернативами.</p>
    <footer class="ah-tool-foot"><b>Артефакты:</b> <code>CONTEXT.md</code>; ADR для труднообратимого решения.</footer>
  </article>
</div>

## Спецификация {#spec}

<code>/to-spec</code> не интервьюирует повторно: он синтезирует уже обсуждённое. Сначала исследуются словарь
домена и решения затрагиваемой области, намечаются швы (seams) — точки, где фича будет
тестироваться, и предлагается имя integration-ветки. Дальше спецификация записывается файлом и
публикуется в трекер; публикация не передаёт тело inline, а читает его из файла.

Что содержит спецификация:

<div class="ah-blueprint">
  <div class="ah-blueprint-row"><code>Problem Statement</code><span>в чём проблема</span><span class="ah-badge">Контекст</span></div>
  <div class="ah-blueprint-row"><code>Solution</code><span>что меняется</span><span class="ah-badge">Решение</span></div>
  <div class="ah-blueprint-row"><code>User Stories</code><span>что нужно пользователю и зачем</span><span class="ah-badge">Пользователь</span></div>
  <div class="ah-blueprint-row"><code>Implementation Decisions</code><span>модули, интерфейсы и решения, без путей к коду</span><span class="ah-badge">Архитектура</span></div>
  <div class="ah-blueprint-row"><code>Testing Decisions</code><span>какие швы проверяются и на каком уровне</span><span class="ah-badge ah-badge--primary">Seams</span></div>
  <div class="ah-blueprint-row"><code>Out of Scope</code><span>что явно не входит в работу</span><span class="ah-badge ah-badge--warn">Guardrail</span></div>
  <div class="ah-blueprint-row"><code>Integration Branch</code><span>точное имя ветки, в которую пойдёт работа</span><span class="ah-badge">Ветка</span></div>
</div>

!!! warning "Важно для контроля агента"

    Раздел Out of Scope ограничивает объём: без явного запрета агент склонен добавить попутное
    кэширование или правку инфраструктуры. После публикации integration-ветка создаётся от базовой
    ветки проекта; существующую ветку никто не сбрасывает и не удаляет.

## Декомпозиция {#tickets}

`/to-tickets` превращает спецификацию в тикеты — вертикальные слайсы, каждый из которых проверяется
независимо и помещается в одно свежее контекстное окно. До явного одобрения разбивки ничего не
публикуется: агент показывает слайсы, рёбра блокировки и оценку, а затем уточняет их по замечаниям.

- Слайс — не слой. Тикет, который «добавляет слой», не проверяется отдельно.
- Блокировка ставится за зависимость по результату, а не за пересечение файлов.
- Оценка в story points по шкале Фибоначчи даёт метку маршрута: `pipeline::fast` для мелкого
  объёма, `pipeline::full` для значимого.
- Режим исполнения `hitl` или `afk` решает, кто реализует тикет: человек по руководству или агент.

Тикет получает метку состояния `status::ready`, а если он ждёт другой тикет того же пакета —
`status::blocked`. Блокировка снимается только подтверждённым merge и закрытием предшественника.

<figure class="ah-diagram">
  <div class="ah-diagram-bar">
    <figcaption>Как тикет проходит метки <code>status::ready</code>, <code>status::in-progress</code> и <code>status::blocked</code>.</figcaption>
    <button class="ah-diagram-expand" type="button" aria-haspopup="dialog">Развернуть</button>
    <a class="ah-diagram-open" href="../../assets/diagrams/ticket-status.html" target="_blank" rel="noopener">Открыть отдельно ↗</a>
  </div>
  <iframe class="ah-diagram-frame" data-theme-sync src="../../assets/diagrams/ticket-status.html" title="Метка состояния тикета" loading="lazy"></iframe>
</figure>

## Оркестрация Discovery Pipeline {#discovery}

Одобренные на проектировании пути фиксируются как часть договорённости, сохраняются в спецификации
и назначаются конкретным тикетам. Перед реализацией из этих путей, тестов и решений собирается
Context Package — детерминированный набор данных для ролей одного batch. Coordinator регистрирует
пакет в ledger и сверяет его свежесть по хешам источников перед каждым dispatch.

Подробнее об устройстве runtime и хранилища — в [обзоре архитектуры](../architecture/overview.md).

## Дальше {#next}

- [«/implement»](implement.md)
- [«/fast-implement»](fast-implement.md)
- [Обзор архитектуры](../architecture/overview.md)

<script>
  (function () {
    const scenarios = {
      full: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "both",
        route: '<a class="ah-command" href="#idea">/grilling</a><span class="ah-route-or">или</span><a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>'
      },
      single: {
        active: ["implementation", "publish"],
        skipped: ["design", "spec", "tickets"],
        wayfinder: "none",
        route: '<a class="ah-command" href="../../skills/triage/">/triage</a><span class="ah-route-arrow">→</span><code class="ah-status-pill">status::ready</code><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-or">или</span><a class="ah-command" href="../fast-implement/">/fast-implement</a><span class="ah-route-or">/</span><a class="ah-command" href="../../skills/to-guide/">/to-guide</a>'
      },
      epic: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "skip",
        route: '<a class="ah-command" href="#idea">/grilling</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-skip">Wayfinder — SKIPPED</span>'
      },
      large: {
        active: ["design", "spec", "tickets", "implementation", "publish"],
        skipped: [],
        wayfinder: "yes",
        route: '<a class="ah-command" href="../../skills/wayfinder/">/wayfinder</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#spec">/to-spec</a><span class="ah-route-arrow">→</span><a class="ah-command" href="#tickets">/to-tickets</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../implement/">/implement</a><span class="ah-route-arrow">→</span><a class="ah-command" href="../../skills/to-pull-requests/">/to-pull-requests</a>'
      }
    };
    const buttons = Array.from(document.querySelectorAll("[data-scenario]"));
    const steps = Array.from(document.querySelectorAll("[data-step]"));
    const route = document.getElementById("ah-workflow-route");
    const wayfinder = document.querySelector("[data-command='wayfinder']");
    const wayfinderNote = document.getElementById("ah-wayfinder-note");

    function select(name, focus) {
      const scenario = scenarios[name];
      if (!scenario) return;
      buttons.forEach((button) => {
        const active = button.dataset.scenario === name;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-checked", active ? "true" : "false");
        button.tabIndex = active ? 0 : -1;
        if (active && focus) button.focus();
      });
      steps.forEach((step) => {
        const id = step.dataset.step;
        const skipped = scenario.skipped.includes(id);
        step.classList.toggle("is-active", scenario.active.includes(id));
        step.classList.toggle("is-skipped", skipped);
        const badge = step.querySelector(".ah-step-skip");
        if (badge) badge.hidden = !skipped;
      });
      if (wayfinder) {
        wayfinder.classList.toggle("is-skipped", scenario.wayfinder === "skip");
      }
      wayfinderNote.hidden = scenario.wayfinder !== "skip";
      route.innerHTML = scenario.route;
      animate(scenario);
    }

    const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pipeline = document.querySelector(".ah-pipeline");
    const scenarioGrid = document.querySelector(".ah-scenarios");
    const pulse = document.createElement("span");
    pulse.className = "ah-rail-pulse";
    pulse.setAttribute("aria-hidden", "true");
    pipeline.appendChild(pulse);
    let pulseAnimation = null;

    function restart(element, index) {
      element.style.setProperty("--i", index);
      element.classList.remove("is-entering");
      void element.offsetWidth;
      element.classList.add("is-entering");
    }

    function animate(scenario) {
      if (reduced) return;
      let n = 0;
      steps.forEach((step) => {
        if (scenario.active.includes(step.dataset.step)) restart(step, n++);
      });
      Array.from(route.children).forEach((child, i) => child.style.setProperty("--i", i));
      route.classList.remove("is-entering");
      void route.offsetWidth;
      route.classList.add("is-entering");
      movePulse(scenario);
    }

    function movePulse(scenario) {
      if (pulseAnimation) pulseAnimation.cancel();
      const active = steps.filter((step) => scenario.active.includes(step.dataset.step));
      if (active.length < 2 || !pulse.animate) { pulse.style.opacity = "0"; return; }
      const center = (step) => step.offsetTop + step.querySelector(".ah-step-num").offsetTop + 16 - 5;
      const from = center(active[0]);
      const to = center(active[active.length - 1]);
      pulseAnimation = pulse.animate([
        { transform: "translateY(" + from + "px)", opacity: 0 },
        { opacity: 1, offset: 0.12 },
        { opacity: 1, offset: 0.88 },
        { transform: "translateY(" + to + "px)", opacity: 0 }
      ], { duration: 400 + active.length * 520, iterations: Infinity, easing: "ease-in-out" });
    }

    if (!reduced && "IntersectionObserver" in window) {
      scenarioGrid.classList.add("is-motion");
      Array.from(scenarioGrid.children).forEach((card, i) => card.style.setProperty("--i", i));
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          scenarioGrid.classList.add("is-visible");
          observer.disconnect();
        });
      }, { threshold: 0.15 });
      observer.observe(scenarioGrid);
    }

    function remember(name) {
      try {
        const url = new URL(window.location.href);
        if (name === "full") url.searchParams.delete("scenario");
        else url.searchParams.set("scenario", name);
        window.history.replaceState(null, "", url);
      } catch (error) { /* адрес не обязателен для работы переключателя */ }
    }

    buttons.forEach((button, index) => {
      button.addEventListener("click", () => {
        select(button.dataset.scenario);
        remember(button.dataset.scenario);
      });
      button.addEventListener("keydown", (event) => {
        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];
        if (!step && event.key !== "Home" && event.key !== "End") return;
        event.preventDefault();
        const next = event.key === "Home" ? 0
          : event.key === "End" ? buttons.length - 1
          : (index + step + buttons.length) % buttons.length;
        select(buttons[next].dataset.scenario, true);
        remember(buttons[next].dataset.scenario);
      });
    });
    const requested = new URLSearchParams(window.location.search).get("scenario");
    select(scenarios[requested] ? requested : "full");
  })();
</script>
