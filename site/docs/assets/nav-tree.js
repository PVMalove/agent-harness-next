(function () {
  var expandedGroups = {};

  function closeDrawer() {
    var drawer = document.getElementById("__drawer");
    if (!drawer) return;
    drawer.checked = false;
    drawer.dispatchEvent(new Event("change", { bubbles: true }));
    var trigger = document.querySelector('.md-header label[for="__drawer"]');
    if (trigger) trigger.focus();
  }

  document.addEventListener("change", function (event) {
    if (event.target.id !== "__drawer") return;
    var trigger = document.querySelector('.md-header label[for="__drawer"]');
    var close = document.querySelector(".ah-nav-close");
    if (trigger) trigger.setAttribute("aria-expanded", String(event.target.checked));
    if (close) {
      close.disabled = !event.target.checked;
      if (event.target.checked && window.matchMedia("(max-width: 76.234em)").matches) {
        window.requestAnimationFrame(function () {
          if (event.target.checked && close.isConnected) close.focus();
        });
      }
    }
  });

  document.addEventListener("keydown", function (event) {
    var trigger = event.target.closest('.md-header label[for="__drawer"]');
    if (trigger && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      event.stopPropagation();
      trigger.click();
    } else if (event.key === "Escape" && window.matchMedia("(max-width: 76.234em)").matches) {
      var drawer = document.getElementById("__drawer");
      if (drawer && drawer.checked) {
        event.preventDefault();
        closeDrawer();
      }
    }
  }, true);

  // Match stable page routes so RU and EN use the same Material pictograms.
  function pageIcon(link, base) {
    var path = new URL(link.href).pathname;
    if (path === base) return "home";
    var topics = [
      [/\/secrets\//, "key-variant"],
      [/\/integrations\//, "connection"],
      [/\/environment\//, "console"],
      [/\/container\//, "docker"],
      [/\/test-author\//, "test-tube"],
      [/\/orchestration\/roles\//, "account-group"],
      [/\/orchestration\/policies\//, "shield-check"],
      [/\/orchestration\/access\//, "lock"],
      [/verification|qa-gate|\/qa\//, "check-decagram"],
      [/database|migration/, "database"],
      [/diagnos|troubleshoot/, "bug"],
      [/research|ask-matt|wayfinder/, "magnify"],
      [/\/settings\/project\//, "tune-variant"],
      [/\/skills\//, "puzzle"],
      [/\/agents\//, "account-cog"],
      [/\/hooks\//, "hook"],
      [/\/architecture\/|\/diagrams\//, "sitemap"],
      [/\/guides\//, "code-tags"],
      [/\/reference\//, "book-open-page-variant"],
      [/\/concepts\//, "lightbulb-on"],
      [/\/project\//, "source-branch"],
      [/\/releases\//, "tag"],
      [/\/demo\//, "monitor-dashboard"],
      [/\/getting-started\//, "rocket-launch"]
    ];
    var topic = topics.find(function (entry) { return entry[0].test(path); });
    return topic ? topic[1] : "book-open-page-variant";
  }

  function pageLink(item) {
    return item.querySelector(":scope > .md-nav__container > a.md-nav__link, :scope > a.md-nav__link");
  }

  function countPages(item) {
    // Active pages may contain a secondary table of contents, which is not a page group.
    if (!item.classList.contains("md-nav__item--nested")) return 0;
    var list = item.querySelector(":scope > nav.md-nav > ul.md-nav__list");
    if (!list) return 0;
    return Array.from(list.children).reduce(function (total, child) {
      return total + (pageLink(child) ? 1 : 0) + countPages(child);
    }, 0);
  }

  function init() {
    // Language changes reload localized header/search strings; page changes stay instant.
    var languages = Array.from(document.querySelectorAll("a[data-ah-language-base]"));
    var currentPath = new URL(document.URL).pathname;
    var bases = languages.map(function (link) { return new URL(link.dataset.ahLanguageBase, document.URL).pathname; });
    var base = bases.slice().sort(function (a, b) { return b.length - a.length; }).find(function (value) { return currentPath.startsWith(value); });
    if (base) languages.forEach(function (link) {
      link.href = new URL(link.dataset.ahLanguageBase, document.URL).pathname + currentPath.slice(base.length);
    });
    var english = document.documentElement.lang === "en";
    var sidebar = document.querySelector(".md-sidebar--primary");
    if (!sidebar) return;
    var drawer = document.getElementById("__drawer");
    var trigger = document.querySelector('.md-header label[for="__drawer"]');
    if (drawer && trigger) {
      if (!sidebar.id) sidebar.id = "ah-nav-primary";
      trigger.setAttribute("role", "button");
      trigger.setAttribute("tabindex", "0");
      trigger.setAttribute("aria-label", english ? "Open navigation" : "Открыть меню");
      trigger.setAttribute("aria-controls", sidebar.id);
      trigger.setAttribute("aria-expanded", String(drawer.checked));
      if (!sidebar.querySelector(".ah-nav-close")) {
        var close = document.createElement("button");
        close.type = "button";
        close.className = "ah-nav-close";
        close.textContent = "×";
        close.setAttribute("aria-label", english ? "Close navigation" : "Закрыть меню");
        close.disabled = !drawer.checked;
        close.addEventListener("click", closeDrawer);
        (sidebar.querySelector(".md-nav--primary") || sidebar).prepend(close);
      }
    }
    sidebar.querySelectorAll(".md-nav__item:not(.md-nav__item--nested) > a.md-nav__link").forEach(function (link) {
      if (link.closest(".md-nav--secondary")) return;
      var icon = "var(--ah-nav-icon-" + pageIcon(link, base) + ")";
      link.classList.add("ah-nav-page");
      link.style.setProperty("--ah-nav-page", icon);
      // Material shows a separate TOC label for the active page in the drawer.
      var mobileLabel = link.parentElement.querySelector(":scope > label[for='__toc']");
      if (mobileLabel) {
        mobileLabel.classList.add("ah-nav-page");
        mobileLabel.style.setProperty("--ah-nav-page", icon);
      }
    });
    var catalog = Array.from(sidebar.querySelectorAll("li.md-nav__item--nested")).find(function (item) {
      var link = pageLink(item);
      return link && new URL(link.href).pathname.endsWith("/reference/translations/");
    });
    sidebar.querySelectorAll("li.md-nav__item--nested").forEach(function (item) {
      if (item.classList.contains("ah-nav-enhanced")) return;
      var checkbox = item.querySelector(":scope > input.md-nav__toggle");
      var nav = item.querySelector(":scope > nav.md-nav");
      var original = item.querySelector(":scope > .md-nav__container") || item.querySelector(":scope > label.md-nav__link");
      if (!checkbox || !nav || !original) return;
      var link = pageLink(item);
      // An explicit collapse must override Material's active-page defaults too.
      if (Object.prototype.hasOwnProperty.call(expandedGroups, checkbox.id)) {
        checkbox.checked = expandedGroups[checkbox.id];
      } else {
        checkbox.checked = !catalog || !catalog.contains(item) || item.classList.contains("md-nav__item--active");
      }
      var title = (link ? link.textContent : original.textContent).trim();
      var total = countPages(item);
      var row = document.createElement("div");
      row.className = "md-nav__link md-nav__container ah-nav-row";
      var button = document.createElement("button");
      button.type = "button";
      button.className = "ah-nav-toggle";
      button.id = checkbox.id + "_folder";
      if (!nav.id) nav.id = checkbox.id + "_children";
      button.setAttribute("aria-controls", nav.id);
      if (link) {
        row.appendChild(button);
        var titleSpan = link.querySelector(".md-ellipsis");
        if (titleSpan && /^[a-z0-9_-]+\.json$/i.test(title)) {
          var dot = title.lastIndexOf(".");
          titleSpan.replaceChildren(document.createTextNode(title.slice(0, dot)), document.createElement("wbr"), document.createTextNode(title.slice(dot)));
        }
        row.appendChild(link);
        if (!link.id) link.id = checkbox.id + "_page";
        nav.setAttribute("aria-labelledby", link.id);
      } else {
        button.classList.add("ah-nav-toggle--title");
        var caption = document.createElement("span");
        caption.textContent = title;
        button.appendChild(caption);
        row.appendChild(button);
        nav.removeAttribute("aria-labelledby");
        nav.setAttribute("aria-label", title);
      }
      var badge = document.createElement("span");
      badge.className = "ah-nav-count";
      badge.textContent = String(total);
      badge.setAttribute("aria-hidden", "true");
      row.appendChild(badge);
      var description = document.createElement("span");
      description.className = "ah-nav-description";
      description.id = checkbox.id + "_count";
      description.textContent = (english ? "Descendant pages: " : "Дочерних страниц: ") + total;
      row.appendChild(description);
      button.setAttribute("aria-describedby", description.id);
      original.replaceWith(row);
      item.classList.add("ah-nav-enhanced");
      function sync() {
        button.setAttribute("aria-expanded", String(checkbox.checked));
        button.setAttribute("aria-label", (checkbox.checked ? (english ? "Collapse " : "Свернуть ") : (english ? "Expand " : "Развернуть ")) + title);
        nav.setAttribute("aria-expanded", String(checkbox.checked));
      }
      button.addEventListener("click", function () {
        checkbox.checked = !checkbox.checked;
        expandedGroups[checkbox.id] = checkbox.checked;
        checkbox.dispatchEvent(new Event("change", { bubbles: true }));
        sync();
      });
      checkbox.addEventListener("change", sync);
      sync();
    });
  }

  if (window.document$) window.document$.subscribe(init);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
