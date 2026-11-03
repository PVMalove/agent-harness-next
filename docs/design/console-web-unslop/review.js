/* Local design comparison only. No command runner, backend, credentials or writes. */
(() => {
  "use strict";
  const screen = document.querySelector("#screen");
  const mode = document.querySelector("#mode");
  const width = document.querySelector("#width");
  const before = document.querySelector("#before");
  const after = document.querySelector("#after");
  const status = document.querySelector("#review-status");
  const grid = document.querySelector(".review-grid");
  const pages = new Set([...screen.options].map(option => option.value));
  const routes = ["home", "open-project", "update-harness", "diagnostics", "harness", "orchestration", "reports", "repo-map", "configuration", "help"];
  const names = new Map([...screen.options].map(option => [option.textContent.replace(/^\d · /, ""), option.value]));
  let revision = 0;

  // This function runs only inside the sandboxed, generated review frame.
  function frameInteractions() {
    const dialog = document.createElement("dialog");
    dialog.className = "preview-dialog";
    dialog.innerHTML = '<h2></h2><p>Это просмотр макета. Команда не запускалась, данные проекта не менялись. Состояния и подтверждения из исходника доступны в примерах под экраном.</p><button class="btn" autofocus>Вернуться к макету</button>';
    document.body.append(dialog);
    let initiator;
    dialog.querySelector("button").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => initiator?.focus());
    document.addEventListener("click", event => {
      const target = event.target.closest("[data-screen], [data-example-action], .preview-menu");
      if (!target) return;
      if (target.dataset.screen) {
        event.preventDefault();
        parent.postMessage({type: "console-preview:navigate", screen: target.dataset.screen}, "*");
      } else if (target.classList.contains("preview-menu")) {
        const app = target.closest(".app");
        const expanded = app.classList.toggle("nav-open");
        target.setAttribute("aria-expanded", String(expanded));
        if (expanded) app.querySelector("nav a")?.focus();
      } else if (!target.disabled) {
        event.preventDefault();
        initiator = target;
        dialog.querySelector("h2").textContent = target.textContent.trim();
        dialog.showModal();
      }
    });
    document.addEventListener("keydown", event => {
      if (event.key !== "Escape" || dialog.open) return;
      const app = document.querySelector(".app.nav-open");
      if (app) {
        app.classList.remove("nav-open");
        const toggle = app.querySelector(".preview-menu");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  async function read(path) {
    const response = await fetch(path);
    if (!response.ok) throw new Error(`Не удалось прочитать ${path}: HTTP ${response.status}`);
    return response.text();
  }
  const styles = Promise.all([read("../console-mockups/console.css"), read("web-polish.css")]);
  // Handle a file:// opening immediately; the same failure is shown again on selection.
  styles.catch(() => {});

  function buttonFrom(element) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = element.className;
    if (!element.classList.contains("btn")) button.classList.add("preview-text-action");
    button.innerHTML = element.innerHTML;
    button.dataset.exampleAction = "true";
    if (element.matches(".dis, .off, .lockd")) {
      button.disabled = true;
      button.title = "Действие недоступно в показанном состоянии; причина приведена рядом";
    }
    element.replaceWith(button);
    return button;
  }

  function prepare(source, shared, polish, page) {
    const doc = new DOMParser().parseFromString(source, "text/html");
    doc.body.dataset.screen = page;
    doc.querySelectorAll("script,link[rel=stylesheet]").forEach(node => node.remove());
    const baseStyle = doc.createElement("style");
    baseStyle.textContent = shared;
    doc.head.prepend(baseStyle);
    const polishStyle = doc.createElement("style");
    polishStyle.textContent = polish;
    doc.head.append(polishStyle);

    for (const narrow of doc.querySelectorAll(".app.narrow")) {
      if (narrow.previousElementSibling?.classList.contains("caption")) narrow.previousElementSibling.remove();
      narrow.remove();
    }
    const primary = doc.querySelector(".app");
    if (primary?.previousElementSibling?.classList.contains("caption")) primary.previousElementSibling.remove();

    // Keep existing state examples, but reveal them on demand below the primary screen.
    for (const element of [...doc.body.children]) {
      if (element === primary || !element.matches(".sheet, .app.wide, .legend")) continue;
      const caption = element.previousElementSibling?.matches(".caption") ? element.previousElementSibling : null;
      const details = doc.createElement("details");
      details.className = "preview-example";
      const summary = doc.createElement("summary");
      summary.textContent = caption?.querySelector("b")?.textContent || element.querySelector("h3")?.textContent || "Примечания исходного макета";
      element.before(details);
      details.append(summary);
      if (caption) details.append(caption);
      details.append(element);
    }

    for (const nav of doc.querySelectorAll("nav")) {
      nav.setAttribute("aria-label", "Разделы консоли");
      for (const anchor of nav.querySelectorAll("a")) {
        const index = Number(anchor.querySelector("i")?.textContent);
        if (Number.isInteger(index) && routes[index]) {
          anchor.href = `#${routes[index]}`;
          anchor.dataset.screen = routes[index];
          anchor.classList.toggle("on", routes[index] === page);
          if (routes[index] === page) anchor.setAttribute("aria-current", "page");
        }
      }
      const toggle = doc.createElement("button");
      toggle.type = "button";
      toggle.className = "preview-menu";
      toggle.textContent = "Меню";
      toggle.setAttribute("aria-expanded", "false");
      nav.id = `menu-${[...doc.querySelectorAll("nav")].indexOf(nav)}`;
      toggle.setAttribute("aria-controls", nav.id);
      nav.closest(".app")?.querySelector(".brand")?.prepend(toggle);
    }

    for (const anchor of [...doc.querySelectorAll("a:not(nav a)")]) {
      const text = anchor.textContent.trim();
      let route = names.get(text);
      if (/^Открыть восстановление/.test(text)) route = "recovery";
      if (/^Контейнерный (запуск)?\s*→/.test(text)) route = "container-route";
      if (/^Обновить Harness\s*[2→]/.test(text)) route = "update-harness";
      if (/^Открыть настройку/.test(text)) route = "configuration";
      if (route) {
        anchor.href = `#${route}`;
        anchor.dataset.screen = route;
      } else {
        buttonFrom(anchor);
      }
    }
    doc.querySelectorAll(".card.fold").forEach(element => buttonFrom(element));
    // Do not pretend that a drawn caret is an editable, persisted configuration form.
    doc.querySelectorAll(".input").forEach(element => {
      element.setAttribute("role", "note");
      element.setAttribute("aria-label", "Демонстрационное поле исходного макета");
    });

    if (page === "open-project" || page === "update-harness") {
      const note = doc.createElement("p");
      note.className = "note";
      note.textContent = page === "open-project"
        ? "Сравнение оформления исторического мастера. По ADR 0028 веб-консоль не переключает проект: итоговый веб-экран покажет кандидатов и команду запуска отдельной консоли. Этот мастер не реализуется в браузере."
        : "Сравнение оформления. По ADR 0028 закрытие вкладки не останавливает job; исторический запрет выхода в примерах ниже не является правилом веб-консоли.";
      primary.querySelector(".page")?.prepend(note);
    }

    const script = doc.createElement("script");
    script.textContent = `(${frameInteractions.toString()})();`;
    doc.body.append(script);
    return "<!doctype html>" + doc.documentElement.outerHTML;
  }

  async function show(page) {
    if (!pages.has(page)) return;
    const request = ++revision;
    screen.value = page;
    history.replaceState(null, "", `#${page}`);
    status.textContent = "Загрузка макета…";
    before.src = `../console-mockups/${page}.html`;
    try {
      const [source, [shared, polish]] = await Promise.all([read(`../console-mockups/${page}.html`), styles]);
      if (request !== revision) return;
      after.srcdoc = prepare(source, shared, polish, page);
      status.textContent = "Демонстрационные данные · оригиналы сохранены";
    } catch (error) {
      if (request !== revision) return;
      after.srcdoc = "<!doctype html><html lang=ru><meta charset=utf-8><p>Макет не загружен. Откройте сравнение через локальный HTTP-сервер по инструкции README.</p></html>";
      status.textContent = error.message;
    }
  }
  document.querySelector("form").addEventListener("submit", event => event.preventDefault());
  screen.addEventListener("change", () => show(screen.value));
  mode.addEventListener("change", () => { grid.dataset.mode = mode.value; });
  width.addEventListener("change", () => {
    grid.style.setProperty("--frame-width", width.value === "auto" ? "100%" : `${width.value}px`);
  });
  window.addEventListener("message", event => {
    if (event.source === after.contentWindow && event.data?.type === "console-preview:navigate" && pages.has(event.data.screen)) show(event.data.screen);
  });
  show(pages.has(location.hash.slice(1)) ? location.hash.slice(1) : "home");
})();
