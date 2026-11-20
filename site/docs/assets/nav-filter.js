(function () {
  function init() {
    var en = document.documentElement.lang === "en";
    function words(ru, english) { return en ? english : ru; }
    function normalized(text) { return text.normalize("NFKC").toLocaleLowerCase().trim(); }
    document.querySelectorAll("[data-ah-directory]").forEach(function (root) {
      if (root.dataset.ahReady) return;
      root.dataset.ahReady = "true";
      var input = root.querySelector('input[type="search"]');
      var status = root.querySelector('[role="status"]');
      var rows = Array.from(root.querySelectorAll("[data-ah-entry]"));
      var groups = Array.from(root.querySelectorAll("[data-ah-group]"));
      var saved = new Map();
      function apply() {
        var query = normalized(input.value);
        var art = root.querySelector("[data-ah-directory-art]");
        if (art) art.hidden = Boolean(query);
        var count = 0;
        rows.forEach(function (row) {
          var names = row.textContent;
          var parent = row.parentElement;
          while (parent && parent !== root) {
            if (parent.matches("[data-ah-group]")) {
              var summary = parent.querySelector(":scope > summary");
              if (summary) names += " " + summary.textContent;
            }
            parent = parent.parentElement;
          }
          var match = !query || normalized(names).includes(query);
          row.hidden = !match;
          if (match) count++;
        });
        groups.slice().reverse().forEach(function (group) {
          var any = Array.from(group.querySelectorAll("[data-ah-entry]")).some(function (row) { return !row.hidden; });
          group.hidden = !any;
          if (group.tagName === "DETAILS" && query && any) {
            if (!saved.has(group)) saved.set(group, group.open);
            group.open = true;
          }
        });
        if (!query) {
          saved.forEach(function (open, group) { group.open = open; });
          saved.clear();
        }
        status.textContent = count ? words("Найдено: ", "Matches: ") + count : words("Ничего не найдено. Измени запрос.", "No matches. Change the query.");
      }
      input.addEventListener("input", apply);
      root.querySelector("form").addEventListener("submit", function (event) { event.preventDefault(); apply(); });
      root.querySelector("[data-ah-clear]").addEventListener("click", function () { input.value = ""; apply(); input.focus(); });
      apply();
    });
  }
  if (window.document$) window.document$.subscribe(init);
  else if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
