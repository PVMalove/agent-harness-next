# Веб-консоль

TUI и браузер — клиенты одного Сервера консоли. Ниже — интерактивная демонстрация: выберите
раздел в меню консоли, и описание и подробности в блоке под ней обновятся.

<div class="ah-demo-wrap">
  <iframe class="ah-demo" id="ah-demo-frame" src="console.html#home" title="Демонстрация веб-консоли" loading="lazy"></iframe>
</div>

<p class="ah-demo-note">Данные демонстрационные: команды не выполняются, файлы не меняются.
  Если консоль не загрузилась, <a href="console.html" target="_blank" rel="noreferrer">откройте
  демонстрацию отдельной страницей</a>.</p>

<div class="ah-demo-about" markdown="1">
<img class="ah-demo-about-mascot" src="../assets/mascot.svg" alt="Воксельный маскот Agent Harness Next" width="120" height="156">

<div class="ah-demo-about-current" aria-live="polite">
<p class="ah-demo-about-kicker">Текущий экран</p>
<p class="ah-demo-about-title" id="ah-demo-title">Главная</p>
<p class="ah-demo-about-text" id="ah-demo-text">Здоровье harness, runtime-store, скиллы, контекст проекта и последние задачи.</p>
</div>

## Что такое веб-консоль

Веб-консоль — браузерный клиент Сервера консоли. TUI и браузер показывают одни и те же
факты: состояние harness, задачи, оркестрацию, отчёты и восстановление. Консоль не заменяет
CLI и не принимает решения за человека: она читает состояние и показывает, что произошло и
что делать дальше.

### Что показывает

- здоровье harness и runtime-store: проверки, предупреждения, ошибки и пропуски;
- доску задач: спеки, колонки, блокеры, критерии приёмки и промпт тикета;
- ход работы агентов и оркестрацию: батчи, dispatch, QA lane и маршруты;
- отчёты ролей и evidence: что проверено, что осталось и где блокер;
- публикацию: candidate, Release Gate, preflight и черновик PR/MR;
- установку и runtime: версии, адаптеры, контейнеры и команды harness.

### Экраны

| Экран | Что показывает |
| --- | --- |
| Главная | Здоровье harness, runtime-store, скиллы, контекст проекта и последние задачи. |
| Диагностика | Проверки, пропуски, причины и команда исправления. |
| Обновление | Diff управляемых файлов, режимы, миграция runtime-store и конфликты. |
| Проект | Текущий проект, схема внедрения, план установки и проверки. |
| Доска задач | Спеки, колонки, карточки, блокеры и критерии приёмки. |
| Ход работы | Сессии агентов, маршрут и наблюдаемые события. |
| Оркестрация | Пайплайн, батчи, dispatch, QA lane и аналитика. |
| Отчёты | Отчёты ролей, evidence, качество и готовность к публикации. |
| Публикация | Candidate, Release Gate, preflight и черновик PR/MR. |
| Harness | Установка, runtime, адаптеры, контейнеры и команды. |
| Repo Map | Индекс символов и связей, файлы, символы и карта модулей. |
| Настройки | project.json, orchestration.json, мастер параметров и история. |
| Справка | Экраны, команды, горячие клавиши и границы консоли. |

### Как читать консоль

Слева — стабильные разделы, а роли и статусы — фильтры внутри «Хода работы» и «Оркестрации».
В шапке показано состояние соединения: `online` означает, что сервер отвечает, но не означает,
что все проверки пройдены. Пропущенная проверка не считается успешной.

Консоль read-only: она показывает факты и предлагает команды, но не выполняет их. Решения об
approve, повторном запуске, публикации и merge остаются за человеком.

### Границы демонстрации

- данные и события демонстрационные, совпадения с реальным проектом случайны;
- команды, approve, публикация и merge не выполняются;
- файлы, Git и `.harness` не читаются и не меняются;
- сетевое соединение не используется: все состояния переключаются в памяти.
</div>

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
