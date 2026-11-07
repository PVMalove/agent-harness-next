(function () {
  function countLeaves(node) {
    var nested = node.querySelectorAll(":scope > nav.md-nav > ul.md-nav__list li.md-nav__item");
    var total = 0;
    nested.forEach(function (item) {
      if (!item.classList.contains("md-nav__item--nested")) total += 1;
    });
    return total;
  }

  function init() {
    var sidebar = document.querySelector(".md-sidebar--primary");
    if (!sidebar) return;
    sidebar.querySelectorAll("li.md-nav__item--nested").forEach(function (item) {
      var row = item.querySelector(":scope > .md-nav__container") || item.querySelector(":scope > .md-nav__link");
      if (!row || row.querySelector(".ah-nav-count")) return;
      var total = countLeaves(item);
      if (!total) return;
      var badge = document.createElement("span");
      badge.className = "ah-nav-count";
      badge.textContent = String(total);
      badge.setAttribute("aria-hidden", "true");
      row.appendChild(badge);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
