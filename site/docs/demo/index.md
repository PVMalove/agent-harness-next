# Веб-консоль

TUI и браузер — клиенты одного Сервера консоли. Ниже — интерактивная демонстрация: выберите
раздел в меню консоли, и описание под ней обновится.

<div class="ah-demo-wide">
  <iframe class="ah-demo" id="ah-demo-frame" src="console.html#home" title="Демонстрация веб-консоли" loading="lazy"></iframe>
  <section class="ah-demo-about" aria-live="polite">
    <img src="../assets/mascot.svg" alt="Воксельный маскот Agent Harness Next" width="120" height="156">
    <div>
      <h2 id="ah-demo-title">Главная</h2>
      <p id="ah-demo-text">Здоровье harness, runtime-store, скиллы, контекст проекта и последние задачи.</p>
    </div>
  </section>
</div>

<p class="ah-demo-note">Данные демонстрационные: команды не выполняются, файлы не меняются.
  Если консоль не загрузилась, <a href="console.html" target="_blank" rel="noreferrer">откройте
  демонстрацию отдельной страницей</a>.</p>

<script>
  (function () {
    const frame = document.getElementById("ah-demo-frame");
    const title = document.getElementById("ah-demo-title");
    const text = document.getElementById("ah-demo-text");
    const screens = {
      home: ["Главная", "Здоровье harness, runtime-store, скиллы, контекст проекта и последние задачи."],
      diagnostics: ["Диагностика", "Проверки: что проверено, что пропущено, причины и команда исправления."],
      "update-harness": ["Обновление", "Diff управляемых файлов, режимы обновления, миграция runtime-store и конфликты."],
      "open-project": ["Проект", "Текущий проект, список проектов, схема внедрения, план установки и проверки."],
      board: ["Доска задач", "Спеки, колонки, карточки, блокеры, критерии приёмки и промпт тикета."],
      "agent-activity": ["Ход работы", "Сессии агентов, фильтры по роли и статусу, маршрут и наблюдаемые события."],
      orchestration: ["Оркестрация", "Пайплайн, батчи, dispatch, QA lane и аналитика оркестрации."],
      reports: ["Отчёты", "Отчёты ролей, evidence, качество и готовность к публикации."],
      publish: ["Публикация", "Candidate, Release Gate, preflight, черновик PR/MR и evidence."],
      harness: ["Harness", "Установка, runtime, адаптеры, контейнеры и команды harness."],
      "repo-map": ["Repo Map", "Индекс символов и связей, файлы, символы и карта модулей."],
      configuration: ["Настройки", "project.json, orchestration.json, мастер параметров и история изменений."],
      help: ["Справка", "Экраны, команды, горячие клавиши и границы консоли."]
    };
    let bound = false;

    function update(name) {
      const entry = screens[name] || ["Веб-консоль", "Выберите раздел в меню консоли — описание появится здесь."];
      title.textContent = entry[0];
      text.textContent = entry[1];
    }

    function bind() {
      if (bound || !frame.contentWindow) return;
      bound = true;
      const sync = () => {
        const route = frame.contentWindow.location.hash.slice(1).split("?")[0] || "home";
        update(route);
      };
      frame.contentWindow.addEventListener("hashchange", sync);
      sync();
    }

    frame.addEventListener("load", bind);
    if (frame.contentDocument && frame.contentDocument.readyState === "complete") bind();
  })();
</script>
