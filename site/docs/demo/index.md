# Веб-консоль

TUI и браузер — клиенты одного Сервера консоли. Выберите экран — он откроется во встроенной
демонстрации.

<div class="ah-demo-switcher" role="group" aria-label="Экраны веб-консоли">
  <button class="ah-demo-tab" type="button" aria-pressed="false" data-screen="home">Главная</button>
  <button class="ah-demo-tab" type="button" aria-pressed="false" data-screen="board">Доска задач</button>
  <button class="ah-demo-tab" type="button" aria-pressed="false" data-screen="orchestration">Оркестрация</button>
  <button class="ah-demo-tab" type="button" aria-pressed="false" data-screen="reports">Отчёты</button>
</div>

<div class="ah-demo-empty" id="ah-demo-empty">
  <img src="../assets/mascot.svg" alt="Воксельный маскот Agent Harness Next" width="120" height="156">
  <p><b>Экран не выбран.</b> Нажмите «Главная», «Доска задач», «Оркестрация» или «Отчёты» —
    консоль откроется прямо на выбранном экране. Демонстрация не запускает команды и не меняет файлы.</p>
</div>

<iframe class="ah-demo" id="ah-demo-frame" title="Демонстрация веб-консоли" loading="lazy" hidden></iframe>

<p class="ah-demo-note">Данные демонстрационные: команды не выполняются, файлы не меняются.
  Если консоль не загрузилась, <a href="console.html" target="_blank" rel="noreferrer">откройте
  демонстрацию отдельной страницей</a>.</p>

<script>
  (function () {
    const frame = document.getElementById("ah-demo-frame");
    const empty = document.getElementById("ah-demo-empty");
    const tabs = Array.from(document.querySelectorAll(".ah-demo-switcher [data-screen]"));
    const available = new Set(tabs.map((tab) => tab.dataset.screen));
    function select(name) {
      const chosen = available.has(name);
      tabs.forEach((tab) => {
        const active = tab.dataset.screen === name;
        tab.setAttribute("aria-pressed", active ? "true" : "false");
      });
      empty.hidden = chosen;
      frame.hidden = !chosen;
      if (chosen) frame.src = "console.html#" + name;
      else frame.removeAttribute("src");
    }
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const name = tab.dataset.screen;
        history.replaceState(null, "", "#" + name);
        select(name);
      });
    });
    select(window.location.hash.replace(/^#/, ""));
  })();
</script>
