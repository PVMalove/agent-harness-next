(function () {
  function mount(host, note) {
  var NS = "http://www.w3.org/2000/svg";
  var W = 1120;
  var H = 576;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var nodes = {};
  var edges = [];

  function node(id, kind, x, y, w, h, label, sub, title, text) {
    nodes[id] = { id: id, kind: kind, x: x, y: y, w: w, h: h, cx: x + w / 2, cy: y + h / 2,
      label: label, sub: sub, title: title, text: text };
  }

  /* --- данные ------------------------------------------------------------ */
  node("g-install", "machine", 40, 24, 300, 64, "install-global.py", "--runtime claude · --runtime codex",
    "Глобальный слой", "Ставится один раз на машину: минимальный профиль инструкций и скиллы start-project и integrate-project. --check показывает статус без записи. MCP, модели, плагины, credentials и permissions установщик не трогает.");
  node("g-profile", "machine", 390, 24, 300, 64, "Глобальный профиль", "минимум инструкций агента",
    "Глобальный профиль", "Минимальный профиль инструкций для Claude Code и Codex. Параметр --runtime повторяемый, поэтому один запуск настраивает оба.");
  node("g-skills", "machine", 740, 24, 300, 64, "start-project · integrate-project", "скиллы входа",
    "Скиллы входа", "start-project удобнее для нового проекта, integrate-project — для существующего: он сначала изучает соглашения репозитория, а потом встраивает harness.");

  var capY = [164, 234, 304, 374];
  var caps = [
    ["project-foundation", "project-foundation", "5 скиллов · по умолчанию", "Доменно-нейтральная база по умолчанию: дизайн, research, handoff, язык проекта."],
    ["mattpocock-suite", "mattpocock-suite", "25 скиллов · pinned upstream", "Полный upstream-набор, закреплённый на проверенном коммите."],
    ["engineering-suite", "engineering-suite", "расширяет mattpocock-suite", "Инженерный workflow: эпики и тикеты, триаж, двухосевое review, qa-gate, подготовка PR."],
    ["backend-orchestration", "backend-orchestration", "расширяет engineering-suite", "Поверх engineering-suite: coordinator, роли, briefs, worktrees, ledger и QA lane."]
  ];
  caps.forEach(function (c, i) {
    node(c[0], "cap", 46, capY[i], 238, 56, c[1], c[2], c[1], c[3] + " Сборки взаимоисключающие: состав snapshot задаёт выбранная capability.");
  });

  node("init", "command", 352, 210, 196, 64, "init", "новый проект · --capability",
    "init", "Прямая установка в Git-репозиторий: --capability, --project-type, --stack, --base-branch, --language, --qa-gate-command.");
  node("adopt", "command", 352, 330, 196, 64, "adopt", "уже есть свои скиллы",
    "adopt", "Сохраняет всё, что не входит в выбранную capability, и падает со списком конфликтов. --replace-conflicts заменяет конфликтующие каталоги без backup, поэтому сначала проверьте список.");

  var snap = [
    ["s-skills", ".harness/skills/", "пакеты выбранной сборки", ".harness/skills/", "Пакеты выбранной сборки: независимая поставка в проект. Исходный клон harness во время работы не нужен."],
    ["s-lock", "harness.lock", "snapshot и provenance", "harness.lock", "Фиксирует snapshot и provenance; по нему diff находит расхождения, а update сохраняет локальные правки."],
    ["s-reg", "REGISTRY.md", "индекс скиллов", "REGISTRY.md", "Индекс установленного набора; им пользуются, когда native discovery недоступен."],
    ["s-conf", ".harness/project.json", "язык, ветка, QA-команды", ".harness/project.json", "Язык проекта, base branch, шаблон ветки и команды проверок qa_gate_commands."],
    ["s-roots", "Native skill roots", ".claude/skills · .agents/skills", "Native skill roots", "Claude Code и Codex находят один и тот же snapshot через свои native skill roots."],
    ["s-hooks", "hook-policy.json", "профиль hooks", "hook-policy.json", "Сгенерированная политика hooks проекта: профили задают предупреждения и повторы, критические guards не ослабляются."]
  ];
  snap.forEach(function (s, i) {
    node(s[0], "snap", i % 2 === 0 ? 620 : 868, 164 + Math.floor(i / 2) * 84, 224, 60, s[1], s[2], s[3], s[4]);
  });

  node("health", "step", 340, 500, 220, 64, "health", "локальные проверки, --fix",
    "health", "Проверяет установку и окружение и без флагов ничего не меняет. Запускайте после init, adopt или update и когда агент не находит скиллы. На fail команда печатает причину и команду исправления.");
  node("cmds", "step", 610, 500, 220, 64, "list · diff · update", "первые команды",
    "Первые команды", "list показывает установленные скиллы, diff — расхождения с залоченным snapshot, update подтягивает новую версию capability и сохраняет локальные правки.");
  node("console", "step", 880, 500, 220, 64, "console", "TUI и веб-консоль · beta",
    "console", "Нужен uv; при первом запуске скачивает зависимости, поэтому нужна сеть. console --web поднимает Сервер консоли, печатает URL с токеном и открывает браузер.");

  var order = ["project-foundation", "mattpocock-suite", "engineering-suite", "backend-orchestration"];
  var chain = {
    "project-foundation": ["project-foundation"],
    "mattpocock-suite": ["mattpocock-suite"],
    "engineering-suite": ["mattpocock-suite", "engineering-suite"],
    "backend-orchestration": ["mattpocock-suite", "engineering-suite", "backend-orchestration"]
  };
  var snapshotSub = {
    "project-foundation": "5 скиллов базы",
    "mattpocock-suite": "25 скиллов upstream",
    "engineering-suite": "upstream + 7 новых, 12 overrides",
    "backend-orchestration": "+ coordinator, роли, ledger"
  };
  var snapshotNote = {
    "project-foundation": "5 скиллов доменно-нейтральной базы",
    "mattpocock-suite": "25 скиллов upstream, закреплённых на проверенном коммите",
    "engineering-suite": "upstream-набор mattpocock-suite плюс 7 добавлений и 12 overrides",
    "backend-orchestration": "engineering-suite плюс coordinator, роли, briefs, worktrees, ledger и QA lane"
  };

  /* --- статические связи ------------------------------------------------- */
  function edge(pts, dashed) { edges.push({ pts: pts, dashed: dashed }); }
  edge([[nodes["g-install"].x + 300, 56], [nodes["g-profile"].x, 56]]);
  edge([[nodes["g-profile"].x + 300, 56], [nodes["g-skills"].x, 56]]);
  edge([[nodes["g-skills"].cx, 88], [nodes["g-skills"].cx, 116], [nodes.init.cx, 116], [nodes.init.cx, nodes.init.y]], true);
  edge([[nodes["g-skills"].cx + 60, 88], [nodes["g-skills"].cx + 60, 124], [572, 124], [572, nodes.adopt.cy], [nodes.adopt.x + nodes.adopt.w, nodes.adopt.cy]], true);
  caps.forEach(function (c) {
    var n = nodes[c[0]];
    edge([[n.x + n.w, n.cy], [312, n.cy], [312, nodes.init.cy], [nodes.init.x, nodes.init.cy]]);
    edge([[n.x + n.w, n.cy], [326, n.cy], [326, nodes.adopt.cy], [nodes.adopt.x, nodes.adopt.cy]]);
  });
  edge([[nodes.init.x + nodes.init.w, nodes.init.cy], [610, nodes.init.cy]]);
  edge([[nodes.adopt.x + nodes.adopt.w, nodes.adopt.cy], [586, nodes.adopt.cy], [586, nodes.init.cy], [610, nodes.init.cy]]);
  edge([[852, 446], [852, 470], [nodes.health.cx, 470], [nodes.health.cx, nodes.health.y]]);
  edge([[nodes.health.x + nodes.health.w, nodes.health.cy], [nodes.cmds.x, nodes.cmds.cy]]);
  edge([[nodes.cmds.x + nodes.cmds.w, nodes.cmds.cy], [nodes.console.x, nodes.console.cy]]);

  /* --- SVG --------------------------------------------------------------- */
  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, cls, str, anchor) {
    var t = el("text", { x: x, y: y, class: cls }, parent);
    if (anchor) t.setAttribute("text-anchor", anchor);
    t.textContent = str;
    return t;
  }
  function pathD(pts) {
    return pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
  }

  var svg = el("svg", { viewBox: "20 0 " + (W - 30) + " " + H, role: "group", class: "ah-core-svg",
    "aria-label": "Схема установки: глобальный слой, выбор capability, init или adopt, snapshot в проекте, health и первые команды" });
  var defs = el("defs", {}, svg);
  var marker = el("marker", { id: "ah-install-arrow", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0 0 L8 4 L0 8 z", class: "ah-core-arrowhead" }, marker);
  var gBands = el("g", {}, svg);
  var gEdges = el("g", {}, svg);
  var gRoute = el("g", {}, svg);
  var gNodes = el("g", {}, svg);
  var gPackets = el("g", {}, svg);

  function band(x, y, w, h, cls, label) {
    el("rect", { x: x, y: y, width: w, height: h, rx: 12, class: "ah-core-band " + cls }, gBands);
    text(gBands, x + 16, y + 20, "ah-core-bandlabel", label);
  }
  band(30, 134, 270, 312, "is-policy", "КАТАЛОГ · ВЫБЕРИТЕ СБОРКУ");
  band(340, 134, 220, 312, "", "КОМАНДА");
  band(600, 134, 500, 312, "is-store", "ПРОЕКТ · SNAPSHOT");
  text(gBands, 40, 14, "ah-core-bandlabel", "МАШИНА · ОДИН РАЗ");
  text(gBands, 340, 488, "ah-core-bandlabel", "ПРОВЕРКА И ПЕРВЫЕ КОМАНДЫ");

  edges.forEach(function (e) {
    var p = el("path", { d: pathD(e.pts), class: "ah-core-edge" + (e.dashed ? " is-soft" : "") }, gEdges);
    p.setAttribute("marker-end", "url(#ah-install-arrow)");
  });

  var els = {};
  var subEls = {};
  Object.keys(nodes).forEach(function (id) {
    var n = nodes[id];
    var g = el("g", { class: "ah-core-node is-" + n.kind, tabindex: 0, role: "button", "data-node": id,
      "aria-label": n.label + ": " + n.sub }, gNodes);
    el("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: 9, class: "ah-core-rect" }, g);
    text(g, n.cx, n.cy - 3, "ah-core-label", n.label, "middle");
    subEls[id] = text(g, n.cx, n.cy + 15, "ah-core-sub", n.sub, "middle");
    els[id] = g;
  });

  host.innerHTML = "";
  host.appendChild(svg);

  /* --- маршрут ------------------------------------------------------------ */
  var current = "engineering-suite";
  var mode = "init";
  var userTouched = false;
  var timer = null;

  function setNote(title, body) {
    if (!note) return;
    note.innerHTML = "";
    var b = document.createElement("b");
    b.textContent = title;
    var s = document.createElement("span");
    s.textContent = body;
    note.appendChild(b);
    note.appendChild(s);
  }

  function packet(pts, cls, begin) {
    var c = el("circle", { r: 4.5, class: "ah-core-packet " + cls }, gPackets);
    el("animateMotion", { dur: "4.4s", repeatCount: "indefinite", begin: begin, path: pathD(pts), calcMode: "linear" }, c);
  }

  function routePoints(capId, cmd) {
    var cap = nodes[capId];
    var c = nodes[cmd];
    var channel = cmd === "init" ? 312 : 326;
    var start = [[cap.x + cap.w, cap.cy], [channel, cap.cy], [channel, c.cy], [c.x, c.cy], [c.x + c.w, c.cy]];
    var into = cmd === "init" ? [[610, c.cy]] : [[586, c.cy], [586, nodes.init.cy], [610, nodes.init.cy]];
    return start.concat(into, [[852, nodes.init.cy], [852, 470], [nodes.health.cx, 470], [nodes.health.cx, nodes.health.cy]]);
  }

  function select(capId, cmd) {
    current = capId;
    mode = cmd || mode;
    gRoute.innerHTML = "";
    gPackets.innerHTML = "";
    Object.keys(els).forEach(function (id) {
      els[id].classList.remove("is-on");
      els[id].removeAttribute("aria-pressed");
    });
    order.forEach(function (id) { els[id].setAttribute("aria-pressed", id === capId ? "true" : "false"); });
    ["init", "adopt"].forEach(function (id) { els[id].setAttribute("aria-pressed", id === mode ? "true" : "false"); });

    chain[capId].forEach(function (id) { els[id].classList.add("is-on"); });
    els[mode].classList.add("is-on");
    snap.forEach(function (s) { els[s[0]].classList.add("is-on"); });
    els.health.classList.add("is-on");
    subEls["s-skills"].textContent = snapshotSub[capId];

    var pts = routePoints(capId, mode);
    el("path", { d: pathD(pts), class: "ah-core-route" }, gRoute);
    if (!reduce) {
      packet(pts, "is-request", "0s");
      packet(pts, "is-request", "-2.2s");
    }
    setNote(capId + " · " + mode,
      (mode === "init" ? "init кладёт в проект snapshot выбранной сборки. " : "adopt встраивает сборку, сохраняя ваши скиллы, и падает со списком конфликтов. ") +
      "Состав snapshot: " + snapshotNote[capId] + ". Затем запустите health.");
  }

  function pause() { if (timer) { window.clearInterval(timer); timer = null; } }
  function autoplay() {
    pause();
    if (reduce || userTouched) return;
    timer = window.setInterval(function () {
      if (document.hidden) return;
      select(order[(order.indexOf(current) + 1) % order.length]);
    }, 5200);
  }

  Object.keys(els).forEach(function (id) {
    var g = els[id];
    g.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); g.dispatchEvent(new MouseEvent("click")); }
    });
    g.addEventListener("click", function () {
      userTouched = true;
      pause();
      if (order.indexOf(id) !== -1) select(id);
      else if (id === "init" || id === "adopt") { select(current, id); setNote(nodes[id].title, nodes[id].text); }
      else setNote(nodes[id].title, nodes[id].text);
    });
  });

  select(current, "init");
  autoplay();
  return { destroy: pause };
  }

  var mainHost = document.getElementById("ah-install-map");
  if (!mainHost) return;
  mount(mainHost, document.getElementById("ah-install-note"));

  var open = document.getElementById("ah-install-expand");
  if (!open) return;
  open.addEventListener("click", function () {
    var dialog = document.createElement("dialog");
    dialog.className = "ah-diagram-modal ah-diagram-modal--fit";
    dialog.setAttribute("aria-label", "Схема установки на весь экран");
    dialog.innerHTML =
      '<div class="ah-diagram-modal-bar"><span class="ah-diagram-modal-title">Путь установки</span>' +
      '<button type="button" class="ah-diagram-modal-close" aria-label="Закрыть">×</button></div>' +
      '<div class="ah-core-modal"><div class="ah-flow"><div class="ah-core" id="ah-install-map-full"></div>' +
      '<div class="ah-flow-note" aria-live="polite"><b>Выберите сборку</b><span>Нажмите на capability или на любой узел схемы.</span></div></div></div>';
    document.body.appendChild(dialog);
    var instance = mount(dialog.querySelector(".ah-core"), dialog.querySelector(".ah-flow-note"));
    function close() { instance.destroy(); dialog.remove(); }
    dialog.querySelector(".ah-diagram-modal-close").addEventListener("click", function () { dialog.close(); });
    dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", close);
    dialog.showModal();
  });
})();
