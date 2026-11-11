/* Agent Harness Next — docs site mockup behavior. No external dependencies. */
(function () {
  "use strict";

  const root = document.documentElement;
  const THEME_KEY = "ah-theme";

  function applyTheme(theme) {
    root.dataset.theme = theme;
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const dark = theme === "dark";
      button.setAttribute("aria-label", dark ? "Включить светлую тему" : "Включить тёмную тему");
      button.setAttribute("title", dark ? "Светлая тема" : "Тёмная тема");
      const icon = button.querySelector("[data-theme-icon]");
      if (icon) icon.textContent = dark ? "☀" : "☾";
    });
  }

  function storedTheme() {
    try {
      return localStorage.getItem(THEME_KEY);
    } catch (error) {
      return null;
    }
  }

  applyTheme(storedTheme() || "dark");

  document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const next = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch (error) {
        /* localStorage can be disabled; the theme still changes in memory. */
      }
    });
  });

  // Mobile docs sidebar.
  const sidebar = document.querySelector(".docs-side");
  document.querySelectorAll("[data-sidebar-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      if (!sidebar) return;
      const open = sidebar.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
    });
  });
  if (sidebar) {
    sidebar.addEventListener("click", (event) => {
      if (event.target.closest("a")) sidebar.classList.remove("open");
    });
  }

  // Copy buttons inside code blocks.
  document.querySelectorAll(".doc-content pre, .copyable").forEach((block) => {
    if (block.querySelector(":scope > .copy")) return;
    const code = block.querySelector("code") || block;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy";
    button.textContent = "Копировать";
    button.addEventListener("click", async () => {
      const text = code.innerText;
      try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Скопировано";
      } catch (error) {
        const range = document.createRange();
        range.selectNodeContents(code);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        button.textContent = "Выделено";
      }
      window.setTimeout(() => (button.textContent = "Копировать"), 1600);
    });
    block.appendChild(button);
  });

  // Copy the install command from the hero.
  document.querySelectorAll(".install .copy").forEach((button) => {
    button.addEventListener("click", async () => {
      const code = button.parentElement.querySelector("code");
      if (!code) return;
      try {
        await navigator.clipboard.writeText(code.textContent);
        button.setAttribute("aria-label", "Скопировано");
        button.setAttribute("title", "Скопировано");
      } catch (error) {
        button.setAttribute("aria-label", "Не удалось скопировать");
      }
      window.setTimeout(() => {
        button.setAttribute("aria-label", "Скопировать команду");
        button.setAttribute("title", "Скопировать");
      }, 1600);
    });
  });

  // Table of contents: mark the heading that is currently in view.
  const tocLinks = Array.from(document.querySelectorAll(".toc a[href^='#']"));
  if (tocLinks.length) {
    const targets = tocLinks
      .map((link) => document.getElementById(link.getAttribute("href").slice(1)))
      .filter(Boolean);
    const byId = new Map();
    tocLinks.forEach((link) => byId.set(link.getAttribute("href").slice(1), link));
    if ("IntersectionObserver" in window && targets.length) {
      const observer = new IntersectionObserver(
        (entries) => {
          const visible = entries
            .filter((entry) => entry.isIntersecting)
            .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
          if (!visible.length) return;
          tocLinks.forEach((link) => link.classList.remove("active"));
          const active = byId.get(visible[0].target.id);
          if (active) active.classList.add("active");
        },
        { rootMargin: "-90px 0px -65% 0px", threshold: [0, 1] }
      );
      targets.forEach((target) => observer.observe(target));
    }
  }

  // Search modal.
  const searchIndex = [
    { title: "Обзор Agent Harness Next", path: "index.html", group: "Начало", text: "портативный harness оркестрация агентов Rust runtime" },
    { title: "Установка", path: "docs.html", group: "Начало", text: "install-global init health quick start установка" },
    { title: "Быстрый старт", path: "docs.html#quick-start", group: "Начало", text: "быстрый старт harness init capability engineering-suite" },
    { title: "Архитектура", path: "architecture.html", group: "Архитектура", text: "Python policy Rust runtime SQLite WAL supervisor IPC" },
    { title: "Rust runtime", path: "architecture.html#runtime", group: "Архитектура", text: "harness-runtime supervisor OCI reconcile" },
    { title: "Runtime store", path: "architecture.html#store", group: "Архитектура", text: "SQLite WAL ledger version 4 AUTHORITY audit" },
    { title: "Веб-консоль", path: "demo.html", group: "Демо", text: "console web FastAPI React TUI demo" },
    { title: "Hooks", path: "docs.html#hooks", group: "Концепции", text: "minimal standard strict hook policy guards" },
    { title: "Verification", path: "docs.html#verification", group: "Концепции", text: "ChangeImpact VerificationPlan failed-only clean-room QA" },
    { title: "Release Gate", path: "docs.html#release-gate", group: "Руководства", text: "candidate target tree sha evidence publish" },
    { title: "CLI", path: "docs.html#cli", group: "Справочник", text: "harness init adopt update health diff list cleanup uninstall" }
  ];

  const modal = document.createElement("div");
  modal.className = "search-modal";
  modal.id = "search-modal";
  modal.innerHTML = `
    <div class="search-panel" role="dialog" aria-modal="true" aria-label="Поиск по документации">
      <div class="search-input">
        <span aria-hidden="true">⌕</span>
        <input id="search-input" type="search" placeholder="Поиск по документации…" autocomplete="off" spellcheck="false">
        <kbd>esc</kbd>
      </div>
      <div class="search-results" id="search-results"></div>
      <div class="search-foot"><span>↑↓ выбрать</span><span>↵ открыть</span><span>esc закрыть</span></div>
    </div>`;
  document.body.appendChild(modal);

  const input = modal.querySelector("#search-input");
  const results = modal.querySelector("#search-results");
  let selected = 0;
  let current = searchIndex;

  function renderResults(items, query) {
    if (!items.length) {
      results.innerHTML = `<div class="search-empty">Ничего не найдено${query ? ` по запросу «${escapeHtml(query)}»` : ""}.</div>`;
      return;
    }
    results.innerHTML = items
      .map(
        (item, index) => `
        <a class="search-result" href="${item.path}" data-index="${index}" ${index === selected ? 'aria-selected="true"' : ""}>
          <div class="r-title">${escapeHtml(item.title)}</div>
          <div class="r-path">${escapeHtml(item.group)} · ${escapeHtml(item.path)}</div>
        </a>`
      )
      .join("");
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[char]);
  }

  function search(query) {
    const q = query.trim().toLowerCase();
    if (!q) return searchIndex;
    return searchIndex.filter((item) =>
      `${item.title} ${item.group} ${item.text} ${item.path}`.toLowerCase().includes(q)
    );
  }

  function openSearch() {
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
    input.value = "";
    selected = 0;
    current = searchIndex;
    renderResults(current, "");
    window.setTimeout(() => input.focus(), 20);
  }

  function closeSearch() {
    modal.classList.remove("open");
    document.body.style.overflow = "";
  }

  document.querySelectorAll("[data-search-open]").forEach((button) => {
    button.addEventListener("click", openSearch);
  });

  input.addEventListener("input", () => {
    selected = 0;
    current = search(input.value);
    renderResults(current, input.value);
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      selected = Math.min(selected + 1, Math.max(current.length - 1, 0));
      renderResults(current, input.value);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      selected = Math.max(selected - 1, 0);
      renderResults(current, input.value);
    } else if (event.key === "Enter") {
      const item = current[selected];
      if (item) {
        event.preventDefault();
        window.location.href = item.path;
      }
    }
  });

  modal.addEventListener("click", (event) => {
    if (event.target === modal) closeSearch();
  });

  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openSearch();
    } else if (event.key === "/" && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      event.preventDefault();
      openSearch();
    } else if (event.key === "Escape" && modal.classList.contains("open")) {
      closeSearch();
    }
  });

  // Demo iframe fallback: if it cannot load, show a link to the prototype.
  document.querySelectorAll("[data-demo-frame]").forEach((frame) => {
    frame.addEventListener("error", () => {
      const fallback = frame.parentElement.querySelector(".demo-fallback");
      if (fallback) fallback.hidden = false;
    });
  });
})();
