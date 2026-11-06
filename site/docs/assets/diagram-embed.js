(function () {
  function theme() {
    var scheme = document.body.getAttribute("data-md-color-scheme");
    return scheme === "default" ? "light" : "dark";
  }

  var COMPACT_CSS = [
    "html,body{overflow:hidden!important}",
    "body{min-height:0!important;padding:6px 12px!important}",
    ".container{max-width:none!important}",
    ".toolbar{top:4px!important;right:12px!important}",
    ".header{display:flex!important;align-items:center;min-height:48px;margin:0 0 2px!important;padding:0!important}",
    ".header-row{flex:1 1 0;min-width:0;max-width:calc(100% - 436px);margin:0!important}",
    ".header h1{flex:1 1 0;min-width:0;margin:0!important;overflow:hidden;font-size:15px!important;line-height:1.3!important;text-overflow:ellipsis;white-space:nowrap}",
    ".subtitle,.cards{display:none!important}",
    ".diagram-container{padding:4px 6px 56px!important;overflow:visible!important}",
    ".diagram-container>svg{min-width:0!important}",
    "@media (max-width:720px){.header{display:none!important}.container{padding-top:48px}}"
  ].join("\n");

  var SKIP = { defs: 1, title: 1, desc: 1, style: 1, script: 1 };

  function crop(svg) {
    var vb = svg.viewBox.baseVal;
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    Array.prototype.forEach.call(svg.children, function (child) {
      if (SKIP[child.tagName]) return;
      var box;
      try { box = child.getBBox(); } catch (error) { return; }
      if (!box.width && !box.height) return;
      // фоновая подложка на весь холст рамку не задаёт
      if (child.tagName === "rect" && !child.getAttribute("class") && Math.abs(box.width - vb.width) < 2) return;
      x0 = Math.min(x0, box.x); y0 = Math.min(y0, box.y);
      x1 = Math.max(x1, box.x + box.width); y1 = Math.max(y1, box.y + box.height);
    });
    if (x1 > x0 && y1 > y0) {
      svg.setAttribute("viewBox", [x0 - 14, y0 - 14, x1 - x0 + 28, y1 - y0 + 28].map(Math.round).join(" "));
    }
  }

  // archify прижимает узлы к рамкам полос на 8-12px; даём воздух по краям и снизу
  function pad(svg) {
    if (svg.hasAttribute("data-ah-padded")) return;
    var X = 16;
    var Y = 10;
    var frames = svg.querySelectorAll('rect[data-graph-role="structural-frame"]');
    Array.prototype.forEach.call(frames, function (rect) {
      var cls = rect.getAttribute("class") || "";
      var grow = /lane/.test(cls) ? 1 : 0.5;
      var x = parseFloat(rect.getAttribute("x"));
      var w = parseFloat(rect.getAttribute("width"));
      var h = parseFloat(rect.getAttribute("height"));
      rect.setAttribute("x", x - X * grow);
      rect.setAttribute("width", w + 2 * X * grow);
      rect.setAttribute("height", h + Y * grow);
      var label = rect.nextElementSibling;
      if (label && label.tagName === "text") {
        label.setAttribute("x", parseFloat(label.getAttribute("x")) - X * grow);
      }
    });
    svg.setAttribute("data-ah-padded", "");
  }

  function compact(doc) {
    if (doc.documentElement.hasAttribute("data-ah-compact")) return;
    var style = doc.createElement("style");
    style.textContent = COMPACT_CSS;
    doc.head.appendChild(style);
    var svg = doc.querySelector(".diagram-container > svg");
    if (svg) { pad(svg); crop(svg); }
    doc.documentElement.setAttribute("data-ah-compact", "");
  }

  function fit(frame) {
    try {
      var doc = frame.contentDocument;
      var box = doc.querySelector(".container");
      var cs = doc.defaultView.getComputedStyle(doc.body);
      var height = box
        ? Math.ceil(box.getBoundingClientRect().bottom + parseFloat(cs.paddingBottom || 0) + 2)
        : doc.documentElement.scrollHeight;
      if (height > 0) frame.style.height = height + "px";
    } catch (error) { /* ignore */ }
  }

  // высота рамки следует за реальным размером содержимого схемы
  function watch(frame, doc) {
    if (frame.__ahWatched || !doc.defaultView || !doc.defaultView.ResizeObserver) return;
    var target = doc.querySelector(".container") || doc.body;
    new doc.defaultView.ResizeObserver(function () { fit(frame); }).observe(target);
    frame.__ahWatched = true;
  }

  function apply(frame) {
    try {
      var doc = frame.contentDocument;
      if (!doc || !doc.documentElement) return;
      doc.documentElement.setAttribute("data-theme", theme());
      if (frame.classList.contains("ah-diagram-modal-frame")) {
        var big = doc.querySelector(".diagram-container > svg");
        if (big) pad(big);
        return;
      }
      compact(doc);
      watch(frame, doc);
      window.requestAnimationFrame(function () { fit(frame); });
      window.setTimeout(function () { fit(frame); }, 400);
      window.setTimeout(function () { fit(frame); }, 1500);
    } catch (error) { /* кросс-доменная рамка: остаётся высота из CSS */ }
  }

  var modal = null;

  function ensureModal() {
    if (modal) return modal;
    var dialog = document.createElement("dialog");
    dialog.className = "ah-diagram-modal";
    dialog.setAttribute("aria-label", "Схема на весь экран");
    dialog.innerHTML =
      '<div class="ah-diagram-modal-bar"><span class="ah-diagram-modal-title"></span>' +
      '<button type="button" class="ah-diagram-modal-close" aria-label="Закрыть">×</button></div>' +
      '<iframe class="ah-diagram-modal-frame" title=""></iframe>';
    document.body.appendChild(dialog);
    var frame = dialog.querySelector("iframe");
    frame.addEventListener("load", function () {
      try { frame.contentDocument.documentElement.setAttribute("data-theme", theme()); } catch (error) { /* ignore */ }
    });
    dialog.querySelector(".ah-diagram-modal-close").addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", function () { frame.removeAttribute("src"); });
    modal = { dialog: dialog, frame: frame, title: dialog.querySelector(".ah-diagram-modal-title") };
    return modal;
  }

  function expand(figure) {
    var source = figure.querySelector(".ah-diagram-frame");
    var m = ensureModal();
    m.title.textContent = source.getAttribute("title") || "";
    m.frame.setAttribute("title", source.getAttribute("title") || "");
    m.frame.setAttribute("src", source.getAttribute("src"));
    m.dialog.showModal();
  }

  function init() {
    Array.prototype.forEach.call(document.querySelectorAll(".ah-diagram .ah-diagram-expand"), function (button) {
      button.addEventListener("click", function () { expand(button.closest(".ah-diagram")); });
    });
    var frames = Array.prototype.slice.call(document.querySelectorAll(".ah-diagram-frame[data-theme-sync]"));
    frames.forEach(function (frame) {
      frame.addEventListener("load", function () { apply(frame); });
      if (frame.contentDocument && frame.contentDocument.readyState === "complete") apply(frame);
    });
    if (window.ResizeObserver) {
      var ro = new ResizeObserver(function (entries) {
        entries.forEach(function (entry) {
          var frame = entry.target;
          window.requestAnimationFrame(function () { fit(frame); });
        });
      });
      frames.forEach(function (frame) { ro.observe(frame); });
    }
    new MutationObserver(function () {
      frames.forEach(apply);
      if (modal && modal.dialog.open) apply(modal.frame);
    })
      .observe(document.body, { attributes: true, attributeFilter: ["data-md-color-scheme"] });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
