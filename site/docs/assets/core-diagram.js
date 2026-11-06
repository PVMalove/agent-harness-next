(function () {
  var host = document.getElementById("ah-core");
  if (!host) return;

  var NS = "http://www.w3.org/2000/svg";
  var W = 1120;
  var H = 640;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- English strings: keyed by the Russian source string --------------- */
  var LANG = document.documentElement.lang === "en" ? "en" : "ru";
  var EN = {
    "harness и coordinator запускаются из терминала. Команды идут в policy-слой Python, а тот обращается к runtime через runtime_client.": "harness and coordinator run from the terminal. Commands go to the Python policy layer, which calls the runtime through runtime_client.",
    "Терминальный клиент Сервера консоли: задачи, оркестрация, отчёты и восстановление. Данные берёт у сервера, а не из файлов.": "Terminal client of the Console Server: tasks, orchestration, reports, and recovery. It takes data from the server, not from files.",
    "Браузерный клиент того же Сервера консоли. Подключается по /ws с токеном сессии; действия восстановления сервер выполняет как job.": "Browser client of the same Console Server. It connects over /ws with a session token; the server runs recovery actions as a job.",
    "Claude Code и Codex находят скиллы и hooks через native skill roots. Hooks проверяют действия агента по профилю политики.": "Claude Code and Codex find skills and hooks through native skill roots. Hooks check agent actions against the policy profile.",
    "Планирует batch, собирает approvals, принимает отчёты ролей и выбирает состояние dispatch по наблюдению runtime. Operational state сам не пишет.": "Plans a batch, collects approvals, accepts role reports, and picks the dispatch state from what the runtime observes. It does not write operational state itself.",
    "Сервер консоли": "Console Server",
    "Один сервер для TUI и браузера: отдаёт снимки экранов по /ws и ходит в runtime тем же клиентом, что и coordinator.": "One server for the TUI and the browser: it serves screen snapshots over /ws and calls the runtime with the same client as the coordinator.",
    "профили hooks": "hook profiles",
    "Профили задают предупреждения и повторы. Критические guards профилем не отключаются, а strict не блокирует recovery.": "Profiles set warnings and retries. A profile never disables critical guards, and strict does not block recovery.",
    "человек и policy": "human and policy",
    "Решение принимает человек и policy-слой. Immutable brief связывает план, образ, policy digest и verification digest.": "A human and the policy layer make the decision. The immutable brief binds the plan, image, policy digest, and verification digest.",
    "ChangeImpact → план": "ChangeImpact → plan",
    "ChangeImpact строит набор затронутого, VerificationPlan закрепляется digest-ом в approval. QA делает полный прогон на финальном SHA.": "ChangeImpact builds the set of affected items, and the VerificationPlan is pinned by a digest in the approval. QA runs the full pass on the final SHA.",
    "hello · operation_id · повтор до request_deadline": "hello · operation_id · retry until request_deadline",
    "Единственный путь Python к состоянию: hello, operation_id, повтор до request_deadline. Недоступный runtime даёт runtime_unavailable без записи в обход.": "The only Python path to state: hello, operation_id, retry until request_deadline. An unavailable runtime returns runtime_unavailable and nothing is written around it.",
    "Unix socket / named pipe · protocol 1.7 · uid/SID + токен · expected_revision · fencing_token": "Unix socket / named pipe · protocol 1.7 · uid/SID + token · expected_revision · fencing_token",
    "Unix domain socket, на Windows — named pipe. Кадр — длина и JSON. Проверяются peer uid/SID и токен; каталог 0700, сокет 0600.": "Unix domain socket; on Windows, a named pipe. A frame is a length plus JSON. The peer uid/SID and the token are checked; the directory is 0700, the socket is 0600.",
    "Lifecycle и intent": "Lifecycle and intent",
    "Переходы batch и dispatch сохраняются транзакцией: intent, запуск, committed. Единственный writer этих сущностей.": "Batch and dispatch transitions are saved in a transaction: intent, launch, committed. The only writer of these entities.",
    "intent ↔ факт хоста": "intent ↔ host fact",
    "Сверяет сохранённый intent с фактом на хосте. После SIGKILL усыновляет исполнение по меткам или доказывает, что процесса нет.": "Compares the saved intent with the fact on the host. After SIGKILL, it adopts the execution by labels or proves that the process is gone.",
    "образы, метки dispatch": "images, dispatch labels",
    "Контейнеры по метке dispatch. Сокеты движка и runtime в worker не монтируются, образы harness не собирает.": "Containers by the dispatch label. The engine and runtime sockets are not mounted into the worker, and harness does not build images.",
    "процессы, cgroup / Job": "processes, cgroup / Job",
    "Учёт процессов: группа процессов и cgroup v2 на Linux, Job Object на Windows. Исполняет только approved brief и policy не решает.": "Process accounting: a process group and cgroup v2 on Linux, a Job Object on Windows. It runs only the approved brief and does not decide policy.",
    "Operational state с короткими транзакциями. Несовместимая версия схемы отвергается без записи.": "Operational state with short transactions. An incompatible schema version is rejected without a write.",
    "хэш-цепочка": "hash chain",
    "Каждая мутация оставляет запись в хэш-цепочке с checkpoint; ledger validate --full пересчитывает её целиком.": "Every mutation leaves a record in the hash chain with a checkpoint; ledger validate --full recomputes the whole chain.",
    "Владелец, fencing_token и expires_at. Истёкший срок lease не снимает: сначала проверяется живость владельца.": "Owner, fencing_token, and expires_at. An expired lease is not dropped automatically: the owner's liveness is checked first.",
    "эпоха runtime-store": "runtime-store epoch",
    "Называет store единственным writer-ом operational state. Fallback-writer в Python запрещён.": "Names the store as the only writer of operational state. A fallback writer in Python is forbidden.",
    "Хранит operation_id, digest запроса и результат, поэтому повтор после обрыва возвращает тот же ответ.": "Stores operation_id, the request digest, and the result, so a retry after a dropped connection returns the same answer.",
    "Владелец истории: кандидат, ветки и worktree — обычные Git-объекты. Runtime их не переписывает.": "Owner of history: the candidate, branches, and worktrees are ordinary Git objects. The runtime does not rewrite them.",
    "Проект": "Project",
    ".harness/project.json, harness.lock и REGISTRY.md принадлежат целевому репозиторию; их обновляет установщик, а не runtime.": ".harness/project.json, harness.lock, and REGISTRY.md belong to the target repository; the installer updates them, not the runtime.",
    "контейнер или процесс": "container or process",
    "Untrusted: кандидат в контейнере или отдельном процессе. Получает только approved brief; сокеты engine и runtime ему недоступны.": "Untrusted: the candidate runs in a container or a separate process. It gets only the approved brief; the engine and runtime sockets are not available to it.",
    "сеть только по allowlist": "network via allowlist only",
    "Сетевой доступ worker-а идёт только через allowlist proxy.": "The worker's network access goes only through the allowlist proxy.",
    "Пример маршрута: coordinator → runtime_client → IPC → Lifecycle → SQLite WAL. Переход batch сохраняется одной транзакцией.": "Example route: coordinator → runtime_client → IPC → Lifecycle → SQLite WAL. A batch transition is saved in one transaction.",
    "Пример маршрута: Сервер консоли → IPC → Reconcile → Leases. Действие восстановления сервер выполняет как job, запись требует подтверждения.": "Example route: Console Server → IPC → Reconcile → Leases. The server runs a recovery action as a job, and a write needs confirmation.",
    "Пример маршрута: Сервер консоли → IPC → Lifecycle → Audit chain. Снимок леджера собирается через runtime и кэшируется на сервере.": "Example route: Console Server → IPC → Lifecycle → Audit chain. The ledger snapshot is built through the runtime and cached on the server.",
    "Пример маршрута: Hook policy проверяет действие агента, затем approved brief уходит в runtime, а Supervisor запускает worker-а.": "Example route: Hook policy checks the agent action, then the approved brief goes to the runtime, and the Supervisor starts the worker.",
    "Схема ядра harness: клиенты, policy на Python, IPC, Rust runtime, runtime-store, Git, worker": "Diagram of the harness core: clients, Python policy, IPC, Rust runtime, runtime-store, Git, worker",
    "POLICY · PYTHON РЕШАЕТ": "POLICY · PYTHON DECIDES",
    "RUNTIME · RUST ИСПОЛНЯЕТ": "RUNTIME · RUST EXECUTES",
    "STATE · ЕДИНСТВЕННЫЙ WRITER": "STATE · SINGLE WRITER",
    "ГРАНИЦА ДОВЕРИЯ · UNTRUSTED": "TRUST BOUNDARY · UNTRUSTED",
    "ВЛАДЕЛЬЦЫ ВНЕ RUNTIME": "OWNERS OUTSIDE RUNTIME",
    " · маршрут": " · route"
  };
  function t(s) { return LANG === "en" && EN[s] ? EN[s] : s; }

  var nodes = {};
  var edges = [];

  function node(id, kind, x, y, w, h, label, sub, title, text) {
    label = t(label); sub = t(sub); title = t(title); text = t(text);
    nodes[id] = { id: id, kind: kind, x: x, y: y, w: w, h: h, cx: x + w / 2, cy: y + h / 2,
      label: label, sub: sub, title: title, text: text };
  }

  function row(items, x0, total, gap, y, h, kind) {
    var w = (total - gap * (items.length - 1)) / items.length;
    items.forEach(function (it, i) {
      node(it[0], kind, x0 + i * (w + gap), y, w, h, it[1], it[2], it[3], it[4]);
    });
  }

  /* --- данные схемы ------------------------------------------------------ */
  row([
    ["cli", "CLI", "harness · coordinator", "CLI", "harness и coordinator запускаются из терминала. Команды идут в policy-слой Python, а тот обращается к runtime через runtime_client."],
    ["tui", "TUI", "harness console", "TUI", "Терминальный клиент Сервера консоли: задачи, оркестрация, отчёты и восстановление. Данные берёт у сервера, а не из файлов."],
    ["web", "Web console", "harness console --web", "Web console", "Браузерный клиент того же Сервера консоли. Подключается по /ws с токеном сессии; действия восстановления сервер выполняет как job."],
    ["skills", "Skills", "Claude Code · Codex", "Skills", "Claude Code и Codex находят скиллы и hooks через native skill roots. Hooks проверяют действия агента по профилю политики."]
  ], 46, 728, 26, 22, 46, "client");

  row([
    ["coordinator", "Coordinator", "batch, dispatch", "Coordinator", "Планирует batch, собирает approvals, принимает отчёты ролей и выбирает состояние dispatch по наблюдению runtime. Operational state сам не пишет."],
    ["console", "Сервер консоли", "WebSocket /ws", "Сервер консоли", "Один сервер для TUI и браузера: отдаёт снимки экранов по /ws и ходит в runtime тем же клиентом, что и coordinator."],
    ["hooks", "Hook policy", "профили hooks", "Hook policy", "Профили задают предупреждения и повторы. Критические guards профилем не отключаются, а strict не блокирует recovery."],
    ["approvals", "Approvals", "человек и policy", "Approvals", "Решение принимает человек и policy-слой. Immutable brief связывает план, образ, policy digest и verification digest."],
    ["verification", "Verification", "ChangeImpact → план", "Verification", "ChangeImpact строит набор затронутого, VerificationPlan закрепляется digest-ом в approval. QA делает полный прогон на финальном SHA."]
  ], 46, 728, 14, 128, 64, "policy");

  node("rtclient", "bar", 46, 232, 728, 34, "runtime_client", "hello · operation_id · повтор до request_deadline",
    "runtime_client", "Единственный путь Python к состоянию: hello, operation_id, повтор до request_deadline. Недоступный runtime даёт runtime_unavailable без записи в обход.");
  node("wire", "bar", 46, 286, 728, 34, "IPC", "Unix socket / named pipe · protocol 1.7 · uid/SID + токен · expected_revision · fencing_token",
    "IPC", "Unix domain socket, на Windows — named pipe. Кадр — длина и JSON. Проверяются peer uid/SID и токен; каталог 0700, сокет 0600.");

  row([
    ["lifecycle", "Lifecycle и intent", "intent → committed", "Lifecycle и intent", "Переходы batch и dispatch сохраняются транзакцией: intent, запуск, committed. Единственный writer этих сущностей."],
    ["reconcile", "Reconcile", "intent ↔ факт хоста", "Reconcile", "Сверяет сохранённый intent с фактом на хосте. После SIGKILL усыновляет исполнение по меткам или доказывает, что процесса нет."],
    ["engine", "OCI engine", "образы, метки dispatch", "OCI engine", "Контейнеры по метке dispatch. Сокеты движка и runtime в worker не монтируются, образы harness не собирает."],
    ["supervisor", "Supervisor", "процессы, cgroup / Job", "Supervisor", "Учёт процессов: группа процессов и cgroup v2 на Linux, Job Object на Windows. Исполняет только approved brief и policy не решает."]
  ], 46, 728, 14, 390, 64, "runtime");

  row([
    ["wal", "SQLite WAL", "schema 7", "SQLite WAL", "Operational state с короткими транзакциями. Несовместимая версия схемы отвергается без записи."],
    ["audit", "Audit chain", "хэш-цепочка", "Audit chain", "Каждая мутация оставляет запись в хэш-цепочке с checkpoint; ledger validate --full пересчитывает её целиком."],
    ["leases", "Leases", "fencing_token", "Leases", "Владелец, fencing_token и expires_at. Истёкший срок lease не снимает: сначала проверяется живость владельца."],
    ["authority", "AUTHORITY.json", "эпоха runtime-store", "AUTHORITY.json", "Называет store единственным writer-ом operational state. Fallback-writer в Python запрещён."],
    ["idem", "Idempotency", "operation_id", "Idempotency", "Хранит operation_id, digest запроса и результат, поэтому повтор после обрыва возвращает тот же ответ."]
  ], 46, 728, 14, 534, 64, "store");

  node("git", "side", 830, 128, 260, 64, "Git", "candidate · branch · worktree", "Git", "Владелец истории: кандидат, ветки и worktree — обычные Git-объекты. Runtime их не переписывает.");
  node("project", "side", 830, 216, 260, 64, "Проект", "project.json · harness.lock", "Проект", ".harness/project.json, harness.lock и REGISTRY.md принадлежат целевому репозиторию; их обновляет установщик, а не runtime.");
  node("worker", "untrusted", 836, 390, 248, 64, "Worker / QA", "контейнер или процесс", "Worker / QA", "Untrusted: кандидат в контейнере или отдельном процессе. Получает только approved brief; сокеты engine и runtime ему недоступны.");
  node("egress", "side", 830, 534, 260, 64, "Egress proxy", "сеть только по allowlist", "Egress proxy", "Сетевой доступ worker-а идёт только через allowlist proxy.");

  /* --- маршруты клиентов ------------------------------------------------- */
  var routes = {
    cli: { ids: ["cli", "coordinator", "rtclient", "wire", "lifecycle", "wal"],
      text: t("Пример маршрута: coordinator → runtime_client → IPC → Lifecycle → SQLite WAL. Переход batch сохраняется одной транзакцией.") },
    tui: { ids: ["tui", "console", "rtclient", "wire", "reconcile", "leases"],
      text: t("Пример маршрута: Сервер консоли → IPC → Reconcile → Leases. Действие восстановления сервер выполняет как job, запись требует подтверждения.") },
    web: { ids: ["web", "console", "rtclient", "wire", "lifecycle", "audit"],
      text: t("Пример маршрута: Сервер консоли → IPC → Lifecycle → Audit chain. Снимок леджера собирается через runtime и кэшируется на сервере.") },
    skills: { ids: ["skills", "hooks", "rtclient", "wire", "supervisor", "worker"],
      text: t("Пример маршрута: Hook policy проверяет действие агента, затем approved brief уходит в runtime, а Supervisor запускает worker-а.") }
  };
  var order = ["cli", "tui", "web", "skills"];

  /* --- геометрия --------------------------------------------------------- */
  function bottom(n, x) { return [x === undefined ? n.cx : x, n.y + n.h]; }
  function top(n, x) { return [x === undefined ? n.cx : x, n.y]; }

  function edge(id, pts, dir) { edges.push({ id: id, pts: pts, dir: dir }); }

  // клиенты → policy: колено на своём уровне, чтобы линии не слипались
  var clientMid = { cli: 84, tui: 90, web: 96, skills: 102 };
  [["cli", "coordinator"], ["tui", "console"], ["web", "console"], ["skills", "hooks"]].forEach(function (p) {
    var a = nodes[p[0]], b = nodes[p[1]];
    edge(p[0] + ">" + p[1], [bottom(a), [a.cx, clientMid[p[0]]], [b.cx, clientMid[p[0]]], top(b)]);
  });
  ["coordinator", "console", "hooks", "approvals", "verification"].forEach(function (id) {
    var a = nodes[id];
    edge(id + ">rtclient", [bottom(a), [a.cx, nodes.rtclient.y]]);
    edge("rtclient>wire@" + id, [[a.cx, nodes.rtclient.y + nodes.rtclient.h], [a.cx, nodes.wire.y]]);
  });
  ["lifecycle", "reconcile", "engine", "supervisor"].forEach(function (id) {
    var a = nodes[id];
    edge("wire>" + id, [[a.cx, nodes.wire.y + nodes.wire.h], top(a)]);
    edge(id + ">store", [bottom(a), [a.cx, 500]]);
  });
  edge("coordinator>git", [[nodes.verification.x + nodes.verification.w, 160], [830, 160]]);
  edge("supervisor>worker", [[nodes.supervisor.cx, 454], [nodes.supervisor.cx, 468], [806, 468], [806, nodes.worker.cy], [nodes.worker.x, nodes.worker.cy]]);
  edge("worker>egress", [bottom(nodes.worker), top(nodes.egress)]);

  // путь маршрута: через бары идём по горизонтали внутри бара
  function routePath(ids) {
    var pts = [];
    var lastX = null;
    ids.forEach(function (id, i) {
      var n = nodes[id];
      var prev = nodes[ids[i - 1]];
      var next = nodes[ids[i + 1]];
      if (!prev) { pts.push(bottom(n)); lastX = n.cx; return; }
      if (n.kind === "bar") {
        var enter = lastX;
        var exit = next && next.kind !== "bar" ? next.cx : enter;
        pts.push([enter, n.y], [enter, n.cy], [exit, n.cy], [exit, n.y + n.h]);
        lastX = exit;
        return;
      }
      if (prev.kind === "bar") {
        pts.push([n.cx, n.y]);
      } else if (n.kind === "untrusted") {
        pts.push([prev.cx, 468], [806, 468], [806, n.cy], [n.x, n.cy]);
        return;
      } else {
        var mid = prev.kind === "client" ? clientMid[prev.id]
          : prev.kind === "runtime" && n.kind === "store" ? 506
          : (prev.y + prev.h + n.y) / 2;
        pts.push([prev.cx, mid], [n.cx, mid], [n.cx, n.y]);
      }
      lastX = n.cx;
      if (!next) pts.push([n.cx, n.cy]);
    });
    return pts;
  }

  function pathD(pts) {
    return pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
  }

  function reversed(pts) { return pts.slice().reverse(); }

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

  var svg = el("svg", { viewBox: "14 0 " + (W - 28) + " " + H, role: "group", class: "ah-core-svg",
    "aria-label": t("Схема ядра harness: клиенты, policy на Python, IPC, Rust runtime, runtime-store, Git, worker") });
  var gBands = el("g", {}, svg);
  var gEdges = el("g", {}, svg);
  var gRoute = el("g", {}, svg);
  var gNodes = el("g", {}, svg);
  var gPackets = el("g", {}, svg);

  function band(x, y, w, h, cls, label) {
    el("rect", { x: x, y: y, width: w, height: h, rx: 12, class: "ah-core-band " + cls }, gBands);
    if (label) text(gBands, x + 16, y + 18, "ah-core-bandlabel", label);
  }
  band(30, 98, 760, 118, "is-policy", t("POLICY · PYTHON РЕШАЕТ"));
  band(30, 356, 760, 124, "is-runtime", t("RUNTIME · RUST ИСПОЛНЯЕТ"));
  band(30, 500, 760, 118, "is-store", t("STATE · ЕДИНСТВЕННЫЙ WRITER"));
  el("rect", { x: 22, y: 340, width: 776, height: 290, rx: 16, class: "ah-core-authority" }, gBands);
  text(gBands, 40, 335, "ah-core-authlabel", "runtime authority");
  el("rect", { x: 822, y: 370, width: 276, height: 104, rx: 12, class: "ah-core-untrusted" }, gBands);
  text(gBands, 840, 365, "ah-core-trustlabel", t("ГРАНИЦА ДОВЕРИЯ · UNTRUSTED"));
  text(gBands, 826, 111, "ah-core-bandlabel", t("ВЛАДЕЛЬЦЫ ВНЕ RUNTIME"));

  edges.forEach(function (e) {
    var p = el("path", { d: pathD(e.pts), class: "ah-core-edge", "data-edge": e.id }, gEdges);
    p.setAttribute("marker-end", "url(#ah-core-arrow)");
  });

  var defs = el("defs", {}, svg);
  var marker = el("marker", { id: "ah-core-arrow", viewBox: "0 0 8 8", refX: 7, refY: 4, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" }, defs);
  el("path", { d: "M0 0 L8 4 L0 8 z", class: "ah-core-arrowhead" }, marker);

  var els = {};
  Object.keys(nodes).forEach(function (id) {
    var n = nodes[id];
    var g = el("g", { class: "ah-core-node is-" + n.kind, tabindex: 0, role: "button", "data-node": id,
      "aria-label": n.label + ": " + n.sub }, gNodes);
    el("rect", { x: n.x, y: n.y, width: n.w, height: n.h, rx: n.kind === "bar" ? 8 : 9, class: "ah-core-rect" }, g);
    if (n.kind === "bar") {
      text(g, n.x + 14, n.cy + 4, "ah-core-label is-bar", n.label);
      text(g, n.x + 14 + n.label.length * 8.2 + 12, n.cy + 4, "ah-core-sub is-bar", n.sub);
    } else {
      text(g, n.cx, n.y + n.h / 2 - 3, "ah-core-label", n.label, "middle");
      text(g, n.cx, n.y + n.h / 2 + 15, "ah-core-sub", n.sub, "middle");
    }
    els[id] = g;
  });

  text(gBands, 960, 507, "ah-core-note", "allowlist", "middle");

  host.innerHTML = "";
  host.appendChild(svg);

  /* --- состояние и анимация ---------------------------------------------- */
  var note = document.getElementById("ah-flow-note");
  var clientButtons = order;
  var current = null;
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

  function clearRoute() {
    gRoute.innerHTML = "";
    gPackets.innerHTML = "";
    Object.keys(els).forEach(function (id) { els[id].classList.remove("is-on"); });
    Array.prototype.forEach.call(gEdges.children, function (p) { p.classList.remove("is-on"); });
  }

  function packet(pts, cls, begin) {
    var c = el("circle", { r: 4.5, class: "ah-core-packet " + cls }, gPackets);
    var a = el("animateMotion", { dur: "3.4s", repeatCount: "indefinite", begin: begin, path: pathD(pts),
      calcMode: "linear" }, c);
    a.setAttribute("rotate", "0");
  }

  function select(id) {
    var route = routes[id];
    if (!route) return;
    current = id;
    clearRoute();
    order.forEach(function (c) {
      els[c].setAttribute("aria-pressed", c === id ? "true" : "false");
    });
    route.ids.forEach(function (n) { els[n].classList.add("is-on"); });
    var pts = routePath(route.ids);
    el("path", { d: pathD(pts), class: "ah-core-route" }, gRoute);
    if (!reduce) {
      packet(pts, "is-request", "0s");
      packet(pts, "is-request", "-1.7s");
      packet(reversed(pts), "is-reply", "-0.85s");
    }
    setNote(nodes[id].title + t(" · маршрут"), route.text);
  }

  function pause() {
    if (timer) { window.clearInterval(timer); timer = null; }
  }

  function autoplay() {
    pause();
    if (reduce || userTouched) return;
    timer = window.setInterval(function () {
      if (document.hidden) return;
      select(order[(order.indexOf(current) + 1) % order.length]);
    }, 5200);
  }

  order.forEach(function (id) {
    var g = els[id];
    g.setAttribute("aria-pressed", "false");
    g.addEventListener("click", function () { userTouched = true; pause(); select(id); });
  });

  Object.keys(els).forEach(function (id) {
    var g = els[id];
    function key(event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); g.dispatchEvent(new MouseEvent("click")); }
    }
    g.addEventListener("keydown", key);
    if (order.indexOf(id) === -1) {
      g.addEventListener("click", function () {
        userTouched = true;
        pause();
        setNote(nodes[id].title, nodes[id].text);
      });
    }
  });

  select("web");
  autoplay();
})();
