(function () {
  var LANG = document.documentElement.lang === "en" ? "en" : "ru";
  var EN = {
    "Скиллы": "Skills",
    "Фильтр навыков…": "Filter skills…",
    "Агенты": "Agents",
    "Фильтр агентов…": "Filter agents…",
    "Фильтр hooks…": "Filter hooks…"
  };
  function t(s) { return LANG === "en" && EN[s] ? EN[s] : s; }

  var SECTIONS = [
    { title: t("Скиллы"), placeholder: t("Фильтр навыков…") },
    { title: t("Агенты"), placeholder: t("Фильтр агентов…") },
    { title: "Hooks", placeholder: t("Фильтр hooks…") }
  ];

  function init() {
    var labels = Array.from(document.querySelectorAll(".md-sidebar--primary .md-nav__link"));
    labels.forEach(function (label) {
      var text = (label.textContent || "").trim();
      var section = SECTIONS.filter(function (entry) { return text.startsWith(entry.title); })[0];
      if (!section) return;
      var item = label.closest("li.md-nav__item");
      if (!item) return;
      var nav = item.querySelector(":scope > nav.md-nav");
      if (!nav || nav.querySelector(".ah-skill-filter")) return;
      var list = nav.querySelector(":scope > ul.md-nav__list");
      if (!list) return;

      var input = document.createElement("input");
      input.type = "search";
      input.className = "ah-skill-filter";
      input.placeholder = section.placeholder;
      input.setAttribute("aria-label", section.placeholder.replace("…", ""));
      nav.insertBefore(input, nav.firstChild);

      input.addEventListener("input", function () {
        var query = input.value.trim().toLowerCase();
        Array.from(list.children).forEach(function (row) {
          if (!row.matches("li")) return;
          var nested = row.querySelector(":scope > nav.md-nav");
          if (nested) {
            var children = Array.from(nested.querySelectorAll(":scope > ul.md-nav__list > li"));
            var any = false;
            children.forEach(function (child) {
              var match = !query || (child.textContent || "").toLowerCase().indexOf(query) !== -1;
              child.hidden = !match;
              if (match) any = true;
            });
            row.hidden = !any;
            if (query && any) {
              var toggle = row.querySelector(":scope > input.md-nav__toggle");
              if (toggle) toggle.checked = true;
            }
          } else {
            var match = !query || (row.textContent || "").toLowerCase().indexOf(query) !== -1;
            row.hidden = !match;
          }
        });
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
